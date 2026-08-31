# Mobile App Channels Report

Church-wide report of every involvement with a mobile-app Channel enabled — built for Arianah Torres (Men's Ministry Assistant & Social Media Associate) and Marlene Godinez, requested by email 2026-08-31.

## Why this exists

The native `Admin > Communications > Channels` Excel export lists every channel-enabled involvement, including inactive ones, but has no column distinguishing active from inactive. Ari's actual workflow is app cleanup: find past-due/inactive involvements that still have a channel enabled in the app, and get staff to disable them. This report adds the missing Active/Inactive column and a Status filter so "Inactive Only" becomes a ready-made cleanup worklist.

## What it does

`RPC_ChannelReport.py` (TouchPoint Special Content Python Script, read-only) renders a single sortable table — no ministry/division picker, no row-level security. It's a small named-audience tool (Ari, Marlene, Brian), not a self-service report for arbitrary staff.

Columns: Involvement ID, Name, Type, Campus, Photo (✓/blank), Public (✓/blank — unchecked means Closed), Leaders (count), Followers (count), Posts (count), Status (Active/Inactive).

A **Status** dropdown (All / Active Only / Inactive Only) reruns the query server-side via a GET form. Column headers are **click-to-sort** (client-side JS, ascending/descending toggle, numeric-aware for Involvement ID/Leaders/Followers/Posts) — no server round-trip, since the table tops out around a few hundred rows. A **Download CSV** button builds a CSV client-side from the rendered table (same pattern as `student-contact-export/SM_StudentContactExport.py`); because it reads the table's current DOM order, exporting after sorting a column exports in that sorted order automatically.

## Schema (confirmed live 2026-08-31 — see `DB_REFERENCE.md`, "Mobile App Channels")

| Field | Source |
|---|---|
| "has a Channel" filter | `Organizations.MobileChannelEnabled = 1` |
| Public/Closed | `Organizations.MobileChannelPrivate` (0/NULL = public, 1 = closed) |
| Photo | `Organizations.ImageUrl` — **not** `BadgeUrl`. Confirmed by checking the live app: RockPointe Church (OrgId 3506) has `ImageUrl` set and no `BadgeUrl`, and its channel clearly shows a photo. |
| Active/Inactive | `Organizations.OrganizationStatusId` (30 = Active, 40 = Inactive) |
| Leaders | `OrganizationMembers` rows, `MemberTypeId = 140` (Leader), `InactiveDate IS NULL` |
| Followers | `OrganizationMembers` active row count. Confirmed live: RockPointe Church's app screen shows "889 Members" — an exact match. (The app itself says "Members"; the report uses Ari's requested label "Followers" for the same number.) |
| Posts | `dbo.UserPost` rows, `OrganizationId` match, `DeletedDate IS NULL` |

## How the schema was found

No existing tool in this repo, `bswaby/Touchpoint`, or `TenthPres/TouchPointScripts` covers Channels, and TouchPoint's public docs don't document the underlying tables. The candidate columns were found by structurally searching the existing 2026-08-13 full data-dictionary export (`data-dictionary-expander/exports/2026-08-13/`) for `Channel`/`Follow`/`Post`/`Photo`-shaped columns — no live query needed for that part. A one-shot confirmation query, `data-dictionary-expander/sql/focused/RPC_ChannelReportDiscovery.sql`, was then run live (252 channel-enabled involvements: 144 Active / 108 Inactive) and its output validated against the live mobile app — see `DB_REFERENCE.md` for the full reasoning per field.

## Deploy

`Admin > Advanced > Special Content > Python Scripts > +New`, script name `RPC_ChannelReport`, paste in the file contents. Access via `/PyScript/RPC_ChannelReport` so the Status dropdown's Apply button (a GET form back to the same URL) works correctly. No email is sent; nothing is written.

## Status

Built 2026-08-31. Syntax-checked (`python3 -m py_compile`) and smoke-tested locally with mocked `q`/`model` objects: verified the Status filter actually changes which rows come back (all/active/inactive/invalid-falls-back-to-all), HTML escaping on a name containing quotes/commas/ampersands doesn't break table structure, and the CSV `data-csv` attributes and checkmark markers render correctly. Click-to-sort headers added same day; the sort/compare logic (numeric vs text, `data-csv`-aware, ascending/descending toggle) was unit-tested standalone in Node against mock row objects, separate from the Python-rendered HTML.

**Still needs a full live pass inside TouchPoint** — the underlying SQL was run and validated live (`RPC_ChannelReportDiscovery.sql`), but this specific script (picker chrome, CSV export JS, checkmark rendering, the Status dropdown as an actual `/PyScript/` request) has not been deployed and exercised inside TouchPoint yet.
