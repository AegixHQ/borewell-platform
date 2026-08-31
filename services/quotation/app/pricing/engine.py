"""
Quotation/Pricing Engine - RFC 0001 FR-K14 / SRS FR-QUOTE-01.

Pure calculation logic, no I/O, no framework dependency - takes a pricing
rule's configured values and produces line items + totals. Kept separate
from main.py so it's independently unit-testable (see
tests/test_pricing_engine.py), matching the pattern already established in
platform-spine's app/job_state_machine.py.
"""
from dataclasses import dataclass


@dataclass
class LineItem:
    label: str
    amount: float


@dataclass
class PricingResult:
    line_items: list[LineItem]
    subtotal: float
    margin_amount: float
    total: float
    minimum_charge_applied: bool


def calculate_quotation(
    assumed_depth_ft: float,
    base_rate_per_ft: float,
    casing_rate_per_ft: float,
    labour_flat_fee: float,
    transport_flat_fee: float,
    equipment_flat_fee: float,
    installation_flat_fee: float,
    margin_percent: float,
    minimum_job_charge: float,
) -> PricingResult:
    line_items = [
        LineItem("Drilling", round(base_rate_per_ft * assumed_depth_ft, 2)),
        LineItem("Casing", round(casing_rate_per_ft * assumed_depth_ft, 2)),
        LineItem("Labour", round(labour_flat_fee, 2)),
        LineItem("Transport", round(transport_flat_fee, 2)),
        LineItem("Equipment", round(equipment_flat_fee, 2)),
        LineItem("Installation", round(installation_flat_fee, 2)),
    ]
    subtotal = round(sum(li.amount for li in line_items), 2)
    margin_amount = round(subtotal * margin_percent / 100, 2)
    total = round(subtotal + margin_amount, 2)

    # BR-01 / FR-QUOTE-06: total is never allowed below the configured
    # minimum - bumped up, not rejected, since a small job should still be
    # quotable at the contractor's minimum rather than refused outright.
    minimum_charge_applied = False
    if total < minimum_job_charge:
        total = minimum_job_charge
        minimum_charge_applied = True

    return PricingResult(
        line_items=line_items,
        subtotal=subtotal,
        margin_amount=margin_amount,
        total=total,
        minimum_charge_applied=minimum_charge_applied,
    )
