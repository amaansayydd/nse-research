"""Turn NSE corporate-action PURPOSE text into price-adjustment terms.

NSE's PREV_CLOSE is NOT adjusted on ex-dates (verified: LITL 04-Jan-2010 shows
prev close 576.70 against an open of 59.40 after a Rs10 -> Re1 split). So the
ex-date return must be repaired here:

    base    = prev_close * factor            (factor < 1 for splits and bonuses)
    ret_cc  = (close + dividend) / base - 1

Anything we cannot turn into a factor with confidence is marked `unresolved`
and the ex-date return is set to missing rather than guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUM = r"(\d+(?:\.\d+)?)"
_FV_CHANGE = re.compile(
    rf"R[SE]\.?\s*{_NUM}\s*(?:/-?)?\s*(?:PER SHARE\s*)?TO\s*R[SE]\.?\s*{_NUM}(?:\s*/-?)?"
)
_BONUS = re.compile(r"BON[A-Z]*\s*-?\s*(\d+)\s*:\s*(\d+)")
_RIGHTS = re.compile(
    rf"(?:RIGHTS?|RHTS?|RGHTS?)\s*-?\s*(\d+)\s*:\s*(\d+)\s*@?\s*(?:PREMIUM|PREM|PRM)\s*(?:OF\s*)?(?:R[SE]\.?)?\s*{_NUM}(?:\s*/-?)?"
)
_RUPEES = re.compile(rf"R[SE]\.?\s*-?\s*{_NUM}")
_BARE_DIV = re.compile(rf"(?:DIV[A-Z]*|FIN|SPL|INT)[\s\-:]*{_NUM}(?!\s*(?:ND|RD|ST|TH|:|\d))")
_SPLIT_WORD = re.compile(r"SP[LT]|CONSOL|SUB-?\s?DIV|FV|FACE")
_RIGHTS_WORD = re.compile(r"RIGHT|RHT|RGHT")
_UNRESOLVED_WORD = re.compile(
    r"SCH\b|SCHEME|ARR[A-Z]*G|DEMER|DE-MER|DMRG|REDUC|CAP\.? ?RED|AMALG|MERGER|SPIN|CCPS|WARRANT|WRNT|DVR"
)


@dataclass(frozen=True)
class Action:
    factor: float = 1.0          # multiply prev_close by this (splits, bonuses)
    dividend: float = 0.0        # rupees per share
    rights: tuple[int, int, float] | None = None  # (new, per_held, premium)
    div_unknown: bool = False    # a dividend with no parseable amount
    unresolved: bool = False     # price-moving event we cannot quantify
    kinds: str = ""


def parse_purpose(text: str) -> Action:
    t = re.sub(r"\s+", " ", (text or "").upper()).strip()
    rest = t
    factor, kinds, unresolved, rights = 1.0, [], False, None

    m = _FV_CHANGE.search(rest)
    if m and _SPLIT_WORD.search(t):
        old, new = float(m.group(1)), float(m.group(2))
        if old > 0 and new > 0 and old != new:
            factor *= new / old
            kinds.append("split" if new < old else "consolidation")
        rest = rest.replace(m.group(0), " ")
    elif re.search(r"SPLIT|SPLT|CONSOL|SUB-?\s?DIVISION", t) and "DIV" not in t.replace("SUB-DIV", "").replace("SUBDIV", ""):
        unresolved = True  # says split but gives no usable ratio

    m = _BONUS.search(rest)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 0 and b > 0:
            factor *= b / (a + b)
            kinds.append("bonus")
        rest = rest.replace(m.group(0), " ")
    if "BON" in rest:
        unresolved = True  # bonus of another class, or unparsed ratio

    if _RIGHTS_WORD.search(rest):
        m = _RIGHTS.search(rest)
        tail = rest.replace(m.group(0), " ") if m else rest
        if m and not re.search(r"&|WRNT|WARRANT|CCPS|NCD", tail):
            rights = (int(m.group(1)), int(m.group(2)), float(m.group(3)))
            kinds.append("rights")
            rest = tail
        else:
            unresolved = True

    if _UNRESOLVED_WORD.search(rest):
        unresolved = True

    dividend, div_unknown = 0.0, False
    rest = re.sub(r"SUB[\s-]?DIVISION", " ", rest)  # a split word, not a dividend
    if "DIV" in rest:
        amounts = [float(x) for x in _RUPEES.findall(rest)]
        if not amounts and "%" not in rest:
            amounts = [float(x) for x in _BARE_DIV.findall(rest)]
        if amounts:
            dividend = sum(amounts)
            kinds.append("dividend")
        else:
            div_unknown = True
            kinds.append("dividend?")

    if unresolved:
        kinds.append("unresolved")
    return Action(factor, dividend, rights, div_unknown, unresolved, "+".join(kinds))


def rights_factor(rights: tuple[int, int, float], prev_close: float) -> float:
    """Theoretical ex-rights price / cum-rights price.

    Issue price is approximated by the premium alone because face value is not
    in the text; the error is a/(a+b) * face_value/price, normally well under 1%.
    Rights priced above the market have no value and get factor 1.
    """
    a, b, premium = rights
    if prev_close <= 0 or premium >= prev_close:
        return 1.0
    return (b * prev_close + a * premium) / ((a + b) * prev_close)
