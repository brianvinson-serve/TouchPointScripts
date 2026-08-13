-- SM_TaskNote-ToDo.sql - RockPointe Student Ministry Task Recipients
-- Generates list of Student Ministry staff with outstanding Tasks
-- Used as recipient list for SM_OutstandingTaskNotifications
--
-- DEPLOYMENT: Admin > Advanced > Special Content > SQL Scripts
-- File name should be: SM_TaskNote-ToDo
--
-- Confirmed SM staff PeopleId list. Keep synchronized with DB_REFERENCE.md.
-- Do not infer staff/leader status from MemberTypeId 220; lookup.MemberType says
-- 220 = Member globally and 140 = Leader. Use the diagnostic dashboard query to
-- validate any future involvement-based filter before replacing this list.
DECLARE @SMStaff TABLE (PeopleId INT)
INSERT INTO @SMStaff VALUES
    (46965), (659), (284), (23164), (1675),
    (40594), (36696), (28000), (19570), (118)

SELECT t.PeopleId, COUNT(*) AS TaskCount
FROM (
    SELECT tn.OwnerId AS PeopleId
    FROM TaskNote tn
    WHERE (
        tn.StatusId = 4 OR
        ((tn.StatusId = 2 OR tn.StatusId = 3) AND tn.AssigneeId IS NULL)
    )
    AND (tn.IsNote = 0 OR tn.IsNote IS NULL)
    AND (tn.Instructions IS NULL OR tn.Instructions NOT LIKE 'New Person Data Entry%')
    AND tn.OwnerId IN (SELECT PeopleId FROM @SMStaff)

    UNION ALL

    SELECT ta.AssigneeId AS PeopleId
    FROM TaskNote ta
    WHERE (ta.StatusId = 2 OR ta.StatusId = 3)
    AND ta.AssigneeId IS NOT NULL
    AND (ta.IsNote = 0 OR ta.IsNote IS NULL)
    AND (ta.Instructions IS NULL OR ta.Instructions NOT LIKE 'New Person Data Entry%')
    AND ta.AssigneeId IN (SELECT PeopleId FROM @SMStaff)
) t
GROUP BY t.PeopleId
HAVING COUNT(*) > 0
