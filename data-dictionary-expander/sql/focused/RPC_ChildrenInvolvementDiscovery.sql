/*
RPC Children’s Ministry involvement discovery
=============================================
Purpose:
  Produce one export-friendly row per active TouchPoint involvement that is
  likely relevant to Children’s Ministry or directly connected to Angela
  Cheshire / Jennifer Schmitz, limited to Sunday activity.

Confirmed staff identities:
  Angela Cheshire   PeopleId 2879
  Jennifer Schmitz  PeopleId 6523

Safety:
  Read-only SELECT. Returns organization-level metadata and meeting totals;
  it does not return participant names, contact information, or attendance rows.

Run in:
  TouchPoint > Admin > Advanced > Special Content > SQL Scripts

Export the single result grid to Excel/CSV and return it to Brian/Kyle.
*/

DECLARE @AngelaPeopleId INT = 2879;
DECLARE @JenniferPeopleId INT = 6523;
DECLARE @RecentMeetingDays INT = 120;

SELECT TOP 1000
    o.OrganizationId,
    o.OrganizationName,
    o.OrganizationStatusId,
    os.Description AS OrganizationStatus,
    o.OrganizationTypeId,
    ot.Description AS OrganizationType,
    o.CampusId,
    c.Code AS CampusCode,
    c.Description AS CampusName,
    o.FirstMeetingDate,
    o.LastMeetingDate,
    o.MemberCount,
    o.LeaderId,
    o.MainLeaderId,
    o.LeaderName,

    -- Why this row was included in the discovery export.
    DirectStaffLink = CASE WHEN
        o.LeaderId IN (@AngelaPeopleId, @JenniferPeopleId)
        OR o.MainLeaderId IN (@AngelaPeopleId, @JenniferPeopleId)
        OR EXISTS (
            SELECT 1
            FROM dbo.OrganizationMembers directMember
            WHERE directMember.OrganizationId = o.OrganizationId
              AND directMember.PeopleId IN (@AngelaPeopleId, @JenniferPeopleId)
              AND directMember.InactiveDate IS NULL
        )
        THEN 1 ELSE 0 END,

    ChildrenHierarchyMatch = CASE WHEN EXISTS (
        SELECT 1
        FROM dbo.DivOrg hierarchyLink
        JOIN dbo.Division hierarchyDivision
          ON hierarchyDivision.Id = hierarchyLink.DivId
        LEFT JOIN dbo.Program hierarchyProgram
          ON hierarchyProgram.Id = hierarchyDivision.ProgId
        WHERE hierarchyLink.OrgId = o.OrganizationId
          AND (
              ISNULL(hierarchyProgram.Name, '') LIKE '%Children%'
              OR ISNULL(hierarchyProgram.Name, '') LIKE '%Kids%'
              OR ISNULL(hierarchyProgram.Name, '') LIKE '%Preschool%'
              OR ISNULL(hierarchyProgram.Name, '') LIKE '%Childcare%'
              OR ISNULL(hierarchyDivision.Name, '') LIKE '%Children%'
              OR ISNULL(hierarchyDivision.Name, '') LIKE '%Kids%'
              OR ISNULL(hierarchyDivision.Name, '') LIKE '%Preschool%'
              OR ISNULL(hierarchyDivision.Name, '') LIKE '%Childcare%'
          )
    ) THEN 1 ELSE 0 END,

    OrganizationNameMatch = CASE WHEN
        o.OrganizationName LIKE '%Children%'
        OR o.OrganizationName LIKE '%Kids%'
        OR o.OrganizationName LIKE '%Preschool%'
        OR o.OrganizationName LIKE '%Childcare%'
        OR o.OrganizationName LIKE '%Nursery%'
        OR o.OrganizationName LIKE '%Elementary%'
        THEN 1 ELSE 0 END,

    SundayScheduleOrMeeting = CASE WHEN
        EXISTS (
            SELECT 1
            FROM dbo.OrgSchedule sundaySchedule
            WHERE sundaySchedule.OrganizationId = o.OrganizationId
              AND sundaySchedule.SchedDay = 0
        )
        OR EXISTS (
            SELECT 1
            FROM dbo.Meetings sundayMeeting
            WHERE sundayMeeting.OrganizationId = o.OrganizationId
              AND sundayMeeting.MeetingDate >= DATEADD(DAY, -@RecentMeetingDays, GETDATE())
              AND sundayMeeting.MeetingDate < DATEADD(DAY, 1, GETDATE())
              AND DATEDIFF(DAY, '19000107', CAST(sundayMeeting.MeetingDate AS DATE)) % 7 = 0
              AND ISNULL(sundayMeeting.Canceled, 0) = 0
              AND ISNULL(sundayMeeting.DidNotMeet, 0) = 0
        )
        THEN 1 ELSE 0 END,

    LikelyVolunteerInvolvement = CASE WHEN
        o.OrganizationTypeId = 207
        OR o.OrganizationName LIKE '%Volunteer%'
        OR o.OrganizationName LIKE '%Leader%'
        OR o.OrganizationName LIKE '%Serve%'
        THEN 1 ELSE 0 END,

    -- Direct links for each requested stakeholder. Global member-type labels
    -- are included as evidence, not as proof of a ministry-specific role.
    AngelaConnection = STUFF((
        SELECT '; ' + connection.ConnectionLabel
        FROM (
            SELECT 'Organization LeaderId' AS ConnectionLabel
            WHERE o.LeaderId = @AngelaPeopleId
            UNION ALL
            SELECT 'Organization MainLeaderId'
            WHERE o.MainLeaderId = @AngelaPeopleId
            UNION ALL
            SELECT 'MemberType ' + CAST(om.MemberTypeId AS VARCHAR(20))
                 + '=' + ISNULL(mt.Description, ISNULL(mt.Code, '(unlabeled)'))
            FROM dbo.OrganizationMembers om
            LEFT JOIN lookup.MemberType mt ON mt.Id = om.MemberTypeId
            WHERE om.OrganizationId = o.OrganizationId
              AND om.PeopleId = @AngelaPeopleId
              AND om.InactiveDate IS NULL
        ) connection
        ORDER BY connection.ConnectionLabel
        FOR XML PATH(''), TYPE
    ).value('.', 'NVARCHAR(MAX)'), 1, 2, ''),

    JenniferConnection = STUFF((
        SELECT '; ' + connection.ConnectionLabel
        FROM (
            SELECT 'Organization LeaderId' AS ConnectionLabel
            WHERE o.LeaderId = @JenniferPeopleId
            UNION ALL
            SELECT 'Organization MainLeaderId'
            WHERE o.MainLeaderId = @JenniferPeopleId
            UNION ALL
            SELECT 'MemberType ' + CAST(om.MemberTypeId AS VARCHAR(20))
                 + '=' + ISNULL(mt.Description, ISNULL(mt.Code, '(unlabeled)'))
            FROM dbo.OrganizationMembers om
            LEFT JOIN lookup.MemberType mt ON mt.Id = om.MemberTypeId
            WHERE om.OrganizationId = o.OrganizationId
              AND om.PeopleId = @JenniferPeopleId
              AND om.InactiveDate IS NULL
        ) connection
        ORDER BY connection.ConnectionLabel
        FOR XML PATH(''), TYPE
    ).value('.', 'NVARCHAR(MAX)'), 1, 2, ''),

    ProgramDivisionLinks = STUFF((
        SELECT '; Division ' + CAST(d.Id AS VARCHAR(20))
             + '=' + ISNULL(d.Name, '')
             + ' / Program ' + CAST(ISNULL(d.ProgId, 0) AS VARCHAR(20))
             + '=' + ISNULL(pr.Name, '')
        FROM dbo.DivOrg divisionLink
        JOIN dbo.Division d ON d.Id = divisionLink.DivId
        LEFT JOIN dbo.Program pr ON pr.Id = d.ProgId
        WHERE divisionLink.OrgId = o.OrganizationId
        ORDER BY d.ProgId, d.Id
        FOR XML PATH(''), TYPE
    ).value('.', 'NVARCHAR(MAX)'), 1, 2, ''),

    ScheduleLinks = STUFF((
        SELECT '; Day ' + CAST(scheduleRow.SchedDay AS VARCHAR(10))
             + CASE
                   WHEN scheduleRow.SchedTime IS NULL THEN ''
                   ELSE ' at ' + CONVERT(VARCHAR(8), scheduleRow.SchedTime, 108)
               END
        FROM dbo.OrgSchedule scheduleRow
        WHERE scheduleRow.OrganizationId = o.OrganizationId
        ORDER BY scheduleRow.SchedDay, scheduleRow.SchedTime
        FOR XML PATH(''), TYPE
    ).value('.', 'NVARCHAR(MAX)'), 1, 2, ''),

    RecentSundayMeetingCount = ISNULL(recentStats.RecentSundayMeetingCount, 0),
    RecentSundayTotalPresent = ISNULL(recentStats.RecentSundayTotalPresent, 0),
    RecentSundayAveragePresent = recentStats.RecentSundayAveragePresent,
    LatestSundayMeetingDate = latestMeeting.MeetingDate,
    LatestSundayMeetingPresent = latestMeeting.NumPresent,
    LatestSundayMeetingDidNotMeet = latestMeeting.DidNotMeet,
    LatestSundayMeetingCanceled = latestMeeting.Canceled

FROM dbo.Organizations o
LEFT JOIN lookup.OrganizationStatus os
  ON os.Id = o.OrganizationStatusId
LEFT JOIN lookup.OrganizationType ot
  ON ot.Id = o.OrganizationTypeId
LEFT JOIN lookup.Campus c
  ON c.Id = o.CampusId

OUTER APPLY (
    SELECT
        COUNT(*) AS RecentSundayMeetingCount,
        SUM(ISNULL(m.NumPresent, 0)) AS RecentSundayTotalPresent,
        CAST(AVG(CAST(m.NumPresent AS DECIMAL(10, 2))) AS DECIMAL(10, 2)) AS RecentSundayAveragePresent
    FROM dbo.Meetings m
    WHERE m.OrganizationId = o.OrganizationId
      AND m.MeetingDate >= DATEADD(DAY, -@RecentMeetingDays, GETDATE())
      AND m.MeetingDate < DATEADD(DAY, 1, GETDATE())
      AND DATEDIFF(DAY, '19000107', CAST(m.MeetingDate AS DATE)) % 7 = 0
      AND ISNULL(m.Canceled, 0) = 0
      AND ISNULL(m.DidNotMeet, 0) = 0
) recentStats

OUTER APPLY (
    SELECT TOP 1
        m.MeetingDate,
        m.NumPresent,
        m.DidNotMeet,
        m.Canceled
    FROM dbo.Meetings m
    WHERE m.OrganizationId = o.OrganizationId
      AND m.MeetingDate < DATEADD(DAY, 1, GETDATE())
      AND DATEDIFF(DAY, '19000107', CAST(m.MeetingDate AS DATE)) % 7 = 0
    ORDER BY m.MeetingDate DESC, m.MeetingId DESC
) latestMeeting

WHERE
    -- Confirmed active status in the RPC data dictionary.
    o.OrganizationStatusId = 30
    AND (
        -- Direct current connection to Angela or Jennifer.
        o.LeaderId IN (@AngelaPeopleId, @JenniferPeopleId)
        OR o.MainLeaderId IN (@AngelaPeopleId, @JenniferPeopleId)
        OR EXISTS (
            SELECT 1
            FROM dbo.OrganizationMembers directMember
            WHERE directMember.OrganizationId = o.OrganizationId
              AND directMember.PeopleId IN (@AngelaPeopleId, @JenniferPeopleId)
              AND directMember.InactiveDate IS NULL
        )

        -- Children’s-related program or division hierarchy.
        OR EXISTS (
            SELECT 1
            FROM dbo.DivOrg candidateLink
            JOIN dbo.Division candidateDivision
              ON candidateDivision.Id = candidateLink.DivId
            LEFT JOIN dbo.Program candidateProgram
              ON candidateProgram.Id = candidateDivision.ProgId
            WHERE candidateLink.OrgId = o.OrganizationId
              AND (
                  ISNULL(candidateProgram.Name, '') LIKE '%Children%'
                  OR ISNULL(candidateProgram.Name, '') LIKE '%Kids%'
                  OR ISNULL(candidateProgram.Name, '') LIKE '%Preschool%'
                  OR ISNULL(candidateProgram.Name, '') LIKE '%Childcare%'
                  OR ISNULL(candidateDivision.Name, '') LIKE '%Children%'
                  OR ISNULL(candidateDivision.Name, '') LIKE '%Kids%'
                  OR ISNULL(candidateDivision.Name, '') LIKE '%Preschool%'
                  OR ISNULL(candidateDivision.Name, '') LIKE '%Childcare%'
              )
        )

        -- Broad naming fallback for organizations stored under an unexpected hierarchy.
        OR o.OrganizationName LIKE '%Children%'
        OR o.OrganizationName LIKE '%Kids%'
        OR o.OrganizationName LIKE '%Preschool%'
        OR o.OrganizationName LIKE '%Childcare%'
        OR o.OrganizationName LIKE '%Nursery%'
        OR o.OrganizationName LIKE '%Elementary%'
    )

    -- Sunday-only: retain organizations with a Sunday schedule or actual
    -- recent Sunday meeting. This automatically excludes Wednesday-only
    -- programs while preserving Sunday volunteer check-in organizations.
    AND (
        EXISTS (
            SELECT 1
            FROM dbo.OrgSchedule sundaySchedule
            WHERE sundaySchedule.OrganizationId = o.OrganizationId
              AND sundaySchedule.SchedDay = 0
        )
        OR EXISTS (
            SELECT 1
            FROM dbo.Meetings sundayMeeting
            WHERE sundayMeeting.OrganizationId = o.OrganizationId
              AND sundayMeeting.MeetingDate >= DATEADD(DAY, -@RecentMeetingDays, GETDATE())
              AND sundayMeeting.MeetingDate < DATEADD(DAY, 1, GETDATE())
              AND DATEDIFF(DAY, '19000107', CAST(sundayMeeting.MeetingDate AS DATE)) % 7 = 0
              AND ISNULL(sundayMeeting.Canceled, 0) = 0
              AND ISNULL(sundayMeeting.DidNotMeet, 0) = 0
        )
    )

ORDER BY
    CASE WHEN
        o.LeaderId IN (@AngelaPeopleId, @JenniferPeopleId)
        OR o.MainLeaderId IN (@AngelaPeopleId, @JenniferPeopleId)
        OR EXISTS (
            SELECT 1
            FROM dbo.OrganizationMembers sortMember
            WHERE sortMember.OrganizationId = o.OrganizationId
              AND sortMember.PeopleId IN (@AngelaPeopleId, @JenniferPeopleId)
              AND sortMember.InactiveDate IS NULL
        )
        THEN 0 ELSE 1 END,
    CASE WHEN
        o.OrganizationTypeId = 207
        OR o.OrganizationName LIKE '%Volunteer%'
        OR o.OrganizationName LIKE '%Leader%'
        OR o.OrganizationName LIKE '%Serve%'
        THEN 0 ELSE 1 END,
    c.Description,
    o.OrganizationName;
