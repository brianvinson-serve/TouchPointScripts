/*
RPC Children’s Ministry — four-week Sunday attendance validation
================================================================
Purpose:
  Independently validate the proposed Children’s Ministry Sunday reporting
  boundary and show attendance for each candidate involvement across the last
  four completed Sundays.

Validation approach:
  - Start from active organizations linked to Program 1111 (Children’s
    Ministry) or reporting Programs 1137/1138.
  - Do NOT assume every reporting-program link is correct: retain and flag
    non-CM names, unexpected types, cross-campus links, and auxiliary CM rows.
  - Return one row per involvement per Sunday, including rows with no meeting.
  - Show both Meetings.NumPresent and positive Attend rows for reconciliation.
  - Include Organization Type 207 volunteer attendance alongside Type 201
    child/classroom attendance.

Expected proposed production boundary:
  - Active organization (StatusId 30)
  - Name begins with "CM:"
  - Organization Type 201 (children) or 207 (volunteers)
  - Linked to Program 1137 (Central Sunday AM) or 1138 (Parker Square Sunday AM)

Safety:
  Read-only SELECT. No participant names, contact information, or individual
  attendance records are returned.

Run in:
  TouchPoint > Admin > Advanced > Special Content > SQL Scripts

Export the single result grid to Excel/CSV and return it to Brian/Kyle.
*/

DECLARE @Today DATE = CAST(GETDATE() AS DATE);
DECLARE @DaysSinceSunday INT = DATEDIFF(DAY, '19000107', @Today) % 7;

-- Most recent fully completed Sunday. If run on Sunday, use the prior Sunday
-- rather than a partially completed current day.
DECLARE @LatestCompletedSunday DATE = DATEADD(
    DAY,
    -CASE WHEN @DaysSinceSunday = 0 THEN 7 ELSE @DaysSinceSunday END,
    @Today
);
DECLARE @EarliestSunday DATE = DATEADD(DAY, -21, @LatestCompletedSunday);

;WITH SundayDates AS (
    SELECT 0 AS WeekOffset, @LatestCompletedSunday AS ReportSunday
    UNION ALL SELECT 1, DATEADD(DAY, -7, @LatestCompletedSunday)
    UNION ALL SELECT 2, DATEADD(DAY, -14, @LatestCompletedSunday)
    UNION ALL SELECT 3, DATEADD(DAY, -21, @LatestCompletedSunday)
),
CandidateOrganizations AS (
    SELECT
        o.OrganizationId,
        o.OrganizationName,
        o.OrganizationStatusId,
        o.OrganizationTypeId,
        o.CampusId,
        o.FirstMeetingDate,
        o.LastMeetingDate,

        HasChildrenMinistryProgram1111 = CASE WHEN EXISTS (
            SELECT 1
            FROM dbo.DivOrg programLink
            JOIN dbo.Division programDivision
              ON programDivision.Id = programLink.DivId
            WHERE programLink.OrgId = o.OrganizationId
              AND programDivision.ProgId = 1111
        ) THEN 1 ELSE 0 END,

        HasCentralReportingProgram1137 = CASE WHEN EXISTS (
            SELECT 1
            FROM dbo.DivOrg reportLink
            JOIN dbo.Division reportDivision
              ON reportDivision.Id = reportLink.DivId
            WHERE reportLink.OrgId = o.OrganizationId
              AND reportDivision.ProgId = 1137
        ) THEN 1 ELSE 0 END,

        HasParkerReportingProgram1138 = CASE WHEN EXISTS (
            SELECT 1
            FROM dbo.DivOrg reportLink
            JOIN dbo.Division reportDivision
              ON reportDivision.Id = reportLink.DivId
            WHERE reportLink.OrgId = o.OrganizationId
              AND reportDivision.ProgId = 1138
        ) THEN 1 ELSE 0 END,

        HasSundaySchedule = CASE WHEN EXISTS (
            SELECT 1
            FROM dbo.OrgSchedule sundaySchedule
            WHERE sundaySchedule.OrganizationId = o.OrganizationId
              AND sundaySchedule.SchedDay = 0
        ) THEN 1 ELSE 0 END

    FROM dbo.Organizations o
    WHERE o.OrganizationStatusId = 30
      AND EXISTS (
          SELECT 1
          FROM dbo.DivOrg candidateLink
          JOIN dbo.Division candidateDivision
            ON candidateDivision.Id = candidateLink.DivId
          WHERE candidateLink.OrgId = o.OrganizationId
            AND candidateDivision.ProgId IN (1111, 1137, 1138)
      )
)
SELECT TOP 1000
    sd.WeekOffset,
    sd.ReportSunday,

    co.OrganizationId,
    co.OrganizationName,
    co.OrganizationStatusId,
    os.Description AS OrganizationStatus,
    co.OrganizationTypeId,
    ot.Description AS OrganizationType,

    AttendanceCategory = CASE
        WHEN co.OrganizationTypeId = 201 THEN 'Children/Classroom'
        WHEN co.OrganizationTypeId = 207 THEN 'Volunteer'
        ELSE 'Review Type'
    END,

    ProposedReportAction = CASE
        WHEN co.OrganizationName LIKE 'CM:%'
         AND co.OrganizationTypeId IN (201, 207)
         AND (co.HasCentralReportingProgram1137 = 1 OR co.HasParkerReportingProgram1138 = 1)
        THEN 'INCLUDE'
        WHEN co.HasCentralReportingProgram1137 = 1 OR co.HasParkerReportingProgram1138 = 1
        THEN 'REVIEW REPORTING LINK'
        ELSE 'REVIEW AUXILIARY CM'
    END,

    ValidationWarning = CASE
        WHEN co.HasCentralReportingProgram1137 = 1
         AND co.HasParkerReportingProgram1138 = 1
        THEN 'Linked to both CC and PS reporting programs'
        WHEN co.HasCentralReportingProgram1137 = 1
         AND ISNULL(co.CampusId, 0) <> 10
        THEN 'CC reporting link does not match CampusId 10'
        WHEN co.HasParkerReportingProgram1138 = 1
         AND ISNULL(co.CampusId, 0) <> 11
        THEN 'PS reporting link does not match CampusId 11'
        WHEN (co.HasCentralReportingProgram1137 = 1 OR co.HasParkerReportingProgram1138 = 1)
         AND co.OrganizationName NOT LIKE 'CM:%'
        THEN 'Non-CM name inside Children Sunday reporting program'
        WHEN (co.HasCentralReportingProgram1137 = 1 OR co.HasParkerReportingProgram1138 = 1)
         AND co.OrganizationTypeId NOT IN (201, 207)
        THEN 'Unexpected organization type inside reporting program'
        WHEN co.HasCentralReportingProgram1137 = 0
         AND co.HasParkerReportingProgram1138 = 0
        THEN 'Children Ministry hierarchy but outside Sunday AM reporting programs'
        ELSE ''
    END,

    co.CampusId,
    campus.Code AS CampusCode,
    campus.Description AS CampusName,
    co.HasChildrenMinistryProgram1111,
    co.HasCentralReportingProgram1137,
    co.HasParkerReportingProgram1138,
    co.HasSundaySchedule,
    co.FirstMeetingDate,
    co.LastMeetingDate,

    ProgramDivisionLinks = STUFF((
        SELECT '; Division ' + CAST(d.Id AS VARCHAR(20))
             + '=' + ISNULL(d.Name, '')
             + ' / Program ' + CAST(ISNULL(d.ProgId, 0) AS VARCHAR(20))
             + '=' + ISNULL(p.Name, '')
        FROM dbo.DivOrg divisionLink
        JOIN dbo.Division d ON d.Id = divisionLink.DivId
        LEFT JOIN dbo.Program p ON p.Id = d.ProgId
        WHERE divisionLink.OrgId = co.OrganizationId
        ORDER BY d.ProgId, d.Id
        FOR XML PATH(''), TYPE
    ).value('.', 'NVARCHAR(MAX)'), 1, 2, ''),

    SundayScheduleTimes = STUFF((
        SELECT '; ' + CASE
            WHEN scheduleRow.SchedTime IS NULL THEN '(time not set)'
            ELSE CONVERT(VARCHAR(8), scheduleRow.SchedTime, 108)
        END
        FROM dbo.OrgSchedule scheduleRow
        WHERE scheduleRow.OrganizationId = co.OrganizationId
          AND scheduleRow.SchedDay = 0
        ORDER BY scheduleRow.SchedTime
        FOR XML PATH(''), TYPE
    ).value('.', 'NVARCHAR(MAX)'), 1, 2, ''),

    MeetingStatus = CASE
        WHEN meetingStats.AllMeetingCount = 0 THEN 'NO MEETING'
        WHEN meetingStats.ReportableMeetingCount > 0 THEN 'REPORTED'
        WHEN meetingStats.DidNotMeetCount > 0 THEN 'DID NOT MEET'
        WHEN meetingStats.CanceledCount > 0 THEN 'CANCELED'
        ELSE 'MEETING EXISTS — REVIEW'
    END,

    MeetingCount = ISNULL(meetingStats.AllMeetingCount, 0),
    ReportableMeetingCount = ISNULL(meetingStats.ReportableMeetingCount, 0),
    CanceledMeetingCount = ISNULL(meetingStats.CanceledCount, 0),
    DidNotMeetCount = ISNULL(meetingStats.DidNotMeetCount, 0),
    MeetingNumPresent = ISNULL(meetingStats.NumPresent, 0),
    PositiveAttendRows = ISNULL(attendStats.PositiveAttendRows, 0),
    AttendanceDifference = ISNULL(meetingStats.NumPresent, 0)
                         - ISNULL(attendStats.PositiveAttendRows, 0),

    MeetingIds = STUFF((
        SELECT '; ' + CAST(m.MeetingId AS VARCHAR(20))
        FROM dbo.Meetings m
        WHERE m.OrganizationId = co.OrganizationId
          AND CAST(m.MeetingDate AS DATE) = sd.ReportSunday
        ORDER BY m.MeetingDate, m.MeetingId
        FOR XML PATH(''), TYPE
    ).value('.', 'NVARCHAR(MAX)'), 1, 2, '')

FROM CandidateOrganizations co
CROSS JOIN SundayDates sd
LEFT JOIN lookup.OrganizationStatus os
  ON os.Id = co.OrganizationStatusId
LEFT JOIN lookup.OrganizationType ot
  ON ot.Id = co.OrganizationTypeId
LEFT JOIN lookup.Campus campus
  ON campus.Id = co.CampusId

OUTER APPLY (
    SELECT
        AllMeetingCount = COUNT(*),
        ReportableMeetingCount = SUM(CASE
            WHEN ISNULL(m.Canceled, 0) = 0
             AND ISNULL(m.DidNotMeet, 0) = 0
            THEN 1 ELSE 0 END),
        CanceledCount = SUM(CASE WHEN ISNULL(m.Canceled, 0) = 1 THEN 1 ELSE 0 END),
        DidNotMeetCount = SUM(CASE WHEN ISNULL(m.DidNotMeet, 0) = 1 THEN 1 ELSE 0 END),
        NumPresent = SUM(CASE
            WHEN ISNULL(m.Canceled, 0) = 0
             AND ISNULL(m.DidNotMeet, 0) = 0
            THEN ISNULL(m.NumPresent, 0) ELSE 0 END)
    FROM dbo.Meetings m
    WHERE m.OrganizationId = co.OrganizationId
      AND CAST(m.MeetingDate AS DATE) = sd.ReportSunday
) meetingStats

OUTER APPLY (
    SELECT
        PositiveAttendRows = COUNT(*)
    FROM dbo.Attend a
    WHERE a.OrganizationId = co.OrganizationId
      AND CAST(a.MeetingDate AS DATE) = sd.ReportSunday
      AND a.AttendanceFlag = 1
) attendStats

-- Always retain anything already placed in an official Sunday reporting
-- program—even if both meeting and schedule setup are missing—so bad setup is
-- visible. Auxiliary Program 1111 rows need a Sunday schedule or actual Sunday
-- meeting during the four-week window.
WHERE co.HasCentralReportingProgram1137 = 1
   OR co.HasParkerReportingProgram1138 = 1
   OR co.HasSundaySchedule = 1
   OR EXISTS (
       SELECT 1
       FROM dbo.Meetings actualSundayMeeting
       WHERE actualSundayMeeting.OrganizationId = co.OrganizationId
         AND CAST(actualSundayMeeting.MeetingDate AS DATE)
             BETWEEN @EarliestSunday AND @LatestCompletedSunday
         AND DATEDIFF(
             DAY,
             '19000107',
             CAST(actualSundayMeeting.MeetingDate AS DATE)
         ) % 7 = 0
   )

ORDER BY
    CASE
        WHEN co.OrganizationName LIKE 'CM:%'
         AND co.OrganizationTypeId IN (201, 207)
         AND (co.HasCentralReportingProgram1137 = 1 OR co.HasParkerReportingProgram1138 = 1)
        THEN 0
        WHEN co.HasCentralReportingProgram1137 = 1 OR co.HasParkerReportingProgram1138 = 1
        THEN 1
        ELSE 2
    END,
    CASE WHEN co.OrganizationTypeId = 207 THEN 0 ELSE 1 END,
    campus.Description,
    co.OrganizationName,
    sd.ReportSunday DESC;
