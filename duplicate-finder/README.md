# TP_DuplicatePersonFinder

A read-only TouchPoint Special Content (Python Script) report that finds likely duplicate `People` records — specifically the kind that online registration forms create when TouchPoint's own matching fails to find someone's existing record (a nickname, a typo, a missing field) and creates a brand-new person instead of attaching to the real one.

It never merges anything. It produces a reviewable list; a human merges via TouchPoint's own Admin tool.

## Why this exists

TouchPoint ships native duplicate-detection tables — `dbo.Duplicate` (candidate pairs), `dbo.DuplicatesRun` (finder job history), `dbo.MergeHistory` (merge log), and a `People.HasDuplicates` flag. That native finder exists at every TouchPoint church, but in practice it appears to key on close/exact name matches and does not catch **nickname variants** (it won't connect "Jonathan Smith" to "Johnny Smith") — which is exactly the shape of duplicate a registration form produces, since a returning person often types their own name slightly differently than however staff originally entered it.

This script is a gap-filler, not a replacement: it fuzzy-matches recently-created `People` records with a nickname-aware layer the native tool lacks, and explicitly **excludes** any pair the native tool already knows about (`dbo.Duplicate`), so its output is only what the native finder is missing.

## How it works

**1. Candidate pool.** Pull every `People` record created in the last `LOOKBACK_DAYS` (default 120, override per-run with `?Days=NN`) — a proxy for "came in through a recent registration." Excludes archived, deceased, and business records. Capped at `MAX_RECENT_ROWS` (default 500) as a safety valve.

**2. SQL-side blocking.** For each recent person, find everyone else in `People` who shares at least one plausible signal with them — a SOUNDEX-equivalent last name, a matching email (full address or just the part before `@`, so a domain typo like `gmial.com` still counts), a matching phone (any of cell/home/work, punctuation-normalized), or a birth date that's exact or a documented near-miss (see "Date-of-birth handling" below). This narrows an otherwise-unbounded `People` × `People` comparison down to a manageable candidate set. Every normalized field (SOUNDEX'd last name, cleaned phone digits, lowercased email/local-part) is precomputed once per row in a CTE, and each signal is checked via its own single-key join, unioned together — see "A SQL performance note" below for why it's built this way rather than one big `OR`.

**3. Python-side scoring.** Every candidate pair gets a 0–100 composite score, built from independent signals:

| Signal | How it's scored |
|---|---|
| Last name | Exact match, or a fuzzy Levenshtein ratio for a typo/spelling variant |
| First name | Exact match, a shared nickname cluster (Jon/Johnny/Jonathan), or a fuzzy ratio, discounted for weak matches |
| Email | Exact match, or fuzzy (a one-character typo/misspelled domain earns partial credit) |
| Phone | Exact match, or fuzzy (a transposed/substituted digit earns partial credit) |
| Date of birth | Exact match, or one of several documented near-miss patterns (see below) |

Scores bucket into **High** (≥70), **Medium** (≥45), or **Low** (dropped entirely, below 45). No external matching libraries are used — TouchPoint's Python Script sandbox can't `pip install`, so the Levenshtein distance function and nickname table are hand-rolled, pure-Python.

**4. Household-aware adjustment.** Shared contact info between two *different* people in the same household (a parent and a child with no email of their own, siblings, spouses) is expected, not suspicious — see "Household handling" below for how this avoids flooding the report with family members instead of real duplicates.

**5. Exclude known duplicates.** Any pair already present in `dbo.Duplicate` (either row order) is dropped — this report only shows what the native finder missed.

**6. Render.** One HTML page, sections by confidence tier plus a separate "household link" section (below), capped at `MAX_CANDIDATES_PER_PERSON` (default 5) matches per person so one common last name can't flood the report. Each row links to both people's TouchPoint profile (`{CmsHost}/Person2/{PeopleId}`) for manual review/merge. A collapsible legend at the top (open by default) explains every badge and tier in plain language, using the actual config values so it can't drift out of sync with the thresholds.

## Visual design

Colors are chosen to not rely on hue alone — each signal type also gets a distinct fill style (solid = confirmed exact match, outlined/tinted = a fuzzy "similar" near-miss, dashed = "found but not counted toward the score"), so the distinction still reads even for colorblind viewers, on top of every badge already carrying a text label. Confidence tiers use a single-hue sequential ramp (dark→light blue for High→Low) rather than a red/green/orange traffic-light scheme, plus a left-border accent on each section as a redundant, non-color cue. The household-link section deliberately uses an unrelated hue (teal) to signal "this is a different kind of finding, not a severity level." Self-contained inline CSS only (CSS custom properties, no JS, no external fonts/frameworks) — consistent with the rest of this repo's TouchPoint-hosted-HTML constraints.

## Date-of-birth handling

Modeled on documented record-linkage practice: matching on multiple independent identifiers (name, DOB, contact info) rather than trusting any single field is the standard approach to identity resolution, and day/month-transposed birth dates specifically are a well-known, common data-entry error worth matching explicitly (see Oracle EDQ's "Date Transposition Match" comparator, and the ADGN address/DOB/gender/name record-linkage algorithm). `dob_score()` recognizes:

- Exact match — full credit
- Day/month transposed (e.g. `5/14` entered as `14/5`) — high credit
- Month + day exact, birth year off by ≤9 (a plausible single mistyped digit) — partial credit
- Year + month exact, day off by exactly one — partial credit
- Anything else — **zero credit, not a penalty.** A mismatched field never counts against a pair; it just fails to add corroborating evidence. This script implements a lightweight, deterministic version of that idea (a hand-weighted composite score), not a full probabilistic Fellegi-Sunter model — appropriate for a human-reviewed list, not an automated match/no-match decision.

## Household handling

Two related but different problems show up when a "recent" person shares a last name and contact info with someone else, and the fix depends on whether they're already linked as the same TouchPoint household (`FamilyId`):

**Already linked, unrelated first names → not scored as a duplicate.** A child using a parent's email, siblings sharing a phone, or spouses on the same landline are *expected* to share contact info — that's not evidence they're the same individual. When two records share `FamilyId` and their first names *don't* look like the same person (below `FAMILY_CONTACT_NAME_MIN`, default 0.5 similarity), shared email/phone contributes nothing to the score. A genuine duplicate that happens to live in that household (e.g. "Jonathan Smith" double-registered as "Johnny Smith," both in the same family) is unaffected, since the nickname match keeps the name score high enough that the dampening doesn't apply.

**Not linked, unrelated first names, strong contact overlap → flagged separately, not as a duplicate.** If two records are *not* linked as the same household, but share a near-identical last name, clearly different first names, and at least two of email/phone/DOB, that's usually a different, real, and separate issue: two family members (often siblings/twins) whose records simply haven't been connected in TouchPoint yet. This is a data-maintenance action ("check/fix the family link"), not a merge candidate, so it's routed into its own **"Household link to verify"** report section instead of inflating the duplicate tiers.

## Configuration reference

All at the top of the script:

| Constant | Default | What it controls |
|---|---|---|
| `LOOKBACK_DAYS` | 120 | How far back "recently created" People go. Overridable per-run via `?Days=NN`. |
| `MAX_RECENT_ROWS` | 500 | Safety cap on how many recent records get matched in one run. |
| `MAX_CANDIDATES_PER_PERSON` | 5 | Caps matches shown per recent person, so a common last name can't flood the report. |
| `ORIGIN_FILTER_IDS` | `None` (any source) | Once a church confirms its `lookup.Origin` values, set this to the Id(s) meaning "Web"/"Online Registration" to scope the recent set to actual registrations instead of every new record. |
| `TIER_HIGH_MIN` / `TIER_MEDIUM_MIN` | 70 / 45 | Score cutoffs for the confidence tiers. |
| `PHONE_FUZZY_MIN` / `EMAIL_FUZZY_MIN` | 0.80 / 0.82 | Minimum similarity ratio for a phone/email typo to earn partial credit instead of being treated as unrelated. |
| `FAMILY_CONTACT_NAME_MIN` | 0.5 | Minimum first-name similarity for a same-household pair's shared contact info to count as duplicate evidence (see "Household handling"). |
| `HOUSEHOLD_GAP_LAST_NAME_MIN` / `HOUSEHOLD_GAP_MIN_SIGNALS` | 0.85 / 2 | Thresholds for flagging a not-yet-linked household pair (see "Household handling"). |
| `NICKNAME_CLUSTERS` | — | A general-English common-nickname list (not church-specific). Extend it as real misses turn up. |

## Known limitations

- **Blocking still needs an exact-ish signal somewhere.** If a person's name is *also* completely unrelated (not a nickname/typo variant) and the only shared signal is a fat-fingered phone or email, the pair still won't be pulled into the candidate pool — SQL-side blocking requires an exact phone/email-local-part match or one of the documented DOB near-miss patterns, not a fully fuzzy one. Widening this further would require a much looser SQL filter with real risk of candidate-volume blowup and false positives on a large `People` table.
- **The household-link-gap flag depends on `FamilyId`.** It only fires when there's no shared household link at all *and* at least two independent corroborating signals — a genuinely different pair that only shares one weak signal won't be flagged either way.
- **Human review is still required.** This is a heuristic composite score, not a certainty. It's designed to shrink a large `People` table down to a short, ranked, explainable list for a person to check — not to make the merge/don't-merge decision itself.

## A SQL performance note (relevant if you extend the blocking query)

The candidate-pair query is written as a `UNION` of several separate joins — one per signal (last name, full email, email local-part, phone, three DOB near-miss shapes) — each on exactly one equality key, rather than a single join with a big `OR` across all of them. This isn't stylistic: SQL Server generally can't plan an `OR`-across-unrelated-columns join as an efficient hash/index join, even when every column involved is precomputed, because there's no single shared key to build a hash table on. It tends to fall back to a nested-loop scan of the whole candidate set per recent row, evaluating the `OR` as a residual filter — which is still `O(recent × candidates)` even with cheap per-comparison cost. Decomposing into single-key `UNION`ed joins lets the optimizer plan each branch properly; `UNION` (not `UNION ALL`) then dedupes any pair caught by more than one signal. If you add a new blocking signal, follow the same pattern rather than adding another `OR` clause to an existing join.

## Portability — how church-specific is this?

Not very. Unlike most of this repo (attendance dashboards, roster reports), this script has no hardcoded church Program/Division/OrgIds, campus names, or staff lists anywhere. Everything it touches — `dbo.People`, `dbo.Duplicate`, and standard columns like `EmailAddress`, `CellPhone`, `FamilyId`, `BirthYear` — is core TouchPoint schema, identical across every TouchPoint installation. `NICKNAME_CLUSTERS` is a general-English name list, and every config constant is a generic tunable, not a fact specific to any one church's setup. That makes this one of the more shareable scripts in this repo as-is — another TouchPoint church could deploy it with no code changes beyond confirming their own `lookup.Origin` values if they want registration-only scoping.

(This script was renamed 2026-08-27 from an `RPC_`-prefixed name, this repo's convention for RockPointe-specific deployed scripts, to the generic `TP_` prefix, since it has no RockPointe-specific facts baked in.)

## Architecture — GET shell + AJAX scan (2026-09-01)

The original version ran the entire pipeline (SQL blocking query, Python fuzzy scoring, HTML render) synchronously on one GET request — with a 120-day/500-row window that's slow enough that the browser sat on a blank tab for the whole run. Restructured as a single-file mini-app, the same pattern as this repo's `roll-sheet-report/TPxi_RollSheet.py`:

- **GET** renders an HTML shell instantly — header, legend, a lookback-days input, Quick/Full scan buttons, empty stat tiles and results area. No heavy query runs here.
- A cheap `COUNT(*)` fires via AJAX on page load to fill in the "recently created" stat tile fast, independent of the expensive fuzzy-match pass.
- **Quick scan** (last 30 days, capped at 150 rows) and **Full scan** (the configured lookback/500-row cap, or the Days field's value) POST to the same script and run the real pipeline server-side, returning JSON (counts + a pre-rendered HTML fragment) that JS injects into the page without a reload.

The scoring/blocking logic itself is unchanged — see "How it works" above. Only the driver changed shape, from "always print the full page" to "print a shell on GET, print JSON on POST."

## Deploy

`Admin > Advanced > Special Content > Python Scripts > +New`, script name `TP_DuplicatePersonFinder`, paste in `TP_DuplicatePersonFinder.py`. Access via `/PyScriptForm/TP_DuplicatePersonFinder` (the shell auto-redirects there from `/PyScript/` if visited directly, since AJAX POSTs need the Form path — same reason `TPxi_RollSheet.py` does this). No email is sent; nothing is written.

## Live validation status

The original synchronous version was live-tested against RockPointe's TouchPoint instance 2026-08-26/27, judged a clear improvement by the admin who requested it. The default 120-day window (500 recent People, capped) completed without timing out and correctly surfaced nickname matches, fat-fingered last names, case-formatting duplicates, and pairs caught mainly through email+phone+DOB triangulation despite a weak name match — while excluding same-household family members and routing not-yet-linked household pairs (e.g. siblings) into their own section instead of the duplicate list.

The GET-shell/AJAX-scan restructure (above) has been verified locally against a mocked TouchPoint runtime (GET renders instantly with no query calls; `count`, Quick scan, and Full scan POST actions all return correct JSON; nickname/household scoring behavior unchanged) but **not yet exercised against RPC's live instance**. Still open:
- [ ] Confirm the shell loads instantly and both Quick/Full scan buttons return real results against live RPC data.
- [ ] Confirm `lookup.Origin` values and set `ORIGIN_FILTER_IDS` for registration-only scoping.
- [ ] Get the ministries who originally flagged this problem to sanity-check a run's output.

### Development history

For anyone tracing why the code looks the way it does — several rounds of live testing found and fixed real issues, in order:

1. **Fat-fingered contact info wasn't credited.** Email/phone/DOB started as exact-match-only; extended to fuzzy scoring with partial credit for near-misses (see "Date-of-birth handling" above). Also caught: phone wasn't wired into SQL blocking at all in the first version.
2. **The query could hang / 504.** Two separate problems, both described in "A SQL performance note" above: first, the "recent" filter lived outside the join instead of inside its own CTE; second, even after fixing that, a single `OR`-heavy join condition couldn't get an efficient query plan and needed decomposing into `UNION`ed single-key joins.
3. **Household false positives.** Different family members sharing a phone/email were scoring as high-confidence duplicates. Fixed via the two-part household handling described above (score dampening for already-linked households, a separate flag for not-yet-linked ones).
4. **Inconsistent score display** (`100` vs `75.0`). Caused by `round()` returning a `float` under the Python runtime TouchPoint scripts run on; fixed by forcing `int(round(score))`.
5. **A dampened DOB match was silently hidden.** `signal_badges()` originally returned early for an already-linked-household pair, showing only "Same household" + a generic "shared contact" note — which also hid a real, still-scored "DOB match" badge on any such pair, since DOB is never dampened. Fixed to always show DOB's real signal regardless of the email/phone dampening state.
6. **Visual design pass.** First version used solid, saturated, hue-only badge colors (a duplicate-detection report that looked, per direct feedback, "a little Windows 95") with no legend explaining what any of it meant. Redone per "Visual design" above: colorblind-safe palette with fill-style redundancy, a collapsible legend, and a cleaner card/table layout.
