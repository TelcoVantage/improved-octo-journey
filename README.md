# Genesys Cloud – Email Assistant script

An agent script for **email interactions** in Genesys Cloud that gives agents Outlook-style tools inside the
Genesys UI: a colour-coded **category dropdown**, importance and follow-up flags, a triage note, **search for all
emails from this sender or from the whole domain**, message details (MIME headers) and one-click quick replies.

Everything is native Genesys: a `.script` file you import in *Admin > Scripts*, plus one Genesys Cloud
**data action** that performs the search through the Platform API.

```
genesys/
  scripts/Email-Assistant.script                                 <- import this in Admin > Scripts
  data-actions/Email-Assistant-Search-Inbound-Emails.json        <- import this in Admin > Integrations > Actions
  tools/Deploy-EmailScript.ps1                                   <- optional one-shot deploy (PowerShell 5.1, CLM-safe)
  tools/build_email_script.py                                    <- generator that produced the two files above
  tools/editor-harness/validate-in-editor.js                     <- loads a .script with the real Genesys editor code (headless) and reports what would fail
```

## What the agent sees

**Page 1 – Email**

| Section | What it does |
|---|---|
| Header | Sender address, subject, queue, agent, interaction id, status line |
| **Categorise** | Dropdown with Outlook-like categories (🔴 Complaint, 🟠 Billing / payment, 🟡 Technical support, 🟢 Sales enquiry, 🔵 Account / profile change, 🟣 General question, ⚫ Spam / junk, ⚪ Other), an **Importance** dropdown (Low / Normal / High), a **Flag for follow-up** checkbox and a **triage note** |
| **Search emails** | Buttons *All emails from this sender* and *All emails from this domain (example.com)*, plus a free search box with *Match* (exact sender / whole domain) and *Period* (7 / 30 / 90 / 180 days). Results appear as a **Matching emails** dropdown (date \| sender) and a markdown list with interaction ids. *Open selected interaction* opens the chosen email in a new tab. |
| **Message details** | *Load message details* reads the MIME headers From, To, Reply-To, Date, Message-ID of the customer's email |

**Page 2 – Quick replies**: four templates (acknowledge, need more information, resolved, transferred) that are
copied to the clipboard with the agent's name filled in, and a category guide table.

### Where the category goes

`EmailCategory`, `EmailPriority`, `EmailFollowUp` and `EmailCategoryNote` are **script output variables**. Genesys
writes output variables to the conversation as **participant data** (key/value attributes), so the category is:

- visible in the interaction's *Participant data* panel and through `GET /api/v2/conversations/{id}`,
- available to Architect (for example after a transfer) and to the Conversation Details / participant-attribute reporting,
- usable as a filter dimension in your own analytics or exports.

No data action is needed for categorisation; only the search uses one.

## Prerequisites

1. **Genesys Cloud Data Actions integration** (*Admin > Integrations*, type "Genesys Cloud Data Actions"), active,
   with OAuth client credentials whose role includes `analytics:conversationDetail:view`.
2. Permissions for the person importing: *Scripter > Script > All*, *Scripter > Published Script > Add / View*,
   *Integrations > Action > Add / View*. Script uploads require these at **user** level (not group-inherited).
3. Agents need *Scripter > Published Script > View* and *Integrations > Action > Execute* (to run the search).

## Install – option A: through the Genesys Cloud UI

1. **Data action**: *Admin > Integrations > Actions > Import*, pick the Genesys Cloud Data Actions integration and
   upload `genesys/data-actions/Email-Assistant-Search-Inbound-Emails.json`. Save & publish. Copy the action's
   **ID** from the URL or the action page.
2. **Point the script at the action**: open `genesys/scripts/Email-Assistant.script` in a text editor and replace the
   three occurrences of `11111111-1111-1111-1111-111111111111` with that ID. If your org is not on
   `apps.mypurecloud.com`, also replace that value (variable `GenesysAppHost`) with your region's host, for example
   `apps.mypurecloud.ie`, `apps.mypurecloud.com.au`, `apps.euw2.pure.cloud`, `apps.usw2.pure.cloud`.
3. **Import the script**: *Admin > Contact Center > Scripts > Import*, choose a division, select the `.script` file.
4. Open the script, click **Preview**, try *All emails from this sender*, then **Publish**.
5. Make it available for email: in your inbound email flow's *Transfer to ACD* action select the published script
   (or set it on the queue), or let agents open it from the **Scripts** panel in Agent Workspace.

If step 2 is skipped the script still imports; the custom actions *Run email search*, *Search – all emails from this
sender* and *Search – all emails from this domain* will simply show an unselected data action that you can pick in
the editor.

## Install – option B: PowerShell (Constrained Language Mode safe)

```powershell
cd genesys\tools
.\Deploy-EmailScript.ps1 -Region mypurecloud.ie -ClientId <id> -ClientSecret <secret>
# optional: -DivisionId <guid> -ScriptName "Email Assistant" -IntegrationName "Genesys Cloud Data Actions" -SkipPublish
```

The script gets a token, finds the integration, creates the data action (or reuses one with the same name), patches
the placeholder id and the app host into the `.script`, uploads it through the same endpoint the Scripts UI uses
(`https://apps.<region>/uploads/v2/scripter`), polls `/api/v2/scripts/uploads/{id}/status` and publishes.
It uses cmdlets, hashtables and arrays only; Base64 for the Basic auth header is implemented with bit operators.

## How the search works

1. The script computes two **dynamic variables**:
   `SenderDomain` = the part of `{{email.customerEmailAddress}}` after `@`, and
   `SearchInterval` = `DaysBack` days before this email arrived up to one hour after it arrived
   (`formatDateISO(...)/formatDateISO(...)`, built from the built-in raw interaction start time).
2. The custom action runs the data action with `Mode` (sender / domain), `Address` and `Interval`.
3. The data action posts to `POST /api/v2/analytics/conversations/details/query` for inbound **email** segments in
   that interval (newest first, 50 rows). For *sender* mode it also filters `addressFrom` server-side; the Analytics
   API only supports exact address matches, so for *domain* mode the success template keeps rows whose sender ends
   with `@domain`. Genesys allows only `#if` / `#set` in templates (no `#foreach`), so the template reduces every
   conversation to one `id|start|sender` record with Java regex string methods and filters/re-renders those records.
4. It returns `Count`, `ConversationIds[]`, `Labels[]` (`date | sender`) and a markdown `Summary`. The script binds the
   two lists to the results dropdown (values = ids, labels = text) and shows the summary.

**Testing the action in Admin > Integrations > Actions > Test**: `Mode` must be the word `sender`, `domain` or `all`
(not an address), `Address` is the email address (sender) or the bare domain such as `rabobank.com` (domain), and
`Interval` an ISO-8601 range such as `2026-08-01T00:00:00Z/2026-09-01T00:00:00Z`.

## Assumptions and limits (read before go-live)

- **Region host**: opening a result uses `https://{{GenesysAppHost}}/directory/#/engage/admin/interactions/{id}`.
  Default is `apps.mypurecloud.com`; change the variable for other regions.
- **Search window end** is the current email's arrival time + 1 hour, because scripts have no "now" function.
  Emails that arrived after that are not listed. Edit the `SearchInterval` expression if you prefer a fixed end.
- **Domain search scans the 50 most recent inbound emails** in the window (`pageSize` in the request template; the
  Analytics API allows up to 100). Shorten the period for very busy mailboxes.
- Analytics data is available a few minutes after a conversation is created; brand-new emails may not appear yet.
- Sender address for each result is taken from the first participant's first session (`participants[0].sessions[0]`),
  which is the customer for inbound emails.
- The email feature exposes `Email.Customer Email Address` and `Email.Subject` only; body text is not available to
  scripts. Headers come from the *Get Email Headers* action (first email in the thread).
- Nothing here was executed against a live org (no org access from this workspace). What **was** verified:
  the `.script` was loaded with the **real Genesys script editor code** (the public scripter web-app bundles, run
  headless with `genesys/tools/editor-harness/validate-in-editor.js`): the script, both pages, all 24 variables and
  all 15 custom actions build without error, with every scripter feature toggle off and on. All variable/page/action
  cross-references resolve, and both Velocity templates were executed under Velocity 1.7 against a mock analytics response (compact and
  pretty-printed JSON) for sender / domain / all / no-match / empty cases and produce valid JSON without `#foreach`. Run the Preview after import.

## Validating a `.script` before importing

If the editor shows **"Failed to load script"** after an import, the JSON contains something the editor cannot build.
`validate-in-editor.js` reproduces that step locally and prints the real error:

```bash
cd genesys/tools/editor-harness
npm i playwright && npx playwright install chromium     # once
node validate-in-editor.js ../../scripts/Email-Assistant.script        # add "on" to enable all feature toggles
```

It downloads the public editor bundles from apps.mypurecloud.com (cached in `cache/`), stubs every API call, and
builds the script, pages, variables and custom actions exactly like *open script* does. Only GET requests for the
public JavaScript are made; nothing is sent to your org.

## Regenerating the files

`python3 genesys/tools/build_email_script.py` rebuilds both JSON files with stable ids. Edit categories, quick
replies, day ranges or layout there rather than in the generated JSON.
