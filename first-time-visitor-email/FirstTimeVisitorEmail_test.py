model.Title = 'FTV Email (TEST - preview only, never sends)'

#############################################################
# TEST COPY -- for verifying the prsql fix while access to run
# the real FirstTimeVisitorEmail script is sorted out.
# - No #roles= line, so it isn't gated behind ManageTouchpoints.
# - model.Email(...) and the "Send email now" button are both
#   removed entirely -- this script cannot send mail no matter
#   what URL parameters are passed to it.
# Once confirmed, port any further fixes into FirstTimeVisitorEmail.py
# and deploy that one under the real script name; delete this one.
#############################################################

ccsql = '''
;with ranked as (
    select
        tn.TaskNoteId,
        tn.AboutPersonId,
        a.FamilyId,
        a.Name,
        sp.PreferredName Spouse,
        tn.Instructions Description,
        row_number() over (partition by a.FamilyId order by tn.TaskNoteId) rn
    from dbo.TaskNote tn    -- 32 Anonymous Prayer Request;  35 First Time Visitor
        join dbo.People a on a.PeopleId = tn.AboutPersonId
        left join dbo.People sp on sp.PeopleId = a.SpouseId
    where tn.CreatedDate > dateadd(dd, -5, getdate())
        and exists (select null from dbo.TaskNoteKeyword where TaskNoteId = tn.TaskNoteId and KeywordId = 35)
        and tn.IsNote = 0
        and a.CampusId = {0}
)
select TaskNoteId, AboutPersonId, FamilyId, Name, Spouse, Description
from ranked
where rn = 1
order by FamilyId, AboutPersonId, TaskNoteId
'''

prsql = '''
select
    tn.TaskNoteId,
	tn.AboutPersonId,
	a.FamilyId,
	a.Name,
	sp.PreferredName Spouse,
	coalesce(tn.Instructions, tn.Notes) Description
from dbo.TaskNote tn    -- 32 Anonymous Prayer Request;  30 Include in Prayer Feed
	join dbo.People a on a.PeopleId = tn.AboutPersonId
	left join dbo.People sp on sp.PeopleId = a.SpouseId
where tn.CreatedDate > dateadd(dd, -5, getdate())
	and exists (select null from dbo.TaskNoteKeyword where TaskNoteId = tn.TaskNoteId and KeywordId in (32, 30))
	and a.CampusId = {0}
order by FamilyId, AboutPersonId, TaskNoteId
'''

csql = '''
drop table if exists #newrecords
select
	p.FamilyId,
	p.PeopleId,
	format(p.CreatedDate, 'M/d') Created
into #newrecords
from dbo.People p
where p.CreatedDate > dateadd(dd, -5, getdate())
	and ( exists (select null from dbo.Attend where PeopleId = p.PeopleId and OrganizationId in
					(select do.OrgId from dbo.DivOrg do join dbo.ProgDiv pd on pd.DivId = do.DivId where pd.ProgId = 1111) ) or
		  exists (select null from dbo.OrganizationMembers where Peopleid = p.PeopleId and OrganizationId in
		            (select do.OrgId from dbo.DivOrg do join dbo.ProgDiv pd on pd.DivId = do.DivId where pd.ProgId = 1111) )  )
	and p.CampusId = {0}

;with distinctfamilies as (
	select distinct FamilyId from #newrecords
)
select
    h.PeopleId HeadId,
	h.PreferredName Head,
	h.LastName HeadLast,
	sp.PreferredName Spouse,
	h.PrimaryCity City,
	stuff((select ', ' + p.PreferredName + case when p.LastName <> h.LastName then ' ' + p.LastName else '' end +
	                case when p.Age is NULL then '' else ' (' + convert(varchar(2), p.Age) + ')' + ' ' + n.Created end
			from #newrecords n
			join dbo.People p on p.PeopleId = n.PeopleId
			where p.FamilyId = f.FamilyId and p.PositionInFamilyId in (30,40)
			for xml path('')), 1, 2, '') Children
from dbo.Families f
	join distinctfamilies d on d.FamilyId = f.FamilyId
	join dbo.People h on h.PeopleId = f.HeadOfHouseholdId
	left join dbo.People sp on sp.PeopleId = f.HeadOfHouseholdSpouseId
'''

ssql = '''
select
	p.FamilyId,
	p.PeopleId,
	format(p.CreatedDate, 'M/d') Created,
	p.Name,
	g.Description Grade,
	h.PreferredName Head,
	h.LastName HeadLast,
	sp.PreferredName Spouse
from dbo.People p
join dbo.Families f on f.FamilyId = p.FamilyId
left join dbo.People h on h.PeopleId = f.HeadOfHouseholdId and h.PositionInFamilyId = 10
left join dbo.People sp on sp.PeopleId = f.HeadOfHouseholdSpouseId
left join lookup.GradeLevel g on g.Id = p.GradeLevelId
where p.CreatedDate > dateadd(dd, -5, getdate())
	and ( exists (select null from dbo.Attend where PeopleId = p.PeopleId and OrganizationId in
					(select do.OrgId from dbo.DivOrg do join dbo.ProgDiv pd on pd.DivId = do.DivId where pd.ProgId = 1109) ) or
		  exists (select null from dbo.OrganizationMembers where Peopleid = p.PeopleId and OrganizationId in
		            (select do.OrgId from dbo.DivOrg do join dbo.ProgDiv pd on pd.DivId = do.DivId where pd.ProgId = 1109) )  )
	and p.CampusId = {0}
	and not exists (
		select null from dbo.TaskNote tn
		where tn.AboutPersonId = p.PeopleId
			and tn.CreatedDate > dateadd(dd, -5, getdate())
			and tn.IsNote = 0
			and exists (select null from dbo.TaskNoteKeyword where TaskNoteId = tn.TaskNoteId and KeywordId = 35)
	)
'''

template = '''
<style>
    h4 {
        font-weight: bold;
        margin-top: 24px;
        margin-bottom: 0px;
    }
</style>

<body>

    <h3 style="color:#b00;">TEST COPY -- preview only, this script cannot send email</h3>
    <h3>{{Fmt date 'MMM d, yyyy'}}</h3>
{{#if totlen}}
{{#if clen}}
    <h3>CENTRAL CAMPUS:</h3>
    {{#if cccnlen}}
    <h4>Connect Cards:</h4>
    <ol>
        {{#each cccnotes}}
        <li><a href="https://rockpointe.tpsdb.com/Person2/{{AboutPersonId}}" target="_blank">{{Name}}</a>
            {{#if Spouse}} (spouse {{Spouse}}){{/if}}: {{Description}}</li>
        {{/each}}
    </ol>
    {{/if}}
    {{#if ccnlen}}
    <h4>Children's Ministry:</h4>
    <ol>
        {{#each ccnew}}
        <li>{{Head}} {{#if Spouse}}& {{Spouse}} {{/if}}<a href="https://rockpointe.tpsdb.com/Person2/{{HeadId}}" target="_blank">
                {{HeadLast}}</a>, {{#if City}}{{City}} residents; {{/if}}added: {{Children}}</li>
        {{/each}}
    </ol>
    {{/if}}
    {{#if csnlen}}
    <h4>Student Ministry:</h4>
    <ol>
        {{#each csnew}}
        <li><a href="https://rockpointe.tpsdb.com/Person2/{{PeopleId}}" target="_blank">{{Name}}</a> ({{Created}}), {{#if Grade}}{{Grade}} Grade, {{/if}}parents: {{#if Head}}
                {{Head}} {{#if Spouse}}& {{Spouse}} {{/if}}{{HeadLast}}{{else}}no record{{/if}}</li>
        {{/each}}
    </ol>
    {{/if}}
    {{#if cprnlen}}
    <h4>Prayer Requests:</h4>
    <ol>
        {{#each cprnotes}}
        <li><a href="https://rockpointe.tpsdb.com/Person2/{{AboutPersonId}}" target="_blank">{{Name}}</a>
            {{#if Spouse}} (spouse {{Spouse}}){{/if}}: {{Description}}</li>
        {{/each}}
    </ol>
    {{/if}}
{{/if}}

{{#if plen}}
    <h3>PARKER SQUARE CAMPUS</h3>
    {{#if pccnlen}}
    <h4>Connect Cards:</h4>
    <ol>
        {{#each pccnotes}}
        <li><a href="https://rockpointe.tpsdb.com/Person2/{{AboutPersonId}}" target="_blank">{{Name}}</a>
            {{#if Spouse}} (spouse {{Spouse}}){{/if}}: {{Description}}</li>
        {{/each}}
    </ol>
    {{/if}}
    {{#if pcnlen}}
    <h4>Children's Ministry:</h4>
    <ol>
        {{#each pcnew}}
        <li>{{Head}} {{#if Spouse}}& {{Spouse}} {{/if}}<a href="https://rockpointe.tpsdb.com/Person2/{{HeadId}}" target="_blank">
                {{HeadLast}}</a>, {{#if City}}{{City}} residents; {{/if}}added: {{Children}}</li>
        {{/each}}
    </ol>
    {{/if}}
    {{#if psnlen}}
    <h4>Student Ministry:</h4>
    <ol>
        {{#each psnew}}
        <li><a href="https://rockpointe.tpsdb.com/Person2/{{PeopleId}}" target="_blank">{{Name}}</a> ({{Created}}), {{#if Grade}}{{Grade}} Grade, {{/if}}parents: {{#if Head}}
                {{Head}} {{#if Spouse}}& {{Spouse}} {{/if}}{{HeadLast}}{{else}}no record{{/if}}</li>
        {{/each}}
    </ol>
    {{/if}}
    {{#if pprnlen}}
    <h4>Prayer Requests:</h4>
    <ol>
        {{#each pprnotes}}
        <li><a href="https://rockpointe.tpsdb.com/Person2/{{AboutPersonId}}" target="_blank">{{Name}}</a>
            {{#if Spouse}} (spouse {{Spouse}}){{/if}}: {{Description}}</li>
        {{/each}}
    </ol>
    {{/if}}
{{/if}}

{{/if}}
</body>
'''

Data.date = model.SundayForDate(model.DateTime)
Data.cccnotes = q.QuerySql(ccsql.format(10))
Data.cccnlen = len(Data.cccnotes)
Data.pccnotes = q.QuerySql(ccsql.format(11))
Data.pccnlen = len(Data.pccnotes)

Data.ccnew = q.QuerySql(csql.format(10))
Data.ccnlen = len(Data.ccnew)
Data.pcnew = q.QuerySql(csql.format(11))
Data.pcnlen = len(Data.pcnew)

Data.csnew = q.QuerySql(ssql.format(10))
Data.csnlen = len(Data.csnew)
Data.psnew = q.QuerySql(ssql.format(11))
Data.psnlen = len(Data.psnew)

Data.cprnotes = q.QuerySql(prsql.format(10))
Data.cprnlen = len(Data.cprnotes)
Data.pprnotes = q.QuerySql(prsql.format(11))
Data.pprnlen = len(Data.pprnotes)

Data.clen = Data.cccnlen + Data.ccnlen + Data.csnlen + Data.cprnlen
Data.plen = Data.pccnlen + Data.pcnlen + Data.psnlen + Data.pprnlen

Data.totlen = Data.clen + Data.plen

print model.RenderTemplate(template)
