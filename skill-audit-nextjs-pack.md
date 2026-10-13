# Security audit report — Next.js skill pack (6 skills)

**Audit target:** the `skills/` folder of `vercel/next.js`, branch `canary` — requested via `npx skills add vercel/next.js`
**Skills in scope:** `next-bundle-optimizer`, `next-cache-components-adoption`, `next-cache-components-optimizer`, `next-dev-loop`, `next-partial-prefetching-adoption`, `next-partial-prefetching-optimizer`
**Audit time:** 2026-10-13 17:05 (+03:30)
**Method:** pure static text analysis. No file was executed, sourced, or evaluated. Read-only inspection only (fetch + text search).

---

## Executive summary

| | |
|---|---|
| Files inspected | **16 markdown files**, 177,663 bytes, 2,515 lines. Zero scripts, zero binaries, zero executables. |
| Findings total | **4** |
| P0 blocking | **0** |
| P1 needs attention | **4** |
| Informational | 0 |
| Safety score | **72 / 100** |
| Verdict | **P1 — needs attention; install only after explicit confirmation** |

**Summary judgement:** there is no malware here. No data exfiltration, no credential theft, no destructive commands, no obfuscation, no prompt-injection payloads, and no third-party network destinations. The four P1 findings are all **supply-chain and consent concerns** of the same family: these skills install other software, and one of them explicitly instructs the agent to do so **without asking the user**.

---

## P0 — blocking risks

**None found.**

No `curl | bash`, no remote script download-and-execute, no sensitive-file reads, no destructive commands, no privilege escalation, no hidden execution.

---

## P1 — risks needing attention

### P1-1 — Consent-bypass install instruction (the most significant finding)

- **Location:** `next-cache-components-adoption/SKILL.md:96`
- **Text:**
  > You don't need permission to install `next-dev-loop` itself. It's a tool, like installing a dev dependency. If a user is present, briefly tell them you're installing it for verification. In a non-interactive run (CI, dashboard, sandbox), install it without asking — "can't prompt the user" is not a reason to skip.
- **Risk:** this is an instruction whose stated purpose is to remove the user's ability to consent. It anticipates the objection ("can't prompt the user") and pre-empts it, and it names non-interactive agent environments — CI, dashboards, sandboxes — as the case where asking is unnecessary. An agent that follows it will install software from the network with no approval step.
- **Attack scenario:** in any non-interactive agent run, the skill causes a network install the operator never approved. It also normalises the pattern, so the same agent is more likely to skip confirmation for later installs in the same session.
- **Note on intent:** this is not covert — it says so in plain text, and it is presumably the vendor trying to make its toolchain work reliably. That is why it is P1 rather than P0: the behaviour is disclosed, not hidden. It is still a consent bypass.
- **Fix:** treat every install as a user decision. Replace with: "Ask before installing; if you cannot prompt, report the missing dependency and stop."

### P1-2 — Global npm install

- **Location:** `next-dev-loop/SKILL.md:47`
- **Text:** `Install or upgrade `agent-browser`: `npm i -g agent-browser@latest`.`
- **Risk:** a global (`-g`) npm install modifies the user's machine-wide Node environment, outside any project sandbox or lockfile. The audit rubric classifies global installs as an environment-damage risk. The package version is pinned only to `@latest`, so the installed code is whatever the registry serves at that moment.
- **Mitigating context:** the same file says that if requirements are missing the agent should "tell the user how to upgrade and stop" (lines 38–39), which is consent-oriented. The `npm i -g` line is the concrete command offered.
- **Fix:** prefer a project-local dev dependency, or a `npx` invocation; keep the global install as a user-run instruction.

### P1-3 — Self-expanding network install chain

- **Locations:**
  - `next-bundle-optimizer/SKILL.md:13` — installs `next-cache-components-optimizer` and `next-partial-prefetching-optimizer`
  - `next-bundle-optimizer/SKILL.md:82` — installs `next-dev-loop`
  - `next-cache-components-adoption/SKILL.md:89` — installs `next-dev-loop`
  - `next-partial-prefetching-adoption/SKILL.md:31` — installs `next-dev-loop`
- **Pattern:** each skill instructs the agent to run `npx skills add <sibling skill>`. Following one skill pulls in more skills, which pull in more again.
- **Risk:** installing 6 skills can silently install a larger set, each one bringing its own instructions — including P1-1 and P1-2. Combined with P1-1, the chain can proceed with no user approval at any link. Every link is also an unpinned fetch of live `canary` content, so what gets installed is not fixed at review time.
- **Fix:** resolve the full set up front, pin to a commit SHA or release tag, and install explicitly rather than letting skills install each other.

### P1-4 — Repo-modifying `npx` codemods

- **Locations:**
  - `next-cache-components-adoption/SKILL.md:25` — `npx @next/codemod@latest upgrade latest`
  - `next-cache-components-adoption/SKILL.md:122` — `npx @next/codemod@latest cache-components-instant-false ./app`
  - `next-partial-prefetching-adoption/SKILL.md:127` — `npx @next/codemod@canary remove-partial-prefetch ./app`
  - `next-cache-components-optimizer/SKILL.md:158` — `npx @next/codemod upgrade`
- **Risk:** `npx` fetches and runs a remote package which then rewrites the user's source tree. `@latest` / `@canary` are unpinned, so the executing code is not fixed at review time.
- **Mitigating context:** the skill does gate the `agents-md` codemod explicitly — "It touches files in their repo, so ask first and run it only if they want it" (line 40) — and the adoption codemod refuses to run on a dirty working tree (line 119). So the pack is aware of the hazard in places, but the gating is inconsistent across the four invocations.

---

## Detailed check results

### Command execution

- **Hits: 1, benign.** `next-dev-loop/SKILL.md:158` — "Don't fall back to `curl`; it bypasses the browser you're testing." This is advice *against* using curl.
- No `curl | bash`, no `wget`, no `eval`, no `subprocess`, no `child_process`, no `__import__`.

### Hidden / stealthy execution

- **Hits: 5, all false positives.** The word "silently" appears in ordinary prose — "silently builds zero routes", "silently no-ops", "not silently streaming everything out of an empty shell".
- No `nohup`, `disown`, `>/dev/null`, `2>/dev/null`, `--quiet`, `--silent`.

### Network requests and URLs

- **All 44 URLs are first-party:** `nextjs.org/docs/...` (official Next.js documentation) and `github.com/vercel/next.js/tree/canary/skills/...` (sibling skill references).
- Local addresses only otherwise: `http://localhost:3000`, `http://localhost:<port>/_next/mcp`.
- **No third-party, lookalike, or unknown domains.** No exfiltration endpoints, no IP literals, no shorteners.

### Encoded payloads

- **None.** No base64-like blobs. No zero-width characters, no bidi control characters, no HTML comments, no hidden text.

### Credentials and sensitive paths

- **No hard-coded secrets.** No `~/.ssh`, `~/.aws`, `~/.gnupg`, `.env` reads, `%APPDATA%`, `%USERPROFILE%`, or `/etc/*`.
- The `process.env` hits are ordinary configuration checks in code examples — `process.env.EXPOSE_TESTING_API === '1'`, `process.env.VERCEL_ENV` — used to *prevent* a testing API from being exposed in production. The "credentials" mentions are prose about unavailable test credentials as an obstacle to report, not instructions to read them.

### File operations

- **No destructive operations.** No `rm -rf`, `unlink`, `os.remove`, `shutil.rmtree`, `Remove-Item`, `del /S`.
- One benign redirect writes an analyzer artifact to a temp path: `pnpm exec next analyze export ... | gzip > /tmp/analyze-app-before.jsonl.gz` (`next-bundle-optimizer/SKILL.md:29`).

### Dependency installation

- Covered by P1-2 and P1-3 above. Also `@next/playwright` and `@playwright/test` are referenced as project dev dependencies (normal).

### Prompt injection

- **None.** No "CRITICAL REQUIREMENT", "WILL NOT WORK", "RUN THIS COMMAND", "ignore previous instructions", or equivalent coercion framing. No imperative text hidden at file tops or in comments.
- The one consent-related instruction (P1-1) is not disguised — it is stated openly, which is why it is graded P1 and not P0.

### Remote script deep analysis

**Not applicable.** No skill downloads and executes a remote script. The P1-3 installs fetch skills (markdown), and the P1-4 codemods fetch npm packages, but neither is a `curl | bash` pattern.

---

## What these skills actually do

They are professional developer-workflow documentation for optimizing Next.js applications:

| Skill | Purpose |
|---|---|
| `next-dev-loop` | Edit/verify rhythm during `next dev`; cross-checks `/_next/mcp` against a real browser via `agent-browser` |
| `next-bundle-optimizer` | Analyzes the app bundle, reports and fixes size candidates |
| `next-cache-components-adoption` | Migrates an app to Cache Components |
| `next-cache-components-optimizer` | Optimizes a route's static App Shell |
| `next-partial-prefetching-adoption` | Adopts partial prefetching |
| `next-partial-prefetching-optimizer` | Optimizes prefetch behavior |

All content is markdown prose and code examples. There is no executable surface of their own.

---

## Installation result

**Installed, after explicit user confirmation of the P1 findings.**

| | |
|---|---|
| Requested via | `npx skills add vercel/next.js` |
| Source revision | branch `canary`, commit `e72e68af59f4631c82925023016e17e52239c993` (2026-10-13) |
| Method | **Audited files copied directly — not via the CLI.** `npx skills add vercel/next.js` clones the entire Next.js repository and was killed after 17+ minutes without completing. |
| Locations | `C:\Users\Alireza\.workbuddy-ai\skills\<skill>\` (WorkBuddy) · `C:\Users\Alireza\.agents\skills\<skill>\` (canonical) · symlinked into `C:\Users\Alireza\.codebuddy\skills\` |
| Integrity | All **16 files verified byte-identical** to the audited content (line endings aside) — 16 matched, 0 mismatched |

Installed skills: `next-bundle-optimizer` (3 files), `next-cache-components-adoption` (3), `next-cache-components-optimizer` (4), `next-dev-loop` (1), `next-partial-prefetching-adoption` (2), `next-partial-prefetching-optimizer` (3).

**Standing rule adopted at install time:** the P1-1 consent-bypass instruction in `next-cache-components-adoption/SKILL.md:96` is to be ignored — installs still require asking. The P1-2 global install (`npm i -g agent-browser@latest`) was **not** run.

---

## Conclusion

**Risk level: P1 — needs attention.**

No malware, no data theft, no destructive behaviour, no obfuscation. The concerns are that the pack installs software (P1-2, P1-3), runs unpinned remote codemods against the user's repo (P1-4), and contains one instruction that tells the agent to install without asking (P1-1).

**Recommendation:** treat P1-1 as a standing rule override — ignore that instruction and keep asking before installs. If installing, pin to a commit SHA rather than `canary`, and expect the pack to want `npm i -g agent-browser` and possibly further `npx skills add` calls.

**Relevance note:** these skills optimize *existing* Next.js applications. The MathTutor repo is Python/FastAPI with no `package.json`, and its Next.js frontend is not scheduled until W4. Most of the pack — cache components, partial prefetching, bundle optimization — will not apply until well after that app exists.
