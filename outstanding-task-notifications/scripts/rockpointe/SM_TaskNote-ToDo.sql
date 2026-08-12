-- SM_TaskNote-ToDo.sql - RockPointe Student Ministry Task Recipients
-- Generates list of SM staff with outstanding Tasks
-- Used as recipient list for SM_OutstandingTaskNotifications
--
-- DEPLOYMENT: Admin > Advanced > Special Content > SQL Scripts
-- File name should be: SM_TaskNote-ToDo
--
-- SM Staff list (update PeopleIds here when staff changes):
--   46965  Isaac Jiles
--   659    Price Peden
--   284    Courtney Edmondson
--   23164  Joseph McCalley
--   1675   Libbie Risberg
--   40594  Haven Burton
--   36696  Joshua Watson
--   28000  Abbie Vinson
--   19570  Weston Watts
--   118    Shawn Adams

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
    AND tn.IsNote = 0
    AND tn.Instructions NOT LIKE 'New Person Data Entry%'
    AND tn.OwnerId IN (SELECT PeopleId FROM @SMStaff)

    UNION ALL

    SELECT ta.AssigneeId AS PeopleId
    FROM TaskNote ta
    WHERE (ta.StatusId = 2 OR ta.StatusId = 3)
    AND ta.AssigneeId IS NOT NULL
    AND ta.IsNote = 0
    AND ta.Instructions NOT LIKE 'New Person Data Entry%'
    AND ta.AssigneeId IN (SELECT PeopleId FROM @SMStaff)
) t
GROUP BY t.PeopleId
HAVING COUNT(*) > 0
