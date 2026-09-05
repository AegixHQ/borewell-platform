from app.pricing.engine import calculate_quotation


def test_line_items_sum_to_subtotal():
    result = calculate_quotation(
        assumed_depth_ft=300,
        base_rate_per_ft=150,
        casing_rate_per_ft=80,
        labour_flat_fee=5000,
        transport_flat_fee=2000,
        equipment_flat_fee=3000,
        installation_flat_fee=4000,
        margin_percent=15,
        minimum_job_charge=20000,
    )
    assert result.subtotal == 83000
    assert result.margin_amount == 12450
    assert result.total == 95450
    assert result.minimum_charge_applied is False


def test_minimum_charge_bumps_low_total_up():
    result = calculate_quotation(
        assumed_depth_ft=100,
        base_rate_per_ft=10,
        casing_rate_per_ft=5,
        labour_flat_fee=100,
        transport_flat_fee=100,
        equipment_flat_fee=100,
        installation_flat_fee=100,
        margin_percent=10,
        minimum_job_charge=50000,
    )
    assert result.total == 50000
    assert result.minimum_charge_applied is True


def test_zero_margin_means_total_equals_subtotal():
    result = calculate_quotation(
        assumed_depth_ft=100,
        base_rate_per_ft=100,
        casing_rate_per_ft=0,
        labour_flat_fee=0,
        transport_flat_fee=0,
        equipment_flat_fee=0,
        installation_flat_fee=0,
        margin_percent=0,
        minimum_job_charge=0,
    )
    assert result.subtotal == 10000
    assert result.margin_amount == 0
    assert result.total == 10000


def test_results_are_exact_decimal_not_float():
    # This specific rate pair is chosen because 0.1 + 0.2 != 0.3 in float,
    # but IS exact in Decimal - would fail if the engine still used float.
    from decimal import Decimal

    result = calculate_quotation(
        assumed_depth_ft=1,
        base_rate_per_ft=0.1,
        casing_rate_per_ft=0.2,
        labour_flat_fee=0,
        transport_flat_fee=0,
        equipment_flat_fee=0,
        installation_flat_fee=0,
        margin_percent=0,
        minimum_job_charge=0,
    )
    assert isinstance(result.subtotal, Decimal)
    assert result.subtotal == Decimal("0.30")


def test_many_small_additions_do_not_drift():
    from decimal import Decimal as D

    result = calculate_quotation(
        assumed_depth_ft=333,
        base_rate_per_ft=33.33,
        casing_rate_per_ft=11.11,
        labour_flat_fee=1234.56,
        transport_flat_fee=987.65,
        equipment_flat_fee=555.55,
        installation_flat_fee=222.22,
        margin_percent=17.5,
        minimum_job_charge=0,
    )
    expected_subtotal = (
        D("33.33") * D("333")
        + D("11.11") * D("333")
        + D("1234.56")
        + D("987.65")
        + D("555.55")
        + D("222.22")
    ).quantize(D("0.01"))
    assert result.subtotal == expected_subtotal
