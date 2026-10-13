# Security audit report — `frontend-design`

**Audit target:** `frontend-design` skill, repository `anthropics/skills`, branch `main`, path `skills/frontend-design`
**Requested by:** user, via `npx skills add https://github.com/anthropics/skills --skill frontend-design`
**Audit time:** 2026-10-13 17:00 (+03:30)
**Method:** pure static text analysis. No file from the skill was executed, sourced, or evaluated. Only read-only inspection (fetch + text search) was used.

---

## Executive summary

| | |
|---|---|
| Findings total | **0** |
| P0 blocking | 0 |
| P1 needs attention | 0 |
| Informational (not counted as risk) | 0 |
| Safety score | **100 / 100** |
| Verdict | **P2 — safe to use** |

---

## File inventory

The entire skill is two files. There are no scripts, no executables, no bundled assets, no reference documents, no `scripts/` directory.

| File | Size | Lines | Type |
|---|---|---|---|
| `SKILL.md` | 9,390 bytes | 71 | Prose guidance |
| `LICENSE.txt` | 10,174 bytes | 201 | Apache License 2.0 |

Verified against the repository's recursive tree listing: `skills/frontend-design` contains exactly these two entries.

---

## P0 — blocking risks

**None found.**

## P1 — risks needing attention

**None found.**

## Informational reminders

**None.** No hard-coded credentials, no author-owned secrets, no third-party demo assets.

---

## Detailed check results

### Command execution and privilege escalation

- **Hits: 0.** No `curl`, `wget`, `bash`, `sh`, `eval`, `exec(`, `os.system`, `subprocess`, `popen`, `ProcessBuilder`, `check_output`.
- No `sudo`, `chmod`, `chown`, `setuid`, or `requires_approval`.

### Hidden / stealthy execution

- **Regex hits: 2 — both false positives.** Lines 39 and 40 use the word "background" as a *design* term:
  - line 39: `a warm cream background (near #F4F1EA) with a high-contrast serif display…`
  - line 40: `a near-black background with a single bright acid-green or vermilion accent`
- No `nohup`, `disown`, `>/dev/null`, `2>/dev/null`, `--quiet`, `--silent`, or "silently".

### Network requests

- **URLs found: none.** No `http://`, `https://`, `ftp://`, `fetch`, `axios`, `requests.get/post`, `urllib`, `httpx`, `aiohttp`, `node-fetch`, `XMLHttpRequest`, or `$.ajax`.
- The only domain-shaped token anywhere in the file is the literal filename `LICENSE.txt`.
- The skill makes no network calls of any kind.

### Base64 / encoded payloads

- **Hits: 0.** No blobs matching `[A-Za-z0-9+/]{20,}={0,2}`.

### Sensitive paths and credentials

- **Hits: 0.** No `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.gcloud`, `~/.azure`, `~/.kube`, `~/.docker`, `/etc/passwd`, `/etc/shadow`, `/etc/hosts`, `%APPDATA%`, `%USERPROFILE%`.
- No `.env`, `credentials`, `secrets`, `password`, `api_key`, `private_key`, `secret_key`.

### File operations

- **Hits: 0.** No `rm`, `rm -rf`, `unlink`, `shutil.rmtree`, `os.remove`, `readFileSync`, `writeFileSync`, `open(`.
- The skill writes, moves, and deletes nothing.

### Dependency installation (supply chain)

- **Hits: 0.** No `pip install`, `npm install -g`, `yarn global add`, `pnpm add -g`, `gem install`, `cargo install`, `go install`, `brew install`.
- No virtualenv or conda instructions, and no non-official registry flags (`--index-url`, `--registry`).
- The skill installs nothing and requires nothing.

### Prompt-injection bait

- **Hits: 0.** No `CRITICAL REQUIREMENT`, `WILL NOT WORK`, `RUN THIS COMMAND`, `MANDATORY`, `必须先执行`, `请先运行`, or equivalent coercion patterns.
- The document contains no instruction that tries to make an agent execute something.

### Remote script deep analysis

**Not applicable.** The deep-analysis step (step 4 of the audit process) triggers only when a skill automatically downloads and executes a remote script. This skill downloads and executes nothing, so there is no remote URL to analyse.

---

## Repository-level manifest check

Checked beyond the skill folder itself, because a plugin-level hook would be a real supply-chain vector:

- `.claude-plugin/marketplace.json` (repo `anthropics/skills`, `main`) declares `frontend-design` as a plain entry in the `example-skills` plugin: `"skills": ["./skills/frontend-design", …]`, with `"strict": false`.
- The manifest contains **no** `hooks`, `commands`, `mcpServers`, `agents`, `scripts`, `postInstall`, or `install` keys.
- **Conclusion:** installing this skill registers no hooks, runs no install script, and starts no MCP server. It adds advisory text only.

---

## LICENSE verification

- `LICENSE.txt` is unmodified **Apache License 2.0** boilerplate.
- Exactly one URL: `http://www.apache.org/licenses/` (standard boilerplate, not a payload host).
- Nothing appended after `END OF TERMS AND CONDITIONS` — a common place to hide a payload. The file ends cleanly at the standard terminator.
- No script or execution tokens in the license text (the single match for "executed", line 136, is the standard legal phrase "any separate license agreement you may have executed").

---

## What the skill actually does

The skill is ~71 lines of prose design guidance. It advises on:

- grounding a design in the subject matter rather than applying a template;
- typography choices, type scales, line length, and avoiding default treatments;
- using visual structure as information (borders, numbering only when content is genuinely a sequence);
- restrained, purposeful motion;
- a two-pass process — plan a token system (color/type/layout/principles), review it against the brief, then build and self-critique;
- a catalogue of generic "AI-generated design" tells to avoid;
- interface copywriting.

There is no instruction to run a command, read a file, contact a network, or install anything. Its influence is limited to design decisions.

---

## Installation result

| | |
|---|---|
| Installed via | `npx skills add https://github.com/anthropics/skills --skill frontend-design -g -y` |
| Canonical location | `C:\Users\Alireza\.agents\skills\frontend-design\` |
| Agent symlink created by the CLI | `C:\Users\Alireza\.codebuddy\skills\frontend-design` → `.agents/skills/frontend-design` |
| WorkBuddy location | `C:\Users\Alireza\.workbuddy-ai\skills\frontend-design\` (added separately — the CLI does not target this directory) |
| Integrity | `SKILL.md` and `LICENSE.txt` byte-identical to the audited content (line endings aside) — no tampering during install |

Non-fatal CLI message: `frontend-design → PromptScript: PromptScript does not support global skill installation`. This is a limitation of one agent target in the installer, not a security or integrity issue; the skill installed correctly for every other target.

---

## Conclusion

**Risk level: P2 — safe.**

The skill is pure documentation with no executable surface. It contains no commands, no network access, no file operations, no credential access, and no dependency installation. The repository manifest attaches no hooks. Installed and verified.

**Advisory:** the CLI's own output says "Review skills before use; they run with full agent permissions." That warning is generic to all skills. For this one, the review is complete and the surface is a single prose document.
