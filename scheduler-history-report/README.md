# Scheduler Coverage Board

Read-only TouchPoint report answering Marlene's request: the built-in
Scheduler tab (shift sign-up grid inside a Scheduler-type Involvement, e.g.
"AD: PS Staff on Campus 2026") only shows names for shifts that haven't
happened yet, and even for upcoming shifts it's a flat grid of identical
small cards with no visual hierarchy -- an unfilled shift looks like any
other day unless you're staring right at it. TouchPoint support told her
this needs a custom script; this is that script.

Two views of the same data, switched with the tabs at the top of the page:

- **Coverage board** (`?View=Board`, the default) -- a week grid, days as
  columns, shift slots as rows. This is Marlene's view: "is everything
  covered, and who do I need to chase down." An unfilled shift renders as
  a solid, loud red block (labeled GAP if it's still upcoming, NOT COVERED
  if the date has passed) -- absence is drawn, not left as a quiet blank
  cell. Filled shifts stay deliberately quiet (name only, no icon), so the
  one thing announcing itself on the page is the thing that needs
  attention.
- **My shifts** (`?View=Mine&PersonName=...`) -- Debbie's view: a plain
  chronological list of one person's shifts, past and upcoming, found by
  typing a name rather than needing to know a PeopleId. Past shifts are
  visually faded rather than removed, so "did I cover it" stays answerable
  after the fact.

This folder also has `WidgetTodaysCoveragePython.py` -- a small, separate
script, hardcoded to both Staff on Campus orgs (`CC` 3951, `PS` 3726),
showing just today's shifts side by side with no controls (no OrgId
picker, no date range). It's the "quick glance" companion to the Board
above, not a replacement -- each org block links out to that org's full
Board for more detail. Named `WidgetXxxPython` rather than this folder's
usual `RPC_` prefix to match RPC's existing Special Content Widget naming
convention (it's meant to sit alongside those, not read as a standalone
report). See that file's own docstring for specifics.

## Note to pass along to Marlene

Both Scheduler involvements checked so far have the same underlying data
quirk: whoever sets up each week's shifts isn't typing the shift name
exactly the same way every time.

- `AD: PS Staff on Campus 2026`: `"PS MOC 9a - noon"` vs. `"PS MOC 9a-noon"`
  (extra spaces around the dash).
- `AD: CC Staff on Campus 2026`: `"CC MOC noon-3p"` vs. `"CC MOC noon-3P"`
  (capital vs. lowercase P).

This report now treats those as the same shift automatically, so it's not
blocking anything here. But it's worth asking whoever builds each week's
Scheduler shifts to copy the existing shift name forward instead of
retyping it, for two reasons: it's the kind of inconsistency that could
also affect sorting/grouping/search inside TouchPoint's own native
Scheduler screen (unconfirmed either way -- this report doesn't touch that
UI -- but it's the same underlying shift-name field TouchPoint's screen
reads too), and if it keeps happening on new shift types this report
hasn't seen yet, a difference bigger than spacing/capitalization (a typo,
an abbreviation swap) would still slip through as two separate rows here.

## Design background

Before building, three concept directions were sketched against a design
brief (audience split, jobs-to-be-done, data shape, TouchPoint embedding
constraints) using the `frontend-design` plugin skill (Anthropic,
`claude-plugins-official` marketplace):

1. **The Board** (built here) -- the coverage-grid concept above.
2. **The Stub** -- a phone-native "ticket stub" personal view for Debbie,
   with a perforated divider between the time and the shift that visually
   "tears off" once the shift closes. Higher delight, not built -- nobody
   had asked for a phone-first experience specifically, and it's a
   reasonable follow-up if Debbie's actually checking this mid-shift.
3. **Now/Next** -- an unattended shared-screen kiosk view ("who's on
   right now / up next," oversized type, no chrome). Not built -- solves a
   problem nobody raised (there's no shared screen to put it on yet).

The Board was chosen because it directly answers Marlene's stated ask
(see past coverage) and, per its own logic, gives "My shifts" essentially
for free as a filtered slice of the same query -- covering Debbie's need
without a second build.

## Why this is possible

The Scheduler feature is backed by its own table set --
`TimeSlots` / `TimeSlotTeams` / `TimeSlotTeamSubGroups` / `TimeSlotMeetings`
/ `TimeSlotMeetingTeams` / `TimeSlotMeetingTeamSubGroups` /
`TimeSlotMeetingTeamSubGroupVolunteers` / `TimeSlotMeetingVolunteers` --
separate from `Meetings`/`Attend`. Sign-up rows aren't deleted once a
shift's date passes; the built-in Scheduler tab just filters to
`ShiftDateTime > GETDATE()`. This report runs the same underlying join
without that filter.

## Source

Table names and join shape adapted from Ben Swaby's (TPxi Software)
`TPxi_SchedulerReport.py` in the community repo
[bswaby/Touchpoint](https://github.com/bswaby/Touchpoint) (`TPxi/Scheduler
Report`) -- per this repo's own guidance to prefer adapting an existing
community tool. That script is a much larger forward-looking "who's signed
up" email report with fill-percentage tracking and Morning Batch delivery;
this report keeps only what's needed to answer "who was on this shift,
including past ones."

## Live validation status

This table set never appeared in any of RPC's own schema-discovery exports
(see `DB_REFERENCE.md`) before this report -- confirmed live 2026-09-24/27
against real data:

- The `TimeSlot*` table set exists on RPC's instance and the join to
  `Organizations`/`Meetings` works (`sql_reference.sql` query 2 returned
  real `ShiftCount`s for both `AD: PS Staff on Campus 2026` (`OrgId 3726`,
  396 shifts) and `AD: CC Staff on Campus 2026` (`OrgId 3951`, 240 shifts)).
- The full report renders against `OrgId 3726` with plausible real names
  (Leea Plank, Jennifer Schmitz, Leah McBain, Debbie Avinger) in the right
  shift slots.
- Two runtime bugs surfaced and were fixed during this validation, both
  the same root cause -- an assumed object shape instead of a verified
  one: `model.GetOrganization()` returns `.name` (lowercase), not
  `.OrganizationName`; and `q.QuerySql`'s `DateTime` columns come back as
  .NET `DateTime` objects with no `.strftime`, requiring the
  `to_python_datetime()` stringify-and-reparse step now in the script.
- A data quirk also surfaced on both orgs checked so far, in two different
  forms: `AD: PS Staff on Campus 2026`'s shift names aren't spelled
  consistently week to week (`"PS MOC 9a - noon"` vs. `"PS MOC 9a-noon"`,
  a whitespace difference), and `AD: CC Staff on Campus 2026`'s do the same
  thing with case (`"CC MOC noon-3p"` vs. `"CC MOC noon-3P"`).
  `canonical_team_key()` now groups board rows case- and
  whitespace-insensitively (picking whichever raw spelling actually
  appeared most often as the row's display label, via
  `normalize_team_label()`) so the same recurring shift doesn't fragment
  into multiple board rows with false gaps. Confirmed live 2026-09-27. See
  "Note to pass along to Marlene" above -- worth flagging to whoever builds
  these shifts each week, since it's plausibly affecting more than just
  this report.

**Still open:** nobody has yet compared this report's output side-by-side
against the live Scheduler tab for a specific date/time to confirm the
*people* shown are exactly right (as opposed to plausible) -- do that
before treating a "GAP"/"NOT COVERED" cell as ground truth for a real
staffing conversation. Once done, add a short "Scheduler (shift sign-up)"
section to `DB_REFERENCE.md` with the confirmed table/column names and
`OrgId 3726`/`3951` as worked examples, per this repo's normal practice.

## Deployment

Admin > Advanced > Special Content > Python Scripts > + New
  Name: `RPC_SchedulerHistoryReport`
  Paste `RPC_SchedulerHistoryReport.py`, Save.

Then visit:

    /PyScript/RPC_SchedulerHistoryReport?OrgId=1234

`OrgId` is the Scheduler involvement's `OrganizationId`. `StartDate`/
`EndDate` (optional, `YYYY-MM-DD`) override the default window, which is
the current calendar week (Sunday-Saturday). The page includes a small
form, tabs for the two views, and previous/next-period links so staff
don't need to edit the URL by hand.

Not wired into the Blue Toolbar (`CustomReports`) yet since only one
Scheduler involvement was named in the original request -- add a
`CustomReports` entry (see other reports in this repo for the XML pattern)
if Marlene will use this often enough to want a menu link instead of a
bookmarked URL.

## Files

- `RPC_SchedulerHistoryReport.py` -- the deployable TouchPoint Python
  Script (Board + My shifts).
- `WidgetTodaysCoveragePython.py` -- the deployable TouchPoint Python
  Script for the hardcoded, today-only, two-org widget (named per RPC's
  Widget convention, not this folder's usual `RPC_` prefix).
- `sql_reference.sql` -- standalone SQL to (1) confirm the TimeSlot* tables
  exist on RPC's instance, (2) find a Scheduler involvement's
  `OrganizationId` by name, and (3) run the same query the Python script
  runs, for ad-hoc spot-checking in the SQL Scripts editor. Not required
  at runtime.

## Known limitations

- The `OrgId` dropdown lists any *active* involvement with at least one
  `TimeSlotMeetings` row -- confirmed live to include both real Scheduler
  involvements (`3726`, `3951`). An inactive Scheduler involvement, or one
  whose only shifts fall outside whatever window SQL Server scans
  cheaply, wouldn't appear; the "or enter an OrganizationId" fallback
  field covers that case.
- No email/Morning Batch delivery -- this is a live-browsed report, not a
  scheduled digest. Marlene's ask was to *see* past shifts on demand, not
  receive them proactively; add that later if wanted.
- The Coverage board groups rows by a case- and whitespace-blind key
  (`canonical_team_key()`) -- confirmed necessary live on two different
  orgs, each with a different variation (PS: whitespace, CC: case). This
  still only fixes *cosmetic* variation; a genuinely different name for
  what's meant to be the same shift (a typo, an abbreviation swap, e.g.
  "MOC" vs. "Man on Campus" on the same slot) would still fragment into
  two rows and needs a human to notice and fix the naming at the
  TouchPoint config level, not this script.
- Setting a `StartDate`/`EndDate` wider than about two weeks makes the
  board's day-columns wide enough to need horizontal scrolling (it's
  wrapped in a scrolling container so it won't break the page, just won't
  all be visible at once) -- the grid is designed around a one-week glance,
  not a month-at-a-time view.
- "My shifts" matches by substring against first-name-or-full-name, case
  insensitive, scoped to whoever actually has a shift in the selected date
  range -- it can't find someone with zero shifts in that window, and two
  people matching the same search term (e.g. two "Amy"s) require picking
  from a short disambiguation list rather than it guessing.
- `VolunteerOption` (shown in parens after a name, when set) is a Scheduler
  concept from the source script (e.g. a person choosing a specific option
  within a time slot) that hasn't been seen in any RPC Scheduler
  involvement yet -- harmless to leave in, but unverified whether RPC uses
  it.
