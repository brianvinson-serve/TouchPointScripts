/*
RPC Mobile App Channels — discovery / confirmation query
==========================================================
Purpose:
  Ari (Arianah Torres) and Marlene asked for a report on all mobile-app
  Channels (public and closed) that shows Involvement ID, Name, Type,
  Campus, Photo, Public/Closed, Leaders, Followers, Posts, and — the one
  thing the native Admin > Communications > Channels Excel export is
  missing — Active/Inactive status, with the ability to include/exclude
  inactive involvements.

  This query is NOT the final report. It's a one-shot confirmation pass:
  the structural data dictionary (2026-08-13 export) identified candidate
  columns/tables for every field Ari asked for, but several are guesses
  that need a live side-by-side check against the native Channels Excel
  export before RPC_ChannelReport.py gets built on top of them.

Candidate schema (from data-dictionary-expander structural export,
2026-08-13 — NOT yet confirmed against live values or the native export):
  - Organizations.MobileChannelEnabled  -> "has a Channel in the app" filter
  - Organizations.MobileChannelPrivate  -> Public (0/NULL) vs Closed (1)
  - Organizations.BadgeUrl / ImageUrl   -> two candidate "Photo" fields;
    unclear which one the app/native export actually uses. Both included
    below so you can see which one is populated on channels you know have
    a photo vs. ones you know don't.
  - lookup.OrganizationStatus 30=Active / 40=Inactive (already confirmed
    elsewhere in DB_REFERENCE.md) -> the missing Active/Inactive column.
  - OrganizationMembers, MemberTypeId = 140 (Leader) -> "Leaders" count guess.
  - OrganizationMembers, all active rows -> "Followers" count guess (no
    dedicated channel-follower table exists at RPC; UserFollower is a
    107-row person-to-person social follow table, not this).
  - UserPost.OrganizationId, DeletedDate IS NULL -> "Posts" count guess.

How to validate:
  1. Run this in TouchPoint > Admin > Advanced > Special Content > SQL Scripts.
  2. Open Admin > Communications > Channels in TouchPoint and download its
     Excel export as usual.
  3. Pick 4-5 involvements you recognize (mix of public/closed, some with
     a photo, at least one you know is inactive) and compare each column
     below against what the native export/UI shows for that same
     Involvement ID. Note any mismatch.
  4. Report back which Photo field was right, whether LeaderCount and
     FollowerCount lined up, and whether PostCount matched. That confirms
     the join pattern for the real interactive Python Script report.

Safety:
  Read-only SELECT. No participant names or contact info returned —
  organization-level metadata and counts only.
*/

SELECT
    o.OrganizationId,
    o.OrganizationName,
    o.OrganizationTypeId,
    ot.Description                         AS OrganizationType,
    o.CampusId,
    c.Description                          AS CampusName,
    o.OrganizationStatusId,
    os.Description                         AS OrganizationStatus,
    CASE WHEN o.OrganizationStatusId = 30 THEN 'Active'
         WHEN o.OrganizationStatusId = 40 THEN 'Inactive'
         ELSE 'Other (' + CAST(o.OrganizationStatusId AS VARCHAR(10)) + ')'
    END                                     AS ActiveInactive,

    o.MobileChannelEnabled,
    o.MobileChannelPrivate,
    CASE WHEN ISNULL(o.MobileChannelPrivate, 0) = 0 THEN 1 ELSE 0 END
                                             AS IsPublicGuess,

    o.BadgeUrl,
    CASE WHEN ISNULL(o.BadgeUrl, '') <> '' THEN 1 ELSE 0 END
                                             AS HasPhoto_BadgeUrlGuess,
    o.ImageUrl,
    CASE WHEN ISNULL(o.ImageUrl, '') <> '' THEN 1 ELSE 0 END
                                             AS HasPhoto_ImageUrlGuess,

    leaderStats.LeaderCountGuess,
    followerStats.FollowerCountGuess,
    postStats.PostCountGuess

FROM dbo.Organizations o
LEFT JOIN lookup.OrganizationType ot ON ot.Id = o.OrganizationTypeId
LEFT JOIN lookup.OrganizationStatus os ON os.Id = o.OrganizationStatusId
LEFT JOIN lookup.Campus c ON c.Id = o.CampusId

OUTER APPLY (
    SELECT COUNT(*) AS LeaderCountGuess
    FROM dbo.OrganizationMembers om
    WHERE om.OrganizationId = o.OrganizationId
      AND om.MemberTypeId = 140
      AND om.InactiveDate IS NULL
) leaderStats

OUTER APPLY (
    SELECT COUNT(*) AS FollowerCountGuess
    FROM dbo.OrganizationMembers om
    WHERE om.OrganizationId = o.OrganizationId
      AND om.InactiveDate IS NULL
) followerStats

OUTER APPLY (
    SELECT COUNT(*) AS PostCountGuess
    FROM dbo.UserPost up
    WHERE up.OrganizationId = o.OrganizationId
      AND up.DeletedDate IS NULL
) postStats

WHERE o.MobileChannelEnabled = 1

ORDER BY
    ActiveInactive,
    c.Description,
    o.OrganizationName;
