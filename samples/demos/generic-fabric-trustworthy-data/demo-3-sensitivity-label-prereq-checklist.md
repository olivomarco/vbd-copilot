# Demo 3 - Sensitivity Label Inheritance: Pre-Session Prerequisite Checklist
## Microsoft Fabric - Trustworthy Data Demo Series

**Audience:** Solution Engineer (SE) running the demo  
**When to use:** Complete every item the morning of the session, before the customer arrives.  
**Estimated check time:** 20 minutes

---

## SECTION A - Microsoft 365 / Purview Licensing

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| A1 | Demo user has Microsoft 365 E3 or E5 license (or Purview Information Protection P1/P2) | | Required for sensitivity labels in Fabric |
| A2 | Fabric tenant admin account has Compliance Administrator or Global Administrator role in M365 admin center | | Needed to verify label policies |

---

## SECTION B - Sensitivity Labels in Purview Compliance Portal

Navigate to: **https://compliance.microsoft.com -> Information protection -> Labels**

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| B1 | A leaf label named "Confidential" exists (NOT a parent label - must have no child sublabels) | | Parent labels cannot be applied to Fabric items |
| B2 | A leaf label named "Highly Confidential" exists under the same parent (or as a standalone leaf) | | Used for the escalation step of the demo |
| B3 | "Confidential" label priority is LOWER than "Highly Confidential" (Fabric respects label priority order - higher number = more sensitive) | | Verify in Labels pane - priority shown in column |
| B4 | Neither "Confidential" nor "Highly Confidential" have encryption enabled (Fabric items with encrypted labels cannot be committed to Git) | | If encryption is required by policy, use a test label without encryption for the demo |

Navigate to: **https://compliance.microsoft.com -> Information protection -> Label policies**

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| B5 | A label policy exists that includes both "Confidential" and "Highly Confidential" labels | | Labels not in a published policy are invisible to users |
| B6 | The demo presenter account is in scope for the label policy (either directly or via group membership) | | Use "Edit policy -> Choose users and groups" to verify |
| B7 | Policy has been published for at least 24 hours (sync delay) | | If recently published, labels may not appear in Fabric UI yet |

---

## SECTION C - Fabric Tenant Admin Settings

Navigate to: **Fabric Admin portal -> Tenant settings -> Information protection**

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| C1 | "Allow users to apply sensitivity labels for content" is ENABLED | | Without this, the label picker is not available in Fabric |
| C2 | "Automatically apply sensitivity labels to downstream content" is ENABLED | | This drives the label cascade (the "tsunami" WOW moment) |
| C3 | "Users can export items with sensitivity labels" is ENABLED (if Git integration is also being demoed) | | Without this, commits are blocked on labeled items |

---

## SECTION D - Fabric Workspace and Item Pre-Check

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| D1 | Lakehouse "LH_SecurityDemo" exists in the demo workspace | | Or substitute your actual Lakehouse name |
| D2 | SQL analytics endpoint for LH_SecurityDemo has NO existing sensitivity label | | Pre-existing manual labels are NOT overwritten by inheritance - this would break the demo |
| D3 | Default semantic model for LH_SecurityDemo has NO existing sensitivity label | | Same reason as D2 |
| D4 | No Power BI reports based on the default semantic model already exist in the workspace (or if they do, confirm they have no existing sensitivity labels) | | Clean slate ensures label inheritance is visible from scratch |
| D5 | Workspace has fewer than 80 items total | | Downstream inheritance caps at 80 items; larger workspaces may have partial propagation |

---

## SECTION E - Purview Hub Access (for Step 6 of Demo 3)

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| E1 | Admin monitoring workspace is visible in workspace list (or you can navigate to it directly) | | Created automatically by Fabric for Fabric admins |
| E2 | Purview Hub report opens without errors | | Open it once before the session to confirm no permission issues |
| E3 | Sensitivity labels tab in Purview Hub shows existing label count (even if zero) | | If tab is blank, confirm admin account has Fabric admin + Purview viewer permissions |
| E4 | Purview compliance portal audit log is accessible at https://compliance.microsoft.com -> Audit | | Pre-filter to last 24 hours to confirm audit trail is active |

---

## SECTION F - Demo Flow Dry Run

| # | Check | Pass/Fail | Notes |
|---|-------|-----------|-------|
| F1 | Open LH_SecurityDemo in Fabric; confirm sensitivity indicator (shield icon) is visible in header | | If not visible, revisit tenant setting C1 |
| F2 | Click sensitivity indicator; confirm "Confidential" and "Highly Confidential" labels appear in the picker | | If missing, revisit label policy scope (B6) and sync delay (B7) |
| F3 | Apply "Confidential" and confirm SQL endpoint + semantic model pick up the label automatically | | Wait up to 2 minutes for propagation; if not seen after 5 min, check tenant setting C2 |
| F4 | Create an auto-generated report from the semantic model; confirm it inherits "Confidential" | | |
| F5 | Escalate to "Highly Confidential" and confirm cascade to all 3 downstream items | | |
| F6 | Remove all labels - reset Lakehouse, SQL endpoint, semantic model, and any report to unlabeled state before the real session | | The live session must start with a clean (unlabeled) Lakehouse for the demo to land correctly |

---

## RECOVERY PLAN (if demo breaks live)

**Symptom:** Sensitivity picker does not show labels  
**Fix:** Refresh the page. If still missing, open a new InPrivate window and reload the Fabric portal. Confirm label policy sync (B7).

**Symptom:** Downstream items do NOT inherit the label after applying to Lakehouse  
**Fix:** Verify tenant setting C2 is enabled. Wait 2-3 minutes and refresh workspace list. If still not propagated, manually apply the label to the SQL endpoint as a fallback and explain that the automatic inheritance setting required admin propagation time.

**Symptom:** "Highly Confidential" downgrade back to "Confidential" succeeds (should be blocked)  
**Fix:** This can happen if both labels have the same priority value. Verify label priority order in Purview compliance portal (B3). If labels are equal priority during the session, explain the concept verbally and show the Purview audit log to demonstrate traceability instead.

**Symptom:** Purview Hub report is blank or permission denied  
**Fix:** Navigate directly to https://app.powerbi.com/groups/0000-admin-monitoring and open the Information protection report. If still blocked, switch to the Purview compliance portal audit log as the verification surface.

---

## HELPFUL LINKS (verified, do not modify)

- Sensitivity labels in Fabric: https://learn.microsoft.com/en-us/fabric/governance/information-protection
- Downstream inheritance: https://learn.microsoft.com/en-us/fabric/governance/service-security-sensitivity-label-downstream-inheritance
- Applying labels in Fabric: https://learn.microsoft.com/en-us/fabric/fundamentals/apply-sensitivity-labels
- Purview Hub: https://learn.microsoft.com/en-us/fabric/governance/use-microsoft-purview-hub
