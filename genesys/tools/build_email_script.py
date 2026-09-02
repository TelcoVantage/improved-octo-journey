#!/usr/bin/env python3
"""
Generates the Genesys Cloud email agent script (.script) and the data action
export JSON that powers its "search by sender / domain" feature.

The JSON shapes emitted here mirror real Genesys Cloud script exports
(verticalStackContainer / text / button / dropdown / textInput / checkbox /
markdown components, scripter.* / email.* / bridge.bridge actions, list and
listPair property types, objectFields for data action input/output mapping).

Run:  python3 genesys/tools/build_email_script.py
Out:  genesys/scripts/Email-Assistant.script
      genesys/data-actions/Email-Assistant-Search-Inbound-Emails.json
"""
import json
import os
import uuid
from collections import OrderedDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT_OUT = os.path.join(ROOT, "genesys", "scripts", "Email-Assistant.script")
ACTION_OUT = os.path.join(ROOT, "genesys", "data-actions", "Email-Assistant-Search-Inbound-Emails.json")
FOLLOWUP_ACTION_OUT = os.path.join(ROOT, "genesys", "data-actions", "Email-Assistant-List-Follow-Ups.json")

# Stable identifiers so re-running the generator produces a diff-friendly file.
NS = uuid.UUID("6f1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d")


def uid(name):
    return str(uuid.uuid5(NS, name))


SCRIPT_ID = uid("script")
VERSION_ID = uid("version")
ORG_ID = "00000000-0000-0000-0000-000000000000"        # overwritten by Genesys on import
DATA_ACTION_PLACEHOLDER = "11111111-1111-1111-1111-111111111111"  # replace after creating the data action
DATA_ACTION_NAME = "Email Assistant - Search Inbound Emails"
FOLLOWUP_ACTION_PLACEHOLDER = "22222222-2222-2222-2222-222222222222"  # replace after creating the follow-ups data action
FOLLOWUP_ACTION_NAME = "Email Assistant - List Follow-Ups"
FONT = 'Arial, "Helvetica Neue", Helvetica, sans-serif'

# --------------------------------------------------------------------------
# Property-type helpers (typeName / value pairs exactly as the scripter stores them)
# --------------------------------------------------------------------------

def spacing(v=(5, 5, 5, 5)):
    return {"typeName": "spacing", "value": list(v) if isinstance(v, (list, tuple)) else v}


def sizing(kind="auto", size=None):
    v = {"sizeType": kind}
    if size is not None:
        v["size"] = size
    return {"typeName": "sizing", "value": v}


def itext(s):
    return {"typeName": "interpolatedText", "value": s}


def boolean(b):
    return {"typeName": "boolean", "value": bool(b)}


def integer(n):
    return {"typeName": "integer", "value": n}


def var_ref(var_id=None):
    return {"typeName": "variable", "value": var_id} if var_id else {"typeName": "variable"}


def null():
    return {"typeName": "null"}


def action_ref(custom_action_id):
    return {"typeName": "action", "value": {"actionName": custom_action_id}}


def no_action():
    return {"typeName": "action", "value": {}}


def border(width=0, color="000000"):
    side = {"width": width, "style": "solid", "color": color}
    return {"typeName": "border", "value": [dict(side) for _ in range(4)]}


def base_props(width=("auto", None), height=("auto", None), margin=(5, 5, 5, 5), visible_var=None):
    return OrderedDict([
        ("margin", spacing(margin)),
        ("alignment", {"typeName": "alignment", "value": "start"}),
        ("width", sizing(*width)),
        ("height", sizing(*height)),
        ("visible", var_ref(visible_var)),
        ("preserveLayoutLocation", boolean(False)),
    ])


def font_props(bold=False, size=12, justification="left"):
    return OrderedDict([
        ("bold", boolean(bold)),
        ("italic", boolean(False)),
        ("underline", boolean(False)),
        ("font", {"typeName": "font", "value": FONT}),
        ("fontSize", integer(size)),
        ("justification", {"typeName": "text", "value": justification}),
    ])


# --------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------

def container(kind, children, width=("stretch", 100), height=("auto", None), margin=(0, 0, 0, 0),
              padding=(5, 5, 5, 5), border_width=0, border_color="000000", visible_var=None):
    props = base_props(width, height, margin, visible_var)
    props["backgroundColor"] = null()
    props["padding"] = spacing(padding)
    props["childArrangement"] = {"typeName": "childArrangement", "value": "start"}
    props["border"] = border(border_width, border_color)
    return {"type": kind, "properties": props, "children": children}


def vstack(children, **kw):
    return container("verticalStackContainer", children, **kw)


def hstack(children, **kw):
    kw.setdefault("width", ("auto", None))
    return container("horizontalStackContainer", children, **kw)


def text(value, bold=False, size=12, width=("stretch", 100), visible_var=None, margin=(2, 5, 2, 5)):
    props = base_props(width, ("auto", None), margin, visible_var)
    props["text"] = itext(value)
    props.update(font_props(bold, size))
    props["backgroundColor"] = null()
    props["textColor"] = null()
    props["padding"] = spacing(0)
    return {"type": "text", "properties": props}


def markdown(value, size=12, visible_var=None):
    props = base_props(("stretch", 100), ("auto", None), (2, 5, 2, 5), visible_var)
    props["text"] = itext(value)
    props["fontSize"] = integer(size)
    props["ariaLive"] = boolean(False)
    return {"type": "markdown", "properties": props}


def button(label, click, width=("auto", None), visible_var=None, disabled_var=None):
    props = base_props(width, ("auto", None), (5, 5, 5, 5), visible_var)
    props["text"] = itext(label)
    props["clickAction"] = click
    props["backgroundColor"] = null()
    props["textColor"] = null()
    props.update(font_props(False, 11, "center"))
    props["disabled"] = var_ref(disabled_var)
    return {"type": "button", "properties": props}


def dropdown(label, value_var, options=None, list_pair=None, placeholder="Select...", change=None,
             width=("stretch", 100), require=False, visible_var=None):
    """options: list of (value, display). list_pair: (values_list_var_id, labels_list_var_id)."""
    props = base_props(width, ("auto", None), (5, 5, 5, 5), visible_var)
    props["label"] = itext(label)
    props["labelPosition"] = {"typeName": "labelPosition", "value": "above"}
    props["placeholderText"] = itext(placeholder)
    if list_pair:
        props["options"] = {"typeName": "listPair",
                            "value": {"valuesList": list_pair[0], "labelsList": list_pair[1]}}
    else:
        props["options"] = {"typeName": "list", "value": [[itext(v), itext(d)] for v, d in options]}
    props["doesRequireValue"] = boolean(require)
    props["value"] = var_ref(value_var)
    props["changeAction"] = change or no_action()
    props["disabled"] = var_ref()
    return {"type": "dropdown", "properties": props}


def text_input(label, value_var, placeholder="", multiline=False, width=("stretch", 100), change=None,
               visible_var=None):
    props = base_props(width, ("auto", None), (5, 5, 5, 5), visible_var)
    props["label"] = itext(label)
    props["labelPosition"] = {"typeName": "labelPosition", "value": "above"}
    props["placeholderText"] = itext(placeholder)
    props["validation"] = {"typeName": "inputValidation", "value": ""}
    props["doesRequireValue"] = boolean(False)
    props["isMultilineInput"] = boolean(multiline)
    props["isPasswordInput"] = boolean(False)
    props["isPasswordToggleVisible"] = boolean(False)
    props["value"] = var_ref(value_var)
    props["changeAction"] = change or no_action()
    props["disabled"] = var_ref()
    return {"type": "input", "properties": props}


def checkbox(label, value_var, change=None):
    props = base_props(("auto", None), ("auto", None), (5, 5, 5, 5))
    props["text"] = itext(label)
    props.update(font_props(False, 12))
    props["textColor"] = null()
    props["clickAction"] = no_action()
    props["value"] = var_ref(value_var)
    props["changeAction"] = change or no_action()
    props["disabled"] = var_ref()
    return {"type": "checkbox", "properties": props}


# --------------------------------------------------------------------------
# Actions (steps inside custom actions, or inline component actions)
# --------------------------------------------------------------------------

def step(action_name, args):
    return {"type": "action", "actionName": action_name, "actionArgumentValues": args}


def set_string(var_id, value):
    return step("scripter.setVariable", [{
        "typeName": "variableWithValue",
        "value": {"variable": var_ref(var_id), "variableTypeName": "string",
                  "valueOfVariableProperty": itext(value)}}])


def set_bool(var_id, value):
    return step("scripter.setVariable", [{
        "typeName": "variableWithValue",
        "value": {"variable": var_ref(var_id), "variableTypeName": "boolean",
                  "valueOfVariableProperty": boolean(value)}}])


def alert(msg):
    return step("scripter.alert", [itext(msg)])


def open_url(url):
    return step("scripter.webPage", [itext(url)])


def copy_to_clipboard(txt):
    return step("scripter.copyToClipboard", [itext(txt)])


def change_page(page_id):
    return step("scripter.changePage", [{"typeName": "page", "value": page_id}])


def if_step(var_id, operator, rhs, if_block, else_block=None):
    return {"type": "if",
            "condition": {"type": "standard", "leftHandSide": var_ref(var_id),
                          "operator": operator, "rightHandSide": itext(rhs)},
            "ifBlock": if_block, "elseBlock": else_block or []}


def execute_data_action(action_id, inputs, outputs):
    """inputs: {contractField: var_id | ("text", literal)}, outputs: {contractField: var_id}"""
    return step("bridge.bridge", [{
        "typeName": "bridgeActionArguments",
        "value": {
            "actionName": action_id,
            "inputProperty": {"typeName": "objectFields",
                              "value": {"fieldProperties": {k: (itext(v[1]) if isinstance(v, tuple) else var_ref(v))
                                                            for k, v in inputs.items()}}},
            "successProperty": {"typeName": "objectFields",
                                "value": {"fieldProperties": {k: var_ref(v) for k, v in outputs.items()}}},
            "isHedwigAction": True,
        }}])


def get_email_headers(rows):
    """rows: list of (headerName, var_id). Reads MIME headers of the customer's inbound email."""
    return step("email.getEmailHeaders", [{
        "typeName": "list",
        "value": [[itext(h), var_ref(v), boolean(True)] for h, v in rows]}])


def inline(custom_action_id):
    return action_ref(custom_action_id)


def inline_steps_action(action_name, args):
    return {"typeName": "action", "value": {"actionName": action_name, "actionArgumentValues": args}}


# --------------------------------------------------------------------------
# Variables
# --------------------------------------------------------------------------
VARS = []


def var(name, vtype="string", value=None, description="", output=False, inp=False, is_list=False, dynamic=False):
    if value is None:
        value = {"string": "", "number": 0, "boolean": False}[vtype]
        if is_list:
            value = []
    v = OrderedDict([
        ("id", uid("var:" + name)),
        ("name", name),
        ("description", description),
        ("type", {"isDynamic": dynamic, "isList": is_list, "name": vtype}),
        ("value", value),
        ("input", inp),
        ("output", output),
    ])
    VARS.append(v)
    return v["id"]


# Category / triage (output = written to the conversation as participant attributes)
V_CATEGORY = var("EmailCategory", output=True,
                 description="Outlook-style category chosen by the agent. Saved to the interaction as participant data 'EmailCategory'.")
V_PRIORITY = var("EmailPriority", value="normal", output=True,
                 description="Importance flag (low / normal / high). Saved as participant data.")
V_FOLLOWUP = var("EmailFollowUp", "boolean", False, output=True,
                 description="Follow-up flag. Saved as participant data.")
V_NOTE = var("EmailCategoryNote", output=True,
             description="Free-text triage note. Saved as participant data.")
V_STATUS = var("StatusMessage", value="Ready.", description="Feedback line shown under the toolbar.")

# Search
V_SEARCH_ADDRESS = var("SearchAddress", description="Address or domain typed by the agent.")
V_SEARCH_MODE = var("SearchMode", value="sender", description="sender | domain")
V_DAYS_BACK = var("DaysBack", value="30", description="How far back to search (days).")
V_SEARCH_STATUS = var("SearchStatus", description="Search progress text.")
V_HAS_RESULTS = var("HasResults", "boolean", False, description="Shows the results panel.")
V_RESULT_COUNT = var("ResultCount", "number", 0, description="Number of matching emails (from data action).")
V_RESULT_IDS = var("ResultConversationIds", is_list=True, description="Conversation IDs (from data action).")
V_RESULT_LABELS = var("ResultLabels", is_list=True, description="'date | sender' labels (from data action).")
V_RESULT_SUMMARY = var("ResultSummary", description="Markdown list of results (from data action).")
V_SELECTED_ID = var("SelectedConversationId", description="Result chosen in the results dropdown.")
V_APP_HOST = var("GenesysAppHost", value="apps.mypurecloud.com",
                 description="Genesys Cloud app host for your region (apps.mypurecloud.ie, apps.mypurecloud.com.au, apps.euw2.pure.cloud ...). Used to open interactions.")

# Dynamic (computed) variables
V_SENDER_DOMAIN = var(
    "SenderDomain", dynamic=True,
    value='addr = {{email.customerEmailAddress}}; ifElse(indexOf(addr, "@") >= 0, slice(addr, indexOf(addr, "@") + 1), "")',
    description="Domain part of the customer's email address (computed).")
V_SEARCH_INTERVAL = var(
    "SearchInterval", dynamic=True,
    value=('days = number({{' + V_DAYS_BACK + '}}); '
           'endMs = {{scripter.rawCustomersCallStartTime}} + 3600000; '
           'startMs = endMs - days * 86400000; '
           'concat(formatDateISO(startMs), "/", formatDateISO(endMs))'),
    description="Analytics interval 'start/end' = DaysBack days before this email up to one hour after it arrived (computed).")

# Follow-ups list (emails flagged EmailFollowUp = true, from the analytics data action)
V_FU_COUNT = var("FollowUpCount", "number", 0, description="Number of flagged emails found.")
V_FU_IDS = var("FollowUpConversationIds", is_list=True, description="Conversation IDs of flagged emails.")
V_FU_LABELS = var("FollowUpLabels", is_list=True, description="'date | sender' labels of flagged emails.")
V_FU_SUMMARY = var("FollowUpSummary", description="Markdown list of flagged emails.")
V_FU_SELECTED = var("FollowUpSelectedId", description="Flagged email chosen in the follow-ups dropdown.")
V_FU_STATUS = var("FollowUpStatus", description="Follow-ups page status text.")
V_FU_LOADED = var("FollowUpsLoaded", "boolean", False, description="Shows the follow-ups list.")

# Message details (MIME headers of the customer's email)
V_HDR_FROM = var("HeaderFrom", description="MIME From header.")
V_HDR_TO = var("HeaderTo", description="MIME To header.")
V_HDR_DATE = var("HeaderDate", description="MIME Date header.")
V_HDR_REPLYTO = var("HeaderReplyTo", description="MIME Reply-To header.")
V_HDR_MSGID = var("HeaderMessageId", description="MIME Message-ID header.")
V_HEADERS_LOADED = var("HeadersLoaded", "boolean", False, description="Shows the message details panel.")

# --------------------------------------------------------------------------
# Pages (ids needed before actions that navigate)
# --------------------------------------------------------------------------
PAGE_HOME = uid("page:home")
PAGE_REPLIES = uid("page:quick-replies")
PAGE_FOLLOWUPS = uid("page:follow-ups")

# --------------------------------------------------------------------------
# Custom actions
# --------------------------------------------------------------------------
CUSTOM_ACTIONS = []


def custom_action(name, steps):
    a = {"id": uid("action:" + name), "name": name, "action": {"block": steps}}
    CUSTOM_ACTIONS.append(a)
    return a["id"]


SEARCH_INPUTS = {"Mode": V_SEARCH_MODE, "Address": V_SEARCH_ADDRESS, "Interval": V_SEARCH_INTERVAL}
SEARCH_OUTPUTS = {"Count": V_RESULT_COUNT, "ConversationIds": V_RESULT_IDS,
                  "Labels": V_RESULT_LABELS, "Summary": V_RESULT_SUMMARY}


def search_steps():
    return [
        set_bool(V_HAS_RESULTS, False),
        set_string(V_SELECTED_ID, ""),
        if_step(V_SEARCH_ADDRESS, "equal", "", [
            set_string(V_SEARCH_STATUS, "Enter an email address or a domain first."),
        ], [
            if_step(V_SEARCH_INTERVAL, "equal", "", [
                set_string(V_SEARCH_STATUS, "Could not compute the date window (interaction start time not available). Check the SearchInterval variable."),
            ], [
                set_string(V_SEARCH_STATUS, "Searching {{" + V_SEARCH_MODE + "}} '{{" + V_SEARCH_ADDRESS + "}}' for the last {{" + V_DAYS_BACK + "}} days ..."),
                execute_data_action(DATA_ACTION_PLACEHOLDER, SEARCH_INPUTS, SEARCH_OUTPUTS),
                set_bool(V_HAS_RESULTS, True),
                set_string(V_SEARCH_STATUS, "{{" + V_RESULT_COUNT + "}} inbound email(s) found for {{" + V_SEARCH_MODE + "}} '{{" + V_SEARCH_ADDRESS + "}}' in the last {{" + V_DAYS_BACK + "}} days (window {{" + V_SEARCH_INTERVAL + "}})."),
            ]),
        ]),
    ]


A_ON_LOAD = custom_action("Page load - reset", [
    set_string(V_STATUS, "Ready. Pick a category, then use the search tools below."),
    set_bool(V_HAS_RESULTS, False),
    set_bool(V_HEADERS_LOADED, False),
])

A_CATEGORY_CHANGED = custom_action("Category changed", [
    set_string(V_STATUS, "Category '{{" + V_CATEGORY + "}}' saved to this interaction (participant data: EmailCategory)."),
])

A_PRIORITY_CHANGED = custom_action("Priority changed", [
    set_string(V_STATUS, "Priority '{{" + V_PRIORITY + "}}' saved to this interaction (participant data: EmailPriority)."),
])

A_FOLLOWUP_CHANGED = custom_action("Follow-up flag changed", [
    set_string(V_STATUS, "Follow-up flag = {{" + V_FOLLOWUP + "}} saved to this interaction (participant data: EmailFollowUp). Flagged emails appear on the Follow-ups page."),
])

A_RUN_SEARCH = custom_action("Run email search", search_steps())

A_SEARCH_SENDER = custom_action("Search - all emails from this sender", [
    set_string(V_SEARCH_MODE, "sender"),
    set_string(V_SEARCH_ADDRESS, "{{email.customerEmailAddress}}"),
] + search_steps())

A_SEARCH_DOMAIN = custom_action("Search - all emails from this domain", [
    set_string(V_SEARCH_MODE, "domain"),
    set_string(V_SEARCH_ADDRESS, "{{" + V_SENDER_DOMAIN + "}}"),
] + search_steps())

A_OPEN_SELECTED = custom_action("Open selected interaction", [
    if_step(V_SELECTED_ID, "equal", "", [
        alert("Select a result in the 'Matching emails' list first."),
    ], [
        open_url("https://{{" + V_APP_HOST + "}}/directory/#/engage/admin/interactions/{{" + V_SELECTED_ID + "}}"),
    ]),
])

A_LOAD_HEADERS = custom_action("Load message details (MIME headers)", [
    get_email_headers([
        ("From", V_HDR_FROM), ("To", V_HDR_TO), ("Date", V_HDR_DATE),
        ("Reply-To", V_HDR_REPLYTO), ("Message-ID", V_HDR_MSGID),
    ]),
    set_bool(V_HEADERS_LOADED, True),
    set_string(V_STATUS, "Message details loaded."),
])

A_LOAD_FOLLOWUPS = custom_action("Load follow-ups list", [
    set_bool(V_FU_LOADED, False),
    set_string(V_FU_SELECTED, ""),
    if_step(V_SEARCH_INTERVAL, "equal", "", [
        set_string(V_FU_STATUS, "Could not compute the date window (interaction start time not available)."),
    ], [
        set_string(V_FU_STATUS, "Loading emails flagged for follow-up in the last {{" + V_DAYS_BACK + "}} days ..."),
        execute_data_action(FOLLOWUP_ACTION_PLACEHOLDER,
                            {"Interval": V_SEARCH_INTERVAL, "Attribute": ("text", "EmailFollowUp"), "Value": ("text", "true")},
                            {"Count": V_FU_COUNT, "ConversationIds": V_FU_IDS, "Labels": V_FU_LABELS, "Summary": V_FU_SUMMARY}),
        set_bool(V_FU_LOADED, True),
        set_string(V_FU_STATUS, "{{" + V_FU_COUNT + "}} email(s) flagged for follow-up in the last {{" + V_DAYS_BACK + "}} days (window {{" + V_SEARCH_INTERVAL + "}})."),
    ]),
])

A_OPEN_FOLLOWUP = custom_action("Open selected follow-up", [
    if_step(V_FU_SELECTED, "equal", "", [
        alert("Select an email in the follow-ups list first."),
    ], [
        open_url("https://{{" + V_APP_HOST + "}}/directory/#/engage/admin/interactions/{{" + V_FU_SELECTED + "}}"),
    ]),
])

A_CLEAR_SEARCH = custom_action("Clear search results", [
    set_bool(V_HAS_RESULTS, False),
    set_string(V_SELECTED_ID, ""),
    set_string(V_SEARCH_STATUS, ""),
    set_string(V_SEARCH_ADDRESS, ""),
])

A_COPY_SENDER = custom_action("Copy sender address", [
    copy_to_clipboard("{{email.customerEmailAddress}}"),
    set_string(V_STATUS, "Sender address copied to clipboard."),
])

QUICK_REPLIES = [
    ("Acknowledge receipt",
     "Hello,\n\nThank you for your email. We have received your request and a member of our team is looking into it. "
     "We will get back to you as soon as possible.\n\nKind regards,\n{{scripter.agentName}}"),
    ("Need more information",
     "Hello,\n\nThank you for contacting us. To help us resolve this quickly, could you please reply with:\n"
     "- Your account or reference number\n- A short description of the issue\n- Any relevant dates or screenshots\n\n"
     "Kind regards,\n{{scripter.agentName}}"),
    ("Resolved - closing",
     "Hello,\n\nWe are pleased to confirm that your request has been resolved. If there is anything else we can help with, "
     "simply reply to this email.\n\nKind regards,\n{{scripter.agentName}}"),
    ("Transferred to specialist team",
     "Hello,\n\nThank you for your email. Your request has been passed to our specialist team, who will contact you directly. "
     "Your reference is {{scripter.interactionId}}.\n\nKind regards,\n{{scripter.agentName}}"),
]
A_QUICK = []
for title, body in QUICK_REPLIES:
    A_QUICK.append((title, custom_action("Quick reply - " + title, [
        copy_to_clipboard(body),
        set_string(V_STATUS, "Quick reply '" + title + "' copied to clipboard - paste it into your reply."),
    ])))

# --------------------------------------------------------------------------
# Home page layout
# --------------------------------------------------------------------------
CATEGORY_OPTIONS = [
    ("complaint", "\U0001F534 Complaint"),
    ("billing", "\U0001F7E0 Billing / payment"),
    ("technical_support", "\U0001F7E1 Technical support"),
    ("sales", "\U0001F7E2 Sales enquiry"),
    ("account_change", "\U0001F535 Account / profile change"),
    ("general", "\U0001F7E3 General question"),
    ("spam", "⚫ Spam / junk"),
    ("other", "⚪ Other"),
]
PRIORITY_OPTIONS = [("low", "Low"), ("normal", "Normal"), ("high", "High importance")]
MODE_OPTIONS = [("sender", "Exact sender address"), ("domain", "Whole domain (everyone @domain)")]
DAYS_OPTIONS = [("7", "Last 7 days"), ("30", "Last 30 days"), ("90", "Last 90 days"), ("180", "Last 180 days")]

header = vstack([
    text("✉️ Email Assistant", bold=True, size=18),
    text("From: {{email.customerEmailAddress}}   |   Subject: {{email.emailSubject}}", size=12),
    text("Queue: {{scripter.queueName}}   |   Agent: {{scripter.agentName}}   |   Interaction: {{scripter.interactionId}}", size=10),
    text("{{" + V_STATUS + "}}", size=11, bold=True),
], padding=(8, 8, 8, 8), border_width=1, border_color="c9c9c9")

triage = vstack([
    text("Categorise", bold=True, size=14),
    hstack([
        dropdown("Category", V_CATEGORY, options=CATEGORY_OPTIONS, placeholder="Choose a category...",
                 change=inline(A_CATEGORY_CHANGED), width=("pixels", 260)),
        dropdown("Importance", V_PRIORITY, options=PRIORITY_OPTIONS, placeholder="Normal",
                 change=inline(A_PRIORITY_CHANGED), width=("pixels", 170)),
        checkbox("Flag for follow-up", V_FOLLOWUP, change=inline(A_FOLLOWUP_CHANGED)),
    ]),
    text_input("Triage note (saved with the interaction)", V_NOTE,
               placeholder="Optional note for reporting / the next agent ...", multiline=True),
], padding=(8, 8, 8, 8), border_width=1, border_color="c9c9c9", margin=(8, 0, 0, 0))

search = vstack([
    text("Search emails (like Outlook search)", bold=True, size=14),
    hstack([
        button("\U0001F50D All emails from this sender", inline(A_SEARCH_SENDER)),
        button("\U0001F310 All emails from this domain ({{" + V_SENDER_DOMAIN + "}})", inline(A_SEARCH_DOMAIN)),
        button("Copy sender address", inline(A_COPY_SENDER)),
    ]),
    hstack([
        text_input("Address or domain", V_SEARCH_ADDRESS, placeholder="someone@example.com  or  example.com",
                   width=("pixels", 280)),
        dropdown("Match", V_SEARCH_MODE, options=MODE_OPTIONS, placeholder="Exact sender address", width=("pixels", 230)),
        dropdown("Period", V_DAYS_BACK, options=DAYS_OPTIONS, placeholder="Last 30 days", width=("pixels", 150)),
        button("Search", inline(A_RUN_SEARCH)),
        button("Clear", inline(A_CLEAR_SEARCH)),
    ]),
    text("{{" + V_SEARCH_STATUS + "}}", size=11),
    vstack([
        hstack([
            dropdown("Matching emails ({{" + V_RESULT_COUNT + "}})", V_SELECTED_ID,
                     list_pair=(V_RESULT_IDS, V_RESULT_LABELS), placeholder="Select an email to open ...",
                     width=("pixels", 420)),
            button("Open selected interaction", inline(A_OPEN_SELECTED)),
        ]),
        markdown("{{" + V_RESULT_SUMMARY + "}}"),
    ], visible_var=V_HAS_RESULTS, padding=(0, 0, 0, 0)),
], padding=(8, 8, 8, 8), border_width=1, border_color="c9c9c9", margin=(8, 0, 0, 0))

details = vstack([
    text("Message details", bold=True, size=14),
    hstack([
        button("Load message details (MIME headers)", inline(A_LOAD_HEADERS)),
        button("\U0001F6A9 Follow-ups list", inline_steps_action("scripter.changePage", [{"typeName": "page", "value": PAGE_FOLLOWUPS}])),
        button("Quick replies →", inline_steps_action("scripter.changePage", [{"typeName": "page", "value": PAGE_REPLIES}])),
    ]),
    vstack([
        text("From: {{" + V_HDR_FROM + "}}", size=11),
        text("To: {{" + V_HDR_TO + "}}", size=11),
        text("Reply-To: {{" + V_HDR_REPLYTO + "}}", size=11),
        text("Date: {{" + V_HDR_DATE + "}}", size=11),
        text("Message-ID: {{" + V_HDR_MSGID + "}}", size=11),
    ], visible_var=V_HEADERS_LOADED, padding=(0, 0, 0, 0)),
], padding=(8, 8, 8, 8), border_width=1, border_color="c9c9c9", margin=(8, 0, 0, 0))

home_root = vstack([header, triage, search, details], height=("stretch", 100), padding=(5, 5, 5, 5))

# --------------------------------------------------------------------------
# Quick replies page
# --------------------------------------------------------------------------
reply_buttons = [button("\U0001F4CB " + title, inline(aid), width=("stretch", 100)) for title, aid in A_QUICK]

replies_root = vstack([
    text("\U0001F4CB Quick replies", bold=True, size=18),
    text("Click a template to copy it to your clipboard, then paste it into the email reply. "
         "Templates use your name ({{scripter.agentName}}) automatically.", size=11),
    text("{{" + V_STATUS + "}}", size=11, bold=True),
    vstack(reply_buttons, padding=(8, 8, 8, 8), border_width=1, border_color="c9c9c9", margin=(8, 0, 0, 0)),
    markdown(
        "### Category guide\n\n"
        "| Category | Use it for |\n|---|---|\n"
        "| \U0001F534 Complaint | Customer is unhappy with service, product or a previous contact |\n"
        "| \U0001F7E0 Billing / payment | Invoices, refunds, payment failures, pricing disputes |\n"
        "| \U0001F7E1 Technical support | Faults, outages, configuration help |\n"
        "| \U0001F7E2 Sales enquiry | New business, upgrades, quotes |\n"
        "| \U0001F535 Account / profile change | Contact details, users, permissions, cancellations |\n"
        "| \U0001F7E3 General question | Anything informational that is not one of the above |\n"
        "| ⚫ Spam / junk | Unsolicited or automated mail - disconnect without reply |\n"
        "| ⚪ Other | Use sparingly and add a triage note |\n\n"
        "Category, importance, follow-up flag and note are saved on the interaction as participant data "
        "(EmailCategory, EmailPriority, EmailFollowUp, EmailCategoryNote) so they can be reported on and used in Architect."),
    button("← Back to email", inline_steps_action("scripter.changePage", [{"typeName": "page", "value": PAGE_HOME}])),
], height=("stretch", 100), padding=(5, 5, 5, 5))


# --------------------------------------------------------------------------
# Follow-ups page
# --------------------------------------------------------------------------
followups_root = vstack([
    text("\U0001F6A9 Emails flagged for follow-up", bold=True, size=18),
    text("Every email where an agent ticked 'Flag for follow-up' (participant data EmailFollowUp = true). "
         "Select one and open it to reply, or untick the flag in that interaction's script to remove it from this list.", size=11),
    hstack([
        dropdown("Period", V_DAYS_BACK, options=DAYS_OPTIONS, placeholder="Last 30 days", width=("pixels", 150)),
        button("\U0001F504 Refresh", inline(A_LOAD_FOLLOWUPS)),
        button("← Back to email", inline_steps_action("scripter.changePage", [{"typeName": "page", "value": PAGE_HOME}])),
    ]),
    text("{{" + V_FU_STATUS + "}}", size=11, bold=True),
    vstack([
        hstack([
            dropdown("Flagged emails ({{" + V_FU_COUNT + "}})", V_FU_SELECTED,
                     list_pair=(V_FU_IDS, V_FU_LABELS), placeholder="Select an email to open ...",
                     width=("pixels", 420)),
            button("Open selected interaction", inline(A_OPEN_FOLLOWUP)),
        ]),
        markdown("{{" + V_FU_SUMMARY + "}}"),
    ], visible_var=V_FU_LOADED, padding=(8, 8, 8, 8), border_width=1, border_color="c9c9c9", margin=(8, 0, 0, 0)),
], height=("stretch", 100), padding=(5, 5, 5, 5))


def page(page_id, name, root, on_load=None):
    return OrderedDict([
        ("id", page_id),
        ("name", name),
        ("organizationId", ORG_ID),
        ("scriptId", SCRIPT_ID),
        ("versionId", VERSION_ID),
        ("properties", {"onLoadAction": action_ref(on_load) if on_load else no_action(),
                        "backgroundColor": null()}),
        ("dataVersion", 0),
        ("rootContainer", root),
    ])


def feature(enabled, extra=None):
    props = {"enabled": boolean(enabled)}
    if extra:
        props.update(extra)
    return {"properties": props}


FEATURES = OrderedDict([
    ("dialer", feature(False, {"contactListId": {"typeName": "text", "value": ""},
                               "onContactDataLoadAction": no_action()})),
    ("scripter", feature(True)),
    ("screenPop", feature(False)),
    ("callback", feature(False)),
    ("chat", feature(False)),
    ("email", feature(True)),          # exposes {{email.customerEmailAddress}}, {{email.emailSubject}}, email.getEmailHeaders
    ("message", feature(False)),
    ("bridge", feature(True)),         # "Data Actions" script property -> bridge.bridge (Execute Data Action)
    ("uuiData", feature(False)),
    ("customerSecuredData", feature(False)),
    ("list", feature(True)),           # list variables / List.Push
    ("workItem", feature(False)),
])

SCRIPT = OrderedDict([
    ("id", SCRIPT_ID),
    ("createdDate", "2026-09-01T00:00:00.000Z"),
    ("modifiedDate", "2026-09-01T00:00:00.000Z"),
    ("name", "Email Assistant"),
    ("organizationId", ORG_ID),
    ("versionId", VERSION_ID),
    ("startPageId", PAGE_HOME),
    ("pages", [
        page(PAGE_HOME, "Email", home_root, on_load=A_ON_LOAD),
        page(PAGE_REPLIES, "Quick replies", replies_root),
        page(PAGE_FOLLOWUPS, "Follow-ups", followups_root, on_load=A_LOAD_FOLLOWUPS),
    ]),
    ("features", FEATURES),
    ("variables", VARS),
    ("customActions", CUSTOM_ACTIONS),
    ("dataVersion", 0),
])

# --------------------------------------------------------------------------
# Data action: search inbound emails by exact sender or by domain
# --------------------------------------------------------------------------
REQUEST_TEMPLATE = (
    '#set($mode = "$!input.Mode")'
    '#set($mode = $mode.toLowerCase().trim())'
    '#set($needle = "$!input.Address")'
    '#set($needle = $needle.toLowerCase().trim())'
    '{'
    ' "interval": "${input.Interval}",'
    ' "order": "desc",'
    ' "orderBy": "conversationStart",'
    ' "paging": { "pageSize": 50, "pageNumber": 1 },'
    ' "segmentFilters": [ { "type": "and", "predicates": ['
    '   { "type": "dimension", "dimension": "mediaType", "operator": "matches", "value": "email" },'
    '   { "type": "dimension", "dimension": "direction", "operator": "matches", "value": "inbound" }'
    '#if($mode == "sender")'
    '   ,{ "type": "dimension", "dimension": "addressFrom", "operator": "matches", "value": "$esc.jsonEncode($needle)" }'
    '#end'
    '#if($mode == "domain")'
    '   ,{ "type": "dimension", "dimension": "addressFrom", "operator": "matches", "value": "*@$esc.jsonEncode($needle)" }'
    '#end'
    ' ] } ]'
    '}'
)

FOLLOWUP_REQUEST_TEMPLATE = (
    '#set($attr = "$!input.Attribute")#set($attr = $attr.trim())'
    '#if($attr == "")#set($attr = "EmailFollowUp")#end'
    '#set($val = "$!input.Value")#set($val = $val.trim())'
    '#if($val == "")#set($val = "true")#end'
    '{'
    ' "interval": "${input.Interval}",'
    ' "order": "desc",'
    ' "orderBy": "conversationStart",'
    ' "paging": { "pageSize": 50, "pageNumber": 1 },'
    ' "segmentFilters": [ { "type": "and", "predicates": ['
    '   { "type": "dimension", "dimension": "mediaType", "operator": "matches", "value": "email" },'
    '   { "type": "property", "propertyType": "string", "property": "$esc.jsonEncode($attr)", "value": "$esc.jsonEncode($val)" }'
    ' ] } ]'
    '}'
)

# Velocity notes: Genesys allows only #if / #set in templates (no #foreach) and the success
# template cannot see $input (only translation-map values), so all filtering happens in the
# request above and this template only formats. Each conversation in the JSON text of the
# conversations array is reduced to one "id|start|from;" record with Java regex string methods,
# then re-rendered as JSON arrays and a markdown list. Velocity single-quoted strings are not
# interpolated, which is why the regexes are written in single quotes.
SUCCESS_TEMPLATE = (
    '#set($src = "${convs}")'
    '#set($rows = "")'
    '#if($src.contains(\'"conversationId"\'))'
    '#set($rows = $src.replaceFirst(\'(?s)^.*?(?="conversationId")\', ""))'
    '#set($rows = $rows.replaceAll(\'(?s)"conversationId"\s*:\s*"([^"]+)".*?"conversationStart"\s*:\s*"([^"]+)".*?"addressFrom"\s*:\s*"([^"]+)".*?(?="conversationId"|$)\', \'$1|$2|$3;\'))'
    '#end'
    '#set($n = $rows.length() - $rows.replace(";", "").length())'
    '#set($ids = $rows.replaceAll(\'([^|;]*)\|([^|;]*)\|([^|;]*);\', \'"$1",\'))'
    '#set($lbl = $rows.replaceAll(\'([^|;]*)\|(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})[^|;]*\|([^|;]*);\', \'"$2 $3  |  $4",\'))'
    '#set($sum = $rows.replaceAll(\'([^|;]*)\|(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})[^|;]*\|([^|;]*);\', \'- $2 $3 | $4 | `$1`\\\\n\'))'
    '#set($ids = $ids.replaceAll(",$", ""))'
    '#set($lbl = $lbl.replaceAll(",$", ""))'
    '{ "Count": $n,'
    ' "ConversationIds": [$ids],'
    ' "Labels": [$lbl],'
    ' "Summary": "#if($n == 0)No inbound emails matched.#else**Most recent first** (date | sender | interaction id)\\n\\n$sum#end"'
    ' }'
)

OUTPUT_SCHEMA = OrderedDict([
    ("$schema", "http://json-schema.org/draft-04/schema#"),
    ("title", "Email list - output"),
    ("type", "object"),
    ("properties", OrderedDict([
        ("Count", {"type": "integer"}),
        ("ConversationIds", {"type": "array", "items": {"type": "string"}}),
        ("Labels", {"type": "array", "items": {"type": "string"}}),
        ("Summary", {"type": "string"}),
    ])),
    ("additionalProperties", True),
])


def data_action(name, request_template, input_props, required):
    return OrderedDict([
        ("name", name),
        ("integrationType", "purecloud-data-actions"),
        ("actionType", "custom"),
        ("config", OrderedDict([
            ("request", OrderedDict([
                ("requestUrlTemplate", "/api/v2/analytics/conversations/details/query"),
                ("requestType", "POST"),
                ("headers", {}),
                ("requestTemplate", request_template),
            ])),
            ("response", OrderedDict([
                ("translationMap", OrderedDict([("convs", "$.conversations[*]")])),
                ("translationMapDefaults", OrderedDict([("convs", "[]")])),
                ("successTemplate", SUCCESS_TEMPLATE),
            ])),
        ])),
        ("contract", OrderedDict([
            ("input", {"inputSchema": OrderedDict([
                ("$schema", "http://json-schema.org/draft-04/schema#"),
                ("title", name + " - input"),
                ("type", "object"),
                ("properties", input_props),
                ("required", required),
                ("additionalProperties", True),
            ])}),
            ("output", {"successSchema": OUTPUT_SCHEMA}),
        ])),
        ("secure", False),
    ])


DATA_ACTION = data_action(DATA_ACTION_NAME, REQUEST_TEMPLATE, OrderedDict([
    ("Mode", {"type": "string", "description": "Exactly one of: sender | domain | all"}),
    ("Address", {"type": "string", "description": "Email address (Mode=sender) or domain without @ (Mode=domain)"}),
    ("Interval", {"type": "string", "description": "ISO-8601 interval start/end, e.g. 2026-08-01T00:00:00Z/2026-09-01T00:00:00Z"}),
]), ["Mode", "Address", "Interval"])

FOLLOWUP_ACTION = data_action(FOLLOWUP_ACTION_NAME, FOLLOWUP_REQUEST_TEMPLATE, OrderedDict([
    ("Interval", {"type": "string", "description": "ISO-8601 interval start/end, e.g. 2026-08-01T00:00:00Z/2026-09-01T00:00:00Z"}),
    ("Attribute", {"type": "string", "description": "Participant data key to match (default EmailFollowUp)"}),
    ("Value", {"type": "string", "description": "Value the attribute must equal (default true)"}),
]), ["Interval"])


def main():
    os.makedirs(os.path.dirname(SCRIPT_OUT), exist_ok=True)
    os.makedirs(os.path.dirname(ACTION_OUT), exist_ok=True)
    with open(SCRIPT_OUT, "w", encoding="utf-8") as f:
        json.dump(SCRIPT, f, indent=2, ensure_ascii=True)  # ASCII-safe: emoji become \\uXXXX escapes
        f.write("\n")
    with open(ACTION_OUT, "w", encoding="utf-8") as f:
        json.dump(DATA_ACTION, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(FOLLOWUP_ACTION_OUT, "w", encoding="utf-8") as f:
        json.dump(FOLLOWUP_ACTION, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("wrote", os.path.relpath(SCRIPT_OUT, ROOT))
    print("wrote", os.path.relpath(ACTION_OUT, ROOT))
    print("wrote", os.path.relpath(FOLLOWUP_ACTION_OUT, ROOT))
    print("follow-ups data action placeholder id:", FOLLOWUP_ACTION_PLACEHOLDER)
    print("data action placeholder id:", DATA_ACTION_PLACEHOLDER)


if __name__ == "__main__":
    main()
