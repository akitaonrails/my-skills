# Security Checklist

Use this as a coverage ledger, not a substitute for tracing the project's real
data and authority flows. Mark each item applicable, not applicable with reason,
reviewed with evidence, or finding.

## 1. Scope and architecture

- Pin the audited commit/range and deployment mode.
- Identify public, authenticated, admin, internal, local, plugin, CI, and
  dependency trust boundaries.
- Identify sensitive data, credentials, execution capability, integrity,
  availability, and billing assets.
- Draw input -> parse -> validate -> authorize -> side effect -> persist ->
  output/log paths.
- Identify background jobs and alternate entry points that bypass the primary
  request path.

## 2. Authentication

- Use established authentication libraries/protocols.
- Validate signature/MAC before trusting claims.
- Validate issuer, audience, subject, expiry, not-before, and algorithm.
- Prevent algorithm confusion, unsigned tokens, key-id traversal/SSRF, replay,
  fixation, downgrade, and insecure fallback.
- Use CSPRNG for tokens and sufficient entropy.
- Store tokens/passwords securely; never log them.
- Support expiry, rotation, revocation, logout, and credential compromise.
- Compare fixed secrets in constant time where relevant.
- Bind sessions/callbacks/device flows to the initiating principal.

## 3. Authorization and multi-tenancy

- Deny by default at a centralized capability/policy boundary.
- Authenticate and authorize every route, method, message, background job, and
  alternate protocol entry point.
- Check object ownership and tenant/workspace/project scope on every read,
  search, mutation, export, backup, restore, and destructive operation.
- Fail closed for missing, partial, ambiguous, stale, or conflicting identity.
- Keep cache/index/file/object-store keys fully scoped.
- Prevent IDOR/BOLA, mass assignment, role/self-promotion, confused deputy,
  capability reuse, and check/use races.
- Verify admin/root separation for both UI and API/helper paths.
- Ensure counts, existence errors, timing, logs, search ranking, embeddings, and
  generated summaries do not leak another tenant's data.

## 4. Input and injection

- Normalize once at a typed boundary; validate after decoding/canonicalization.
- Bound length, depth, count, numeric ranges, recursion, and encoding.
- Use parameterized queries and structured builders.
- Pass subprocess argv separately; avoid shell evaluation.
- Escape for the exact output context (HTML, JS, URL, header, CSV/formula, log,
  terminal, template).
- Constrain file paths under canonical roots; handle symlinks and race windows.
- Validate archive entries before extraction; cap expansion ratios and totals.
- Restrict URL schemes, hosts, ports, redirects, DNS/IP resolution, and private
  network targets for server-side fetches.
- Avoid unsafe native/object deserialization and polymorphic type activation.
- Treat prompts/retrieved text/tool output as data; enforce tool/capability
  policy outside the model and sanitize outbound context.
- Prevent CRLF/header, host-header, open redirect, regex, XPath/LDAP, and query
  DSL injection when those sinks exist.

## 5. Filesystem, processes, and plugins

- Use least-privilege users and restrictive create permissions.
- Avoid predictable temp paths; open atomically and resist symlink/hardlink races.
- Preserve canonical ownership and scope across read/write/delete/move/restore.
- Validate executable paths and plugin provenance.
- Scrub inherited environment, cwd, file descriptors, and credentials.
- Bound subprocess time/output/resources and handle cancellation/cleanup.
- Do not grant plugins/hooks more capabilities than required.
- Treat compilers, macros, build scripts, package lifecycle hooks, test discovery,
  and migrations as code execution.
- Verify update channels, checksums/signatures, rollback, and downgrade behavior.

## 6. Network and web

- Bind to the least exposed interface by default.
- Require authentication before parsing expensive/sensitive request bodies.
- Enforce body/header/time/concurrency/rate limits.
- Validate host/proxy headers and trusted proxy configuration.
- Configure CORS narrowly; use CSRF defenses for cookie-authenticated mutation.
- Set secure cookie flags and browser security headers where applicable.
- Verify webhook signatures over raw bytes; prevent replay.
- Do not leak stack traces, secrets, paths, tenant existence, or internal URLs.
- Validate TLS certificates/hostnames; make plaintext remote use explicit.
- Prevent request smuggling/desync at proxy/backend boundaries where applicable.

## 7. Persistence, consistency, and lifecycle

- Validate before mutation and authorize inside the correct transaction/race
  boundary.
- Commit derived indexes with canonical data or expose reliable recovery state.
- Use atomic file writes and durable rename/fsync patterns where required.
- Have one clear ownership model for concurrent writers.
- Make destructive operations explicit, scoped, confirmed, audited, and
  recoverable.
- Verify migrations forward and rollback/recovery paths on representative data.
- Validate backups/restores, archive paths, versions, ownership, and integrity.
- Preserve audit attribution; do not let users forge another actor.
- Define retention/deletion behavior for canonical data, caches, logs, exports,
  backups, embeddings, and model context.

## 8. Secrets and privacy

- Keep real secrets out of source, history, fixtures, docs, images, artifacts,
  logs, errors, metrics, telemetry, command lines, and process listings.
- Centralize secret/config resolution and distinguish absent from empty values.
- Minimize data collection and model/provider context.
- Sanitize before persistence/transport/logging, not after.
- Redact nested and structured fields, not only obvious string patterns.
- Protect exports/backups and avoid insecure default destinations.
- Make cross-border/external provider disclosure visible where relevant.
- Test deletion/retention and user/tenant separation.

## 9. Cryptography

- Use maintained standard primitives and protocols.
- Use CSPRNG and unique nonces/IVs as required.
- Separate keys by purpose and rotate safely.
- Authenticate ciphertext and metadata; do not invent encryption formats.
- Verify signatures before use and pin the intended trust root/provenance.
- Avoid insecure hashes, ciphers, modes, certificate bypasses, and silent
  downgrade/fallback.

## 10. Availability and abuse

- Cap request sizes, collection counts, graph depth, regex work, decompression,
  generated output, log cardinality, and disk growth.
- Bound queues, tasks, threads, connections, pools, and per-user/global work.
- Apply timeouts, cancellation, retry limits, exponential backoff, and jitter.
- Avoid retrying non-idempotent side effects without deduplication.
- Prevent lock starvation/deadlock and long transactions on hot paths.
- Rate-limit expensive auth, search, generation, upload, export, and webhook
  paths as appropriate.
- Make degraded dependencies fail predictably without cascading exhaustion.

## 11. Supply chain, CI, and release

- Explain every dependency addition and registry/source change.
- Review lockfiles, checksums, git revisions, path deps, features, build scripts,
  package lifecycle hooks, vendored code, and licenses.
- Investigate typosquatting, maintainer/provenance changes, stale/unmaintained
  packages, and advisories.
- Keep CI permissions minimal and pin third-party actions according to project
  policy.
- Never run untrusted PR code with repository secrets or write tokens.
- Audit `pull_request_target`, dynamic matrices, shell interpolation, artifact
  names/paths, caches, and reusable workflow inputs.
- Separate build from publish; publish only exact tagged, tested commits.
- Verify version/tag consistency, checksums/signatures/attestations, artifact
  provenance, registry destination, and rollback.
- Protect deploy/release credentials from logs and contributor-controlled code.

## 12. Malicious-code indicators

These are leads, not proof. Determine intent and reachability.

- New network destinations, DNS, telemetry, webhooks, tunnels, or uploads.
- Credential/home/browser/cloud metadata discovery.
- Shell/eval/dynamic loading or downloaded execution.
- Base64/hex/compressed/encrypted blobs or staged decode-and-execute paths.
- Unicode bidi controls, homoglyph identifiers, invisible conditions, minified
  code, generated files without source, unexplained binaries.
- Time/user/host/CI/region-triggered behavior and delayed activation.
- Hidden accounts, static keys/tokens, debug/admin bypasses, permissive fallback.
- Persistence through startup files, cron/services, package hooks, plugins,
  workflows, images, or update channels.
- Disabling security tools, tests, logging, audit, TLS, signature checks, auth,
  sandboxing, or resource limits.
- Tests/mocks that conceal real side effects or assert vacuous behavior.
- Destructive cleanup outside project roots or anti-analysis behavior.

## 13. Evidence quality

- Distinguish code reachability from grep hits.
- State attacker prerequisites and control over each input.
- Prove the sensitive sink and missing/failed control.
- Include a legitimate control case in tests.
- Recheck all alternate callers and failure/fallback paths.
- Verify fixes on the exact final commit and deployment shape.
- State residual risk instead of converting unknowns into a pass.
