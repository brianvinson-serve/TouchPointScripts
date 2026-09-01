-- ============================================================
-- SM Sunday Attendance by Gender — 3-Year History (Central + Parker Square)
-- ============================================================
-- Built to pull a larger, longer-range dataset for the Parker Square
-- staffing business case (see BACKLOG.md), on purpose without
-- pre-deciding whether the numbers support the case.
--
-- Over a 3-year window Student Ministry's involvement structure has
-- likely changed (grade-org rollovers, Parker Square's MS/HS Sunday
-- split, possible renaming) — see DB_REFERENCE.md and BACKLOG.md for
-- what's already known to have shifted just in the last year. So this
-- query deliberately does NOT rely on the things that change year to
-- year:
--   - OrganizationStatusId = 30 — 3-year-old orgs are almost certainly
--     inactive/rolled over by now; NOT filtered here.
--   - DivOrg / Division membership — division links reflect the
--     CURRENT schedule model, not necessarily what applied 3 years
--     ago; NOT used here. "Sunday" is instead determined directly from
--     DATEPART(weekday, MeetingDate).
--   - Gender parsed out of the organization name — older or
--     differently-named orgs may not encode gender in the name at
--     all (e.g. before a grade+gender split existed). Gender instead
--     comes from People.GenderId -> lookup.Gender, per person.
--
-- What IS assumed to be stable: the 'SM: CC ' / 'SM: PS ' campus
-- naming prefix. If that changed at some point in the last 3 years,
-- this query will silently under-count — check the raw
-- OrganizationName column in the output for anything that looks like
-- an old naming scheme this prefix wouldn't catch, and widen the LIKE
-- filter if so.
--
-- Output grain is intentionally granular — one row per
-- (date, campus, organization, member type, gender) — with
-- OrganizationName/OrganizationTypeId/OrganizationStatusId/MemberType
-- all exposed raw. Pivot/filter in Excel or the dashboard rather than
-- trusting a single hard-coded classification across 3 years of org
-- changes.
--
-- UNCONFIRMED, verify on first live run:
--   - Meetings.Canceled / Meetings.DidNotMeet: used elsewhere in this
--     repo (data-dictionary-expander, renew-roster-report) but not yet
--     independently confirmed against RPC's live schema. If this
--     script errors with "Invalid column name", remove those two
--     ISNULL(...) = 0 lines from the WHERE clause below.
--   - lookup.Gender.Description values/labels — sanity-check the
--     Gender column in the output looks like actual Male/Female
--     labels, not something unexpected.
--   - Attend.MemberTypeId = 310 (Guest) has been found (2026-08-27
--     D-Group investigation, DB_REFERENCE.md) to be mis-applied to
--     plenty of actually-enrolled people at RPC. Don't drop 310 rows
--     outright when filtering to "students" — eyeball them first.
-- ============================================================

SET DATEFIRST 7  -- Sunday = 1

-- ============================================================
-- CONFIG
-- ============================================================
DECLARE @StartDate DATE = DATEADD(YEAR, -3, CAST(GETDATE() AS DATE))
DECLARE @EndDate   DATE = CAST(GETDATE() AS DATE);

-- ============================================================
WITH Base AS (
    SELECT
        a.PeopleId,
        MeetingDate  = CAST(m.MeetingDate AS DATE),

        -- Sep–Aug ministry year, so a season lines up as one bucket
        -- regardless of calendar-year boundary.
        MinistryYear = CASE
            WHEN MONTH(m.MeetingDate) >= 9
                THEN CAST(YEAR(m.MeetingDate) AS VARCHAR(4)) + '-' + CAST(YEAR(m.MeetingDate) + 1 AS VARCHAR(4))
            ELSE CAST(YEAR(m.MeetingDate) - 1 AS VARCHAR(4)) + '-' + CAST(YEAR(m.MeetingDate) AS VARCHAR(4))
        END,

        Campus = CASE
            WHEN o.OrganizationName LIKE 'SM: CC %' THEN 'Central'
            WHEN o.OrganizationName LIKE 'SM: PS %' THEN 'Parker Square'
        END,

        o.OrganizationId,
        o.OrganizationName,
        o.OrganizationTypeId,
        o.OrganizationStatusId,

        a.MemberTypeId,
        MemberType = mt.Description,

        GenderId = p.GenderId,
        Gender   = g.Description

    FROM dbo.Attend a
    JOIN dbo.Meetings m         ON m.MeetingId = a.MeetingId
    JOIN dbo.Organizations o    ON o.OrganizationId = a.OrganizationId
    JOIN dbo.People p           ON p.PeopleId = a.PeopleId
    LEFT JOIN lookup.Gender g       ON g.Id = p.GenderId
    LEFT JOIN lookup.MemberType mt  ON mt.Id = a.MemberTypeId

    WHERE
        (o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %')
        AND CAST(m.MeetingDate AS DATE) BETWEEN @StartDate AND @EndDate
        AND m.MeetingDate <= GETDATE()                 -- exclude not-yet-occurred meetings
        AND ISNULL(m.Canceled, 0) = 0                  -- UNCONFIRMED column, see header note
        AND ISNULL(m.DidNotMeet, 0) = 0                -- UNCONFIRMED column, see header note
        AND a.AttendanceFlag = 1
        AND ISNULL(a.NoShow, 0) = 0
        AND DATEPART(weekday, m.MeetingDate) = 1       -- Sunday only, independent of Division/OrgSchedule
)
SELECT
    MinistryYear,
    MeetingDate,
    Campus,
    OrganizationId,
    OrganizationName,
    OrganizationTypeId,
    OrganizationStatusId,
    MemberTypeId,
    MemberType,
    GenderId,
    Gender,
    Attendance = COUNT(DISTINCT PeopleId)
FROM Base
GROUP BY
    MinistryYear, MeetingDate, Campus, OrganizationId, OrganizationName,
    OrganizationTypeId, OrganizationStatusId, MemberTypeId, MemberType,
    GenderId, Gender
ORDER BY
    MeetingDate, Campus, OrganizationName, Gender
