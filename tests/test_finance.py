"""Finance maths in the investment analyzer, checked against independent calculations."""

import numpy_financial as npf
import pytest

from backend.app.agents import local_expert as le


def test_emi_matches_numpy_financial():
    expected = -npf.pmt(0.085 / 12, 240, 6_000_000)
    assert le._monthly_mortgage(6_000_000, 8.5, 20) == pytest.approx(expected, rel=1e-9)


def test_zero_interest_loan_has_zero_emi_by_design():
    assert le._monthly_mortgage(1_000_000, 0, 20) == 0.0
    


def test_remaining_balance_matches_present_value_of_remaining_payments():
    emi = le._monthly_mortgage(6_000_000, 8.5, 20)
    expected = npf.pv(0.085 / 12, 120, -emi)  # 10 of 20 years left
    assert le._remaining_balance(6_000_000, 8.5, 20, 10) == pytest.approx(expected, rel=1e-6)


def test_irr_of_a_single_period_investment():
    assert le._irr([-100, 110]) == pytest.approx(0.10, abs=1e-6)


def test_irr_matches_numpy_financial():
    flows = [-1_800_000, 150_000, 160_000, 170_000, 180_000, 2_900_000]
    assert le._irr(flows) == pytest.approx(npf.irr(flows), abs=1e-6)


def test_irr_is_none_without_an_initial_outflow():
    assert le._irr([100, 50, 50]) is None


def test_compute_matches_hand_calculation():
    """Price 80L, rent 25k/month, 25% down, 8.5% for 20 years (the app's defaults)."""
    m = le.InvestmentAnalyzer().compute(8_000_000, 25_000, down_pct=25.0)

    annual_rent = 25_000 * 12
    assert m["gross_yield"] == pytest.approx(annual_rent / 8_000_000 * 100)  # 3.75%

    loan = 8_000_000 * 0.75
    emi = -npf.pmt(0.085 / 12, 240, loan)
    assert m["monthly_emi"] == pytest.approx(emi, rel=1e-6)

    # rent 3.75% < loan rate 8.5%, so the rent cannot cover the loan payments
    assert m["dscr"] < 1
    assert m["monthly_cf"] < 0
