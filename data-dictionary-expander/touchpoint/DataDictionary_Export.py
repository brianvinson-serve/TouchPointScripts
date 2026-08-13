# ============================================================
# TOUCHPOINT DEPLOYABLE SCRIPT - RockPointe Data Dictionary Export
#
# Deploy as a TouchPoint Python Script named DataDictionary_Export.
# This is the file to paste into TouchPoint. Do not paste any LOCAL_ utility.
#
# VERSION: 2.1 - structural inventory + focused confirmations
# FIXES: lookup-schema qualification and F10 TotalRows alias
# PROBES: 17 total (Q01-Q07 structural; F01-F10 focused aggregate checks)
# DOWNLOADS:
#   1. rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv
#   2. rockpointe-touchpoint-focused-confirmation-YYYY-MM-DD.csv
#
# Privacy: exports schema metadata, lookup labels, and aggregate counts only.
# It does not select person names, emails, phones, addresses, task text,
# attendance-detail rows, or arbitrary sample records.
# ============================================================

global model, q, Data

import json


EXPORT_COLUMNS = [
    "Section",
    "QueryId",
    "SchemaName",
    "TableName",
    "ColumnName",
    "OrdinalPosition",
    "DataType",
    "MaxLength",
    "NumericPrecision",
    "NumericScale",
    "DateTimePrecision",
    "Nullable",
    "ObjectType",
    "ApproxRowCount",
    "ConstraintName",
    "ConstraintType",
    "KeyOrdinal",
    "ReferencedSchema",
    "ReferencedTable",
    "ReferencedColumn",
    "IndexName",
    "IsUnique",
    "IsPrimaryKey",
    "Finding",
    "Error",
]


def text(value):
    if value is None:
        return ""
    return str(value)


def value(row, name):
    try:
        return getattr(row, name)
    except Exception:
        return None


def record(section, query_id, **kwargs):
    item = {}
    for column in EXPORT_COLUMNS:
        item[column] = ""
    item["Section"] = section
    item["QueryId"] = query_id
    for key in kwargs:
        if key in item:
            item[key] = text(kwargs[key])
    return item


def html_escape(value_to_escape):
    return text(value_to_escape).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


rows = []
query_status = []


def run_probe(query_id, section, sql, mapper):
    try:
        result_rows = list(q.QuerySql(sql))
        for result_row in result_rows:
            rows.append(mapper(result_row))
        query_status.append({"QueryId": query_id, "Section": section, "Status": "OK", "Rows": len(result_rows), "Error": ""})
    except Exception as error:
        error_text = text(error)
        rows.append(record(section, query_id, Finding="Probe failed; other probes continued.", Error=error_text))
        query_status.append({"QueryId": query_id, "Section": section, "Status": "ERROR", "Rows": 0, "Error": error_text})


run_probe(
    "Q01",
    "CollectionMetadata",
    """
SELECT
    DB_NAME() AS DatabaseName,
    GETDATE() AS CollectedAt,
    @@VERSION AS SqlVersion
""",
    lambda r: record(
        "CollectionMetadata",
        "Q01",
        Finding="Database={}; CollectedAt={}; SQL={}".format(
            text(value(r, "DatabaseName")),
            text(value(r, "CollectedAt")),
            text(value(r, "SqlVersion")).replace("\r", " ").replace("\n", " "),
        ),
    ),
)


run_probe(
    "Q02",
    "TableInventory",
    """
SELECT
    TABLE_SCHEMA AS SchemaName,
    TABLE_NAME AS TableName,
    TABLE_TYPE AS ObjectType
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
ORDER BY TABLE_SCHEMA, TABLE_NAME
""",
    lambda r: record(
        "TableInventory",
        "Q02",
        SchemaName=value(r, "SchemaName"),
        TableName=value(r, "TableName"),
        ObjectType=value(r, "ObjectType"),
    ),
)


run_probe(
    "Q03",
    "ColumnInventory",
    """
SELECT
    TABLE_SCHEMA AS SchemaName,
    TABLE_NAME AS TableName,
    COLUMN_NAME AS ColumnName,
    ORDINAL_POSITION AS OrdinalPosition,
    DATA_TYPE AS DataType,
    CHARACTER_MAXIMUM_LENGTH AS MaxLength,
    NUMERIC_PRECISION AS NumericPrecision,
    NUMERIC_SCALE AS NumericScale,
    DATETIME_PRECISION AS DateTimePrecision,
    IS_NULLABLE AS Nullable
FROM INFORMATION_SCHEMA.COLUMNS
ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
""",
    lambda r: record(
        "ColumnInventory",
        "Q03",
        SchemaName=value(r, "SchemaName"),
        TableName=value(r, "TableName"),
        ColumnName=value(r, "ColumnName"),
        OrdinalPosition=value(r, "OrdinalPosition"),
        DataType=value(r, "DataType"),
        MaxLength=value(r, "MaxLength"),
        NumericPrecision=value(r, "NumericPrecision"),
        NumericScale=value(r, "NumericScale"),
        DateTimePrecision=value(r, "DateTimePrecision"),
        Nullable=value(r, "Nullable"),
    ),
)


run_probe(
    "Q04",
    "ApproximateRowCounts",
    """
SELECT
    s.name AS SchemaName,
    o.name AS TableName,
    SUM(p.rows) AS ApproxRowCount
FROM sys.objects o
JOIN sys.schemas s ON s.schema_id = o.schema_id
JOIN sys.partitions p ON p.object_id = o.object_id
WHERE o.type = 'U'
  AND p.index_id IN (0, 1)
GROUP BY s.name, o.name
ORDER BY SUM(p.rows) DESC, s.name, o.name
""",
    lambda r: record(
        "ApproximateRowCounts",
        "Q04",
        SchemaName=value(r, "SchemaName"),
        TableName=value(r, "TableName"),
        ApproxRowCount=value(r, "ApproxRowCount"),
        Finding="Approximate SQL Server metadata count; not an exact COUNT(*).",
    ),
)


run_probe(
    "Q05",
    "PrimaryKeys",
    """
SELECT
    tc.TABLE_SCHEMA AS SchemaName,
    tc.TABLE_NAME AS TableName,
    kcu.COLUMN_NAME AS ColumnName,
    tc.CONSTRAINT_NAME AS ConstraintName,
    tc.CONSTRAINT_TYPE AS ConstraintType,
    kcu.ORDINAL_POSITION AS KeyOrdinal
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
  ON kcu.CONSTRAINT_CATALOG = tc.CONSTRAINT_CATALOG
 AND kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
 AND kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
ORDER BY tc.TABLE_SCHEMA, tc.TABLE_NAME, kcu.ORDINAL_POSITION
""",
    lambda r: record(
        "PrimaryKeys",
        "Q05",
        SchemaName=value(r, "SchemaName"),
        TableName=value(r, "TableName"),
        ColumnName=value(r, "ColumnName"),
        ConstraintName=value(r, "ConstraintName"),
        ConstraintType=value(r, "ConstraintType"),
        KeyOrdinal=value(r, "KeyOrdinal"),
    ),
)


run_probe(
    "Q06",
    "ForeignKeys",
    """
SELECT
    OBJECT_SCHEMA_NAME(fkc.parent_object_id) AS SchemaName,
    OBJECT_NAME(fkc.parent_object_id) AS TableName,
    pc.name AS ColumnName,
    fk.name AS ConstraintName,
    fkc.constraint_column_id AS KeyOrdinal,
    OBJECT_SCHEMA_NAME(fkc.referenced_object_id) AS ReferencedSchema,
    OBJECT_NAME(fkc.referenced_object_id) AS ReferencedTable,
    rc.name AS ReferencedColumn
FROM sys.foreign_key_columns fkc
JOIN sys.foreign_keys fk
  ON fk.object_id = fkc.constraint_object_id
JOIN sys.columns pc
  ON pc.object_id = fkc.parent_object_id
 AND pc.column_id = fkc.parent_column_id
JOIN sys.columns rc
  ON rc.object_id = fkc.referenced_object_id
 AND rc.column_id = fkc.referenced_column_id
ORDER BY
    OBJECT_SCHEMA_NAME(fkc.parent_object_id),
    OBJECT_NAME(fkc.parent_object_id),
    fk.name,
    fkc.constraint_column_id
""",
    lambda r: record(
        "ForeignKeys",
        "Q06",
        SchemaName=value(r, "SchemaName"),
        TableName=value(r, "TableName"),
        ColumnName=value(r, "ColumnName"),
        ConstraintName=value(r, "ConstraintName"),
        ConstraintType="FOREIGN KEY",
        KeyOrdinal=value(r, "KeyOrdinal"),
        ReferencedSchema=value(r, "ReferencedSchema"),
        ReferencedTable=value(r, "ReferencedTable"),
        ReferencedColumn=value(r, "ReferencedColumn"),
    ),
)


run_probe(
    "Q07",
    "Indexes",
    """
SELECT
    s.name AS SchemaName,
    o.name AS TableName,
    c.name AS ColumnName,
    i.name AS IndexName,
    i.is_unique AS IsUnique,
    i.is_primary_key AS IsPrimaryKey,
    ic.key_ordinal AS KeyOrdinal
FROM sys.indexes i
JOIN sys.objects o
  ON o.object_id = i.object_id
JOIN sys.schemas s
  ON s.schema_id = o.schema_id
JOIN sys.index_columns ic
  ON ic.object_id = i.object_id
 AND ic.index_id = i.index_id
JOIN sys.columns c
  ON c.object_id = ic.object_id
 AND c.column_id = ic.column_id
WHERE o.type = 'U'
  AND i.is_hypothetical = 0
  AND ic.is_included_column = 0
  AND ic.key_ordinal > 0
ORDER BY s.name, o.name, i.name, ic.key_ordinal
""",
    lambda r: record(
        "Indexes",
        "Q07",
        SchemaName=value(r, "SchemaName"),
        TableName=value(r, "TableName"),
        ColumnName=value(r, "ColumnName"),
        IndexName=value(r, "IndexName"),
        IsUnique=value(r, "IsUnique"),
        IsPrimaryKey=value(r, "IsPrimaryKey"),
        KeyOrdinal=value(r, "KeyOrdinal"),
    ),
)


# Focused aggregate confirmation probes. These return no person names,
# contact data, task text, attendance detail, or arbitrary sample records.
run_probe(
    "F01", "TaskStatusUsage",
    """
SELECT ts.Id AS LookupId, ts.Code, ts.Description, ts.Hardwired,
       COUNT(tn.TaskNoteId) AS UsageCount
FROM lookup.TaskStatus ts
LEFT JOIN dbo.TaskNote tn ON tn.StatusId = ts.Id
GROUP BY ts.Id, ts.Code, ts.Description, ts.Hardwired
ORDER BY ts.Id
""",
    lambda r: record("TaskStatusUsage", "F01", TableName="TaskStatus", ColumnName="StatusId", DataType=value(r, "Code"), ApproxRowCount=value(r, "UsageCount"), Finding="Id={}; Description={}; Hardwired={}".format(text(value(r, "LookupId")), text(value(r, "Description")), text(value(r, "Hardwired")))),
)

run_probe(
    "F02", "UnmappedTaskStatus",
    """
SELECT tn.StatusId, COUNT(*) AS UsageCount
FROM dbo.TaskNote tn
LEFT JOIN lookup.TaskStatus ts ON ts.Id = tn.StatusId
WHERE ts.Id IS NULL
GROUP BY tn.StatusId
ORDER BY tn.StatusId
""",
    lambda r: record("UnmappedTaskStatus", "F02", TableName="TaskNote", ColumnName="StatusId", ApproxRowCount=value(r, "UsageCount"), Finding="Unmapped StatusId={}".format(text(value(r, "StatusId")))),
)

run_probe(
    "F03", "TaskNoteBehavior",
    """
SELECT CASE WHEN tn.IsNote IS NULL THEN 'NULL' ELSE CAST(tn.IsNote AS VARCHAR(20)) END AS IsNoteValue,
       tn.StatusId, ts.Code, ts.Description, COUNT(*) AS UsageCount
FROM dbo.TaskNote tn
LEFT JOIN lookup.TaskStatus ts ON ts.Id = tn.StatusId
GROUP BY CASE WHEN tn.IsNote IS NULL THEN 'NULL' ELSE CAST(tn.IsNote AS VARCHAR(20)) END,
         tn.StatusId, ts.Code, ts.Description
ORDER BY IsNoteValue, tn.StatusId
""",
    lambda r: record("TaskNoteBehavior", "F03", TableName="TaskNote", ColumnName="IsNote", DataType=value(r, "Code"), ApproxRowCount=value(r, "UsageCount"), Finding="IsNote={}; StatusId={}; StatusDescription={}".format(text(value(r, "IsNoteValue")), text(value(r, "StatusId")), text(value(r, "Description")))),
)

run_probe(
    "F04", "OrganizationStatusUsage",
    """
SELECT os.Id AS LookupId, os.Code, os.Description, os.Active,
       COUNT(o.OrganizationId) AS UsageCount
FROM lookup.OrganizationStatus os
LEFT JOIN dbo.Organizations o ON o.OrganizationStatusId = os.Id
GROUP BY os.Id, os.Code, os.Description, os.Active
ORDER BY os.Id
""",
    lambda r: record("OrganizationStatusUsage", "F04", TableName="OrganizationStatus", ColumnName="OrganizationStatusId", DataType=value(r, "Code"), ApproxRowCount=value(r, "UsageCount"), Finding="Id={}; Description={}; Active={}".format(text(value(r, "LookupId")), text(value(r, "Description")), text(value(r, "Active")))),
)

run_probe(
    "F05", "OrganizationTypeUsage",
    """
SELECT ot.Id AS LookupId, ot.Code, ot.Description, ot.Attendance, ot.ShowInMobile,
       COUNT(o.OrganizationId) AS UsageCount
FROM lookup.OrganizationType ot
LEFT JOIN dbo.Organizations o ON o.OrganizationTypeId = ot.Id
GROUP BY ot.Id, ot.Code, ot.Description, ot.Attendance, ot.ShowInMobile, ot.SortOrder
ORDER BY ot.SortOrder, ot.Id
""",
    lambda r: record("OrganizationTypeUsage", "F05", TableName="OrganizationType", ColumnName="OrganizationTypeId", DataType=value(r, "Code"), ApproxRowCount=value(r, "UsageCount"), Finding="Id={}; Description={}; Attendance={}; ShowInMobile={}".format(text(value(r, "LookupId")), text(value(r, "Description")), text(value(r, "Attendance")), text(value(r, "ShowInMobile")))),
)

run_probe(
    "F06", "MemberTypeUsage",
    """
SELECT mt.Id AS LookupId, mt.Code, mt.Description, mt.Pending, mt.Inactive,
       mt.AttendanceTypeId, COUNT(om.PeopleId) AS UsageCount
FROM lookup.MemberType mt
LEFT JOIN dbo.OrganizationMembers om ON om.MemberTypeId = mt.Id
GROUP BY mt.Id, mt.Code, mt.Description, mt.Pending, mt.Inactive, mt.AttendanceTypeId
ORDER BY mt.Id
""",
    lambda r: record("MemberTypeUsage", "F06", TableName="MemberType", ColumnName="MemberTypeId", DataType=value(r, "Code"), ReferencedColumn=value(r, "AttendanceTypeId"), ApproxRowCount=value(r, "UsageCount"), Finding="Id={}; Description={}; Pending={}; Inactive={}".format(text(value(r, "LookupId")), text(value(r, "Description")), text(value(r, "Pending")), text(value(r, "Inactive")))),
)

run_probe(
    "F07", "DivOrgFanout",
    """
SELECT x.DivisionLinkCount, COUNT(*) AS OrganizationCount
FROM (
    SELECT o.OrganizationId, COUNT(d.DivId) AS DivisionLinkCount
    FROM dbo.Organizations o
    LEFT JOIN dbo.DivOrg d ON d.OrgId = o.OrganizationId
    GROUP BY o.OrganizationId
) x
GROUP BY x.DivisionLinkCount
ORDER BY x.DivisionLinkCount
""",
    lambda r: record("DivOrgFanout", "F07", TableName="DivOrg", ColumnName="DivId", ApproxRowCount=value(r, "OrganizationCount"), Finding="DivisionLinkCount={}".format(text(value(r, "DivisionLinkCount")))),
)

run_probe(
    "F08", "OrgScheduleDayUsage",
    """
SELECT os.SchedDay, COUNT(*) AS ScheduleRowCount,
       COUNT(DISTINCT os.OrganizationId) AS OrganizationCount,
       MIN(os.SchedTime) AS EarliestSchedTime, MAX(os.SchedTime) AS LatestSchedTime
FROM dbo.OrgSchedule os
GROUP BY os.SchedDay
ORDER BY os.SchedDay
""",
    lambda r: record("OrgScheduleDayUsage", "F08", TableName="OrgSchedule", ColumnName="SchedDay", ApproxRowCount=value(r, "ScheduleRowCount"), Finding="SchedDay={}; OrganizationCount={}; EarliestSchedTime={}; LatestSchedTime={}".format(text(value(r, "SchedDay")), text(value(r, "OrganizationCount")), text(value(r, "EarliestSchedTime")), text(value(r, "LatestSchedTime")))),
)

run_probe(
    "F09", "MeetingColumnPopulation",
    """
SELECT COUNT(*) AS MeetingRowCount,
       COUNT(CASE WHEN NumPresent IS NOT NULL THEN 1 END) AS NumPresentCount,
       COUNT(CASE WHEN NumVstMembers IS NOT NULL THEN 1 END) AS NumVstMembersCount,
       COUNT(CASE WHEN NumRepeatVst IS NOT NULL THEN 1 END) AS NumRepeatVstCount,
       COUNT(CASE WHEN NumNewVisit IS NOT NULL THEN 1 END) AS NumNewVisitCount,
       MIN(MeetingDate) AS EarliestMeetingDate, MAX(MeetingDate) AS LatestMeetingDate
FROM dbo.Meetings
""",
    lambda r: record("MeetingColumnPopulation", "F09", TableName="Meetings", ColumnName="visitor aggregate columns", ApproxRowCount=value(r, "MeetingRowCount"), Finding="NumPresent={}; NumVstMembers={}; NumRepeatVst={}; NumNewVisit={}; Earliest={}; Latest={}".format(text(value(r, "NumPresentCount")), text(value(r, "NumVstMembersCount")), text(value(r, "NumRepeatVstCount")), text(value(r, "NumNewVisitCount")), text(value(r, "EarliestMeetingDate")), text(value(r, "LatestMeetingDate")))),
)

run_probe(
    "F10", "TaskNoteKeyProfile",
    """
SELECT COUNT(*) AS TotalRows, COUNT(TaskNoteId) AS NonNullCount,
       COUNT(DISTINCT TaskNoteId) AS DistinctCount,
       MIN(TaskNoteId) AS MinimumValue, MAX(TaskNoteId) AS MaximumValue
FROM dbo.TaskNote
""",
    lambda r: record("TaskNoteKeyProfile", "F10", TableName="TaskNote", ColumnName="TaskNoteId", ApproxRowCount=value(r, "TotalRows"), Finding="NonNullCount={}; DistinctCount={}; Minimum={}; Maximum={}".format(text(value(r, "NonNullCount")), text(value(r, "DistinctCount")), text(value(r, "MinimumValue")), text(value(r, "MaximumValue")))),
)


# A summary row makes the export self-describing even after it leaves TouchPoint.
rows.insert(0, record(
    "ExportMetadata",
    "EXPORT",
    Finding="RockPointe TouchPoint data dictionary metadata export. Contains schema metadata and aggregate counts only; no arbitrary table rows or PII were selected.",
))

structural_rows = [r for r in rows if not r["QueryId"].startswith("F")]
focused_rows = [r for r in rows if r["QueryId"].startswith("F")]
structural_status = [s for s in query_status if not s["QueryId"].startswith("F")]
focused_status = [s for s in query_status if s["QueryId"].startswith("F")]

json_rows = json.dumps(structural_rows).replace("</", "<\\/")
json_focused_rows = json.dumps(focused_rows).replace("</", "<\\/")
json_columns = json.dumps(EXPORT_COLUMNS)
json_status = json.dumps(query_status).replace("</", "<\\/")

ok_count = len([s for s in structural_status if s["Status"] == "OK"])
error_count = len(structural_status) - ok_count
focused_ok_count = len([s for s in focused_status if s["Status"] == "OK"])
focused_error_count = len(focused_status) - focused_ok_count

print("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RockPointe Data Dictionary Export</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#f3f6f9;color:#1f2937;margin:0;padding:24px}
.card{max-width:960px;margin:0 auto;background:white;border:1px solid #dbe3ea;border-radius:10px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
h1{font-size:22px;margin:0 0 8px}.muted{color:#64748b}.summary{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.pill{padding:8px 12px;border-radius:999px;font-weight:700;font-size:13px}.ok{background:#dcfce7;color:#166534}.warn{background:#fef3c7;color:#92400e}.info{background:#dbeafe;color:#1e40af}
button{background:#1d4ed8;color:white;border:0;border-radius:7px;padding:11px 16px;font-size:14px;font-weight:700;cursor:pointer}button:hover{background:#1e40af}
table{width:100%%;border-collapse:collapse;margin-top:20px;font-size:12px}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;vertical-align:top}th{background:#f8fafc}.error{color:#b91c1c;word-break:break-word}code{background:#eef2f7;padding:2px 5px;border-radius:4px}
</style>
</head>
<body>
<div class="card">
  <h1>RockPointe Data Dictionary Export</h1>
  <p class="muted">One-shot metadata inventory for <code>DB_REFERENCE.md</code>. This export contains schema metadata and aggregate counts—not arbitrary church records.</p>
  <div class="summary">
    <span class="pill info">%s CSV rows</span>
    <span class="pill ok">%s probes passed</span>
    <span class="pill warn">%s probes blocked</span>
  </div>
  <button type="button" onclick="downloadCSV()">Download Structural CSV</button>
  <p class="muted">File name: <code>rockpointe-touchpoint-data-dictionary-YYYY-MM-DD.csv</code></p>
  <button type="button" onclick="downloadFocusedCSV()">Download Focused Confirmation CSV</button>
  <p class="muted"><strong>%s focused rows; %s focused probes passed; %s blocked.</strong><br>File name: <code>rockpointe-touchpoint-focused-confirmation-YYYY-MM-DD.csv</code></p>
  <table>
    <thead><tr><th>Query</th><th>Section</th><th>Status</th><th>Rows</th><th>Error</th></tr></thead>
    <tbody id="statusRows"></tbody>
  </table>
</div>
<script>
var exportRows=%s;
var focusedRows=%s;
var exportColumns=%s;
var queryStatus=%s;
function csvValue(v){
  if(v===null||v===undefined){v='';}
  v=String(v);
  return '"'+v.replace(/"/g,'""')+'"';
}
function downloadCSV(){
  var lines=[exportColumns.map(csvValue).join(',')];
  exportRows.forEach(function(row){
    lines.push(exportColumns.map(function(column){return csvValue(row[column]);}).join(','));
  });
  var blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{type:'text/csv;charset=utf-8'});
  var link=document.createElement('a');
  link.href=URL.createObjectURL(blob);
  link.download='rockpointe-touchpoint-data-dictionary-'+new Date().toISOString().slice(0,10)+'.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(function(){URL.revokeObjectURL(link.href);},1000);
}
function downloadFocusedCSV(){
  var lines=[exportColumns.map(csvValue).join(',')];
  focusedRows.forEach(function(row){
    lines.push(exportColumns.map(function(column){return csvValue(row[column]);}).join(','));
  });
  var blob=new Blob(['\\ufeff'+lines.join('\\r\\n')],{type:'text/csv;charset=utf-8'});
  var link=document.createElement('a');
  link.href=URL.createObjectURL(blob);
  link.download='rockpointe-touchpoint-focused-confirmation-'+new Date().toISOString().slice(0,10)+'.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(function(){URL.revokeObjectURL(link.href);},1000);
}
(function(){
  var body=document.getElementById('statusRows');
  queryStatus.forEach(function(status){
    var tr=document.createElement('tr');
    [status.QueryId,status.Section,status.Status,status.Rows,status.Error].forEach(function(cell,index){
      var td=document.createElement('td');
      td.textContent=cell===null||cell===undefined?'':String(cell);
      if(index===4&&cell){td.className='error';}
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
})();
</script>
</body>
</html>""" % (len(structural_rows), ok_count, error_count, len(focused_rows), focused_ok_count, focused_error_count, json_rows, json_focused_rows, json_columns, json_status))
