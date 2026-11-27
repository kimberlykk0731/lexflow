"""Independent, deliberately narrow benchmark reference calculations.

No imports from lexflow (in particular rules.py). These are reference formulae
under the assumptions written on each case card, not a general legal oracle.
Qualitative labels require human review; an LLM review never certifies them.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

UNKNOWN = (None, "", "不清楚", "记不清", "不知道", "说不清")


def money(value) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def add_year(anchor: str) -> str:
    d = date.fromisoformat(anchor)
    return d.replace(year=d.year + 1, day=min(d.day, monthrange(d.year + 1, d.month)[1])).isoformat()


def compensated_months(start: str, end: str) -> float:
    """Full years + a half month for ANY positive remainder below six months."""
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    if e <= s:
        raise ValueError("employment end must be after start")
    years = e.year - s.year - ((e.month, e.day) < (s.month, s.day))
    anniversary = s.replace(year=s.year + years,
                            day=min(s.day, monthrange(s.year + years, s.month)[1]))
    if anniversary == e:
        return float(years)
    month_index = anniversary.year * 12 + anniversary.month - 1 + 6
    y, m0 = divmod(month_index, 12)
    six_months = date(y, m0 + 1, min(anniversary.day, monthrange(y, m0 + 1)[1]))
    return years + (1.0 if e >= six_months else 0.5)


def calculate(spec: dict, facts: dict, today: str) -> object:
    op = spec["calculator"]
    if any(facts.get(k) in UNKNOWN for k in spec.get("depends", [])):
        return None
    wage = Decimal(str(facts.get("monthly_wage") or 0))
    if op == "literal":
        return spec["value"]
    if op == "condition":
        return all(facts.get(k) == v for k, v in spec["conditions"].items())
    if op == "fact":
        return facts[spec["field"]]
    if op == "deadline":
        return add_year(facts[spec.get("anchor", "dismiss_date")])
    if op == "expired":
        return today > add_year(facts[spec.get("anchor", "dismiss_date")])
    if op == "dismissal":
        pay = spec["pay_type"]
        if pay == "0":
            return 0.0
        n = Decimal(str(compensated_months(facts["start_date"], facts["dismiss_date"])))
        return money(wage * (n + (1 if pay == "N+1" else 0)) * (2 if pay == "2N" else 1))
    if op == "overtime":
        hourly = wage / Decimal("174")
        parts = [money(hourly * Decimal(mult) * Decimal(str(facts[key])))
                 for key, mult in (("overtime_hours_weekday", "1.5"),
                                   ("overtime_hours_rest", "2"),
                                   ("overtime_hours_holiday", "3"))]
        return money(sum(Decimal(str(x)) for x in parts))
    if op == "double_pay":
        return money(wage * Decimal(str(min(11, max(0, facts["no_contract_months"])))))
    if op == "annual_leave":
        years = facts["cumulative_work_years"]
        entitled = 0 if years < 1 else 5 if years < 10 else 10 if years < 20 else 15
        return money(wage / Decimal("21.75") * Decimal(str(max(0, entitled - facts["annual_leave_taken"]))) * 2)
    if op == "noncompete":
        # These fixtures use an explicit agreed amount, not an assumed local minimum.
        return money(Decimal(str(facts["noncompete_compensation"])) *
                     Decimal(str(min(24, max(0, facts["noncompete_months"])))))
    if op == "work_injury":
        months = {"七级": 13, "八级": 11, "九级": 9, "十级": 7}
        level = facts["disability_level"]
        return money(wage * months[level]) if level in months else None
    raise ValueError(f"unsupported reference calculator: {op}")


def reference_gold(case: dict, facts: dict, today: str) -> list[dict]:
    result = []
    for spec in case.get("reference_specs", []):
        expected = calculate(spec, facts, today)
        result.append({**spec, "expected": expected,
                       "applicable": expected is not None,
                       "reference_kind": "independent_formula" if spec["calculator"] in
                       {"deadline", "expired", "dismissal", "overtime", "double_pay", "annual_leave", "noncompete", "work_injury"}
                       else "author_specified_behavior"})
    return result
