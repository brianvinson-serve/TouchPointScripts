-- ============================================================
-- SM Attendance - Flat Export for Dashboard Filtering
-- ============================================================
-- Returns one row per organization per meeting date.
-- Aggregation, grouping, and pivot happen in the HTML/JS layer.
--
-- Output columns double as filter fields:
--   Campus, PersonType, SchoolLevel, Grade, Gender, DayOfWeek,
--   MeetingDate, OrganizationId, OrganizationName, Attendance
--
-- PORTABILITY: Edit the CONFIG block below. The rest of the
-- query references only those variables and standard TP tables.
-- ============================================================

SET DATEFIRST 7  -- Sunday = 1; required for DayOfWeek label

-- ============================================================
-- CONFIG
-- ============================================================

-- Program and division IDs
DECLARE @ProgramId        INT = 1109   -- Student Ministry program
DECLARE @SundayDivId      INT = 11     -- Division 11 = SM Sundays
DECLARE @WednesdayDivId   INT = 42     -- Division 42 = SM Wednesdays

-- Organization type IDs (confirmed against live RPC data 2026-07-08)
-- Students (Sunday grade orgs): TypeId 201
-- Volunteers (Sunday morning): TypeId 207
-- Wednesday PS grade orgs ('SM: PS WED ...'): TypeId 205
DECLARE @StudentTypeId    INT = 201
DECLARE @VolunteerTypeId  INT = 207
DECLARE @WedGradeTypeId   INT = 205

-- Date range
-- Presets: CUSTOM | LAST30 | LAST90 | LAST6MO | CURRENTYEAR | CURRENTSEMESTER | LASTSEMESTER
DECLARE @DatePreset   VARCHAR(20) = 'LAST90'
DECLARE @StartDate    DATE        = NULL   -- Set only when @DatePreset = 'CUSTOM'
DECLARE @EndDate      DATE        = NULL   -- Set only when @DatePreset = 'CUSTOM'

-- Semester boundaries (month numbers). Adjust for your school calendar.
--   Default: Spring = Jan-May | Summer = Jun-Aug | Fall = Sep-Dec
DECLARE @SpringStart  INT = 1
DECLARE @SummerStart  INT = 6
DECLARE @FallStart    INT = 9

-- Day filters
DECLARE @IncludeSunday    BIT = 1   -- 1 = include Sunday meetings
DECLARE @IncludeWednesday BIT = 1   -- 1 = include Wednesday meetings

-- Campus filter: ALL | CENTRAL | PARKERSQUARE
DECLARE @CampusFilter VARCHAR(20) = 'ALL'

-- Org name campus prefixes (change if your naming convention differs)
DECLARE @CCPrefix  VARCHAR(10) = 'SM: CC '
DECLARE @PSPrefix  VARCHAR(10) = 'SM: PS '
-- The grade/gender parser strips these 7-char prefixes from OrganizationName.
-- If your prefix length differs, update the SUBSTRING(o.OrganizationName, 8, 200)
-- calls in the CROSS APPLY blocks below.

-- ============================================================
-- Resolve date preset to actual dates
-- ============================================================
IF @DatePreset != 'CUSTOM'
BEGIN
    DECLARE @Today     DATE = CAST(GETDATE() AS DATE)
    DECLARE @CurMonth  INT  = MONTH(@Today)
    DECLARE @CurYear   INT  = YEAR(@Today)

    DECLARE @CurSemStart DATE = CASE
        WHEN @CurMonth >= @FallStart   THEN DATEFROMPARTS(@CurYear, @FallStart,   1)
        WHEN @CurMonth >= @SummerStart THEN DATEFROMPARTS(@CurYear, @SummerStart, 1)
        ELSE                                DATEFROMPARTS(@CurYear, @SpringStart,  1)
    END

    DECLARE @LastSemStart DATE = CASE
        WHEN @CurMonth >= @FallStart   THEN DATEFROMPARTS(@CurYear,     @SummerStart,  1)
        WHEN @CurMonth >= @SummerStart THEN DATEFROMPARTS(@CurYear,     @SpringStart,  1)
        ELSE                                DATEFROMPARTS(@CurYear - 1, @FallStart,    1)
    END

    DECLARE @LastSemEnd DATE = CASE
        WHEN @CurMonth >= @FallStart   THEN EOMONTH(DATEFROMPARTS(@CurYear,     @FallStart   - 1, 1))
        WHEN @CurMonth >= @SummerStart THEN EOMONTH(DATEFROMPARTS(@CurYear,     @SummerStart - 1, 1))
        ELSE                                EOMONTH(DATEFROMPARTS(@CurYear - 1, 12,               1))
    END

    SELECT
        @StartDate = CASE @DatePreset
            WHEN 'LAST30'          THEN DATEADD(day,   -30, @Today)
            WHEN 'LAST90'          THEN DATEADD(day,   -90, @Today)
            WHEN 'LAST6MO'         THEN DATEADD(month,  -6, @Today)
            WHEN 'CURRENTYEAR'     THEN DATEFROMPARTS(@CurYear, 1, 1)
            WHEN 'CURRENTSEMESTER' THEN @CurSemStart
            WHEN 'LASTSEMESTER'    THEN @LastSemStart
        END,
        @EndDate = CASE @DatePreset
            WHEN 'LAST30'          THEN @Today
            WHEN 'LAST90'          THEN @Today
            WHEN 'LAST6MO'         THEN @Today
            WHEN 'CURRENTYEAR'     THEN @Today
            WHEN 'CURRENTSEMESTER' THEN @Today
            WHEN 'LASTSEMESTER'    THEN @LastSemEnd
        END
END

IF @StartDate IS NULL OR @EndDate IS NULL
    RAISERROR(
        'Date range not set. Use a valid @DatePreset or set @StartDate/@EndDate manually.',
        16, 1
    )

-- ============================================================
-- Main flat dataset
-- ============================================================
SELECT
    -- Dimension columns - use these as filter fields in the dashboard
    Campus = CASE
        WHEN o.OrganizationName LIKE @CCPrefix + '%' THEN 'Central'
        WHEN o.OrganizationName LIKE @PSPrefix + '%' THEN 'Parker Square'
        ELSE 'Other'
    END,
    PersonType = CASE o.OrganizationTypeId
        WHEN @StudentTypeId   THEN 'Students'
        WHEN @VolunteerTypeId THEN 'Volunteers'
        WHEN @WedGradeTypeId  THEN 'Students'
        ELSE 'Other'
    END,
    SchoolLevel = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId             THEN ''
        WHEN pg.Grade IN ('6th','7th','8th')                     THEN 'Middle School'
        WHEN pg.Grade = 'Middle School Off Hour'                  THEN 'Middle School'
        WHEN pg.Grade IN ('9th','10th','11th','12th')            THEN 'High School'
        WHEN pg.Grade = 'High School Off Hour'                    THEN 'High School'
        ELSE 'Other'
    END,
    Grade = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId THEN ''
        ELSE pg.Grade
    END,
    GradeOrder = CASE
        WHEN o.OrganizationTypeId = @VolunteerTypeId THEN 0
        ELSE CASE pg.Grade
            WHEN '6th'                    THEN 1
            WHEN '7th'                    THEN 2
            WHEN '8th'                    THEN 3
            WHEN '9th'                    THEN 4
            WHEN '10th'                   THEN 5
            WHEN '11th'                   THEN 6
            WHEN '12th'                   THEN 7
            WHEN 'Middle School Off Hour' THEN 8
            WHEN 'High School Off Hour'   THEN 9
            ELSE 99
        END
    END,
    Gender = pg.Gender,
    DayOfWeek = CASE DATEPART(dw, m.MeetingDate)
        WHEN 1 THEN 'Sunday'
        WHEN 4 THEN 'Wednesday'
        ELSE DATENAME(weekday, m.MeetingDate)
    END,

    -- Date
    MeetingDate = CAST(m.MeetingDate AS DATE),

    -- Org identifiers (useful for debugging and future detail drill-down)
    OrganizationId   = o.OrganizationId,
    OrganizationName = o.OrganizationName,

    -- Sunday vs D-Groups: driven by Division membership
    Category = CASE
        WHEN EXISTS (SELECT 1 FROM dbo.DivOrg dc WHERE dc.OrgId = o.OrganizationId AND dc.DivId = @SundayDivId)
            THEN 'Sunday'
        WHEN EXISTS (SELECT 1 FROM dbo.DivOrg dc WHERE dc.OrgId = o.OrganizationId AND dc.DivId = @WednesdayDivId)
            THEN 'D-Groups'
        ELSE 'Other'
    END,

    -- Attendance count for this org on this date
    Attendance = ISNULL(m.NumPresent, 0)

FROM dbo.Organizations o

-- Strip campus prefix to isolate the grade/gender portion of the name.
-- Assumes 7-char prefix ('SM: CC ' or 'SM: PS '). Update offset if prefix length differs.
CROSS APPLY (
    SELECT Remainder = LTRIM(SUBSTRING(o.OrganizationName, 8, 200))
) rm

-- Strip optional 'WED ' prefix for Wednesday PS grade orgs
CROSS APPLY (
    SELECT AfterWed = CASE
        WHEN rm.Remainder LIKE 'WED %' THEN SUBSTRING(rm.Remainder, 5, 200)
        ELSE rm.Remainder
    END
) wd

-- Parse grade and gender from the remainder.
-- Sunday orgs: [grade] Guys / [grade] Girls
-- Wednesday PS grade orgs: WED [grade] Boys / WED [grade] Girls (WED already stripped above)
CROSS APPLY (
    SELECT
        Grade = CASE
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Guys'  THEN RTRIM(LEFT(RTRIM(wd.AfterWed), LEN(RTRIM(wd.AfterWed)) - 5))
            WHEN RIGHT(RTRIM(wd.AfterWed), 6) = ' Girls' THEN RTRIM(LEFT(RTRIM(wd.AfterWed), LEN(RTRIM(wd.AfterWed)) - 6))
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Boys'  THEN RTRIM(LEFT(RTRIM(wd.AfterWed), LEN(RTRIM(wd.AfterWed)) - 5))
            ELSE RTRIM(wd.AfterWed)
        END,
        Gender = CASE
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Guys'  THEN 'Guys'
            WHEN RIGHT(RTRIM(wd.AfterWed), 6) = ' Girls' THEN 'Girls'
            WHEN RIGHT(RTRIM(wd.AfterWed), 5) = ' Boys'  THEN 'Guys'   -- normalize to Guys for consistent display
            ELSE ''
        END
) pg

-- Meetings within the date range
JOIN dbo.Meetings m
    ON  m.OrganizationId = o.OrganizationId
    AND CAST(m.MeetingDate AS DATE) BETWEEN @StartDate AND @EndDate

WHERE
    -- Active orgs only
    o.OrganizationStatusId = 30

    -- Campus name pattern (Students + Volunteers for CC/PS attendance orgs)
    AND (
        o.OrganizationName LIKE @CCPrefix + '%'
        OR o.OrganizationName LIKE @PSPrefix + '%'
    )

    -- Campus selection filter
    AND (
           @CampusFilter = 'ALL'
        OR (@CampusFilter = 'CENTRAL'      AND o.OrganizationName LIKE @CCPrefix + '%')
        OR (@CampusFilter = 'PARKERSQUARE' AND o.OrganizationName LIKE @PSPrefix + '%')
    )

    AND o.OrganizationTypeId IN (@StudentTypeId, @VolunteerTypeId, @WedGradeTypeId)

    -- Must be in the SM program
    AND EXISTS (
        SELECT 1
        FROM dbo.DivOrg do2
        JOIN dbo.Division d ON d.Id = do2.DivId
        WHERE do2.OrgId = o.OrganizationId
          AND d.ProgId  = @ProgramId
    )

    -- Day filter: driven by Division membership, not DATEPART on meeting time.
    -- Division 11 = SM Sundays, Division 42 = SM Wednesdays.
    AND (
        (
            @IncludeSunday = 1
            AND EXISTS (
                SELECT 1 FROM dbo.DivOrg ds
                WHERE ds.OrgId = o.OrganizationId AND ds.DivId = @SundayDivId
            )
        )
        OR (
            @IncludeWednesday = 1
            AND EXISTS (
                SELECT 1 FROM dbo.DivOrg dw
                WHERE dw.OrgId = o.OrganizationId AND dw.DivId = @WednesdayDivId
            )
        )
    )

ORDER BY
    Campus,
    PersonType,
    SchoolLevel,
    GradeOrder,
    Gender,
    MeetingDate
