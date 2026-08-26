# Ministry Roster Report

Printable Leader/Member roster + weekly attendance grid for any active involvement in a configured set of ministry divisions — currently the two Adult Discipleship (AD) divisions that carry ReNew ("AD ReNew" and "AD Classes/Meetings/Groups"), designed to extend to other ministries (e.g. Marriage Ministry classes) as their division IDs get confirmed.

## What it does

`AD_ReNewRosterReport.py` (TouchPoint Special Content Python Script, read-only) has two views, both server-rendered by the same script depending on whether `?OrgId=` is present in the URL:

**No involvement chosen** — a picker: every active (`OrganizationStatusId = 30`) involvement in the divisions listed in `DIVISION_FILTERS`, grouped by division, in a dropdown with an **Apply** button. Choosing one reruns the script with `?OrgId=<id>`.

**Involvement chosen** — the roster for that org. Per person:
- Name, Gender, Member Type (**Leader or Member only** — Coach/InActive/Prospect/Volunteer and any unmapped/stray `MemberTypeId` are excluded entirely), sorted **Leaders first, then Members** within each gender section
- One attendance column per meeting date the org has actually held (checkmark if present; canceled / did-not-meet meetings are excluded from the grid)
- A **Total** column on the right summing meetings attended
- Phone (`model.FmtPhone`), Email (`EmailAddress`, falling back to `EmailAddress2`)

Output is a print-styled HTML page with a section per gender (Men, then Women, then "Unspecified Gender" only if anyone has unset/Unknown `GenderId` — nobody is silently dropped). CSS forces landscape orientation and a page break between sections, so printing (Ctrl/Cmd+P) produces one sheet per gender. A "Choose a different involvement" link (hidden when printing) goes back to the picker.

## Extending to another ministry

The picker's involvement list is driven entirely by `DIVISION_FILTERS` at the top of `AD_ReNewRosterReport.py` — a list of `(DivisionId, "label")` pairs. To add a ministry (e.g. Marriage Ministry classes, raised 2026-08-26 as a likely next one):

1. Find the division: `SELECT Id, Name, ProgId FROM dbo.Division WHERE Name LIKE '%marriage%'` (adjust the search term for whichever ministry).
2. Add a row: `(<DivisionId>, "Marriage Ministry (MM): MM Classes"),` to `DIVISION_FILTERS`.
3. Re-deploy (see below). No other code changes needed — the picker, grouping, and roster logic are all generic.

If a future ministry needs something structurally different (e.g. split by campus instead of gender, a non-weekly meeting cadence, additional member types beyond Leader/Member), that's a real code change, not just a config addition — flag it rather than assuming this script covers it as-is.

## Confirmed for ReNew Fall 2026

- `OrganizationId = 3906`, `OrganizationName = "ReNew Fall 2026"`, `OrganizationStatusId = 30` (Active), `OrganizationTypeId = 201`.
- Division 126 "AD ReNew" (also linked in Division 31 "AD Classes/Meetings/Groups"), Program 1119 "Adult Discipleship" (AD).
- Meets weekly on **Mondays**. Confirmed live 2026-08-26: two meetings held so far (8/17, 8/24).
- `lookup.Gender`: 1 = Male, 2 = Female, 0 = Unknown.
- `lookup.MemberType`: 140 = Leader, 220 = Member (the only two shown on the roster).

See `DB_REFERENCE.md` for the full write-up (Program 1119 addition, `Meetings.Canceled`/`Meetings.DidNotMeet` filter, ReNew org family discovered via name search).

## Deploy

`Admin > Advanced > Special Content > Python Scripts > +New`, script name `AD_ReNewRosterReport`, paste in the file contents. **Access via `/PyScript/AD_ReNewRosterReport`**, not the Special Content admin "run" preview — the picker's Apply button submits a GET form back to the current URL, and the admin preview's own chrome would otherwise bleed into a print job. No email is sent.

## Status

Built 2026-08-26. Round 1 (single hardcoded org, no member-type filter) was live-tested; that run surfaced a date-format bug (RPC's `q.QuerySql` returns `CAST(... AS DATE)` as `M/D/YYYY 12:00:00 AM`, not ISO) fixed via the same `normalize_date()` pattern used in `student-contact-export/SM_StudentContactExport.py`.

Round 2 (this version) adds the Leader/Member-only filter + Leader-first sort, and replaces the hardcoded org with the division-driven picker. Syntax-checked and smoke-tested locally with mocked `q`/`model` objects covering: the picker view's grouped `<optgroup>` rendering, the roster view's generated SQL (asserted to contain both the `MemberTypeId IN (140, 220)` filter and the Leader-first `CASE` sort), and the previously-fixed date formatting. **Not yet run live against RPC TouchPoint** — needs a live pass to confirm:

- The picker actually lists the expected active involvements and the Apply button's GET round-trip works through TouchPoint's `/PyScript/` route.
- `Meetings.Canceled` / `Meetings.DidNotMeet` column behavior generalized across whichever org gets picked (previously only checked conceptually against OrgId 3906).
- Whether `OrganizationMembers` for these orgs contains anyone who should be excluded beyond the Leader/Member filter (e.g. dropped/inactive members still marked 140/220) — not checked yet.
