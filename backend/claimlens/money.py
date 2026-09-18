from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re


@dataclass(frozen=True)
class MoneyParse:
    paise: int | None
    status: str
    reason: str | None = None


def parse_money_to_paise(value: object, rounding=ROUND_HALF_UP) -> MoneyParse:
    if isinstance(value, bool) or value is None:
        return MoneyParse(None, "INVALID", "Amount is missing or not numeric")
    text = str(value).strip().replace("₹", "").replace("INR", "").replace("Rs.", "").replace("Rs", "").strip()
    if not text:
        return MoneyParse(None, "INVALID", "Amount is empty")
    negative = text.startswith("(") and text.endswith(")")
    if ("(" in text or ")" in text) and not negative:
        return MoneyParse(None, "INVALID", "Unbalanced negative amount notation")
    if negative:
        text = text[1:-1].strip()
        if text.startswith(("-", "+")):
            return MoneyParse(None, "INVALID", "Conflicting amount signs")
    if "," in text and "." not in text:
        tail = text.rsplit(",", 1)[1]
        if len(tail) in (1, 2):
            return MoneyParse(None, "AMBIGUOUS", "Comma may be a decimal separator")
    if "," in text:
        integer = text.split(".", 1)[0].lstrip("+-")
        if not (re.fullmatch(r"\d{1,3}(?:,\d{3})+", integer) or re.fullmatch(r"\d{1,2}(?:,\d{2})*,\d{3}", integer)):
            return MoneyParse(None, "AMBIGUOUS", "Unrecognized thousands grouping")
    cleaned = re.sub(r"[\s,]", "", text)
    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned):
        return MoneyParse(None, "INVALID", "Amount contains unsupported characters")
    try:
        amount = Decimal(cleaned)
        if negative:
            amount = -amount
        paise = int((amount * 100).quantize(Decimal("1"), rounding=rounding))
        if abs(paise) > 9007199254740991:
            return MoneyParse(None, "INVALID", "Amount exceeds the exact frontend integer range")
        return MoneyParse(paise, "NORMALIZED")
    except (InvalidOperation, ValueError):
        return MoneyParse(None, "INVALID", "Amount cannot be represented")


def format_inr(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    whole, subunit = divmod(abs(paise), 100)
    return f"{sign}₹{whole:,}.{subunit:02d}"
