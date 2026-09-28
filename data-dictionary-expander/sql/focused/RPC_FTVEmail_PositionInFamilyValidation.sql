-- Read-only. Validates an assumption FirstTimeVisitorEmail.py's Children's
-- Ministry query relies on: that PositionInFamilyId IN (30,40) reliably
-- identifies children. DB_REFERENCE.md flags this join as never
-- live-validated at RPC -- run both queries below in TouchPoint and report
-- back what comes out.

-- 1. What PositionInFamilyId values actually exist and what lookup.FamilyPosition
--    says about each one (Child/PrimaryAdult/SecondaryAdult flags).
select
    fp.Id PositionInFamilyId,
    fp.Description,
    fp.Child,
    fp.PrimaryAdult,
    fp.SecondaryAdult
from lookup.FamilyPosition fp
order by fp.Id;

-- 2. Recently-added people tied to Children's Ministry (Program 1111), with
--    their live PositionInFamilyId/Age and whether the current report's
--    IN (30,40) filter would include or exclude them. Widened to 30 days
--    (vs. the report's live 5-day window) to get more rows to eyeball.
--    A PositionInFamilyId that isn't 30/40 on an obvious kid (has an Age,
--    listed under a head-of-household), or IS 30/40 on an obvious adult,
--    means the filter needs to change.
select
    p.PeopleId,
    p.Name,
    p.Age,
    p.PositionInFamilyId,
    fp.Description PositionDescription,
    fp.Child FamilyPosition_ChildFlag,
    case when p.PositionInFamilyId in (30,40) then 'Included by current script' else 'EXCLUDED by current script' end CurrentScriptResult
from dbo.People p
left join lookup.FamilyPosition fp on fp.Id = p.PositionInFamilyId
where p.CreatedDate > dateadd(dd, -30, getdate())
    and ( exists (select null from dbo.Attend where PeopleId = p.PeopleId and OrganizationId in
                    (select do.OrgId from dbo.DivOrg do join dbo.ProgDiv pd on pd.DivId = do.DivId where pd.ProgId = 1111) ) or
          exists (select null from dbo.OrganizationMembers where Peopleid = p.PeopleId and OrganizationId in
                    (select do.OrgId from dbo.DivOrg do join dbo.ProgDiv pd on pd.DivId = do.DivId where pd.ProgId = 1111) )  )
order by p.PositionInFamilyId, p.Age;
