"""
Quotation/Pricing Engine - RFC 0001 FR-K14 / SRS FR-QUOTE-01.

Pure calculation logic, no I/O, no framework dependency - takes a pricing
rule's configured values and produces line items + totals.

Money is computed in Decimal, not float (Bug 2 - confirmed by an external
technical analysis: repeated float addition/multiplication on INR amounts
introduces representation error that compounds across quotations - e.g.
0.1 + 0.2 != 0.3 in float, but is exact in Decimal).

Inputs arrive as plain floats from Pydantic/JSON (JSON has no native
decimal type) and are converted via Decimal(str(x)), never Decimal(x)
directly - the latter would preserve float's binary imprecision instead
of fixing it (Decimal(0.1) is 0.1000000000000000055511151231257827...;
Decimal(str(0.1)) is exactly 0.1).
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def to_money(value) -> Decimal:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class LineItem:
    label: str
    amount: Decimal


@dataclass
class PricingResult:
    line_items: list[LineItem]
    subtotal: Decimal
    margin_amount: Decimal
    total: Decimal
    minimum_charge_applied: bool


def calculate_quotation(
    assumed_depth_ft,
    base_rate_per_ft,
    casing_rate_per_ft,
    labour_flat_fee,
    transport_flat_fee,
    equipment_flat_fee,
    installation_flat_fee,
    margin_percent,
    minimum_job_charge,
) -> PricingResult:
    depth = Decimal(str(assumed_depth_ft))
    line_items = [
        LineItem("Drilling", to_money(Decimal(str(base_rate_per_ft)) * depth)),
        LineItem("Casing", to_money(Decimal(str(casing_rate_per_ft)) * depth)),
        LineItem("Labour", to_money(labour_flat_fee)),
        LineItem("Transport", to_money(transport_flat_fee)),
        LineItem("Equipment", to_money(equipment_flat_fee)),
        LineItem("Installation", to_money(installation_flat_fee)),
    ]
    subtotal = to_money(sum((li.amount for li in line_items), Decimal("0")))
    margin_amount = to_money(subtotal * Decimal(str(margin_percent)) / Decimal("100"))
    total = to_money(subtotal + margin_amount)

    # BR-01 / FR-QUOTE-06: total is never allowed below the configured
    # minimum - bumped up, not rejected, since a small job should still be
    # quotable at the contractor's minimum rather than refused outright.
    minimum = to_money(minimum_job_charge)
    minimum_charge_applied = False
    if total < minimum:
        total = minimum
        minimum_charge_applied = True

    return PricingResult(
        line_items=line_items,
        subtotal=subtotal,
        margin_amount=margin_amount,
        total=total,
        minimum_charge_applied=minimum_charge_applied,
    )
