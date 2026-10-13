# Skill Security Audit Report

**Source archive:** `E:\Agentic\MathTutor\all-skills.zip` (1,543,233 bytes)
**Audit date:** 2026-10-13
**Method:** Static text analysis only (read-only). No script from the archive was executed, downloaded, or installed during the audit.
**Skills audited:** 14 (433 files total)
**Install destination:** `C:\Users\Alireza\.workbuddy-ai\skills\` (user-level)

---

## Executive summary

| Metric | Count |
|---|---|
| Total findings | 3 |
| P0 (blocking) | 0 |
| P1 (attention) | 3 |
| Informational notes | 1 |
| **Safety score** | **92 / 100** |

**Verdict: P2 — safe to use.** No prompt injection, no obfuscated payloads, no credential theft, no privilege escalation, and no destructive system commands were found. The three P1 items are ordinary supply-chain notes (dependency installation and a GitHub-based installer), not signs of malicious intent.

---

## P0 — blocking risks

✅ None found.

Specifically verified as absent across all 433 files:

- No prompt-injection phrases (`CRITICAL REQUIREMENT`, `WILL NOT WORK`, `RUN THIS COMMAND`, `必须先执行`, `ignore previous instructions`, …)
- No `base64 -d | bash` / `curl | bash` / `wget | sh` patterns
- No hardcoded credentials (OpenAI keys, AWS keys, GitHub tokens, private keys) — regex sweep for `sk-…`, `AKIA…`, `ghp_…`, `BEGIN PRIVATE KEY` returned nothing
- No reads of `~/.ssh`, `~/.aws`, `~/.gnupg`, `/etc/passwd`, `/etc/shadow`, `.netrc`, or keychains
- No `sudo`, `chmod 777`, `chown`, `crontab`, or `authorized_keys` writes
- No destructive system paths (`rm -rf /`, `~/*`, `/etc/`) — the only `rm -rf` calls target self-created temp/staging directories
- No path traversal or absolute paths inside the archive; no symlinks; no nested `.git`

---

## P1 — attention items

### 1. `skill-installer/scripts/install-skill-from-github.py` — remote download + install

- **Location:** `skill-installer/scripts/install-skill-from-github.py:81-115, 131-166, 219-223`
- **Behaviour:** downloads a repo ZIP from `https://codeload.github.com/<owner>/<repo>/zip/<ref>` (or falls back to `git clone --depth 1 --sparse`), extracts it, and copies the selected skill into `$CODEX_HOME/skills`.
- **Assessment:** this is a **capability**, not auto-execution — the agent only runs it when the user asks to install a skill, and the run requires user approval. Mitigations present in the code: GitHub-only URL allowlist (`netloc != "github.com"` → error), relative-path enforcement, symlink rejection, zip-slip protection (`_safe_extract_zip` verifies every entry resolves inside the destination), and refusal to overwrite an existing skill directory.
- **Residual risk:** the content installed is whatever lives in the target repo at that ref — it is not hash-pinned. Supply-chain risk is inherent to "install from GitHub", not a defect of this script.

### 2. `imagegen` — package installation via `uv pip install`

- **Location:** `imagegen/scripts/image_gen.py:59`, `imagegen/SKILL.md:280,285`
- **Behaviour:** on a missing dependency the script runs `uv pip install <package>` (`openai`, `pillow`).
- **Assessment:** scoped to a uv-managed virtual environment, not a global install, and only triggered on the explicit CLI-fallback path (which itself requires the user to confirm CLI mode and set `OPENAI_API_KEY`). Risk is limited to ordinary package resolution.

### 3. `sites` templates — `npm ci` / `pnpm install` in starter projects

- **Location:** `sites/templates/vinext-starter/scripts/install-ci.sh`, `install-pnpm.sh`, `npm-install.mjs`, `pnpm-install.mjs`
- **Behaviour:** installs dependencies for the generated starter project.
- **Assessment:** unusually well-guarded for a template. It pins `vinext` to a resolved tarball + integrity hash from `package-lock.json`, runs a `curl` preflight and verifies the sha512 before installing, pins pnpm to `11.25.0`, isolates `HOME`, npm cache and pnpm store under a project-owned `.sites-runtime/`, takes a file lock to prevent overlapping installs, and disables wrangler telemetry. The single `curl` call fetches the locked tarball from the configured npm registry only, with `--fail --max-time 120`, and the payload is integrity-checked before use.
- **Note:** requires Linux `flock`/`timeout`; on Windows these scripts will not run as-is.

---

## Informational notes (not risks)

**Hardcoded asset URLs (author-owned demo content)** — `ai-elements/scripts/audio-player-remote.tsx:20`, `voice-selector.tsx:40-90`, `web-preview.tsx:108`
Public demo asset URLs pointing at Vercel blob storage / v0 preview hosts, used as sample `src` values in component examples. They are author-owned demo content and are never fetched automatically by the skill. No action required.

---

## Detailed check results

### Command execution and privilege
Matches found: 10 files, all benign.
- `child_process` / `subprocess` usage: `openai-docs/scripts/fetch-codex-manual.mjs` (invokes `curl` to fetch the official Codex manual), `skill-installer/scripts/install-skill-from-github.py` (invokes `git`), `sites/templates/vinext-starter/scripts/{install-ci,npm-install,pnpm-install,run-framework}.mjs` (invokes the project package manager), `ui-ux-pro-max/scripts/tests/*` (test harness).
- No `eval(`, no `os.system`, no shell-string interpolation of untrusted input.
- `sudo` / `chmod 777` / `chown` / `crontab`: **0 matches**.

### File operations and sensitive paths
- `shutil.rmtree` / `rm -rf`: `skill-installer` (self-created `tempfile.mkdtemp`), `sites/scripts/package-site.sh` (self-created `mktemp -d`), `sites/.../install-pnpm.sh` (self-created seed staging dir), `ui-ux-pro-max/scripts/design_system.py` (build artifact). All scoped to directories the code itself created.
- Credential/sensitive-path reads: **none**. The only `.env` references are a build-exclusion glob (`connector-preview-plugin.mjs:55-56`) and framework `import.meta.env` access.

### Network requests
All referenced domains are legitimate and expected for these skills:
`registry.npmjs.org` (887), `github.com` / `codeload.github.com` / `raw.githubusercontent.com` (163), `developers.openai.com` (38), `api.openai.com`, `ui.shadcn.com`, `fonts.googleapis.com` / `fonts.gstatic.com`, `tailwindcss.com`, `react.dev`, `vercel.com`, `www.w3.org`, `images.unsplash.com`, `v0.dev`, plus OpenCollective/Tidelift/Patreon sponsor links in license metadata.
No unknown or look-alike domains. No `ftp://`. No suspicious base64 blobs (the three `base64` hits are `base64.b64decode` of API image payloads in `image_gen.py`, plus an inline data-URI sample in `validate-artifact.mjs`).

### Remote-script deep analysis
No skill in the archive performs download-then-execute of a remote script. The `curl` invocation in `sites/.../install-ci.sh` downloads a package tarball (not a script) and hash-verifies it before `npm ci` consumes it — no execution of fetched content. Therefore no P0 remote-execution item applies.

### Dependency installation
- **Global installs:** none (`npm install -g`, `pipx install`, `gem install`, `cargo install`, `brew install`: 0 matches).
- **Virtual-env isolation:** provided — `imagegen` uses uv-managed environments and documents the preferred path; `sites` fully isolates HOME/cache/store.
- **Non-official sources:** none. No `--index-url` overrides, no `--registry` overrides, no `git+https://` installs. The bundled `.npmrc` only sets `audit=false`, `fund=false`, `update-notifier=false`.

---

## Overall recommendations

1. The three P1 items are behavioural, not malicious. Keep them in mind when these skills run: `skill-installer` will install whatever a given GitHub repo contains at the chosen ref, so only point it at repos you trust.
2. `skill-installer`, `pets`, `create-pet`, `update-pet` and `imagegen` are written for OpenAI Codex (they reference `$CODEX_HOME`, `~/.codex/skills`, and MCP tools such as `list_pets` / built-in `image_gen`). They will install and be discoverable here, but some of their workflows expect tools that do not exist in this environment.
3. Several names overlap with WorkBuddy built-ins (`sites`, `skill-creator`, `imagegen` ≈ `buddy-image-processing`, `openai-docs`, `plugin-management` ≈ `recommend-connectors`). The installed copies live at user level, so they shadow rather than replace the bundled ones — remove the user-level copy if you want the built-in to take precedence.

---

## Conclusion

**Risk level: P2 — safe to use.**
**Recommendation: install.** No poisoning risk detected; the archive contains well-formed, professionally written skills. All 14 were installed to `C:\Users\Alireza\.workbuddy-ai\skills\`.
