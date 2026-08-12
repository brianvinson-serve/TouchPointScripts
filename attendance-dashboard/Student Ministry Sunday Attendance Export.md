-- ============================================================  
-- Student Ministry Sunday Attendance Export (Pivoted)  
-- Program 1109 = Student Ministry (both campuses)  
--  
-- Hierarchy: Campus > Students/Volunteers > MS/HS > Detail  
-- ============================================================  
  
IF OBJECT_ID('tempdb..#Sundays') IS NOT NULL DROP TABLE #Sundays  
IF OBJECT_ID('tempdb..#Results') IS NOT NULL DROP TABLE #Results  
  
-- 1. Get all Sundays in the date range with meetings  
SELECT DISTINCT CAST(m.MeetingDate AS DATE) AS Sunday  
INTO #Sundays  
FROM dbo.Meetings m  
JOIN dbo.Organizations o ON o.OrganizationId = m.OrganizationId  
WHERE o.OrganizationTypeId IN (176, 156)  
  AND DATEPART(dw, m.MeetingDate) = 1  
  AND CONVERT(TIME, m.MeetingDate) < '13:00:00'  
  AND CAST(m.MeetingDate AS DATE) BETWEEN @StartDate AND @EndDate  
  AND EXISTS (  
      SELECT 1 FROM dbo.DivOrg do2  
      JOIN dbo.Division d ON d.Id = do2.DivId  
      WHERE do2.OrgId = o.OrganizationId  
      AND d.ProgId = 1109  
  )  
  AND (o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %')  
  
-- 2. Create results table  
CREATE TABLE #Results (  
    Campus          VARCHAR(100),  
    [Type]          VARCHAR(20),  
    TypeOrder       INT,  
    SchoolLevel     VARCHAR(20),  
    SchoolOrder     INT,  
    RowLabel        VARCHAR(200),  
    GradeOrder      INT,  
    OrganizationId  INT,  
    OrganizationName VARCHAR(200),  
    MeetingDate     DATE,  
    Attendance      INT  
)  
  
-- 3. Insert all qualifying involvements  
INSERT INTO #Results  
SELECT  
    Campus = CASE UPPER(SUBSTRING(o.OrganizationName, 5, 2))  
        WHEN 'CC' THEN 'Central'  
        WHEN 'PS' THEN 'Parker Square'  
    END,  
    [Type] = CASE o.OrganizationTypeId  
        WHEN 176 THEN 'Students'  
        WHEN 156 THEN 'Volunteers'  
    END,  
    TypeOrder = CASE o.OrganizationTypeId  
        WHEN 176 THEN 1  
        WHEN 156 THEN 2  
    END,  
    SchoolLevel = CASE  
        WHEN o.OrganizationTypeId = 156 THEN ''  
        WHEN pg.Grade IN ('6th', '7th', '8th') THEN 'Middle School'  
        WHEN pg.Grade = 'Middle School Off Hour' THEN 'Middle School'  
        WHEN pg.Grade IN ('9th', '10th', '11th', '12th') THEN 'High School'  
        WHEN pg.Grade = 'High School Off Hour' THEN 'High School'  
        ELSE 'Other'  
    END,  
    SchoolOrder = CASE  
        WHEN o.OrganizationTypeId = 156 THEN 0  
        WHEN pg.Grade IN ('6th', '7th', '8th') THEN 1  
        WHEN pg.Grade = 'Middle School Off Hour' THEN 1  
        WHEN pg.Grade IN ('9th', '10th', '11th', '12th') THEN 2  
        WHEN pg.Grade = 'High School Off Hour' THEN 2  
        ELSE 3  
    END,  
    RowLabel = CASE  
        WHEN pg.Gender != '' THEN pg.Grade + ' - ' + pg.Gender  
        ELSE pg.Grade  
    END,  
    GradeOrder = CASE pg.Grade  
        WHEN '6th' THEN 1  
        WHEN '7th' THEN 2  
        WHEN '8th' THEN 3  
        WHEN '9th' THEN 4  
        WHEN '10th' THEN 5  
        WHEN '11th' THEN 6  
        WHEN '12th' THEN 7  
        WHEN 'Middle School Off Hour' THEN 8  
        WHEN 'High School Off Hour' THEN 9  
        ELSE 99  
    END,  
    o.OrganizationId,  
    o.OrganizationName,  
    MeetingDate = CAST(m.MeetingDate AS DATE),  
    Attendance = ISNULL(m.NumPresent, 0)  
FROM dbo.Organizations o  
CROSS APPLY (  
    SELECT Remainder = LTRIM(SUBSTRING(o.OrganizationName, 8, 200))  
) rm  
CROSS APPLY (  
    SELECT  
        Grade = CASE  
            WHEN RIGHT(RTRIM(rm.Remainder), 5) = ' Guys'  
                THEN RTRIM(LEFT(RTRIM(rm.Remainder), LEN(RTRIM(rm.Remainder)) - 5))  
            WHEN RIGHT(RTRIM(rm.Remainder), 6) = ' Girls'  
                THEN RTRIM(LEFT(RTRIM(rm.Remainder), LEN(RTRIM(rm.Remainder)) - 6))  
            ELSE RTRIM(rm.Remainder)  
        END,  
        Gender = CASE  
            WHEN RIGHT(RTRIM(rm.Remainder), 5) = ' Guys' THEN 'Guys'  
            WHEN RIGHT(RTRIM(rm.Remainder), 6) = ' Girls' THEN 'Girls'  
            ELSE ''  
        END  
) pg  
LEFT JOIN dbo.Meetings m  
    ON m.OrganizationId = o.OrganizationId  
    AND CAST(m.MeetingDate AS DATE) IN (SELECT Sunday FROM #Sundays)  
    AND DATEPART(dw, m.MeetingDate) = 1  
    AND CONVERT(TIME, m.MeetingDate) < '13:00:00'  
WHERE o.OrganizationTypeId IN (176, 156)  
  AND o.OrganizationStatusId = 30  
  AND (o.OrganizationName LIKE 'SM: CC %' OR o.OrganizationName LIKE 'SM: PS %')  
  AND EXISTS (  
      SELECT 1 FROM dbo.DivOrg do2  
      JOIN dbo.Division d ON d.Id = do2.DivId  
      WHERE do2.OrgId = o.OrganizationId  
      AND d.ProgId = 1109  
  )  
  AND (  
      EXISTS (  
          SELECT 1 FROM dbo.OrgSchedule os  
          WHERE os.OrganizationId = o.OrganizationId  
          AND os.SchedDay = 0  
          AND CONVERT(TIME, os.SchedTime) < '13:00:00'  
      )  
      OR EXISTS (  
          SELECT 1 FROM dbo.Meetings m2  
          WHERE m2.OrganizationId = o.OrganizationId  
          AND CAST(m2.MeetingDate AS DATE) IN (SELECT Sunday FROM #Sundays)  
          AND DATEPART(dw, m2.MeetingDate) = 1  
          AND CONVERT(TIME, m2.MeetingDate) < '13:00:00'  
      )  
  )  
  
-- -------------------------------------------------------  
-- 4. Count weeks for averaging  
-- -------------------------------------------------------  
DECLARE @NumWeeks INT  
SELECT @NumWeeks = COUNT(*) FROM #Sundays  
IF @NumWeeks = 0 SET @NumWeeks = 1  
  
-- -------------------------------------------------------  
-- 5. Build dynamic pivot columns from #Sundays  
-- -------------------------------------------------------  
DECLARE @ColHeaders NVARCHAR(MAX) = ''  
DECLARE @ColSelect NVARCHAR(MAX) = ''  
DECLARE @ColDetail NVARCHAR(MAX) = ''  
DECLARE @ColDetailSum NVARCHAR(MAX) = ''  
DECLARE @ColSumsAgg NVARCHAR(MAX) = ''  
DECLARE @ColSumGrand NVARCHAR(MAX) = ''  
  
SELECT @ColHeaders = @ColHeaders + ',[' + CONVERT(VARCHAR, Sunday, 107) + ']'  
FROM #Sundays ORDER BY Sunday  
  
SELECT @ColSelect = @ColSelect + ',[' + CONVERT(VARCHAR, Sunday, 107) + ']'  
FROM #Sundays ORDER BY Sunday  
  
SELECT @ColDetail = @ColDetail + ',ISNULL([' + CONVERT(VARCHAR, Sunday, 107) + '], 0) AS [' + CONVERT(VARCHAR, Sunday, 107) + ']'  
FROM #Sundays ORDER BY Sunday  
  
SELECT @ColDetailSum = @ColDetailSum + '+ISNULL([' + CONVERT(VARCHAR, Sunday, 107) + '], 0)'  
FROM #Sundays ORDER BY Sunday  
  
SELECT @ColSumsAgg = @ColSumsAgg + ',SUM(ISNULL([' + CONVERT(VARCHAR, Sunday, 107) + '], 0)) AS [' + CONVERT(VARCHAR, Sunday, 107) + ']'  
FROM #Sundays ORDER BY Sunday  
  
SELECT @ColSumGrand = @ColSumGrand + '+SUM(ISNULL([' + CONVERT(VARCHAR, Sunday, 107) + '], 0))'  
FROM #Sundays ORDER BY Sunday  
  
-- Strip leading delimiters  
SET @ColHeaders = STUFF(@ColHeaders, 1, 1, '')  
SET @ColSelect = STUFF(@ColSelect, 1, 1, '')  
SET @ColDetail = STUFF(@ColDetail, 1, 1, '')  
SET @ColDetailSum = STUFF(@ColDetailSum, 1, 1, '')  
SET @ColSumsAgg = STUFF(@ColSumsAgg, 1, 1, '')  
SET @ColSumGrand = STUFF(@ColSumGrand, 1, 1, '')  
  
-- -------------------------------------------------------  
-- 6. Build and execute the dynamic pivot query  
-- -------------------------------------------------------  
DECLARE @SQL NVARCHAR(MAX)  
  
SET @SQL = '  
;WITH Aggregated AS (  
    SELECT  
        Campus,  
        [Type],  
        TypeOrder,  
        SchoolLevel,  
        SchoolOrder,  
        RowLabel,  
        GradeOrder,  
        MeetingDate,  
        Attendance = SUM(Attendance)  
    FROM #Results  
    WHERE MeetingDate IS NOT NULL  
    GROUP BY Campus, [Type], TypeOrder, SchoolLevel, SchoolOrder, RowLabel, GradeOrder, MeetingDate  
),  
Pivoted AS (  
    SELECT  
        Campus,  
        [Type],  
        TypeOrder,  
        SchoolLevel,  
        SchoolOrder,  
        RowLabel,  
        GradeOrder,  
        ' + @ColSelect + '  
    FROM Aggregated  
    PIVOT (  
        SUM(Attendance)  
        FOR MeetingDate IN (' + @ColHeaders + ')  
    ) pvt  
),  
-- Detail rows (RowType 4)  
DetailRows AS (  
    SELECT  
        RowType      = 4,  
        SortCampus   = Campus,  
        SortType     = TypeOrder,  
        SortSchool   = SchoolOrder,  
        SortGrade    = GradeOrder,  
        SortLabel    = RowLabel,  
        [Row Labels] = ''          '' + RowLabel,  
        ' + @ColDetail + ',  
        [Grand Total] = ' + @ColDetailSum + ',  
        [' + CAST(@NumWeeks AS VARCHAR) + ' wk Avg] = CAST(ROUND((' + @ColDetailSum + ') * 1.0 / ' + CAST(@NumWeeks AS VARCHAR) + ', 0) AS INT)  
    FROM Pivoted  
),  
-- School Level rows - MS/HS under Students only (RowType 3)  
SchoolRows AS (  
    SELECT  
        RowType      = 3,  
        SortCampus   = Campus,  
        SortType     = TypeOrder,  
        SortSchool   = SchoolOrder,  
        SortGrade    = 0,  
        SortLabel    = '''',  
        [Row Labels] = ''        '' + SchoolLevel,  
        ' + @ColSumsAgg + ',  
        [Grand Total] = ' + @ColSumGrand + ',  
        [' + CAST(@NumWeeks AS VARCHAR) + ' wk Avg] = CAST(ROUND((' + @ColSumGrand + ') * 1.0 / ' + CAST(@NumWeeks AS VARCHAR) + ', 0) AS INT)  
    FROM Pivoted  
    WHERE [Type] = ''Students'' AND SchoolLevel != ''''  
    GROUP BY Campus, TypeOrder, SchoolLevel, SchoolOrder  
),  
-- Type rows - Students / Volunteers (RowType 2)  
TypeRows AS (  
    SELECT  
        RowType      = 2,  
        SortCampus   = Campus,  
        SortType     = TypeOrder,  
        SortSchool   = 0,  
        SortGrade    = 0,  
        SortLabel    = '''',  
        [Row Labels] = ''    '' + [Type],  
        ' + @ColSumsAgg + ',  
        [Grand Total] = ' + @ColSumGrand + ',  
        [' + CAST(@NumWeeks AS VARCHAR) + ' wk Avg] = CAST(ROUND((' + @ColSumGrand + ') * 1.0 / ' + CAST(@NumWeeks AS VARCHAR) + ', 0) AS INT)  
    FROM Pivoted  
    GROUP BY Campus, [Type], TypeOrder  
),  
-- Campus rows (RowType 1)  
CampusRows AS (  
    SELECT  
        RowType      = 1,  
        SortCampus   = Campus,  
        SortType     = 0,  
        SortSchool   = 0,  
        SortGrade    = 0,  
        SortLabel    = '''',  
        [Row Labels] = ''  '' + Campus,  
        ' + @ColSumsAgg + ',  
        [Grand Total] = ' + @ColSumGrand + ',  
        [' + CAST(@NumWeeks AS VARCHAR) + ' wk Avg] = CAST(ROUND((' + @ColSumGrand + ') * 1.0 / ' + CAST(@NumWeeks AS VARCHAR) + ', 0) AS INT)  
    FROM Pivoted  
    GROUP BY Campus  
),  
-- Grand Total (RowType 5)  
GrandTotalRow AS (  
    SELECT  
        RowType      = 5,  
        SortCampus   = ''zzz'',  
        SortType     = 0,  
        SortSchool   = 0,  
        SortGrade    = 0,  
        SortLabel    = '''',  
        [Row Labels] = ''Grand Total'',  
        ' + @ColSumsAgg + ',  
        [Grand Total] = ' + @ColSumGrand + ',  
        [' + CAST(@NumWeeks AS VARCHAR) + ' wk Avg] = CAST(ROUND((' + @ColSumGrand + ') * 1.0 / ' + CAST(@NumWeeks AS VARCHAR) + ', 0) AS INT)  
    FROM Pivoted  
),  
AllRows AS (  
    SELECT * FROM CampusRows  
    UNION ALL SELECT * FROM TypeRows  
    UNION ALL SELECT * FROM SchoolRows  
    UNION ALL SELECT * FROM DetailRows  
    UNION ALL SELECT * FROM GrandTotalRow  
)  
SELECT  
    [Row Labels],  
    ' + @ColSelect + ',  
    [Grand Total],  
    [' + CAST(@NumWeeks AS VARCHAR) + ' wk Avg]  
FROM AllRows  
ORDER BY  
    SortCampus,  
    RowType,  
    SortType,  
    SortSchool,  
    SortGrade,  
    SortLabel  
'  
  
EXEC sp_executesql @SQL  
  
-- -------------------------------------------------------  
-- Cleanup  
-- -------------------------------------------------------  
DROP TABLE #Sundays  
DROP TABLE #Results