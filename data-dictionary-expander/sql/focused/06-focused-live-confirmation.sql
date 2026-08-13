-- ============================================================
-- Data Dictionary Expander - 06 Focused Live Confirmation
-- Generated from the 2026-08-13 RockPointe structural export.
--
-- PURPOSE:
--   Confirm business meanings and value behavior that schema metadata alone
--   cannot establish. Run ONE query block at a time in TouchPoint SQL Scripts.
--
-- SAFETY:
--   SELECT-only. Aggregate or lookup data only. No person names, contact data,
--   task instructions, notes, attendance detail, or arbitrary sample rows.
-- ============================================================


/* ============================================================
   QUERY 1: Task status lookup values.
   Tests whether TaskNote.StatusId values map to lookup.TaskStatus.Id.
   Confirmed 2026-08-13: they do not (TaskNote uses 1-5; lookup uses 10-70).
   ============================================================ */
SELECT
    ts.Id,
    ts.Code,
    ts.Description,
    ts.Hardwired,
    COUNT(tn.TaskNoteId) AS TaskNoteRowCount
FROM lookup.TaskStatus ts
LEFT JOIN dbo.TaskNote tn
    ON tn.StatusId = ts.Id
GROUP BY
    ts.Id,
    ts.Code,
    ts.Description,
    ts.Hardwired
ORDER BY ts.Id


/* ============================================================
   QUERY 2: TaskNote status values not represented in TaskStatus.
   Confirmed 2026-08-13: all five TaskNote values (1-5) are unmapped because
   lookup.TaskStatus is a different status domain.
   ============================================================ */
SELECT
    tn.StatusId,
    COUNT(*) AS TaskNoteRowCount
FROM dbo.TaskNote tn
LEFT JOIN lookup.TaskStatus ts
    ON ts.Id = tn.StatusId
WHERE ts.Id IS NULL
GROUP BY tn.StatusId
ORDER BY tn.StatusId


/* ============================================================
   QUERY 3: TaskNote IsNote/null/status behavior.
   Confirms the live combinations used by task filters without exposing text.
   ============================================================ */
SELECT
    CASE
        WHEN tn.IsNote IS NULL THEN 'NULL'
        ELSE CAST(tn.IsNote AS VARCHAR(20))
    END AS IsNoteValue,
    tn.StatusId,
    ts.Code AS StatusCode,
    ts.Description AS StatusDescription,
    COUNT(*) AS RowCount
FROM dbo.TaskNote tn
LEFT JOIN lookup.TaskStatus ts
    ON ts.Id = tn.StatusId
GROUP BY
    CASE
        WHEN tn.IsNote IS NULL THEN 'NULL'
        ELSE CAST(tn.IsNote AS VARCHAR(20))
    END,
    tn.StatusId,
    ts.Code,
    ts.Description
ORDER BY
    IsNoteValue,
    tn.StatusId


/* ============================================================
   QUERY 4: Organization status lookup values and usage.
   ============================================================ */
SELECT
    os.Id,
    os.Code,
    os.Description,
    os.Active,
    COUNT(o.OrganizationId) AS OrganizationCount
FROM lookup.OrganizationStatus os
LEFT JOIN dbo.Organizations o
    ON o.OrganizationStatusId = os.Id
GROUP BY
    os.Id,
    os.Code,
    os.Description,
    os.Active
ORDER BY os.Id


/* ============================================================
   QUERY 5: Organization type lookup values and usage.
   Confirms all eight current lookup rows and their aggregate use.
   ============================================================ */
SELECT
    ot.Id,
    ot.Code,
    ot.Description,
    ot.Attendance,
    ot.ShowInMobile,
    ot.SortOrder,
    COUNT(o.OrganizationId) AS OrganizationCount
FROM lookup.OrganizationType ot
LEFT JOIN dbo.Organizations o
    ON o.OrganizationTypeId = ot.Id
GROUP BY
    ot.Id,
    ot.Code,
    ot.Description,
    ot.Attendance,
    ot.ShowInMobile,
    ot.SortOrder
ORDER BY ot.SortOrder, ot.Id


/* ============================================================
   QUERY 6: Member type lookup values and usage.
   Confirms leader/member/substitute meanings without person-level output.
   ============================================================ */
SELECT
    mt.Id,
    mt.Code,
    mt.Description,
    mt.Pending,
    mt.Inactive,
    mt.AttendanceTypeId,
    COUNT(om.PeopleId) AS OrganizationMemberCount
FROM lookup.MemberType mt
LEFT JOIN dbo.OrganizationMembers om
    ON om.MemberTypeId = mt.Id
GROUP BY
    mt.Id,
    mt.Code,
    mt.Description,
    mt.Pending,
    mt.Inactive,
    mt.AttendanceTypeId
ORDER BY mt.Id


/* ============================================================
   QUERY 7: DivOrg fan-out distribution.
   Confirms direct-join duplicate risk globally, without organization names.
   ============================================================ */
SELECT
    x.DivisionLinkCount,
    COUNT(*) AS OrganizationCount
FROM (
    SELECT
        o.OrganizationId,
        COUNT(d.DivId) AS DivisionLinkCount
    FROM dbo.Organizations o
    LEFT JOIN dbo.DivOrg d
        ON d.OrgId = o.OrganizationId
    GROUP BY o.OrganizationId
) x
GROUP BY x.DivisionLinkCount
ORDER BY x.DivisionLinkCount


/* ============================================================
   QUERY 8: OrgSchedule day values and usage.
   Confirms stored SchedDay values; weekday meaning still depends on known TPC
   convention unless compared to actual meetings.
   ============================================================ */
SELECT
    os.SchedDay,
    COUNT(*) AS ScheduleRowCount,
    COUNT(DISTINCT os.OrganizationId) AS OrganizationCount,
    MIN(os.SchedTime) AS EarliestSchedTime,
    MAX(os.SchedTime) AS LatestSchedTime
FROM dbo.OrgSchedule os
GROUP BY os.SchedDay
ORDER BY os.SchedDay


/* ============================================================
   QUERY 9: Meeting aggregate-column population.
   Confirms which visitor aggregate fields are actually populated.
   ============================================================ */
SELECT
    COUNT(*) AS MeetingRowCount,
    COUNT(CASE WHEN NumPresent IS NOT NULL THEN 1 END) AS NumPresentPopulated,
    COUNT(CASE WHEN NumVstMembers IS NOT NULL THEN 1 END) AS NumVstMembersPopulated,
    COUNT(CASE WHEN NumRepeatVst IS NOT NULL THEN 1 END) AS NumRepeatVstPopulated,
    COUNT(CASE WHEN NumNewVisit IS NOT NULL THEN 1 END) AS NumNewVisitPopulated,
    MIN(MeetingDate) AS EarliestMeetingDate,
    MAX(MeetingDate) AS LatestMeetingDate
FROM dbo.Meetings


/* ============================================================
   QUERY 10: Confirm TaskNoteId is selectable and unique through q.QuerySql.
   Aggregate only; no task content is returned.
   Expected: RowCount = NonNullTaskNoteIdCount = DistinctTaskNoteIdCount.
   ============================================================ */
SELECT
    COUNT(*) AS TotalRows,
    COUNT(TaskNoteId) AS NonNullTaskNoteIdCount,
    COUNT(DISTINCT TaskNoteId) AS DistinctTaskNoteIdCount,
    MIN(TaskNoteId) AS MinimumTaskNoteId,
    MAX(TaskNoteId) AS MaximumTaskNoteId
FROM dbo.TaskNote
