#!/usr/bin/env bash
# Read-only candidate inventory for a human/agent security audit.
set -euo pipefail

ROOT="${1:-.}"
if [[ ! -d "${ROOT}" ]]; then
  printf 'security-surface: not a directory: %s\n' "${ROOT}" >&2
  exit 64
fi
if ! command -v rg >/dev/null 2>&1; then
  printf 'security-surface: rg is required\n' >&2
  exit 69
fi

cd "${ROOT}"

RG_COMMON=(
  --hidden
  --line-number
  --no-heading
  --color never
  --glob '!.git/**'
  --glob '!target/**'
  --glob '!node_modules/**'
  --glob '!vendor/**'
  --glob '!dist/**'
  --glob '!build/**'
  --glob '!coverage/**'
  --glob '!docs/**'
  --glob '!README*'
  --glob '!CHANGELOG.md'
  --glob '!*.md'
  --glob '!.slim/**'
  --glob '!*.min.js'
  --glob '!*.map'
)

RG_DOCS=(
  --hidden
  --line-number
  --no-heading
  --color never
  --glob 'README*'
  --glob 'CHANGELOG.md'
  --glob 'docs/**'
  --glob '*.md'
  --glob '!.git/**'
  --glob '!.slim/**'
)

section() {
  printf '\n## %s\n' "$1"
}

scan() {
  local label="$1"
  local pattern="$2"
  section "${label}"
  rg "${RG_COMMON[@]}" --regexp "${pattern}" . 2>/dev/null \
    | awk 'NR <= 75 { print } END { if (NR > 75) print "... truncated after 75 candidates" }' \
    || true
}

scan_docs() {
  local label="$1"
  local pattern="$2"
  section "${label}"
  rg "${RG_DOCS[@]}" --regexp "${pattern}" . 2>/dev/null \
    | awk 'NR <= 75 { print } END { if (NR > 75) print "... truncated after 75 candidates" }' \
    || true
}

section 'Repository state'
git status --short --branch 2>/dev/null || true

section 'Detected manifests and security-sensitive project files'
find . -type f \
  \( -name Cargo.toml -o -name build.rs -o -name package.json \
     -o -name pyproject.toml -o -name setup.py -o -name go.mod \
     -o -name Gemfile -o -name '*.gemspec' -o -name pom.xml \
     -o -name build.gradle -o -name build.gradle.kts -o -name '*.csproj' \
     -o -name '*.sln' -o -name composer.json -o -name mix.exs \
     -o -name Dockerfile -o -name 'Dockerfile.*' -o -name docker-compose.yml \
     -o -name docker-compose.yaml -o -name '.gitmodules' -o -name '.gitattributes' \
     -o -path '*/.github/workflows/*.yml' -o -path '*/.github/workflows/*.yaml' \) \
  -not -path './.git/*' -not -path '*/node_modules/*' -not -path '*/target/*' \
  -not -path '*/vendor/*' -print 2>/dev/null | sort | awk 'NR <= 150 { print }'

section 'Tracked executable, symlink, and submodule modes'
git ls-files -s 2>/dev/null \
  | awk '$1 == "100755" || $1 == "120000" || $1 == "160000" { print }' \
  | awk 'NR <= 150 { print }' || true

scan 'Process and dynamic execution candidates' \
  '(Command::new|\.arg\(|\.args\(|std::process|subprocess\.|Popen\(|child_process|execFile\(|spawn\(|system\(|Open3\.|Runtime\.getRuntime\(\)\.exec|ProcessBuilder|System\.cmd|os/exec|eval\(|exec\(|new Function|constantize|Class\.forName|Assembly\.Load|dlopen|unsafe\s*\{)'

scan 'Network, redirect, webhook, and SSRF candidates' \
  '(reqwest|hyper::|ureq|fetch\(|axios|requests\.|httpx|urllib|Net::HTTP|Faraday|HTTPoison|Finch|HttpClient|WebClient|http\.NewRequest|urlopen|redirect|Location:|webhook|169\.254\.169\.254|metadata\.google|localhost|127\.0\.0\.1)'

scan 'Authentication, authorization, and tenant-scope candidates' \
  '(Authorization|Bearer|api[_-]?key|auth[_-]?token|session[_-]?id|authorize|permission|capabilit|is_admin|is_root|tenant|workspace[_-]?id|project[_-]?id|user[_-]?id|role|scope)'

scan 'Query, template, deserialization, and injection candidates' \
  '(execute\(|query\(|raw[_ ]?sql|format!\(.*(SELECT|INSERT|UPDATE|DELETE)|SELECT .*(\+|format|\$\{)|pickle|Marshal\.load|YAML\.load|yaml\.load|unserialize|ObjectInputStream|BinaryFormatter|eval\(|exec\(|innerHTML|dangerouslySetInnerHTML|render_template_string|template\.HTML|shell\s*=\s*True)'

scan 'Filesystem, archive, upload, and path candidates' \
  '(canonicalize|realpath|read_link|symlink|hard_link|tempfile|mktemp|NamedTempFile|\.\.\/|PathBuf|join\(|extract|unpack|archive|tar::|zip::|upload|multipart|remove_dir_all|remove_file|rmtree|File\.delete|rm_rf)'

scan 'Secrets, logs, telemetry, and environment candidates' \
  '(std::env|process\.env|os\.environ|os\.Getenv|ENV\[|System\.getenv|secret|password|private[_-]?key|access[_-]?token|refresh[_-]?token|credential|telemetry|analytics|sentry|tracing::|println!|console\.log|logger\.|log\.)'

scan 'Cryptography and randomness candidates' \
  '(md5|sha1|DES|RC4|ECB|rand\(|random\(|Math\.random|thread_rng|nonce|encrypt|decrypt|signature|verify|constant[_-]?time|danger_accept_invalid|verify_none|InsecureSkipVerify)'

scan 'Bounds, queues, retries, and denial-of-service candidates' \
  '(unbounded|spawn\(|tokio::spawn|thread::spawn|go\s+func|Task\.Run|retry|backoff|timeout|body_limit|max[_-]?(size|depth|items|connections|tasks|bytes)|rate[_-]?limit|Semaphore|mpsc|queue|recursion|decompress|regex)'

scan 'Supply-chain, download, and workflow candidates' \
  '(curl .*\|.*(sh|bash)|wget .*\|.*(sh|bash)|Invoke-WebRequest|Start-Process|npm (install|ci)|pip install|cargo install|go install|bundle install|pull_request_target|permissions:|secrets\.|github\.event|uses:|docker/login-action|setup-buildx|upload-artifact|download-artifact)'

scan 'Obfuscation, encoded payload, and persistence candidates' \
  '(base64|from_base64|decode64|hex::decode|unhexlify|gzip\.decompress|zlib\.decompress|powershell.*-[Ee]ncodedCommand|crontab|systemd|LaunchAgent|RunOnce|Startup|autorun|daemonize|nohup)'

scan_docs 'Documentation install and execution snippets' \
  '(curl|wget|Invoke-WebRequest|irm |iex |Start-Process|npm (install|ci)|pip install|cargo install|go install|bundle install|docker (run|compose)|sudo |chmod \+x)'

scan_docs 'Documentation prompt-injection and secret-handling candidates' \
  '(ignore (all |any )?(previous|prior|system|developer)|system prompt|developer message|do not obey|override instructions|prompt injection|jailbreak|api[_-]?key|auth[_-]?token|password|private[_-]?key|credential)'

section 'Unicode bidi controls'
rg "${RG_COMMON[@]}" --pcre2 '[\x{202A}-\x{202E}\x{2066}-\x{2069}]' . 2>/dev/null \
  | awk 'NR <= 75 { print } END { if (NR > 75) print "... truncated after 75 candidates" }' \
  || true

section 'Candidate scan complete'
printf '%s\n' 'Review reachability, attacker control, authorization, and intent before classifying any hit.'
