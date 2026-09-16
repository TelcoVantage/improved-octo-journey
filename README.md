# Genesys Cloud – Email Assistant script

An agent script for **email interactions** in Genesys Cloud that gives agents Outlook-style tools inside the
Genesys UI: a colour-coded **category dropdown**, importance and follow-up flags, a triage note, **search for all
emails from this sender or from the whole domain**, a **follow-ups list** every agent can open, an **email thread
viewer** inside the script, message details (MIME headers) and one-click quick replies.

Everything is native Genesys: a `.script` file you import in *Admin > Scripts*, plus four Genesys Cloud
**data actions** that query the Platform API (search, follow-ups list, email thread, single message).

```
genesys/
  scripts/Email-Assistant.script                                 <- import this in Admin > Scripts
  data-actions/Email-Assistant-Search-Inbound-Emails.json        <- import all four in Admin > Integrations > Actions
  data-actions/Email-Assistant-List-Follow-Ups.json
  data-actions/Email-Assistant-Get-Email-Thread.json
  data-actions/Email-Assistant-Get-Email-Message.json
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
| **Search emails** | Buttons *All emails from this sender* and *All emails from this domain (example.com)*, plus a free search box with *Match* (exact sender / whole domain) and *Period* (7 / 30 / 90 / 180 days). Results appear as a **Matching emails** dropdown (date \| sender \| subject) and a markdown list with subject and interaction id. *View thread* opens the chosen email on the **Email thread** page. |
| **Message details** | *Load message details* reads the MIME headers From, To, Reply-To, Date, Message-ID of the customer's email |

**Page 2 – Quick replies**: four templates (acknowledge, need more information, resolved, transferred) that are
copied to the clipboard with the agent's name filled in, and a category guide table.

**Page 3 – Follow-ups** (button *Follow-ups list* on page 1): every email in the chosen period where an agent ticked
*Flag for follow-up*, newest first, as a dropdown plus a markdown list with sender, subject and interaction id, and a
*View thread* button. It loads automatically when the page opens and has a *Refresh* button. Standard agents
can use it: the list is produced by a data action that runs under the Data Actions integration's own OAuth client, so
agents need only *Integrations > Action > Execute*, not any reporting or analytics permission. Unticking the flag on
an email (in that email's script) removes it from the list on the next refresh.

**Page 4 – Email thread** (opened by *View thread* from the search results or the follow-ups list): lists every
message of that email conversation (time | from | subject) with a text preview of each, oldest first. Select a message
and click *Show full message* to read its complete text body inside the script. *Open in Genesys (new tab)* is still
there for the native interaction view. Both lookups run under the Data Actions integration's OAuth client, whose
role needs *Conversation > Communication > View* for these two actions; agents themselves need nothing extra.

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

1. **Data actions**: *Admin > Integrations > Actions > Import*, pick the Genesys Cloud Data Actions integration and
   upload each file in `genesys/data-actions/`. Save & publish each. Copy each action's **ID** from the URL or the
   action page.
2. **Point the script at the actions**: open `genesys/scripts/Email-Assistant.script` in a text editor and replace
   the placeholders with the real IDs: `11111111-...` (three occurrences) = search, `22222222-...` = follow-ups,
   `33333333-...` = email thread, `44444444-...` = email message. If your org is not on
   `apps.mypurecloud.com`, also replace that value (variable `GenesysAppHost`) with your region's host, for example
   `apps.mypurecloud.ie`, `apps.mypurecloud.com.au`, `apps.euw2.pure.cloud`, `apps.usw2.pure.cloud`.
3. **Import the script**: *Admin > Contact Center > Scripts > Import*, choose a division, select the `.script` file.
4. Open the script, click **Preview**, try *All emails from this sender*, then **Publish**.
5. Make it available for email: in your inbound email flow's *Transfer to ACD* action select the published script
   (or set it on the queue), or let agents open it from the **Scripts** panel in Agent Workspace.

If step 2 is skipped the script still imports; the custom actions that call data actions (*Run email search*, the two
*Search – ...* actions, *Load follow-ups list*, *Load email thread*, *Show full message*) will simply show an
unselected data action that you can pick in the editor.

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
   that interval (newest first, 50 rows) with an `addressFrom` predicate: the exact address in *sender* mode, or
   `*@domain` in *domain* mode. All filtering happens in the request template, because Genesys data actions do not
   expose `$input` in the success template and allow only `#if` / `#set` (no `#foreach`) in templates.
4. The success template only formats: it reduces every conversation in the response to one `id|start|sender|subject`
   record with Java regex string methods (the subject comes from the analytics segment's `subject`, which is the initial
   email's subject) and renders `Count`, `ConversationIds[]`, `Labels[]` (`date | sender | subject`) and a markdown
   `Summary`. The script binds the two lists to the results dropdown (values = ids, labels = text) and shows the summary.

**Domain mode depends on the Analytics API accepting `*` in a `matches` value.** Verify once in API Explorer with
`POST /api/v2/analytics/conversations/details/query` and a predicate `{"type":"dimension","dimension":"addressFrom",
"operator":"matches","value":"*@yourdomain.com"}`. If the API rejects it or returns nothing for a domain you know has
emails, domain search cannot be done through Analytics; exact-sender search is unaffected.

## How the follow-ups list works

The *Follow-ups* page runs the second data action with the same date window as the search (`SearchInterval`, so
"last N days" up to one hour after the current email arrived) and the participant data key/value to match
(`EmailFollowUp` = `true` by default; the action accepts other keys, for example `EmailCategory` = `complaint`).
The request is the same analytics detail query with a **property predicate** on the participant attribute:

```json
{ "type": "property", "propertyType": "string", "property": "EmailFollowUp", "value": "true" }
```

The flag is written to the conversation by the script's output variable, so it only exists on emails handled with
this script, and Analytics needs a few minutes before a newly flagged email shows up. Participant data is retained by
Genesys for 60 days. This predicate has not been run against a live org from this workspace; if the action test
returns a count of zero for an email you know is flagged, try `"propertyType": "bool", "value": true` in the request
template and tell me the result.

## How the thread viewer works

*View thread* stores the chosen conversation id and switches to the *Email thread* page, whose page-load action calls
`GET /api/v2/conversations/emails/{conversationId}/messages`. The translation map projects each message to
`id, time, from, subject, textBodyPreview`; the success template reduces each to one record (fields found in any
order, missing ones left blank) and renders `Count`, `MessageIds[]`, `Labels[]` and a markdown `Thread` with one
section per message and its preview (Genesys truncates `textBodyPreview`). *Show full message* calls
`GET .../messages/{messageId}` and shows the complete `textBody`. Bodies are plain text; HTML-only emails show the
text alternative Genesys stores.

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
  headless with `genesys/tools/editor-harness/validate-in-editor.js`): the script, all four pages, all 44 variables
  and all 20 custom actions build without error, with every scripter feature toggle off and on. All variable/page/action
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
