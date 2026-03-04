# Microsoft Fabric - Trustworthy Data
## Complete Demo Guide

**Level:** L300 - Technical  
**Audience:** Data Engineers + Data Stewards  
**Estimated Duration:** ~1h 45m (approx. 20 min per demo)  
**Environment Required:** Live F-capacity Fabric tenant with Purview admin access  
**CI/CD Platform:** GitHub Actions  
**Last Updated:** March 2026

---

## Table of Contents

1. [Session Overview](#session-overview)
2. [Environment Pre-Check (Morning of Session)](#environment-pre-check)
3. [Demo 1 - OneLake Security Role Layering](#demo-1)
4. [Demo 2 - Row-Level Security on Lakehouse SQL Endpoint](#demo-2)
5. [Demo 3 - Sensitivity Label Inheritance](#demo-3)
6. [Demo 4 - Git Integration + 3-Stage Deployment Pipeline](#demo-4)
7. [Demo 5 - fabric-cicd in GitHub Actions](#demo-5)
8. [Appendix - Companion File Index](#appendix)

---

## Session Overview

This demo series demonstrates five interconnected pillars of trustworthy, governed data engineering on Microsoft Fabric. The story arc moves from data-plane access control (who can see what) through information classification (what is sensitive) and into engineering discipline (how we deploy safely).

Each demo is designed to stand alone if time is limited, but they build on each other when run sequentially - Demos 1 and 2 share the same Lakehouse and test users, Demo 4 creates the Git repository that Demo 5 automates.

**Story arc for the audience:**  
"We are going to show you that in Fabric, the guardrails are built into the platform. You do not need a custom security layer on top of your data warehouse. You do not need a separate deployment tool. You do not need a manual labeling workflow. All of it is native, auditable, and enforceable today."

---

## Environment Pre-Check

Run these checks the morning of the session, before the customer arrives.

### Global Requirements

- [ ] Fabric workspace on F-capacity (SKU F2 minimum; trial capacity does not support all features)
- [ ] Presenter account has Fabric Workspace Admin role on all demo workspaces
- [ ] Presenter account has Purview Compliance Administrator or Global Administrator role
- [ ] Two test user accounts provisioned in Entra ID:
      `demo-user-north@<tenant>.onmicrosoft.com`
      `demo-user-south@<tenant>.onmicrosoft.com`
- [ ] Both test users have Microsoft 365 licenses (for Purview label visibility)
- [ ] Fabric tenant settings verified (see each demo section for specifics)

### Workspace Setup

- [ ] Lakehouse named `LH_SecurityDemo` exists in the primary demo workspace
- [ ] `demo-1-onelake-security-setup.py` has been run successfully inside Fabric
- [ ] `demo-2-rls-setup.py` has been run successfully inside Fabric
- [ ] Workspace for Demo 4 (`DataEng-Dev`) contains at least one Notebook
- [ ] GitHub repository created and script `demo-4-git-pipeline-setup.sh` has been run

### Browser Windows to Pre-Open

- [ ] Presenter Fabric portal - primary screen
- [ ] InPrivate window logged in as `demo-user-north` - secondary screen or second monitor
- [ ] InPrivate window logged in as `demo-user-south` - third if available; otherwise swap with north
- [ ] GitHub repository in a browser tab
- [ ] GitHub Actions tab in a browser tab (for Demo 5)
- [ ] Purview compliance portal (https://compliance.microsoft.com) - background tab

---

## Demo 1 - OneLake Security Role Layering {#demo-1}

**Goal:** Show that OneLake security roles provide folder-scoped and table-scoped access with deny-by-default semantics, without writing a single line of T-SQL GRANT. The same SQL query on the same endpoint returns different results per user identity.

**WOW Moment:** Side-by-side browser windows showing the same SELECT statement returning different rows for different users. Then reveal the Contributor role bypass to show the audience exactly where the boundary is.

**Companion File:** `outputs/demos/generic-fabric-trustworthy-data/demo-1-onelake-security-setup.py`

**Estimated Time:** ~20 minutes

---

### Narrative Context

> PRESENTER NOTES - say approximately this:
>
> "Traditional data warehouses enforce row and table access through T-SQL GRANT statements and stored procedures. You have a security admin writing and maintaining those scripts, you have rotation risk when users change teams, and you have no native UI to inspect who can see what. 
>
> Fabric flips this model. OneLake security is configured in the portal, it's role-based, and it's enforced consistently whether the query comes from a notebook, the SQL analytics endpoint, or a Power BI report. The data plane and the security plane are unified.
>
> Let me show you what deny-by-default looks like in practice."

---

### Prerequisites

- [ ] Fabric workspace on F-capacity
- [ ] Lakehouse named `LH_SecurityDemo` exists
- [ ] `demo-1-onelake-security-setup.py` has been run - tables `NorthSalesData` and `SouthSalesData` exist
- [ ] `demo-user-north` and `demo-user-south` have Viewer workspace role
- [ ] Both users have Fabric Read item permission on `LH_SecurityDemo`
- [ ] SQL analytics endpoint is visible for `LH_SecurityDemo`
- [ ] Two browser windows open and logged in as respective test users

---

### Step-by-Step Instructions

**Step 1 - Enable OneLake security on the Lakehouse**

1. Open `LH_SecurityDemo` in the Fabric portal (presenter account)
2. Click the three-dot menu next to the Lakehouse name
3. Select "Manage OneLake security (preview)"
4. Read the confirmation dialog - it explains that switching to User's identity mode will affect SQL endpoint behavior
5. Click Continue

> PRESENTER NOTES: "Notice the warning here about switching modes. This is a one-way-at-a-time operation - you can switch back, but doing so would destroy any SQL roles you configured in classic mode. Fabric is explicit about this tradeoff."

**Step 2 - Delete the DefaultReader role**

1. In the OneLake security pane, locate the `DefaultReader` role
2. Check the checkbox next to DefaultReader
3. Click Delete and confirm

> PRESENTER NOTES: "This is the most critical setup step. DefaultReader grants every workspace member read access to all data. If we leave it, our per-region roles are meaningless - everyone would see everything through DefaultReader. The very first thing you do when enabling OneLake security is audit and delete this role if you want deny-by-default semantics."

**Step 3 - Create the NorthRegion role**

1. In Manage OneLake security -> click New
2. Role name: `NorthRegion`
3. Permission: Grant, Read
4. Click Add data
5. Browse Lakehouse -> Tables
6. Check `NorthSalesData`
7. Click Add data
8. Click Add members
9. Add: `demo-user-north@<tenant>.onmicrosoft.com`
10. Click Create role

> PRESENTER NOTES: "We are binding a data asset - a specific table - to a specific identity. No stored procs. No GRANT. The scope is the table, the subjects are individuals or Entra security groups, and the permission flows from the role definition."

**Step 4 - Create the SouthRegion role**

1. Click New
2. Role name: `SouthRegion`
3. Permission: Grant, Read
4. Add data: `SouthSalesData`
5. Add members: `demo-user-south@<tenant>.onmicrosoft.com`
6. Click Create role

**Step 5 - Switch SQL endpoint to User's identity mode**

1. In the Lakehouse editor, switch to SQL analytics endpoint view (toggle at top)
2. Click the Security tab. *Alternative path if "Security tab" is not visible: click the gear/settings icon in the SQL analytics endpoint toolbar, or open the endpoint Properties pane. Look for "Query execution mode" or "Identity mode" and switch from "Fixed identity" to "User's identity". UI labeling may vary by Fabric release track and tenant region.*
3. Select "User's identity" mode
4. Confirm the mode change

> PRESENTER NOTES: "User's identity mode means that when a query hits the SQL endpoint, Fabric evaluates permissions based on who is calling, not who owns the endpoint. This is what makes OneLake security apply to SQL queries. Without this step, SQL falls back to classic mode and ignores the roles we just created."

**Step 6 - Run the live test (WOW Moment)**

1. On the demo-user-north window:
   ```sql
   SELECT * FROM NorthSalesData;
   ```
   Shows 3 rows (Alice, Bob, Carol)

2. Still as demo-user-north:
   ```sql
   SELECT * FROM SouthSalesData;
   ```
   Result: ACCESS DENIED error

3. Switch to the demo-user-south window and run the inverse

4. Run both queries as presenter - see all 6 rows from both tables

> PRESENTER NOTES: "Same endpoint. Same query text. Different results. The access control is enforced at the data plane, not at the application layer. This is what zero-trust access on analytical data looks like. Even if a user discovers the SQL connection string and connects from SSMS, they get exactly the same filtered result."

**Step 7 - Reveal the Contributor bypass**

1. Go to workspace Settings -> Manage access
2. Temporarily elevate `demo-user-north` to Contributor role
3. Have demo-user-north re-run: `SELECT * FROM SouthSalesData;`
4. Result: all 6 rows visible
5. Restore demo-user-north to Viewer role

> PRESENTER NOTES: "Here is the architectural boundary you must understand. Admin, Member, and Contributor workspace roles bypass ALL OneLake data-plane security. This is by design - workspace contributors need to be able to build and test without security blocking them. The implication is: your test accounts for security demos must always be workspace Viewers. If you use a Contributor account, you will think your security is broken when it is working correctly. Set your workspace roles deliberately."

---

### Gotcha Reference

| Gotcha | Impact | Workaround |
|--------|--------|------------|
| Admin/Member/Contributor workspace roles bypass ALL OneLake security | Test accounts appear to see everything | Always use Viewer-role test accounts |
| DefaultReader gives everyone full access if not deleted | Roles appear ineffective | Delete DefaultReader before any role testing |
| Role changes take ~5 min; Entra group membership changes take ~1 hour | Demo appears broken after role edit | Use direct user assignment; apply changes at least 10 min before demo |
| Distribution lists are not supported | Members not added | Use individual users or Entra Security Groups only |
| OneLake security is currently incompatible with Private Links | Feature unavailable in some tenants | Confirm the demo tenant has no Private Link configuration |

---

### Recovery Steps

**Symptom:** demo-user-north sees ACCESS DENIED on NorthSalesData (should see data)  
**Fix:** Confirm the user has Fabric Read item permission on the Lakehouse (not just workspace Viewer role). Check that the NorthRegion role lists the user directly (not via a group that has not synced). Wait 5 minutes and retry.

**Symptom:** demo-user-north sees SouthSalesData data (should be denied)  
**Fix:** Confirm DefaultReader was deleted. Confirm demo-user-north is not in the SouthRegion role. Confirm demo-user-north is a Viewer, not Contributor.

**Symptom:** SQL endpoint shows "classic security" warning after switching modes  
**Fix:** Refresh the SQL analytics endpoint page. If the toggle reverts, re-apply User's identity mode and wait 2 minutes.

**If demo cannot be recovered:** Switch to the slides showing the architecture diagram and walk through the role model conceptually. Show the Manage OneLake security UI in read-only mode to display the existing NorthRegion and SouthRegion roles with their table scopes and member assignments. Explain the deny-by-default contract and the Contributor bypass verbally, using https://learn.microsoft.com/en-us/fabric/onelake/security/data-access-control-model as the backup visual.

---

## Demo 2 - Row-Level Security on Lakehouse SQL Endpoint {#demo-2}

**Goal:** Define row-level security predicates via the OneLake UI on a single unified table, and show that the same SELECT query returns different rows per user identity - with no stored procedures and no T-SQL CREATE SECURITY POLICY.

**WOW Moment:** One WHERE predicate per OneLake role enforces consistently across the SQL analytics endpoint, Spark, and Power BI. The same query, the same data, different results - all driven by a predicate you typed in a UI form.

**Companion File:** `outputs/demos/generic-fabric-trustworthy-data/demo-2-rls-setup.py`

**Estimated Time:** ~20 minutes

---

### Narrative Context

> PRESENTER NOTES - say approximately this:
>
> "In Demos 1 we restricted access at the table level. But what if you have a unified table - all regions, all departments, all customers in one place - and you want each user to see only their slice? That's row-level security. 
>
> In a traditional warehouse you'd write a security policy, define an inline table-valued function, and hope nobody accidentally joins around it. In Fabric, you write one predicate in a text box in the portal. Fabric enforces it everywhere that table is queried. No stored procs, no custom code, no chance of a join bypassing it."

---

### Prerequisites

- [ ] Demo 1 complete: OneLake security enabled, DefaultReader deleted, User's identity mode active
- [ ] `demo-2-rls-setup.py` has been run - `SalesOrders` table exists with 6 rows
- [ ] `demo-user-north` and `demo-user-south` retained with Viewer role + Lakehouse Read

---

### Step-by-Step Instructions

**Step 1 - Verify SalesOrders table is present**

1. Open `LH_SecurityDemo` in the Fabric portal
2. In the Lakehouse explorer, expand Tables
3. Confirm `SalesOrders` is listed
4. Preview it: right-click -> Preview -> show all 6 rows (3 North, 3 South)

> PRESENTER NOTES: "This is a single unified table. All regions live together. We are not splitting the data into separate tables per user the way we did in Demo 1. This is a much more realistic pattern - one fact table, multiple access profiles."

**Step 2 - Create ViewNorthOrders role with RLS predicate**

1. Three-dot menu on LH_SecurityDemo -> Manage OneLake security
2. Click New
3. Role name: `ViewNorthOrders`
4. Permission: Grant, Read
5. Click Add data -> Tables -> check `SalesOrders` -> Add data
6. Click the "..." (three-dot) menu next to `SalesOrders` in the role definition
7. Select "Row security (preview)"
8. Enter the predicate:
   ```sql
   SELECT * FROM dbo.SalesOrders WHERE Region = 'North'
   ```
   > *Note: the `dbo.` schema prefix is required. Omitting it causes the predicate to fail silently and return zero rows with no error message.*
9. Click Save
10. Click Add members
11. Add: `demo-user-north@<tenant>.onmicrosoft.com`
12. Click Create role

> PRESENTER NOTES: "Look at what we just did. We wrote a single WHERE clause. Fabric translates this into a filter that is applied every time this user queries this table, from any tool, over any interface. The predicate is: show this user only rows where Region equals North."

**Step 3 - Create ViewSouthOrders role with RLS predicate**

1. Click New
2. Role name: `ViewSouthOrders`
3. Permission: Grant, Read
4. Add data: `SalesOrders`
5. Row security: 
   ```sql
   SELECT * FROM dbo.SalesOrders WHERE Region = 'South'
   ```
6. Save; Add members: `demo-user-south@<tenant>.onmicrosoft.com`
7. Create role

**Step 4 - Run the identical query as each user (WOW Moment)**

Switch to each browser window and run this IDENTICAL query:

```sql
SELECT OrderID, SalesRep, Region, Amount
FROM SalesOrders
ORDER BY Region, OrderID;
```

Expected results:
- demo-user-north: O001, O002, O003 (all North rows only)
- demo-user-south: O004, O005, O006 (all South rows only)
- Presenter (admin): all 6 rows

> PRESENTER NOTES: "Same query text. Same table. Same SQL endpoint URL. Three different result sets. The filter is invisible to the user - they do not see a WHERE clause in their query, they just see their data. This is the gold standard for row-level security: transparent to the consumer, enforced at the platform, no way to accidentally bypass it from the application tier.
>
> And here is what I really want you to remember: this same OneLake role that filters the SQL query, also filters Spark reads through the Lakehouse connector, and also filters the Power BI report that sits on top of this semantic model. One policy, three access surfaces, zero custom code."

**Step 5 - Demonstrate multi-row count from presenter view**

Run from presenter account:
```sql
SELECT Region, COUNT(*) AS OrderCount, SUM(Amount) AS TotalAmount
FROM SalesOrders
GROUP BY Region;
```

> PRESENTER NOTES: "As admin my aggregate shows both regions. A steward auditing data volumes still sees the full picture. The RLS is per user; it's not a data transformation. The data is still there, your governance role can still audit it."

---

### Gotcha Reference

| Gotcha | Impact | Workaround |
|--------|--------|------------|
| Dynamic functions like USER_NAME() are NOT supported in predicates | Cannot build attribute-based RLS dynamically | Use role-per-user-group pattern; create one role per data segment |
| Multi-table JOIN predicates are NOT supported in Public Preview | Cannot reference lookup tables in predicates | Denormalize the filter column into the fact table |
| If a user is in two roles - one with RLS, one without - MOST PERMISSIVE wins | All rows visible even with RLS on one role | Ensure users are in exactly one role per table; never overlap a permissive role with an RLS role for the same user |
| String comparison in predicates is case-INSENSITIVE | Unexpected matches if data has mixed case | Consistent casing in data avoids confusion; document behavior for audience |

---

### Recovery Steps

**Symptom:** Row security option not visible in the three-dot menu on a table  
**Fix:** Confirm the table was added to the role first (Row security only appears after Add data). Refresh the page.

**Symptom:** Both users see all rows  
**Fix:** Confirm User's identity mode is active on the SQL endpoint. Confirm DefaultReader was deleted from the OneLake security pane. Confirm neither user is a workspace Contributor or higher.

**Symptom:** demo-user in ViewNorthOrders sees zero rows instead of 3 rows  
**Fix:** Check the predicate for a typo - Region = 'North' is case-insensitive but the column name must match exactly. Preview the SalesOrders table as admin to confirm data exists.

---

## Demo 3 - Sensitivity Label Inheritance {#demo-3}

**Goal:** Apply a "Confidential" sensitivity label to a Lakehouse once and watch it cascade automatically to the SQL analytics endpoint, the default semantic model, and a Power BI report.

**WOW Moment:** "Label tsunami" - one click on the Lakehouse, three items labeled automatically. Then escalate to "Highly Confidential" and watch it propagate again. Show the audit trail in Purview Hub.

**Companion File:** `outputs/demos/generic-fabric-trustworthy-data/demo-3-sensitivity-label-prereq-checklist.md`

**Estimated Time:** ~20 minutes

---

### Narrative Context

> PRESENTER NOTES - say approximately this:
>
> "Data classification is one of the hardest governance problems to sustain. You classify data at creation, but as it moves through pipelines, as reports are created on top of it, as SQL views abstract it - the classification is lost. Someone creates a Power BI report on confidential data and it inherits no label. The downstream consumer does not know they are looking at sensitive information.
>
> Fabric's sensitivity label inheritance solves this at the platform level. When you classify the source, the classification follows the data. Every downstream artifact is automatically labeled. You do not need to train your report builders on data classification policy - the system does it for them.
>
> Let me show you what this looks like."

---

### Prerequisites

- [ ] Microsoft 365 E3/E5 or Purview Information Protection P1/P2 per demo user
- [ ] Leaf sensitivity label "Confidential" published in Purview compliance portal
- [ ] Leaf sensitivity label "Highly Confidential" published in same or higher priority
- [ ] Label policy published to presenter account
- [ ] Fabric tenant settings ON: "Allow users to apply sensitivity labels" AND "Automatically apply sensitivity labels to downstream content"
- [ ] SQL analytics endpoint for LH_SecurityDemo has NO existing sensitivity label
- [ ] Default semantic model has NO existing sensitivity label
- [ ] Complete pre-session checklist: `demo-3-sensitivity-label-prereq-checklist.md`

---

### Step-by-Step Instructions

**Step 1 - Apply "Confidential" label to the Lakehouse**

1. Open `LH_SecurityDemo` in the Fabric portal
2. In the Lakehouse editor header, locate the sensitivity indicator (shield icon, typically shows "No label" or a dropdown)
3. Click the sensitivity indicator
4. Select "Confidential" from the picker
5. In the confirmation dialog, ensure "Apply this label to downstream content" is checked
6. Click Apply

> PRESENTER NOTES: "One action. We are classifying the data source, not individual rows, columns, or reports. We are saying: this Lakehouse contains confidential data. Everything derived from it inherits that classification. Watch the workspace."

**Step 2 - Verify automatic propagation**

1. Navigate to the workspace item list (click the workspace name in the left nav)
2. Locate `LH_SecurityDemo` - shows "Confidential" sensitivity label
3. Locate the SQL analytics endpoint for LH_SecurityDemo - it now shows "Confidential"
4. Locate the default semantic model - it now shows "Confidential"

> PRESENTER NOTES: "Three items labeled from one action. The SQL analytics endpoint and the semantic model did not require any user interaction. This is downstream inheritance - Fabric applied the classification automatically because the source Lakehouse was labeled. Think about the scale implication: you have 200 Lakehouses. You label 20 of them as Confidential. Every report built on those 20 lakehouses is automatically classified. No manual remediation campaign needed."

**Step 3 - Create a report and show inheritance on creation**

1. Click on the default semantic model
2. Click "Create report" (or "Auto-create report")
3. The new Power BI report opens - observe the sensitivity indicator in the header shows "Confidential"
4. Save the report with a name (e.g., `SalesRegionReport`)
5. Return to workspace list - the new report also shows "Confidential"

> PRESENTER NOTES: "The report was labeled at creation. The report builder did not have to do anything. They may not even know what a sensitivity label is. The platform classified it because it inherited from the semantic model, which inherited from the Lakehouse. The governance policy is self-propagating."

**Step 4 - Escalate to "Highly Confidential" (WOW Moment escalation)**

1. Go back to `LH_SecurityDemo`
2. Click the sensitivity indicator
3. Select "Highly Confidential"
4. Leave downstream checkbox checked
5. Click Apply
6. Navigate back to workspace list
7. Refresh the page

> PRESENTER NOTES: "Watch what happens. The Lakehouse is now Highly Confidential. The SQL endpoint - Highly Confidential. The semantic model - Highly Confidential. The report we just created - Highly Confidential. One escalation action, four items updated. This is the label tsunami. In a real enterprise, this is the difference between a data steward spending two hours doing a manual audit versus a five-second portal action."

**Step 5 - Attempt downgrade (demonstrate label protection)**

1. Click the sensitivity indicator on `LH_SecurityDemo`
2. Select "Confidential"
3. Leave downstream checkbox checked
4. Apply
5. Check the SQL endpoint and semantic model - they retain "Highly Confidential"

> PRESENTER NOTES: "Interesting behavior here. Highly Confidential is a higher-priority label than Confidential. The downstream items will not be downgraded by inheritance when a manual Highly Confidential label was applied to them. Fabric respects the principle of highest sensitivity - if something was manually labeled as more sensitive, that label takes precedence. This matters for compliance: you cannot accidentally downgrade sensitive data through a careless label change on the parent."

**Step 6 - Open Purview Hub**

1. In the Fabric portal left nav, locate "Admin monitoring" workspace (or search for it)
2. Open the Purview Hub report
3. Navigate to the Sensitivity labels tab
4. Show the rising count of labeled items

> PRESENTER NOTES: "This is your governance dashboard. Every labeled item in the tenant is tracked here. Your compliance team can come to this report instead of manually auditing workspaces. And if you need a full audit log, you can go to the Purview compliance portal - Audit - and filter by SensitivityLabelApplied or SensitivityLabelChanged to see every label action with timestamp, user, item name, and old/new label value. Full auditability, no custom logging required."

---

### Gotcha Reference

| Gotcha | Impact | Workaround |
|--------|--------|------------|
| Parent labels cannot be applied (only leaf labels) | Label picker shows label but applying fails silently | Ensure demo label has no sublabels; use a leaf sublabel |
| Power BI -> Fabric inheritance is NOT supported (one-way only) | Labeling a report does not label the Lakehouse | Always flow top-down: Lakehouse -> SQL endpoint -> semantic model -> report |
| Manually applied label on a downstream item is NOT overwritten by inheritance | Downstream item retains higher-priority label | Pre-check all downstream items are unlabeled before the demo |
| Downstream inheritance caps at 80 items per workspace | Some items may not inherit in large workspaces | Keep demo workspace under 80 items |
| Label policy not published to demo user | Labels not visible in picker | Verify policy scope in Purview (B6 in checklist) and allow 24h sync time |

---

### Recovery Steps

**Symptom:** Sensitivity indicator (shield icon) not visible in Fabric header  
**Fix:** Verify tenant setting "Allow users to apply sensitivity labels" is enabled. Reload the page in a new InPrivate window.

**Symptom:** Label picker is empty or missing expected labels  
**Fix:** Verify label policy is published to the presenter account. Allow 24 hours after publication for sync. Test in Purview compliance portal directly.

**Symptom:** SQL endpoint and semantic model did not inherit the label  
**Fix:** Verify "Automatically apply sensitivity labels to downstream content" tenant setting is ON. Wait 3-5 minutes and refresh workspace list. If still not propagated, manually apply the label to each item as a fallback and explain the automatic inheritance timing.

**Symptom:** Purview Hub shows no data  
**Fix:** Navigate to the Admin monitoring workspace directly. If the report is empty, use the Purview compliance portal audit log as the primary evidence surface.

---

## Demo 4 - Git Integration + 3-Stage Deployment Pipeline {#demo-4}

**Goal:** Connect a Fabric workspace to GitHub, commit a Notebook change via the Fabric Source Control UI, configure a Dev/Test/Prod deployment pipeline with a Lakehouse deployment rule, and deploy across all three stages.

**WOW Moment:** A commit made from the Fabric UI creates a real, attributed GitHub commit visible in the repository history. The deployment pipeline promotes Dev to Prod in under 60 seconds, and the deployment rule automatically swaps the Lakehouse binding.

**Companion File:** `outputs/demos/generic-fabric-trustworthy-data/demo-4-git-pipeline-setup.sh`

**Estimated Time:** ~20 minutes

---

### Narrative Context

> PRESENTER NOTES - say approximately this:
>
> "Data engineering teams have been asking for years: why does my ETL pipeline not get the same engineering discipline as application code? Why can't I review a notebook change before it hits production? Why is there no rollback? 
>
> Fabric's Git integration and deployment pipelines answer all of that. You get version control, code review, branch-based promotion, and automated consistency checks - all without leaving the Fabric portal and without any external CICD configuration. Let me walk you through it."

---

### Prerequisites

- [ ] Fabric tenant settings enabled:
      "Users can synchronize workspace items with their Git repositories"
      "Users can synchronize workspace items with GitHub repositories"
- [ ] GitHub account created; `demo-4-git-pipeline-setup.sh` has been run to create the repo with `dev`, `test`, `main` branches
- [ ] Presenter account has Write access to the GitHub repository
- [ ] Workspace `DataEng-Dev` exists and contains at least one Notebook with a meaningful name (e.g., `IngestNotebook`)

---

### Step-by-Step Instructions

**Step 1 - Connect DataEng-Dev workspace to GitHub**

1. Open `DataEng-Dev` workspace in the Fabric portal
2. Workspace settings (gear icon in left nav) -> Git integration
3. Git provider: GitHub
4. Click Add account and complete the OAuth flow (GitHub will prompt for authorization)
5. Repository: select the repo created by the setup script
6. Branch: `dev`
7. Git folder: `fabric-workspace`
8. Click Connect and sync
9. The Source Control icon (branching arrows) appears in the workspace top navigation bar

> PRESENTER NOTES: "I just connected a Fabric workspace to a GitHub branch. Every item in this workspace - notebooks, pipelines, data flows - is now synchronized to the fabric-workspace folder in what is a real GitHub repository. Let me show you what that looks like from the Git side.
>
> [Switch browser tab to GitHub] You can see the fabric-workspace folder was created automatically. Each item is a subfolder. The notebook is a Python file. The lakehouse is represented as a metadata JSON. All of this is diffable, commitable, and reviewable in standard GitHub tooling."

**Step 2 - Modify a Notebook and commit from Fabric**

1. Open `IngestNotebook` in `DataEng-Dev`
2. Find a cell and add a comment at the top: `# Updated: adding region filter logic`
3. Look at the Source Control icon in the top nav - it now shows a "1" badge indicating an uncommitted change
4. Click the Source Control icon
5. Review the Changes tab - shows the notebook file with a diff indicator
6. Enter a commit message: `feat: add region filter comment`
7. Click Commit

> PRESENTER NOTES: "I committed a change to a Notebook from inside the Fabric portal. Now watch GitHub. [Switch to GitHub tab] Refresh the repository. There it is - a real commit with the message I typed, my identity as the author, and a full diff showing exactly what line changed. This is your audit trail. Every data engineering change is attributable, reviewable, and reversible."

**Step 3 - Create a 3-stage deployment pipeline**

1. In the workspace left nav -> Deployment pipelines -> + New pipeline
2. Name: `DataEng-Pipeline`
3. Stages: 3 (Development / Test / Production) - accept defaults
4. Click Create and continue

**Step 4 - Assign workspaces and deploy**

1. Development stage -> Assign workspace -> select `DataEng-Dev`
2. Click the Deploy arrow between Development and Test
3. Select Full deployment
4. Click Deploy and confirm
5. Fabric automatically creates `DataEng-Pipeline [Test]` workspace
6. Wait for completion (~30 seconds)
7. Click the Deploy arrow between Test and Production
8. Deploy and confirm
9. Fabric automatically creates `DataEng-Pipeline [Production]` workspace

> PRESENTER NOTES: "Look at this. I have three workspaces - Dev, Test, Prod - and every item is now promoted consistently from Dev to Test to Prod. No manual copying of notebooks. No risk of accidentally deploying the wrong file. No SSH into a server. The pipeline tracks what is in each stage and shows you the diff before you promote. Speaking of which... [click Compare]"

**Step 5 - Set a deployment rule on Production**

1. Production stage -> click the Deployment rules icon (wrench symbol)
2. Select the Notebook item (`IngestNotebook`)
3. Default lakehouse rule -> click Add rule
4. Select the Production Lakehouse from the dropdown
5. Click Save
6. Re-deploy Test -> Production (click Deploy arrow again)
7. Open the Notebook in the `DataEng-Pipeline [Production]` workspace
8. Verify the default lakehouse binding shows the Production Lakehouse (not Dev)

> PRESENTER NOTES: "This is the killer feature of deployment rules. The source code is identical between Dev and Prod - same notebook, same logic. But in Prod, when the notebook runs, it will attach to the PRODUCTION Lakehouse. Not the Dev Lakehouse. The rule did that swap automatically during the deployment, without any code change.
>
> Think about what manual error this replaces. How many times has a data engineer accidentally run a Dev notebook against Prod data? Or a Prod notebook reading from a Dev Lakehouse? Deployment rules make the environment binding declarative and automatic."

**Step 6 - Show Compare**

1. Click the Compare button between Dev and Test stages
2. Show the item-level diff view

> PRESENTER NOTES: "Before I promote to Prod, I can see exactly what is different between the stages. This is my release manifest. Product owner can review it. Compliance team can approve it. Then I click Deploy and it is deterministic. No surprises."

---

### Gotcha Reference

| Gotcha | Impact | Workaround |
|--------|--------|------------|
| Deployment rules do not apply until a re-deploy after rule creation | Notebook still points to Dev Lakehouse | Always re-deploy after setting or changing a rule |
| 1:1 workspace-to-branch mapping (one workspace per branch only) | Connecting two workspaces to the same branch fails | Use separate branches: dev, test, main |
| Sensitivity-labeled items block commits unless export setting enabled | Commit fails with label error | Enable "Users can export items with sensitivity labels" in Fabric tenant admin settings |
| Max item file size is 25 MB | Large notebooks fail to commit | Keep notebooks lean; externalize large data assets |
| "Add rule" button grayed out if user is not the item owner | Cannot create deployment rules | Transfer item ownership to your admin account first: Notebook menu -> Transfer ownership |

---

### Recovery Steps

**Symptom:** Source Control icon not visible after connecting to GitHub  
**Fix:** Refresh the workspace page. Confirm the OAuth app was properly authorized in GitHub - check GitHub Settings -> Applications -> Authorized OAuth Apps.

**Symptom:** Deploy arrow disabled between stages  
**Fix:** Confirm the source workspace has at least one item. Confirm the deployment pipeline is in a non-pending state (no active deployment running).

**Symptom:** Production Notebook still shows Dev Lakehouse after deployment  
**Fix:** Remember: rules only apply AFTER a re-deploy following rule creation. If rules were set and a re-deploy has been done, confirm the rule was saved (re-open the deployment rules UI to verify) and deploy again.

---

## Demo 5 - fabric-cicd in GitHub Actions {#demo-5}

**Goal:** Automate PROD deployment via `deploy.py` + `parameter.yml` + a GitHub Actions workflow. When a PR is merged to main, the workflow fires and deploys Fabric workspace items to PROD - with the PROD Lakehouse GUID substituted automatically by parameter.yml rules.

**WOW Moment:** Merge the PR, switch to the GitHub Actions tab, watch the workflow steps complete in real time. Open the PROD Notebook - the PROD Lakehouse GUID is in place. Show the SPN audit trail in the Fabric activity log.

**Companion Files:**  
- `outputs/demos/generic-fabric-trustworthy-data/demo-5-deploy.py`  
- `outputs/demos/generic-fabric-trustworthy-data/demo-5-parameter.yml`  
- `outputs/demos/generic-fabric-trustworthy-data/demo-5-deploy-fabric.yml`

**Estimated Time:** ~20 minutes

---

### Narrative Context

> PRESENTER NOTES - say approximately this:
>
> "Demo 4 showed you manual deployment through the pipeline UI. That is a great first step, and for many teams it is sufficient. But enterprise-grade engineering requires that prod deployments are automated, auditable, and triggered by a code merge - not by a human clicking a button at midnight.
>
> fabric-cicd is Microsoft's open-source Python library for exactly this. You describe what to deploy in code. You describe how to parameterize it per environment in YAML. You trigger it from GitHub Actions on a branch merge. And when it runs, it runs as a Service Principal - a non-human identity - so every deployment is auditable, not attributable to whoever happened to have prod access that day.
>
> Let me show you how all four files fit together."

---

### Prerequisites

- [ ] Service Principal created in Entra ID with a client secret
- [ ] SPN granted workspace Admin or Contributor role on the PROD Fabric workspace:
      PROD workspace -> Settings -> Manage access -> Add the SPN by name
- [ ] Fabric tenant admin setting enabled: "Service principals can use Fabric APIs"
- [ ] GitHub repository from Demo 4 with `fabric-workspace/` folder structure in place
- [ ] Four GitHub Actions secrets configured:
      `FABRIC_PROD_WORKSPACE_ID`, `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, `FABRIC_CLIENT_SECRET`
- [ ] `.deploy/deploy.py`, `fabric-workspace/parameter.yml`, and `.github/workflows/deploy-fabric.yml` committed to the repository
- [ ] Python 3.12 available in GitHub Actions runner (ubuntu-latest default)

---

### Step-by-Step Instructions

**Step 1 - Walk through the four files**

1. Open the GitHub repository
2. Navigate to `.deploy/deploy.py`

> PRESENTER NOTES: "Let me walk you through what deploy.py does. [Open file] It reads four environment variables - the workspace ID, tenant ID, client ID, and client secret. These come from GitHub Actions secrets; they are never stored in code. It creates a service principal credential using azure-identity. Then it calls fabric-cicd's FabricWorkspace class and calls publish_all_items and unpublish_all_orphan_items.
>
> publish_all_items pushes every item in the fabric-workspace/ folder into the PROD workspace. unpublish_all_orphan_items removes anything that is in PROD but is no longer in the repo. This keeps PROD in sync with the repo, including deletions."

3. Navigate to `fabric-workspace/parameter.yml`

> PRESENTER NOTES: "Before each item is deployed, fabric-cicd reads parameter.yml and applies find-replace rules. Look at Rule 1. It is a regex that matches the default_lakehouse GUID in the notebook metadata comments. In DEV, that GUID points to the Dev Lakehouse. In PROD, fabric-cicd replaces it with dollar-items-dot-Lakehouse-dot-MyLakehouse-dot-id - which is a token that resolves to the live GUID of the item named MyLakehouse in the PROD workspace at deployment time.
>
> This means the source code in GitHub never needs to be touched. The DEV GUID stays in the file forever. The substitution happens in flight, at deploy time, purely in the PROD artifact."

4. Navigate to `.github/workflows/deploy-fabric.yml`

> PRESENTER NOTES: "The workflow is four steps. Checkout the code. Set up Python. Install fabric-cicd and azure-identity. Run deploy.py with the secrets injected as environment variables. That is it. The entire production deployment infrastructure is 30 lines of YAML."

**Step 2 - Create a PR with a Notebook change (pre-demo setup)**

> NOTE: This should be prepared before the session. Have an open PR ready to merge.

1. Show the open PR on the repository (prepared in advance)
2. Show the diff - a Notebook cell was modified
3. Point out the Notebook metadata section showing the DEV Lakehouse GUID

> PRESENTER NOTES: "Here is the PR. A data engineer updated the Notebook logic. You can see the diff in GitHub. And if you look at the notebook metadata - here [point] - you can see the DEV Lakehouse GUID hardcoded. Let me merge this PR and show you what happens."

**Step 3 - Merge the PR (WOW Moment)**

1. Click Merge pull request -> Confirm merge
2. Switch to the Actions tab immediately
3. Show the `Deploy Fabric Workspace to PROD` workflow appearing and running (yellow)
4. Walk through the steps as they complete:
   - Checkout repository
   - Set up Python 3.12
   - Install fabric-cicd and azure-identity
   - Deploy Fabric workspace to PROD

> PRESENTER NOTES: "Watch the workflow. Every step is running unattended. No human is logged into PROD. No one is clicking buttons in the Fabric portal. The SPN is deploying this. When the deploy step finishes, the PROD workspace is updated. Let me show you the evidence."

**Step 4 - Verify PROD Notebook has PROD Lakehouse GUID**

1. Switch to Fabric portal
2. Open the PROD workspace (created by Demo 4 pipeline, or pre-provisioned)
3. Open `IngestNotebook`
4. Point to the default lakehouse metadata - it shows the PROD Lakehouse GUID (different from what is in the GitHub file)

> PRESENTER NOTES: "Look at this. The PROD Notebook has a different Lakehouse GUID than the file in GitHub. The parameter.yml substitution happened during the deployment. The source of truth stays clean in Git. The right artifact lands in the right environment automatically. No manual GUID patching, no environment-specific branches."

**Step 5 - Show SPN audit trail in Fabric activity log**

1. Open Fabric Admin portal
2. Navigate to Activity log (under Governance section)
3. Filter by date (today) and by the SPN client ID

> PRESENTER NOTES: "Here is the audit entry. The deployment action is attributed to the Service Principal - to the app registration, not to a person. You can see the timestamp, the workspace ID, and the items that were deployed. This is your non-repudiable deployment record. No shared accounts, no ambiguity about who deployed what. The SPN deployed it. The SPN is governed by your Entra ID lifecycle. When an employee leaves, revoking their role does not affect automated deployments. The SPN remains until you choose to retire it."

---

### Gotcha Reference

| Gotcha | Impact | Workaround |
|--------|--------|------------|
| Notebook Lakehouse GUID is hardcoded in notebook-content.py metadata | Without parameter.yml, PROD notebook uses Dev Lakehouse | Use the find_replace regex rule in parameter.yml to match and substitute the GUID at deploy time |
| $items names are CASE-SENSITIVE | Deployment fails or substitutes wrong item | Match item names EXACTLY as they appear in the repo folder names (e.g., MyLakehouse not myLakehouse) |
| fabric-cicd always does FULL deployment (no incremental diff) | Long deploy times if workspace has many items | Keep item_type_in_scope narrow; only include item types you need to deploy |
| Connections are NOT deployed by fabric-cicd | Broken connections in PROD after deploy | Pre-create connections in PROD workspace; use find_replace in parameter.yml to swap DEV connection GUIDs for PROD GUIDs |
| SPN must have Fabric workspace-level permission, not just Entra app registration | Deployment returns 403 Forbidden | Grant SPN Admin or Contributor role in the PROD workspace via Fabric portal -> Manage access; also enable "Service principals can use Fabric APIs" in tenant admin settings |

---

### Recovery Steps

**Symptom:** GitHub Actions workflow fails at the Install step  
**Fix:** Confirm Python 3.12 is specified in the setup-python step. Try pinning specific versions: `pip install fabric-cicd==0.1.x azure-identity==1.x.x`.

**Symptom:** Workflow fails with "FABRIC_PROD_WORKSPACE_ID is missing"  
**Fix:** Verify all four GitHub Actions secrets are set in Repository settings -> Secrets and variables -> Actions. Confirm secret names match exactly (case-sensitive).

**Symptom:** Workflow completes successfully but PROD Notebook still shows Dev Lakehouse GUID  
**Fix:** Confirm parameter.yml is in the `fabric-workspace/` folder (not the repo root). Confirm the item name in the replace_value token matches the folder name exactly. Re-run the workflow manually via workflow_dispatch.

**Symptom:** Workflow fails with 403 on the Deploy Fabric workspace step  
**Fix:** Confirm the SPN has workspace Admin or Contributor role, not just Entra app registration membership. Confirm the "Service principals can use Fabric APIs" tenant setting is enabled and scoped to include the SPN's security group.

**If demo cannot be recovered:** Switch to showing the already-completed workflow run from a previous test. Walk through the logs step by step. Show the PROD workspace item list from the successful run. The SPN audit trail is permanent and can always be shown regardless of live demo state.

---

## Appendix - Companion File Index {#appendix}

All companion files are located in:  
`outputs/demos/generic-fabric-trustworthy-data/`

| File | Demo | Purpose |
|------|------|---------|
| `demo-1-onelake-security-setup.py` | Demo 1 | Fabric Notebook that seeds NorthSalesData and SouthSalesData Delta tables in LH_SecurityDemo |
| `demo-2-rls-setup.py` | Demo 2 | Fabric Notebook that seeds the unified SalesOrders Delta table; prints RLS predicate strings for copy-paste |
| `demo-3-sensitivity-label-prereq-checklist.md` | Demo 3 | Morning-of-session checklist covering licensing, label configuration, tenant settings, and dry-run validation |
| `demo-4-git-pipeline-setup.sh` | Demo 4 | Bash script run from presenter laptop to create the GitHub repo with dev/test/main branches; includes live demo walkthrough reminders |
| `demo-5-deploy.py` | Demo 5 | fabric-cicd deployment script invoked by GitHub Actions; place at `.deploy/deploy.py` in the customer repo |
| `demo-5-parameter.yml` | Demo 5 | fabric-cicd parameter file with find_replace and key_value_replace rules; place at `fabric-workspace/parameter.yml` |
| `demo-5-deploy-fabric.yml` | Demo 5 | GitHub Actions workflow definition; place at `.github/workflows/deploy-fabric.yml` |

---

## Reference Links

- OneLake security data access control model: https://learn.microsoft.com/en-us/fabric/onelake/security/data-access-control-model
- Get started with OneLake security: https://learn.microsoft.com/en-us/fabric/onelake/security/get-started-onelake-security
- Create and manage OneLake roles: https://learn.microsoft.com/en-us/fabric/onelake/security/create-manage-roles
- OneLake row-level security: https://learn.microsoft.com/en-us/fabric/onelake/security/row-level-security
- Sensitivity labels in Fabric: https://learn.microsoft.com/en-us/fabric/governance/information-protection
- Downstream label inheritance: https://learn.microsoft.com/en-us/fabric/governance/service-security-sensitivity-label-downstream-inheritance
- Apply sensitivity labels: https://learn.microsoft.com/en-us/fabric/fundamentals/apply-sensitivity-labels
- Purview Hub: https://learn.microsoft.com/en-us/fabric/governance/use-microsoft-purview-hub
- Git integration introduction: https://learn.microsoft.com/en-us/fabric/cicd/git-integration/intro-to-git-integration
- Git integration get started: https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-get-started
- Deployment pipelines get started: https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/get-started-with-deployment-pipelines
- Deployment pipeline rules: https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/create-rules
- CICD best practices: https://learn.microsoft.com/en-us/fabric/cicd/best-practices-cicd
- fabric-cicd documentation: https://microsoft.github.io/fabric-cicd/latest/
- fabric-cicd GitHub repository: https://github.com/microsoft/fabric-cicd
