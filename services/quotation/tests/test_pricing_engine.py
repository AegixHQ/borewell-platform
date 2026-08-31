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
