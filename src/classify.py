"""Issue classifier for Vireo support tickets.

Two modes:
  - rules (default, free): keyword classifier over customer_message.
  - llm (optional): Claude Haiku over tickets the rules can't place confidently.
    Needs ANTHROPIC_API_KEY. Used only for the residual, so cost stays small.

The taxonomy mirrors the helpdesk's own category list so output is directly
comparable with the bot's intake tag and the agent's closure tag.
"""

import os
import re

CATEGORIES = [
    "Charging & Battery", "Audio Quality", "Connectivity", "App & Firmware",
    "Delivery & Shipping", "Billing & Payments", "Returns & Refunds",
    "Warranty & Repair", "Account & Login", "Product Enquiry", "Other",
]

# Order matters: first hit wins. Patterns were tuned against tickets whose
# category the agent set at closure (see validate.py).
RULES = [
    ("Billing & Payments", r"double payment|amount deducted|payment (?:debited|failed|deducted)|\bupi\b|\butr\b|no order confirmation|refund not (?:received|credited)|(?<!dis)charged twice|invoice|\bemi\b|cashback|coupon|price drop|paid.*(?:no order|nothing shows)"),
    ("Charging & Battery", r"not charging|no charge|charg\w* (?:case|issue|problem)|battery|drain|lasts? (?:all day|\d+ (?:min|hour))|gives up after|only .* lights up|won'?t turn on|dead on arrival|doesn'?t (?:charge|power)|power(?:ing)? (?:on|off) issue|stays flat"),
    ("Delivery & Shipping", r"not delivered|haven'?t received|tracking|courier|shipment|delayed|awb|out for delivery|wrong address|change .*address|address change|update my shipping|flat number|delivery boy|crushed|damaged (?:box|in transit)|box was"),
    ("Returns & Refunds", r"return|pickup|refund status|want (?:a )?refund|money back|replace\w* status|reverse pickup"),
    ("App & Firmware", r"app (?:keeps |is )?(?:crash|not opening|hangs|freez)|firmware|fw update|after (?:the )?update|ota|app not"),
    ("Connectivity", r"\bpaa?ir|bluetooth|\bconnect|discover|disconnect|drops? (?:the )?connection|won'?t sync|sync(?:ing)? (?:fail|issue)|keeps losing my phone"),
    ("Audio Quality", r"crackl|static|no sound|one side|left side.*(?:sound|audio)|distort|buzz|mic|people cannot hear|echo|volume (?:low|issue)"),
    ("Warranty & Repair", r"warranty|service cent|repair|rma|strap|hinge|button (?:broke|stuck|fell)|snapped|physical damage|cracked screen"),
    ("Account & Login", r"login|log in|password|otp|account (?:locked|access)|can'?t sign"),
    ("Product Enquiry", r"before (?:i )?buy|planning to (?:buy|order)|does it support|compatib|which (?:model|colour|size)|difference between|when .*available|in stock"),
]

_COMPILED = [(cat, re.compile(pat, re.I)) for cat, pat in RULES]


def classify_rules(message: str) -> tuple[str, bool]:
    """Return (category, confident). Unmatched -> ('Other', False)."""
    text = message or ""
    for cat, rx in _COMPILED:
        if rx.search(text):
            return cat, True
    return "Other", False


def classify_llm(messages: list[str], model: str = "claude-haiku-4-5-20251001",
                 batch_size: int = 20) -> list[str]:
    """Classify messages with Claude. Only called with --llm. One API call
    per `batch_size` messages, numbered list in, numbered list out."""
    import anthropic  # deferred so the default path has zero deps

    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY
    out: list[str] = []
    cats = " | ".join(CATEGORIES)
    for i in range(0, len(messages), batch_size):
        chunk = messages[i:i + batch_size]
        numbered = "\n".join(f"{j+1}. {m[:400]}" for j, m in enumerate(chunk))
        resp = client.messages.create(
            model=model,
            max_tokens=30 * len(chunk),
            messages=[{"role": "user", "content":
                       f"Classify each customer-support message into exactly one of: {cats}.\n"
                       f"Reply with one line per message: '<number>. <category>'. Nothing else.\n\n{numbered}"}],
        )
        lines = resp.content[0].text.strip().splitlines()
        parsed = {}
        for line in lines:
            m = re.match(r"\s*(\d+)\.\s*(.+)", line)
            if m and m.group(2).strip() in CATEGORIES:
                parsed[int(m.group(1))] = m.group(2).strip()
        out.extend(parsed.get(j + 1, "Other") for j in range(len(chunk)))
    return out
