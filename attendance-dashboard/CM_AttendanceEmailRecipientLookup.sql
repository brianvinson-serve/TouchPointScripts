-- ============================================================
-- CM Attendance Email Recipient Lookup
-- ============================================================
-- Read-only. Resolves the requested CM attendance-email audience (names only,
-- no emails supplied) to TouchPoint PeopleIds + on-file email addresses.
--
-- Deploy/run as a TouchPoint SQL Script. Returns every requested name,
-- including unresolved and duplicate matches, plus whether an email address
-- is on file at all -- since the whole point of this run is confirming we
-- HAVE an email for each of these 14 people before they go into
-- CM_AttendanceDashboardEmail.py's RECIPIENT_PEOPLE_IDS.
--
-- MatchStatus meanings:
--   RESOLVED           = exactly one People record matched the name, and it has an email on file
--   RESOLVED_NO_EMAIL   = exactly one People record matched, but EmailAddress is blank/NULL
--   REVIEW_MULTIPLE     = more than one People record matched; choose manually
--   NOT_FOUND           = no People record matched First/Nick + Last
--
-- Do not add any PeopleId to RECIPIENT_PEOPLE_IDS until its row here says
-- RESOLVED. RESOLVED_NO_EMAIL and REVIEW_MULTIPLE both need a human decision
-- first (get an email added in TouchPoint, or pick the right duplicate).
-- ============================================================

DECLARE @Requested TABLE (
    SortOrder     INT          NOT NULL,
    ExpectedFirst VARCHAR(50)  NOT NULL,
    ExpectedLast  VARCHAR(100) NOT NULL
)

INSERT INTO @Requested (SortOrder, ExpectedFirst, ExpectedLast)
VALUES
    (1,  'Amy',      'Kraus'),
    (2,  'Aimee',    'Whaley'),
    (3,  'Ashley',   'Reynolds'),
    (4,  'Sara',     'Comer'),
    (5,  'Christy',  'McCallum'),
    (6,  'Jen',      'Schmitz'),
    (7,  'Angela',   'Cheshire'),
    (8,  'Leah',     'McBain'),
    (9,  'Christi',  'Victor'),
    (10, 'Courtney', 'Rehbehn'),
    (11, 'Margo',    'Baisley'),
    (12, 'Treeka',   'Andries'),
    (13, 'Darlene',  'Everest'),
    (14, 'Kellie',   'Lampe')

;WITH CandidateMatches AS (
    SELECT
        r.SortOrder,
        r.ExpectedFirst,
        r.ExpectedLast,
        p.PeopleId,
        p.FirstName,
        p.NickName,
        p.LastName,
        p.EmailAddress
    FROM @Requested r
    JOIN dbo.People p
      ON LOWER(LTRIM(RTRIM(ISNULL(p.LastName, '')))) = LOWER(r.ExpectedLast)
     AND (
          LOWER(LTRIM(RTRIM(ISNULL(p.FirstName, '')))) = LOWER(r.ExpectedFirst)
          OR LOWER(LTRIM(RTRIM(ISNULL(p.NickName, '')))) = LOWER(r.ExpectedFirst)
     )
),
RankedMatches AS (
    SELECT
        c.*,
        MatchCount = COUNT(*) OVER (PARTITION BY c.SortOrder),
        MatchRank  = ROW_NUMBER() OVER (PARTITION BY c.SortOrder ORDER BY c.PeopleId)
    FROM CandidateMatches c
)
SELECT
    r.SortOrder,
    ExpectedName = r.ExpectedFirst + ' ' + r.ExpectedLast,
    rm.PeopleId,
    TouchPointName = CASE
        WHEN rm.PeopleId IS NULL THEN NULL
        ELSE COALESCE(NULLIF(LTRIM(RTRIM(rm.NickName)), ''), rm.FirstName)
             + ' ' + rm.LastName
    END,
    TouchPointEmail = rm.EmailAddress,
    MatchStatus = CASE
        WHEN rm.PeopleId IS NULL THEN 'NOT_FOUND'
        WHEN rm.MatchCount > 1 THEN 'REVIEW_MULTIPLE'
        WHEN NULLIF(LTRIM(RTRIM(rm.EmailAddress)), '') IS NULL THEN 'RESOLVED_NO_EMAIL'
        ELSE 'RESOLVED'
    END
FROM @Requested r
LEFT JOIN RankedMatches rm
  ON rm.SortOrder = r.SortOrder
 -- Return every duplicate candidate for review; otherwise the single match.
 AND (rm.MatchCount > 1 OR rm.MatchRank = 1)
ORDER BY r.SortOrder, rm.PeopleId
