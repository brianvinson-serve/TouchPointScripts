# Roll Sheet (TPxi, RPC fork)

Configurable rollsheet/roster generator. Upstream by Ben Swaby (TPxi Software, LLC) — https://github.com/bswaby/Touchpoint/tree/main/TPxi/Roll%20Sheet. Build reusable configs (source Program/Division or a specific involvement list, columns, layout, sort, and per-config extra data like registration answers or RecReg emergency/medical fields) through an in-app UI, then generate print-ready roll sheets.

## Modified for RPC deployment

Upstream ships a self-update feature: a background version check against `scripts.displaycache.com` on every page load, and an "Update Now" button that fetches new source from `touchpoint-scripts.bswaby.workers.dev` and overwrites this Special Content script in place via `model.WriteContentPython` (a raw write with, per upstream's own code comment, no TouchPoint-side role check). Brian asked not to leave that path open on RPC's instance, so it's been fully removed from `TPxi_RollSheet.py` in this folder:

- The `apply_update` server-side action handler.
- The client-side `checkForAppUpdate()` / update banner / `applyAppUpdate()`.
- The `DC_API_BASE` / `DC_API_WORKER` constants those depended on.

Nothing else was changed. To pick up a real upstream update, pull the latest `TPxi_RollSheet.py` from Ben's repo by hand and re-apply this same removal (see the comments left at the removal sites in this file) rather than re-enabling the auto-update path.

## Known behavior gap — not yet decided

Unlike `renew-roster-report/AD_ReNewRosterReport.py` (which explicitly limits to `MemberTypeId IN (140, 220)`), this tool's member query has no `MemberTypeId` filter — it lists every `OrganizationMembers` row for the selected org(s), including InActive (230), Prospect (311), Volunteer (710), Coach (136) alongside Leader/Member. Test against a real RPC roster before handing this to a teacher; add a filter if it turns out to matter for how RPC's orgs are actually populated.

## Deployment

1. `Admin > Advanced > Special Content > Python Scripts > +New`
2. Name it `TPxi_RollSheet`, paste in `TPxi_RollSheet.py`, save.
3. Visit `/PyScriptForm/TPxi_RollSheet`, click **+ New Config** to build the first rollsheet.

Declares `#roles=Edit` (upstream default) — read-only in the sense that it only ever queries and prints, but it does persist its own configs to a `RollSheet_Configs` Special Content Text key via `model.WriteContentText`. Not yet live-tested against RPC's TouchPoint instance.
