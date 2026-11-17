-- RPC_FTVPrayerOverlapCheck (read-only)
-- Brenda 2026-11-17: when an FTV card also has a prayer request, the FTV notes
-- didn't show in the report. This lists every FTV (35) / prayer (30, 32) task
-- from the last 10 days for any family that had BOTH, with all keywords and
-- both text fields, so we can see how the connect card actually stores them:
--   A) separate tasks (prayer task also tagged FTV?), or
--   B) one task carrying both keywords, with FTV notes in Notes vs Instructions.
-- Run in Special Content > SQL Scripts. No writes.

;with recent as (
    select tn.TaskNoteId, tn.AboutPersonId, a.FamilyId, tn.CreatedDate,
           tn.IsNote, tn.Instructions, tn.Notes
    from dbo.TaskNote tn
        join dbo.People a on a.PeopleId = tn.AboutPersonId
    where tn.CreatedDate > dateadd(dd, -10, getdate())
        and exists (select null from dbo.TaskNoteKeyword k
                    where k.TaskNoteId = tn.TaskNoteId and k.KeywordId in (30, 32, 35))
),
families_with_both as (
    select r.FamilyId
    from recent r
        join dbo.TaskNoteKeyword k on k.TaskNoteId = r.TaskNoteId
    group by r.FamilyId
    having max(case when k.KeywordId = 35 then 1 else 0 end) = 1
       and max(case when k.KeywordId in (30, 32) then 1 else 0 end) = 1
)
select
    r.FamilyId,
    r.TaskNoteId,
    r.AboutPersonId,
    p.Name,
    p.PositionInFamilyId,
    r.CreatedDate,
    r.IsNote,
    stuff((select ', ' + convert(varchar(10), k.KeywordId)
           from dbo.TaskNoteKeyword k where k.TaskNoteId = r.TaskNoteId
           order by k.KeywordId for xml path('')), 1, 2, '') Keywords,
    r.Instructions,
    r.Notes
from recent r
    join families_with_both f on f.FamilyId = r.FamilyId
    join dbo.People p on p.PeopleId = r.AboutPersonId
order by r.FamilyId, r.TaskNoteId
