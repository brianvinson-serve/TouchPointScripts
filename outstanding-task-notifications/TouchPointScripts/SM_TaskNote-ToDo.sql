-- SM_TaskNote-ToDo.sql - RockPointe Student Ministry Task Recipients
-- Generates list of Student Ministry staff with outstanding Tasks
-- Used as recipient list for SM_OutstandingTaskNotifications
--
-- DEPLOYMENT: Admin > Advanced > Special Content > SQL Scripts
-- File name should be: SM_TaskNote-ToDo
--
-- MODIFICATIONS FROM ORIGINAL:
-- 1. Can be filtered by Organization/Ministry (commented section below)
-- 2. Excludes system-generated tasks
-- 3. Improved status handling

SELECT t.PeopleId, COUNT(*) AS TaskCount
FROM (
    -- Tasks where user is Owner (and no assignee)
    SELECT tn.*, tn.OwnerId AS PeopleId
    FROM TaskNote tn
    WHERE (
        tn.StatusId = 4 OR  -- Declined
        ((tn.StatusId = 2 OR tn.StatusId = 3) AND tn.AssigneeId IS NULL)  -- Pending/Active with no assignee
    )
    AND tn.Instructions NOT LIKE 'New Person Data Entry%'  -- Exclude system tasks
    -- OPTIONAL: Filter by ministry organization
    -- Uncomment and modify the line below to filter by specific org
    -- AND tn.OwnerId IN (SELECT PeopleId FROM OrganizationMembers WHERE OrganizationId = YOUR_SM_ORG_ID)

    UNION

    -- Tasks where user is Assignee
    SELECT ta.*, ta.AssigneeId AS PeopleId
    FROM TaskNote ta
    WHERE (ta.StatusId = 2 OR ta.StatusId = 3)  -- Pending or Active
    AND ta.AssigneeId IS NOT NULL
    AND ta.Instructions NOT LIKE 'New Person Data Entry%'  -- Exclude system tasks
    -- OPTIONAL: Filter by ministry organization
    -- AND ta.AssigneeId IN (SELECT PeopleId FROM OrganizationMembers WHERE OrganizationId = YOUR_SM_ORG_ID)
) t
GROUP BY t.PeopleId
HAVING COUNT(*) > 0
