# Ecosystem-Specific Security Checks

Load only sections whose signals exist in the audited project. Project-owned
instructions and CI take precedence over example commands. Inspect tool config
and suppressions before interpreting results.

## Rust (`Cargo.toml`)

- Review `build.rs`, proc macros, `cargo` aliases/config, git/path dependencies,
  features, `links`, native libraries, and vendored code before building.
- Search for `unsafe` and forbidden/allowed lint changes; inspect any FFI boundary.
- Review `Command`, shell invocation, `std::env`, temp/filesystem path handling,
  serde custom deserializers/untagged enums, regexes, archive parsing, and async
  task/queue bounds.
- Check integer conversions, allocation from untrusted lengths, blocking work in
  async paths, cancellation, lock ordering, and panic/`unwrap` in request paths.
- Use configured gates such as `cargo clippy`, `cargo test`, `cargo deny`,
  `cargo audit`, and fuzz/property tests in isolation after build-script review.

## JavaScript/TypeScript (`package.json`)

- Use the committed package manager/lockfile. Review `preinstall`/`postinstall`,
  scripts, package overrides/resolutions, git/file URLs, new registries, and
  transitive lockfile surprises before install.
- Inspect `child_process`, `eval`/`Function`, dynamic imports, prototype
  pollution, object merge/mass assignment, regexes, filesystem paths, URL fetch,
  template/DOM sinks, serialization, and source maps.
- For Node servers, audit proxy trust, body limits, CORS/CSRF/cookies, redirects,
  header handling, upload paths, SSRF, and async promise/error cleanup.
- For browser apps, audit XSS sinks, token storage, postMessage origin checks,
  CSP, third-party scripts, service workers, OAuth callbacks, and client-side
  authorization assumptions.
- Run configured lint/type/test/audit/SAST commands only after lifecycle/plugin
  review. Do not assume `npm audit` severity equals exploitability.

## Python (`pyproject.toml`, `setup.cfg`, `setup.py`)

- Review build backend, setup hooks, plugins, editable/path/VCS dependencies,
  indexes, constraints/lockfiles, and native extensions before installation.
- Inspect `subprocess`/shell, `eval`/`exec`, pickle/yaml/object deserialization,
  template rendering, ORM raw queries, filesystem/archive handling, URLs/SSRF,
  regexes, and dynamic imports.
- Audit framework debug modes, secret keys, host/CORS/CSRF/session settings,
  object authorization, upload handling, redirects, and proxy headers when the
  corresponding web framework exists.
- Use configured linters/type checks/tests plus tools such as dependency audit
  or Bandit only when already trusted/configured or installed from a trusted
  source in isolation.

## Go (`go.mod`)

- Review module replacements, vanity/private module sources, generated code,
  cgo, assembly, `//go:linkname`, plugins, and `go:generate` commands. Do not run
  generators automatically.
- Inspect `os/exec`, shell wrappers, template packages, `unsafe`, filesystem and
  archive paths, URL clients/redirects, SQL, regexes, goroutine/channel bounds,
  context cancellation, race conditions, and integer/allocation conversions.
- Use `gofmt`, `go vet`, `go test`, race/fuzz/vuln tools when applicable and
  safe after generator/build review.

## Ruby/Rails (`Gemfile`, `.gemspec`, Rails files)

- Review gem sources, git/path gems, native extensions, install hooks, Rake tasks,
  initializers, engines, and lockfile changes before Bundler execution.
- Inspect `system`/backticks/Open3, eval/send/constantize, YAML/Marshal, raw SQL,
  ERB/HTML safety, redirects/URLs, filesystem/archive paths, regexes, and mass
  assignment.
- In Rails projects only, audit authentication filters, policy/scoping, CSRF,
  session/cookie/encryption keys, Active Storage/uploads, signed IDs, jobs,
  Action Cable, host/proxy configuration, and environment-specific production
  settings.
- Use project tests/lint plus configured Brakeman and dependency audit tools.

## JVM (`pom.xml`, `build.gradle`, `build.gradle.kts`)

- Review Maven/Gradle plugins, repositories, init/settings scripts, wrappers,
  annotation processors, generated code, and dependency locking/verification
  before build.
- Inspect process execution, reflection/class loading, Java/Kotlin scripting,
  object/XML/YAML deserialization, SpEL/expression languages, JNDI, SQL, template
  output, filesystem/archive handling, SSRF, regexes, and thread/pool bounds.
- For actual web frameworks, audit filter/security-chain coverage, method/object
  authorization, CSRF/CORS, actuator/debug endpoints, error disclosure, upload
  limits, and proxy headers.

## .NET (`*.sln`, `*.csproj`, `Directory.Build.*`)

- Review NuGet sources/lockfiles, MSBuild targets/tasks, analyzers/source
  generators, post-build events, and native libraries before build.
- Inspect process execution, reflection/dynamic compilation, unsafe code,
  deserialization, XML, SQL, Razor/HTML, filesystem/archive paths, URLs/SSRF,
  regexes, async cancellation, and resource ownership.
- For ASP.NET projects only, audit middleware order, endpoint authorization,
  antiforgery, CORS/cookies, Data Protection keys, forwarded headers, model
  binding/mass assignment, uploads, and rate/body limits.

## PHP/Composer (`composer.json`)

- Review Composer scripts/plugins, repositories, path/VCS packages, autoload
  changes, and lockfile integrity before installation.
- Inspect command execution, include/require paths, unserialize, SQL, template
  escaping, file upload/path/archive behavior, URLs/SSRF, redirects, sessions,
  and regexes.
- Apply framework-specific auth/CSRF/mass-assignment/debug/storage checks only
  when that framework is present.

## Elixir/Erlang (`mix.exs`, `rebar.config`)

- Review Mix aliases/tasks, Hex/git/path deps, compilers, NIFs/ports, releases,
  and runtime config before build.
- Inspect `System.cmd`, dynamic atom creation, unsafe term decoding, Ecto
  fragments, template safety, filesystem paths, URL clients, process/mailbox
  bounds, supervision/restart loops, ETS ownership, and distributed node
  cookies/TLS.
- For Phoenix projects only, audit plugs/pipelines, CSRF, sockets/channels,
  LiveView authorization, uploads, endpoint secrets, proxy headers, and rate/body
  limits.

## Shell, Make, CI, containers, and infrastructure

Apply whenever corresponding files exist, regardless of application language.

- Shell: quote expansions, avoid `eval`, separate data from commands, protect
  temp files, globbing, `IFS`, traps, pipelines, curl/download execution,
  destructive paths, environment leakage, and privilege changes.
- Make/task runners: targets can execute during setup/test; inspect includes,
  shell expansion, downloaded tools, environment, and cleanup.
- GitHub Actions/CI: least permissions, no secrets with untrusted checkout,
  cautious `pull_request_target`, quote event data, pin actions per policy,
  isolate caches/artifacts, protect environments, and separate build/publish.
- Docker: trusted bases/digests, non-root, minimal capabilities, no host socket or
  sensitive mounts, safe build args/secrets, copy scope, healthcheck, network,
  read-only/rootfs/temp needs, and multi-stage artifact provenance.
- Kubernetes/IaC: RBAC/service accounts, privileged/host namespaces/paths,
  capabilities, seccomp, secrets, network policy, public exposure, metadata
  access, state/plan secrets, encryption, and destructive drift.

## Native/mobile/desktop

Apply only when native/mobile/desktop targets exist.

- Review unsafe/FFI/native libraries, IPC/custom URL schemes, local sockets,
  auto-update signing, deep links, webviews, file associations, permissions,
  keychain/credential storage, sandbox/entitlements, and platform packaging.
- Treat Electron/Tauri preload/IPC and webview bridges as authorization
  boundaries; validate sender/origin and expose a minimal typed API.
- Check platform-specific paths and permission models on every supported OS;
  do not project Linux guarantees onto Windows/macOS or vice versa.
