# FTV Report Review Process

For Marlene, Brenda, Virginia — and anyone else at RPC maintaining a TouchPoint report that needs weekly hand-editing.

## Why this exists

The FTV report pulls new-visitor connect cards, Children's/Student Ministry new-record adds, and prayer requests for Central and Parker Square each week. It still takes real editing before it goes out. Brenda's list of what she corrects breaks into two different problems: real bugs in the report's query logic, and gaps in what gets entered into TouchPoint at check-in that no report can fix after the fact. Keeping those separate is the point of this doc.

## Weekly review checklist

| What you see | Why it happens | What to do |
|---|---|---|
| Address, gender, birthdate, or parent info missing | Not entered at check-in | Fill in by hand — can't be automated |
| A visitor never shows up at all, on either campus | Their record has no campus set | Check TouchPoint directly if you know a card came in but nobody shows |
| A volunteer shows up as a "new kid/student" | Report doesn't yet distinguish volunteer involvements from classroom involvements | **Needs more digging** — not yet fixed |
| Someone shows up who only registered for an event, hasn't attended | Registration and attendance aren't the same signal, report treats them alike | **Needs more digging** — not yet fixed |
| No birthdate/age on file, usually students | Not entered at check-in; exact effect on the report unconfirmed | **Needs more digging** — ask what "doesn't pull" looks like when this happens |
| A couple shows up as two separate lines | A task gets created for each adult, one per spouse — the text often differs per person (each names themself), not just a copy-pasted duplicate | **Fixed, confirmed live 2026-09-28** |
| Same student shows up in both Connect Cards and Student Ministry | Their FTV task and their new-record add both trigger separately | **Fixed, confirmed live 2026-09-25** — if a student is only in Connect Cards and not also in Student Ministry, that's this fix working, not something missing |
| An existing person (not a new record) shows up in Connect Cards only, not in Student Ministry, even though they genuinely started attending | Student Ministry only catches brand-new People records; an existing record's first SM attendance has to be a manually-tagged FTV task instead | **Working as intended** — not a bug |
| Ordered-list numbers (1, 2, 3...) missing when viewing the live report in a browser, but present when pasted into an email | Under investigation — likely a rendering difference, not a data problem | **Needs more info** — a screenshot of both would help |

## Status

- **Fixed, confirmed live 2026-09-25 and 2026-09-28:** prayer request duplicates, couple duplicate rows (widened 2026-09-28 after the first pass missed cases where each spouse's task has different wording), connect-card/student-ministry overlap
- **Needs live investigation:** volunteer-vs-new-kid filter, registration-vs-attendance, missing-DOB effect on pulling students, missing list numbering in the browser view
- **Not fixable in the script:** missing address/gender/DOB/parent info — that's a check-in data-entry gap

## When you hit something new

Note the person's PeopleId, what you expected to see, and what actually happened. That's what turns "needs editing" into an actual fix instead of another manual workaround next week.

## General pattern for other report owners

1. Separate "the report is wrong" (a query bug) from "the source data is incomplete" (a check-in gap). Most of the recurring editing is usually the second one, not the first.
2. If someone silently disappears instead of showing up wrong, suspect a filter that requires a field that isn't always filled in (campus, in this case).
3. If the same person shows up twice, check whether TouchPoint itself created two records or two tasks for one event before assuming the query is broken.
4. Bring a concrete example (a PeopleId, what you expected vs. what you got) when asking for a fix.
