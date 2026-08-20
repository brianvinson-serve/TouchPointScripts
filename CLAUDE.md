# RockPointe TouchPoint Development

Local dev environment for **TouchPoint ChMS (TPC)** custom Special Content — SQL scripts, Python scripts, HTML dashboards, email automation — for **RockPointe Church (RPC)**. Brian's volunteer/admin project, separate from Praxen and Resultant.

For the full TouchPoint execution model, dev workflow, condensed schema guardrails, and pre-finish checklist, run `/rockpointe-dev` before substantive work.

## Load-bearing rules (always apply, not just when the command is invoked)

- **Path has a space.** Always double-quote it in shell commands: `cd "/Users/praxen/RockPointe Dev/TouchPointScripts"`. Unquoted fails and can look like "path doesn't exist."
- **Read-only by default.** No `UPDATE`/`DELETE`/`INSERT`/mutation scripts unless Brian explicitly asks and there's a rollback plan. Be careful with church data, especially minors/student ministry data.
- **`DB_REFERENCE.md` (repo root) is the source of truth for schema.** It has confirmed IDs, table behavior, and "previous assumption was wrong" notes. Don't rely on generic TouchPoint docs or old script assumptions when it disagrees. Add newly confirmed facts back into it.
- **This repo is public** (`github.com/brianvinson-serve/TouchPointScripts`). Never commit raw PII, staff email addresses, or full directory/export dumps — follow the existing `.gitignore` pattern for anything with real church-member data.
- **Not the only agent here.** Hermes runs a dedicated dev-worker profile ("Kenny") that picks up RPC-tagged Linear issues and commits directly to this repo under its own git identity (`Kenny (Hermes) <kenny@praxen-mini.local>`). Run `git log --oneline -10` and `git status` before starting substantial work so this session doesn't duplicate or collide with something already dispatched.

## Key paths

| What | Path |
|------|------|
| Schema reference (authoritative) | `DB_REFERENCE.md` |
| Deeper dev reference / workflow | `/rockpointe-dev` command (`.claude/commands/rockpointe-dev.md`) |
| Attendance dashboards + email reports | `attendance-dashboard/` |
| Schema-discovery tooling | `data-dictionary-expander/` |
| Registration-based signup reports | `meal-signup-report/` |
| Staff task notifications | `outstanding-task-notifications/` |
| Student/household contact export | `student-contact-export/` |
