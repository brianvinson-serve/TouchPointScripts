#roles=ManageTouchpoints

model.Title = 'FTV Email'

#############################################################
MailToQuery = 'IsMemberOf( Org=2756[FTV Email ] ) = 1[True]'   # name of saved search or comma-separated list of IDs (whether saved search or list, enclose in quotes)
QueuedBy = 23670    # People ID of record the email should be queued by
FromAddress = 'Brenda.Bommarito@rpcstaff.org'
FromName = 'Brenda Bommarito'
Subject = 'FTVs for {:MMM d, yyyy}'.format(model.SundayForDate(model.DateTime))
#############################################################

ccsql = '''
select
    tn.TaskNoteId,
	tn.AboutPersonId,
	a.FamilyId,
	a.Name,
	sp.PreferredName Spouse,
	tn.Instructions Description
from dbo.TaskNote tn    -- 32 Anonymous Prayer Request;  35 First Time Visitor
	join dbo.People a on a.PeopleId = tn.AboutPersonId
	left join dbo.People sp on sp.PeopleId = a.SpouseId
where tn.CreatedDate > dateadd(dd, -5, getdate())
	and exists (select null from dbo.TaskNoteKeyword where TaskNoteId = tn.TaskNoteId and KeywordId = 35)
	and tn.IsNote = 0
	and a.CampusId = {0}
order by FamilyId, AboutPersonId, TaskNoteId
'''

prsql = '''
;with combined as (
select
    tn.TaskNoteId,
	tn.AboutPersonId,
	a.FamilyId,
	a.Name,
	sp.PreferredName Spouse,
	coalesce(tn.Instructions, tn.Notes) Description
from dbo.TaskNote tn    -- 32 Anonymous Prayer Request;  35 First Time Visitor
	join dbo.People a on a.PeopleId = tn.AboutPersonId
	left join dbo.People sp on sp.PeopleId = a.SpouseId
where tn.CreatedDate > dateadd(dd, -5, getdate())
	and exists (select null from dbo.TaskNoteKeyword where TaskNoteId = tn.TaskNoteId and KeywordId = 32)  --Anonymous Prayer Request
	and a.CampusId = {0}

UNION

select
    tn.TaskNoteId,
	tn.AboutPersonId,
	a.FamilyId,
	a.Name,
	sp.PreferredName Spouse,
	tn.Instructions Description
from dbo.TaskNote tn
	join dbo.People a on a.PeopleId = tn.AboutPersonId
	left join dbo.People sp on sp.PeopleId = a.SpouseId
where tn.CreatedDate > dateadd(dd, -5, getdate())
	and exists (select null from dbo.TaskNoteKeyword where TaskNoteId = tn.TaskNoteId and KeywordId = 30)  --Include in Prayer Feed
	and a.CampusId = {0}
)
select * from combined
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

{{IfEqual mode "review"}}
    <h3><a href="/PyScript/FirstTimeVisitorEmail/?mode=send" target="_blank"><button type="button">Send email now</button></a></h3>
{{/IfEqual}}

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

body = model.RenderTemplate(template)
if Data.mode == "send":
    model.Email(MailToQuery, QueuedBy, FromAddress, FromName, Subject, body)
    print "Email sent."
else:
    print body
