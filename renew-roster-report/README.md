# ReNew Roster Report

Printable roster for RockPointe's ReNew involvement (Adult Discipleship / Recovery track), split onto separate Men and Women pages with a weekly attendance grid.

## What it does

`AD_ReNewRosterReport.py` (TouchPoint Special Content Python Script, read-only) reports, per current member of the configured ReNew organization:

- Name, Gender, Member Type
- One attendance column per meeting date the org has actually held (checkmark if present; canceled / did-not-meet meetings are excluded from the grid)
- A **Total** column on the right summing weeks attended
- Phone (`model.FmtPhone`), Email (`EmailAddress`, falling back to `EmailAddress2`)

Output is a single print-styled HTML page with a section per gender (Men, then Women, then "Unspecified Gender" only if anyone has unset/Unknown `GenderId` — nobody is silently dropped). CSS forces landscape orientation and a page break between sections, so printing (Ctrl/Cmd+P) produces one sheet per gender.

## Confirmed for Fall 2026

- `OrganizationId = 3906`, `OrganizationName = "ReNew Fall 2026"`, `OrganizationStatusId = 30` (Active), `OrganizationTypeId = 201`.
- Division 126 "AD ReNew" (also linked in Division 31 "AD Classes/Meetings/Groups"), Program 1119 "Adult Discipleship" (AD).
- Meets weekly on **Mondays**. Confirmed live 2026-08-26: two meetings held so far (8/17, 8/24).
- `lookup.Gender`: 1 = Male, 2 = Female, 0 = Unknown.

See `DB_REFERENCE.md` for the full write-up (Program 1119 addition, `Meetings.Canceled`/`Meetings.DidNotMeet` filter, ReNew org family discovered via name search).

## Reuse for a future term

ReNew runs each term under a new `OrganizationId` (e.g. `Renew Fall 25` was 3309/3593, `Renew Spring 26` was 3665). To reuse this script for a new term:

1. Find the new term's org: `SELECT OrganizationId, OrganizationName, OrganizationStatusId FROM dbo.Organizations WHERE OrganizationName LIKE '%renew%' ORDER BY OrganizationName`
2. Update `ORG_ID` and `ORG_LABEL` at the top of `AD_ReNewRosterReport.py`.
3. Re-deploy (see below).

## Deploy

`Admin > Advanced > Special Content > Python Scripts > +New`, script name `AD_ReNewRosterReport`, paste in the file contents. Run directly — renders the HTML report in-browser, no email is sent.

## Status

Built 2026-08-26, one live-test round-trip so far: first live run raised `ValueError: need more than 1 values to unpack` in the date-column-header formatter, because RPC's `q.QuerySql` returns `CAST(... AS DATE)` values as `M/D/YYYY 12:00:00 AM` strings (not ISO `YYYY-MM-DD`) — same gotcha already worked around by `normalize_date()` in `student-contact-export/SM_StudentContactExport.py` and `attendance-dashboard/SM_AttendanceDashboardEmail.py`. Fixed by adopting that same helper here instead of assuming ISO format. Re-verified with syntax check plus mocked smoke tests reproducing the actual `M/D/YYYY` string shape, single-digit month/day, zero-attendance, and unmapped-MemberTypeId cases.

**Needs a fresh live TouchPoint run to confirm the fix**, plus:

- `Meetings.Canceled` / `Meetings.DidNotMeet` column behavior on this specific org (used elsewhere in this repo's `data-dictionary-expander` scripts but not yet exercised against OrgId 3906).
- Whether `OrganizationMembers` for this org contains anyone who should be excluded (e.g. dropped/inactive members) — the current query pulls all current rows with no additional status filter, matching this repo's existing convention (e.g. the Man Up Meal Sign-Up report), but hasn't been checked against ReNew's specific membership hygiene.
