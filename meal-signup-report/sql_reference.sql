-- find_org.sql
-- Confirms an OrganizationId belongs to a registration and shows its title.
SELECT OrganizationId, OrganizationName, RegistrationTypeId, RegistrationTitle
FROM dbo.Organizations
WHERE OrganizationId = 4053;


-- find_night_question.sql
-- Lists the registration questions configured for the org, so you can find
-- the RegQuestionId for the "choose a night" question. Update the OrganizationId
-- below if reusing this for a different sign-up.
SELECT RegQuestionId, [Order], Label, QuestionTypeId, IsRequired, Options
FROM dbo.RegQuestion
WHERE OrganizationId = 4053
ORDER BY [Order];


-- raw_registrants_check.sql
-- Ad hoc check: raw registrant + answer rows for the night question, useful
-- for eyeballing the data before trusting the Python report.
SELECT
    p.Name,
    p.CellPhone,
    p.EmailAddress,
    r.CreatedDate AS RegisteredOn,
    ra.AnswerValue AS RawAnswer
FROM dbo.Registration r
JOIN dbo.RegPeople rp ON rp.RegistrationId = r.RegistrationId
JOIN dbo.RegAnswer ra ON ra.RegPeopleId = rp.RegPeopleId
                     AND ra.RegQuestionId = 'fd1504b9-4cfd-4252-a0f3-f1a34c517c4d'
JOIN dbo.People p ON p.PeopleId = r.PeopleId
WHERE r.OrganizationId = 4053
ORDER BY p.Name;
