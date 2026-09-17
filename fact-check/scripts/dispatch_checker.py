#!/usr/bin/env python3
"""Dispatch one headless checker subagent on any coding-agent CLI harness.

Runs a single prompt through claude / codex / opencode / zcode / kimi / grok / agy
in non-interactive mode, captures the final answer text plus token/cost usage,
and writes everything to an output directory:

    <out>/prompt.txt      the exact prompt sent
    <out>/answer.md       the checker's final answer (secret-scrubbed)
    <out>/stream.ndjson   raw stdout events (secret-scrubbed, for debugging)
    <out>/stderr.log      raw stderr, tail-kept (secret-scrubbed)
    <out>/result.json     status, exit code, tokens, cost, session id

Invocation patterns are adapted from the llm-coding-benchmark harness runners,
tuned for read-only web research instead of coding: web tools enabled where the
benchmark disabled them, sandbox narrowed where the benchmark used full access.

Credentials: never written to any output file. Env vars are injected into the
child process only; all persisted text passes through scrub_text(), which
redacts known secret shapes and the literal values of any env var loaded from
the secrets file. See references/harness-setup.md for per-harness auth setup.

Stdlib only. Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_TIMEOUT = 1500   # 25 min hard wall per checker
DEFAULT_STALL = 300      # 5 min without any stdout event -> kill (zcode exempt)
KILL_GRACE = 10          # SIGTERM -> wait -> SIGKILL

# Env vars the harnesses may need. Injected only if missing and found in the
# secrets file. Names only — values never leave the child process env.
SECRET_ENV_NAMES = (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
    "GEMINI_API_KEY", "GROK_API_KEY", "ZAI_API_KEY", "KIMI_API_KEY",
    "MOONSHOT_API_KEY", "QWEN36_API_KEY", "OLLAMA_API_KEY",
)

SECRET_SHAPES = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"),  # JWT
]

_here = Path(__file__).resolve().parent
DEFAULT_MODELS = _here.parent / "config" / "models.json"


def load_model_config() -> dict:
    try:
        return json.loads(DEFAULT_MODELS.read_text())
    except (OSError, ValueError):
        return {}


def load_default_model(harness: str) -> tuple[str | None, str | None]:
    """Read the skill's default (cheap) model for a harness. (model, variant)"""
    entry = load_model_config().get("harnesses", {}).get(harness, {})
    return entry.get("model"), entry.get("variant")


def estimate_cost_usd(harness: str, tokens_in: int, tokens_out: int) -> float | None:
    """Rough list-price estimate from config/models.json rates (USD per 1M tokens).

    Upper-bound awareness number, not billing: ignores cache-read discounts and
    flat-rate subscriptions. Returns None when no rates are configured.
    """
    rates = load_model_config().get("harnesses", {}).get(harness, {}).get("rates_per_m")
    if not rates:
        return None
    return round(tokens_in / 1e6 * (rates.get("input") or 0)
                 + tokens_out / 1e6 * (rates.get("output") or 0), 4)


# --------------------------------------------------------------------------- #
# Secrets handling
# --------------------------------------------------------------------------- #

def load_secret_env(path: Path | None) -> dict[str, str]:
    """Parse `export NAME=...` lines from the zsh secrets file.

    Returns only vars listed in SECRET_ENV_NAMES that are not already in os.environ.
    """
    if path is None or not path.is_file():
        return {}
    wanted = {}
    try:
        for line in path.read_text().splitlines():
            m = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=(.+)$", line)
            if not m:
                continue
            name, raw = m.group(1), m.group(2).strip().strip('"').strip("'")
            if name in SECRET_ENV_NAMES and name not in os.environ and raw:
                wanted[name] = raw
    except OSError:
        pass
    return wanted


def _env_values_risky(values: list[str]) -> list[str]:
    return [v for v in values if len(v) >= 12 and any(c.isdigit() for c in v)]


def make_scrubber(env: dict[str, str]):
    """Build a scrub function that redacts secret shapes + loaded env values."""
    literal = _env_values_risky(list(env.values()))

    def scrub(text: str) -> str:
        for rx in SECRET_SHAPES:
            text = rx.sub("<REDACTED>", text)
        for v in literal:
            if v in text:
                text = text.replace(v, "<REDACTED>")
        return text

    return scrub


# --------------------------------------------------------------------------- #
# Command builders (one per harness)
# --------------------------------------------------------------------------- #

def _bash_login(cmd: list[str]) -> list[str]:
    """Wrap in bash -lc: some harness binaries are npm/mise shell wrappers."""
    return ["bash", "-lc", " ".join(shlex.quote(a) for a in cmd)]


def build_command(harness: str, model: str | None, variant: str | None,
                  prompt: str, cwd: Path) -> tuple[list[str], str | None]:
    """Return (argv, stdin_prompt). stdin_prompt non-None => write to stdin."""
    if harness == "claude":
        cmd = [
            "claude", "-p",
            "--output-format", "stream-json",
            "--verbose",
            # Sandbox the checker to web + read: no Bash, no file writes.
            "--allowedTools", "WebSearch", "WebFetch", "Read",
            "--disallowedTools", "Bash", "Write", "Edit",
        ]
        if model:
            cmd += ["--model", model]
        cmd.append(prompt)
        return cmd, None

    if harness == "codex":
        cmd = [
            "codex", "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "-s", "read-only",              # research, not coding
            "-C", str(cwd),
            "-c", "tools.web_search=true",  # web access for verification
        ]
        if model:
            cmd += ["-m", model]
        if variant:
            cmd += ["-c", f"model_reasoning_effort={variant}"]
        cmd.append("-")                      # prompt via stdin
        return _bash_login(cmd), prompt

    if harness == "opencode":
        cmd = ["opencode", "run", "--format", "json", "--dir", str(cwd)]
        if model:
            cmd += ["-m", model]
        if variant:
            cmd += ["--variant", variant]
        cmd.append(prompt)
        return cmd, None

    if harness == "zcode":
        # Headless parser only accepts the equals form of --prompt/--cwd.
        cmd = [
            "zcode",
            f"--prompt={prompt}",
            f"--cwd={cwd}",
            "--mode=yolo",
            "--json",
            "--verbose",
        ]
        return cmd, None

    if harness == "kimi":
        # -p mode auto-approves tools; --yolo/--auto are rejected with -p.
        cmd = ["kimi", "-p", "--output-format", "stream-json"]
        if model:
            cmd += ["-m", model]
        cmd.append(prompt)
        return _bash_login(cmd), None

    if harness == "grok":
        # NOTE: web search left ENABLED (the benchmark disabled it for coding).
        cmd = ["grok", "-p", prompt, "--max-turns", "50", "--always-approve",
               "--output-format", "streaming-json"]
        if model:
            cmd += ["-m", model]
        return _bash_login(cmd), None

    if harness == "agy":
        cmd = ["agy", "--print", prompt, "--dangerously-skip-permissions",
               "--add-dir", str(cwd), "--print-timeout", "100m"]
        if model:
            cmd += ["--model", model]
        return cmd, None

    raise ValueError(f"unknown harness: {harness!r}")


# --------------------------------------------------------------------------- #
# zcode model selection quirk: model.main lives in ~/.zcode/cli/config.json
# --------------------------------------------------------------------------- #

class ZcodeModel:
    """Temporarily rewrite zcode's config model.main; restore on exit."""

    def __init__(self, model: str | None):
        self.model = model
        self.path = Path.home() / ".zcode" / "cli" / "config.json"
        self.backup = None

    def __enter__(self):
        if not self.model or not self.path.is_file():
            return self
        try:
            raw = self.path.read_text()
            cfg = json.loads(raw)
            self.backup = raw
            cfg.setdefault("model", {})["main"] = self.model
            self.path.write_text(json.dumps(cfg, indent=2))
        except (OSError, ValueError):
            self.backup = None
        return self

    def __exit__(self, *exc):
        if self.backup is not None:
            try:
                self.path.write_text(self.backup)
            except OSError:
                pass


# --------------------------------------------------------------------------- #
# Stream parsers: harness event formats -> {text, tokens, cost, session, error}
# --------------------------------------------------------------------------- #

def _iter_json_lines(lines: list[str]):
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            yield json.loads(ln)
        except ValueError:
            continue


def parse_claude(lines: list[str]) -> dict:
    out = {"text": "", "tokens_in": 0, "tokens_out": 0,
           "cost_usd": None, "session_id": None, "error": None}
    chunks = []
    for ev in _iter_json_lines(lines):
        t = ev.get("type")
        if t == "assistant":
            for part in ev.get("message", {}).get("content", []):
                if part.get("type") == "text":
                    chunks.append(part.get("text", ""))
        elif t == "result":
            out["text"] = ev.get("result") or ""
            u = ev.get("usage") or {}
            out["tokens_in"] = (u.get("input_tokens") or 0)
            out["tokens_out"] = (u.get("output_tokens") or 0)
            out["cost_usd"] = ev.get("total_cost_usd")
            out["session_id"] = ev.get("session_id")
            if ev.get("is_error"):
                out["error"] = str(ev.get("result", "error"))[:500]
    if not out["text"] and chunks:
        out["text"] = "\n".join(chunks)
    return out


def parse_codex(lines: list[str]) -> dict:
    out = {"text": "", "tokens_in": 0, "tokens_out": 0,
           "cost_usd": None, "session_id": None, "error": None}
    for ev in _iter_json_lines(lines):
        t = ev.get("type")
        if t == "thread.started":
            out["session_id"] = ev.get("thread_id")
        elif t == "item.completed" and ev.get("item", {}).get("type") == "agent_message":
            out["text"] = ev["item"].get("text") or out["text"]
        elif t == "turn.completed":
            u = ev.get("usage") or {}
            out["tokens_in"] = (u.get("input_tokens") or 0) + (u.get("cached_input_tokens") or 0)
            out["tokens_out"] = u.get("output_tokens") or 0
        elif t == "turn.failed":
            out["error"] = str(ev.get("error"))[:500]
    return out


def parse_opencode(lines: list[str]) -> dict:
    out = {"text": "", "tokens_in": 0, "tokens_out": 0,
           "cost_usd": None, "session_id": None, "error": None}
    chunks = []
    for ev in _iter_json_lines(lines):
        t = ev.get("type")
        if t == "message":
            info = ev.get("info") or {}
            if info.get("role") == "assistant":
                texts = [p.get("text", "") for p in info.get("parts", [])
                         if p.get("type") == "text"]
                if texts:
                    chunks.append("\n".join(texts))
        elif t == "step_finish":
            out["session_id"] = ev.get("sessionID") or out["session_id"]
            part = ev.get("part") or {}
            tk = part.get("tokens") or {}
            out["tokens_in"] += (tk.get("input") or 0) + (tk.get("cache", {}).get("read") or 0)
            out["tokens_out"] += tk.get("output") or 0
            cost = part.get("cost")
            if isinstance(cost, (int, float)):
                out["cost_usd"] = (out["cost_usd"] or 0) + cost
    if chunks:
        out["text"] = chunks[-1]
    return out


def parse_zcode(lines: list[str]) -> dict:
    """zcode buffers stdout and prints one final pretty-printed JSON object.

    Shape (verified empirically): {sessionId, traceId, turnId, response,
    usage: {inputTokens, outputTokens, cacheReadTokens, ...}, eventCount,
    projection}. The answer text is the `response` string.
    """
    out = {"text": "", "tokens_in": 0, "tokens_out": 0,
           "cost_usd": None, "session_id": None, "error": None}
    blob = "\n".join(lines).strip()
    obj = None
    for candidate in (blob, blob[blob.find("{"):blob.rfind("}") + 1]):
        try:
            obj = json.loads(candidate)
            break
        except (ValueError, TypeError):
            continue
    if isinstance(obj, dict):
        u = obj.get("usage") or {}
        out["tokens_in"] = u.get("inputTokens") or 0
        out["tokens_out"] = u.get("outputTokens") or 0
        out["session_id"] = obj.get("sessionId")
        v = obj.get("response")
        if isinstance(v, str):
            out["text"] = v.strip()
    if not out["text"]:
        # Fall back to any non-JSON trailing stdout.
        prose = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("{")]
        out["text"] = "\n".join(prose).strip()
    return out


def parse_kimi(lines: list[str]) -> dict:
    out = {"text": "", "tokens_in": 0, "tokens_out": 0,
           "cost_usd": None, "session_id": None, "error": None}
    chunks = []
    for ev in _iter_json_lines(lines):
        t = ev.get("type")
        if t == "assistant":
            for part in ev.get("message", {}).get("content", []):
                if part.get("type") == "text":
                    chunks.append(part.get("text", ""))
        elif t == "session.resume_hint":
            out["session_id"] = ev.get("session_id")
    if chunks:
        out["text"] = "\n".join(chunks)
    return out


def parse_grok(lines: list[str]) -> dict:
    out = {"text": "", "tokens_in": 0, "tokens_out": 0,
           "cost_usd": None, "session_id": None, "error": None}
    chunks = []
    for ev in _iter_json_lines(lines):
        t = ev.get("type")
        if t == "end":
            out["cost_usd"] = ev.get("total_cost_usd")
            u = ev.get("usage") or {}
            out["tokens_in"] = u.get("input_tokens") or u.get("inputTokens") or 0
            out["tokens_out"] = u.get("output_tokens") or u.get("outputTokens") or 0
        elif t in ("assistant", "message"):
            c = ev.get("message", {}).get("content") or ev.get("content")
            if isinstance(c, list):
                chunks.extend(p.get("text", "") for p in c if isinstance(p, dict))
            elif isinstance(c, str):
                chunks.append(c)
    if not out["text"]:
        out["text"] = "\n".join(chunks).strip()
    return out


def parse_agy(lines: list[str]) -> dict:
    """agy --print: plain text answer on stdout, usage not reliably exposed."""
    prose = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("{")]
    return {"text": "\n".join(prose).strip(), "tokens_in": 0, "tokens_out": 0,
            "cost_usd": None, "session_id": None, "error": None}


PARSERS = {
    "claude": parse_claude, "codex": parse_codex, "opencode": parse_opencode,
    "zcode": parse_zcode, "kimi": parse_kimi, "grok": parse_grok, "agy": parse_agy,
}

# Harnesses that buffer stdout (no incremental events): stall detection off.
NO_STREAM_HARNESSES = {"zcode", "agy"}


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #

def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=KILL_GRACE)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def run_one(*, harness: str, prompt: str, out_dir: Path, cwd: Path,
            model: str | None = None, variant: str | None = None,
            timeout: int = DEFAULT_TIMEOUT, stall: int = DEFAULT_STALL,
            env_file: Path | None = None) -> dict:
    """Run a single checker. Returns the result dict (also written to out_dir)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    scrub = make_scrubber(load_secret_env(env_file))

    (out_dir / "prompt.txt").write_text(scrub(prompt))

    with ZcodeModel(model if harness == "zcode" else None):
        cmd, stdin_prompt = build_command(harness, model, variant, prompt, cwd)

        env = dict(os.environ)
        env.update(load_secret_env(env_file))

        started = time.time()
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), env=env,
            stdin=subprocess.PIPE if stdin_prompt is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
        if stdin_prompt is not None and proc.stdin is not None:
            try:
                proc.stdin.write(stdin_prompt)
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass

        lines: list[str] = []
        stalled = timed_out = False
        last_output = time.time()
        detect_stall = harness not in NO_STREAM_HARNESSES and stall > 0

        while True:
            line = proc.stdout.readline() if proc.stdout else ""
            if line:
                lines.append(line)
                last_output = time.time()
                continue
            if proc.poll() is not None:
                # Drain whatever remains.
                if proc.stdout:
                    lines.extend(proc.stdout.read().splitlines())
                break
            now = time.time()
            if now - started > timeout:
                timed_out = True
                _kill_tree(proc)
                break
            if detect_stall and now - last_output > stall:
                stalled = True
                _kill_tree(proc)
                break
            time.sleep(0.2)

        stderr_tail = ""
        if proc.stderr:
            try:
                stderr_tail = proc.stderr.read()[-4000:]
            except OSError:
                pass

        duration = round(time.time() - started, 1)

    (out_dir / "stream.ndjson").write_text(scrub("\n".join(lines)))
    (out_dir / "stderr.log").write_text(scrub(stderr_tail))

    parsed = PARSERS[harness](lines)
    answer = scrub(parsed.pop("text") or "")

    tokens_in = parsed.get("tokens_in", 0)
    tokens_out = parsed.get("tokens_out", 0)
    cost_native = parsed.get("cost_usd")
    if not isinstance(cost_native, (int, float)):
        cost_native = None
    cost_est = None if cost_native is not None else estimate_cost_usd(harness, tokens_in, tokens_out)

    result = {
        "harness": harness,
        "model": model or "(harness default)",
        "status": "timeout" if timed_out else "stalled" if stalled else
                  ("error" if proc.returncode not in (0, None) else "ok"),
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "stalled": stalled,
        "duration_s": duration,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_native,
        "cost_usd_est": cost_est,
        "cost_source": "native" if cost_native is not None
                       else ("estimated" if cost_est is not None else None),
        "session_id": parsed.get("session_id"),
        "error": parsed.get("error"),
        "answer_chars": len(answer),
    }
    (out_dir / "answer.md").write_text(answer)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2))
    return {**result, "answer": answer}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def default_env_file() -> Path | None:
    p = Path.home() / ".config" / "zsh" / "secrets"
    return p if p.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Dispatch one headless checker subagent on any coding-agent CLI harness.")
    ap.add_argument("--harness", required=True,
                    choices=["claude", "codex", "opencode", "zcode", "kimi", "grok", "agy"])
    ap.add_argument("--model", default=None, help="model id; omit for harness default")
    ap.add_argument("--variant", default=None,
                    help="reasoning effort (codex: low/medium/high/xhigh; opencode: minimal/low/...)")
    ap.add_argument("--prompt-file", default=None,
                    help="read prompt from file (default: stdin)")
    ap.add_argument("--cwd", default=".", help="working directory for the checker")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--stall", type=int, default=DEFAULT_STALL)
    ap.add_argument("--env-file", default=None,
                    help=f"secrets file with 'export NAME=...' lines (default: {default_env_file()})")
    args = ap.parse_args()

    prompt = Path(args.prompt_file).read_text() if args.prompt_file else sys.stdin.read()
    if not prompt.strip():
        ap.error("empty prompt")

    res = run_one(
        harness=args.harness, prompt=prompt, out_dir=Path(args.out_dir),
        cwd=Path(args.cwd).resolve(), model=args.model or None,
        variant=args.variant or None, timeout=args.timeout, stall=args.stall,
        env_file=Path(args.env_file) if args.env_file else default_env_file(),
    )
    compact = {k: v for k, v in res.items() if k != "answer"}
    print(json.dumps(compact, indent=2))
    print(f"\nanswer ({res['answer_chars']} chars) -> {Path(args.out_dir) / 'answer.md'}")
    return 0 if res["status"] == "ok" and res["answer_chars"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
