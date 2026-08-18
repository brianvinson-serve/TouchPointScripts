# RPC Children’s Sunday Attendance — Four-Week Validation

Source: `data-dictionary-expander/exports/2026-08-17/RPC_ChildrenFourWeekAttendanceValidation.xlsx`

## Verdict

- Audited production roster: **93 involvements**
- Children/classroom involvements: **78**
- Volunteer involvements: **15**
- Attendance reconciliation differences across all 456 exported rows: **0**
- Excluded from production: the incorrectly linked Student Ministry involvement, auxiliary/PM/event involvements, and ten stale/seasonal reporting-program records with neither a Sunday schedule nor a Sunday meeting during the four-week window.

## Promotion Sunday context

**August 16, 2026 was Promotion Sunday and the start of the new school year.** Children’s Ministry may have cleaned up or recreated involvements for the new year. Therefore:

- Treat August 16 as the start of the current reporting roster and the default beginning of the Fall 2026 reporting period.
- Do not interpret the increase from August 9 to August 16 as ordinary week-over-week growth.
- Do not reject a current involvement merely because it has no attendance before August 16. A valid Sunday schedule and correct reporting-program linkage are sufficient for a newly created involvement.
- Use the July 26–August 9 rows only to validate joins, meeting aggregation, and legacy continuity—not as an apples-to-apples trend baseline for the post-promotion roster.
- The five new Parker Square 8:30 elementary involvements with Sunday schedules remain in the 93-involvement roster despite having no meeting history yet.

## Weekly totals (not roster-comparable across Promotion Sunday)

| Sunday | Children | Volunteers | Combined | Reporting involvements | Missing meeting |
|---|---:|---:|---:|---:|---:|
| 2026-08-16 | 621 | 195 | 816 | 83 | 10 |
| 2026-08-09 | 525 | 55 | 580 | 80 | 13 |
| 2026-08-02 | 496 | 64 | 560 | 80 | 13 |
| 2026-07-26 | 451 | 35 | 486 | 78 | 15 |

## Missing meeting on 2026-08-16

- **Children/Classroom** — `1581` CM: PS 11:15 Toddlers (Walking-24 mo)
- **Children/Classroom** — `1876` CM: CC 10:45 AM 18-24 Months
- **Children/Classroom** — `4106` CM: PS 8:30 2nd Grade
- **Children/Classroom** — `4107` CM: PS 8:30 3rd Grade Boys
- **Children/Classroom** — `4108` CM: PS 8:30 3rd Grade Girls
- **Children/Classroom** — `4109` CM: PS 8:30 4th Grade Boys
- **Children/Classroom** — `4111` CM: PS 8:30 5th Grade Boys
- **Volunteer** — `4021` CM: PS 8:30 Volunteers Elementary 2026-2027
- **Volunteer** — `4026` CM: CC 9:00 Volunteers Welcome Team 2026-2027
- **Volunteer** — `4027` CM: CC 10:45 Volunteers Welcome Team 2026-2027

## Ten stale/seasonal records excluded despite reporting-program links

- **Children/Classroom** — `3633` CM: CC Christmas Eve 2 Year Olds 2025
- **Children/Classroom** — `3634` CM: CC Christmas Eve 3 Year Olds 2025
- **Children/Classroom** — `3631` CM: CC Christmas Eve Newborn/Crawler 2025
- **Children/Classroom** — `3632` CM: CC Christmas Eve Toddlers-24 Months 2025
- **Volunteer** — `2641` CM: All Special Needs Volunteers
- **Volunteer** — `3903` CM: CC Ignite Kids Fall 2026 Volunteers
- **Volunteer** — `1637` CM: CC Preschool Small Group Leaders
- **Volunteer** — `1646` CM: CC Preschool Student Leaders
- **Volunteer** — `4092` CM: PS 8:30 Volunteers Elementary 2026-2027
- **Volunteer** — `1472` CM: Volunteers Encompass

## Production filter

Include an organization only when all conditions hold:

1. `OrganizationStatusId = 30`.
2. Organization name starts with `CM:`.
3. Organization type is `201` (children/classroom) or `207` (volunteer).
4. It is linked through `DivOrg` to Program `1137` or `1138`.
5. It has a Sunday schedule (`OrgSchedule.SchedDay = 0`) **or** an actual Sunday meeting in the operational lookback window.

Explicitly exclude the `SM:` row even though it is incorrectly linked to Program 1138. Keep missing scheduled meetings visible as warnings rather than silently dropping them.
