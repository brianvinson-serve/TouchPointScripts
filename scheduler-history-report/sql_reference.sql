-- sql_reference.sql
-- Read-only. Standalone discovery/spot-check queries for the Scheduler
-- shift-history feature (RPC_SchedulerHistoryReport.py in this folder).
-- Not required at runtime -- the Python script runs its own parameterized
-- version of the second query below. Use these to live-validate before
-- trusting the report; see "NOT YET RPC-CONFIRMED" in the .py docstring.

-- 1. Confirm the TimeSlot* tables exist in RPC's database at all, and get
--    a row-count sanity check. If any of these error with "Invalid object
--    name," the table set differs on RPC's TouchPoint version and the
--    report needs rework before use.
SELECT 'TimeSlots' AS TableName, COUNT(*) AS ApproxRowCount FROM TimeSlots
UNION ALL SELECT 'TimeSlotTeams', COUNT(*) FROM TimeSlotTeams
UNION ALL SELECT 'TimeSlotTeamSubGroups', COUNT(*) FROM TimeSlotTeamSubGroups
UNION ALL SELECT 'TimeSlotMeetings', COUNT(*) FROM TimeSlotMeetings
UNION ALL SELECT 'TimeSlotMeetingTeams', COUNT(*) FROM TimeSlotMeetingTeams
UNION ALL SELECT 'TimeSlotMeetingTeamSubGroups', COUNT(*) FROM TimeSlotMeetingTeamSubGroups
UNION ALL SELECT 'TimeSlotMeetingTeamSubGroupVolunteers', COUNT(*) FROM TimeSlotMeetingTeamSubGroupVolunteers
UNION ALL SELECT 'TimeSlotMeetingVolunteers', COUNT(*) FROM TimeSlotMeetingVolunteers;

-- 2. Find the OrganizationId for a Scheduler involvement by name (e.g.
--    Marlene's "AD: PS Staff on Campus 2026"), and confirm it actually has
--    TimeSlot data (i.e. it's a Scheduler involvement, not a plain org).
SELECT o.OrganizationId, o.OrganizationName, o.OrganizationTypeId,
       COUNT(DISTINCT tsm.TimeSlotMeetingId) AS ShiftCount
FROM Organizations o
JOIN Meetings m ON m.OrganizationId = o.OrganizationId
JOIN TimeSlotMeetings tsm ON tsm.MeetingId = m.MeetingId
WHERE o.OrganizationName LIKE '%Staff on Campus%'
GROUP BY o.OrganizationId, o.OrganizationName, o.OrganizationTypeId;

-- 3. Once the OrganizationId is known (replace @OrgId below), spot-check a
--    handful of shifts spanning today's date -- one that still shows in the
--    live Scheduler tab (future) and one that has already passed (e.g.
--    today's earlier 9am-noon shift vs. the current noon-3pm shift) -- and
--    compare the names returned here against what the Scheduler tab and
--    the person's own knowledge say. This is the same query the Python
--    script runs, unparameterized for ad-hoc use in the SQL Scripts editor.
DECLARE @OrgId INT = 0  -- fill in from query 2 above
DECLARE @StartDate DATE = '2026-09-20'
DECLARE @EndDateExclusive DATE = '2026-09-26'

;WITH
LatestVolunteers AS (
    SELECT
        TimeSlotMeetingId,
        PeopleId,
        MAX(TimeSlotMeetingVolunteerId) AS TimeSlotMeetingVolunteerId
    FROM TimeSlotMeetingVolunteers
    GROUP BY TimeSlotMeetingId, PeopleId
)
SELECT
    tsm.MeetingDateTime AS ShiftStart,
    CASE WHEN mt.Name IS NULL THEN tsmt.TeamName ELSE mt.Name END AS TeamOrSlot,
    p.PeopleId,
    p.Name,
    tsmv.VolunteerOption
FROM TimeSlotMeetingTeams tsmt
JOIN TimeSlotMeetings tsm ON tsm.TimeSlotMeetingId = tsmt.TimeSlotMeetingId
JOIN Meetings m ON m.MeetingId = tsm.MeetingId
LEFT JOIN TimeSlotMeetingTeamSubGroups tssg
    ON tssg.TimeSlotMeetingTeamId = tsmt.TimeSlotMeetingTeamId
   AND (tssg.IsDeleted = 'False' OR tssg.IsDeleted IS NULL)
LEFT JOIN TimeSlotMeetingTeamSubGroupVolunteers tsGrpVol
    ON (tsGrpVol.IsActive <> 0
        AND tsGrpVol.TimeSlotMeetingTeamId = tsmt.TimeSlotMeetingTeamId
        AND tsGrpVol.TimeSlotMeetingTeamSubGroupId IS NULL)
    OR (tsGrpVol.IsActive <> 0
        AND tsGrpVol.TimeSlotMeetingTeamSubGroupId = tssg.TimeSlotMeetingTeamSubGroupId
        AND tsGrpVol.TimeSlotMeetingTeamSubGroupId IS NOT NULL)
LEFT JOIN LatestVolunteers lv
    ON lv.TimeSlotMeetingId = tsmt.TimeSlotMeetingId
   AND lv.PeopleId = tsGrpVol.PeopleId
LEFT JOIN TimeSlotMeetingVolunteers tsmv
    ON tsmv.TimeSlotMeetingVolunteerId = lv.TimeSlotMeetingVolunteerId
LEFT JOIN MemberTags mt ON mt.Id = tssg.MemberTagId AND mt.OrgId = @OrgId
LEFT JOIN People p ON p.PeopleId = tsGrpVol.PeopleId
WHERE m.OrganizationId = @OrgId
  AND tsm.MeetingDateTime >= @StartDate
  AND tsm.MeetingDateTime < @EndDateExclusive
ORDER BY tsm.MeetingDateTime, TeamOrSlot, p.Name;

-- 4. "Someone signed up but the report shows the slot open" diagnostics.
--    Added 2026-11-02 for Dawn's new MOC + welcome desk involvement (4176),
--    where November sign-ups weren't showing. Query 3 only reads people from
--    TimeSlotMeetingTeamSubGroupVolunteers (team/subgroup assignments), with
--    IsActive/IsDeleted filters. Each query below checks one way a real
--    sign-up could fall outside that. Run all three for the same window;
--    whichever returns rows is the cause. Not yet run live.
DECLARE @DiagOrgId INT = 4176
DECLARE @DiagStart DATE = '2026-11-08'          -- week Dawn screenshotted
DECLARE @DiagEndExclusive DATE = '2026-11-15'

-- 4a. Sign-ups recorded on the time slot itself (TimeSlotMeetingVolunteers)
--     with no matching active team/subgroup assignment. Query 3 never shows
--     these people. If this has rows, the report needs to read this table too.
SELECT tsm.MeetingDateTime AS ShiftStart, tsmv.TimeSlotMeetingVolunteerId,
       tsmv.PeopleId, p.Name, tsmv.VolunteerOption
FROM TimeSlotMeetingVolunteers tsmv
JOIN TimeSlotMeetings tsm ON tsm.TimeSlotMeetingId = tsmv.TimeSlotMeetingId
JOIN Meetings m ON m.MeetingId = tsm.MeetingId
LEFT JOIN People p ON p.PeopleId = tsmv.PeopleId
WHERE m.OrganizationId = @DiagOrgId
  AND tsm.MeetingDateTime >= @DiagStart
  AND tsm.MeetingDateTime < @DiagEndExclusive
  AND NOT EXISTS (
      SELECT 1
      FROM TimeSlotMeetingTeams t
      JOIN TimeSlotMeetingTeamSubGroupVolunteers v
        ON v.TimeSlotMeetingTeamId = t.TimeSlotMeetingTeamId
        OR v.TimeSlotMeetingTeamSubGroupId IN (
            SELECT sg.TimeSlotMeetingTeamSubGroupId
            FROM TimeSlotMeetingTeamSubGroups sg
            WHERE sg.TimeSlotMeetingTeamId = t.TimeSlotMeetingTeamId)
      WHERE t.TimeSlotMeetingId = tsmv.TimeSlotMeetingId
        AND v.PeopleId = tsmv.PeopleId
        AND v.IsActive <> 0)
ORDER BY tsm.MeetingDateTime, p.Name;

-- 4b. Time slots with no team rows at all. Query 3 starts FROM
--     TimeSlotMeetingTeams, so these slots vanish from the report entirely
--     (the "slot not showing" half of Dawn's note).
SELECT tsm.TimeSlotMeetingId, tsm.MeetingDateTime AS ShiftStart,
       (SELECT COUNT(*) FROM TimeSlotMeetingVolunteers x
        WHERE x.TimeSlotMeetingId = tsm.TimeSlotMeetingId) AS DirectVolunteerRows
FROM TimeSlotMeetings tsm
JOIN Meetings m ON m.MeetingId = tsm.MeetingId
WHERE m.OrganizationId = @DiagOrgId
  AND tsm.MeetingDateTime >= @DiagStart
  AND tsm.MeetingDateTime < @DiagEndExclusive
  AND NOT EXISTS (SELECT 1 FROM TimeSlotMeetingTeams t
                  WHERE t.TimeSlotMeetingId = tsm.TimeSlotMeetingId)
ORDER BY tsm.MeetingDateTime;

-- 4c. Full unfiltered team/subgroup/volunteer shape for the week: no
--     IsActive or IsDeleted filters, so inactive assignments and deleted
--     subgroups show up (look for IsActive = 0 or IsDeleted = 1 rows on a
--     slot Dawn says is filled). Also shows how team/subgroup names are
--     set up on the new involvement (e.g. "MOC" vs "Welcome Desk" with no
--     time in the name, which the Board would merge per day).
SELECT tsm.MeetingDateTime AS ShiftStart, tsmt.TimeSlotMeetingTeamId, tsmt.TeamName,
       tssg.TimeSlotMeetingTeamSubGroupId, tssg.IsDeleted AS SubGroupDeleted,
       mt.Name AS SubGroupName, v.PeopleId, p.Name, v.IsActive
FROM TimeSlotMeetingTeams tsmt
JOIN TimeSlotMeetings tsm ON tsm.TimeSlotMeetingId = tsmt.TimeSlotMeetingId
JOIN Meetings m ON m.MeetingId = tsm.MeetingId
LEFT JOIN TimeSlotMeetingTeamSubGroups tssg
    ON tssg.TimeSlotMeetingTeamId = tsmt.TimeSlotMeetingTeamId
LEFT JOIN MemberTags mt ON mt.Id = tssg.MemberTagId
LEFT JOIN TimeSlotMeetingTeamSubGroupVolunteers v
    ON v.TimeSlotMeetingTeamId = tsmt.TimeSlotMeetingTeamId
    OR v.TimeSlotMeetingTeamSubGroupId = tssg.TimeSlotMeetingTeamSubGroupId
LEFT JOIN People p ON p.PeopleId = v.PeopleId
WHERE m.OrganizationId = @DiagOrgId
  AND tsm.MeetingDateTime >= @DiagStart
  AND tsm.MeetingDateTime < @DiagEndExclusive
ORDER BY tsm.MeetingDateTime, tsmt.TeamName, SubGroupName, p.Name;
