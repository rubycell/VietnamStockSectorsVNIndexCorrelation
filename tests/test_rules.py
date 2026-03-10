"""Tests for the 9 trading rules."""

import pytest
from app.engine.rules import evaluate_rules, RuleContext, TriggeredRule
from app.engine.fud import FudResult


def _ctx(**kwargs) -> RuleContext:
    defaults = {
        "ticker": "FPT",
        "current_price": 120000,
        "vwap_cost": 110000,
        "total_shares": 100,
        "position_number": 1,
        "latest_swing_low": 105000,
        "swing_low_confirmed": True,
        "important_levels": [95000, 140000, 160000],
        "fud": FudResult(is_fud=False, severity="none"),
        "previous_fud_severity": "none",
    }
    defaults.update(kwargs)
    return RuleContext(**defaults)


def test_no_rules_in_calm_market():
    ctx = _ctx()
    triggered = evaluate_rules(ctx)
    # Rules #1, #3, #5 are dashboard-only, should not appear in alerts
    alertable = [r for r in triggered if r.alert]
    assert len(alertable) == 0


def test_rule4_below_swing_low():
    ctx = _ctx(current_price=100000, latest_swing_low=105000)
    triggered = evaluate_rules(ctx)
    rule4 = [r for r in triggered if r.rule_id == "below_swing_low_sell"]
    assert len(rule4) == 1
    assert rule4[0].severity == "critical"
    assert "below swing low" in rule4[0].message.lower()


def test_rule9_pos2_below_swing_low():
    ctx = _ctx(current_price=100000, latest_swing_low=105000, position_number=2)
    triggered = evaluate_rules(ctx)
    rule9 = [r for r in triggered if r.rule_id == "stoploss_all_pos2"]
    assert len(rule9) == 1
    assert rule9[0].severity == "critical"


def test_rule2_fud_detected():
    fud = FudResult(is_fud=True, severity="medium", reasons=["VN-Index dropped 3%"], fud_sectors=["Ngân hàng"])
    ctx = _ctx(fud=fud)
    triggered = evaluate_rules(ctx)
    rule2 = [r for r in triggered if r.rule_id == "fud_reduce_size"]
    assert len(rule2) == 1


def test_rule6_fud_escalation():
    fud = FudResult(is_fud=True, severity="high", reasons=["Both"], fud_sectors=["Banks"])
    ctx = _ctx(fud=fud, previous_fud_severity="medium")
    triggered = evaluate_rules(ctx)
    rule6 = [r for r in triggered if r.rule_id == "fud_reduce_further"]
    assert len(rule6) == 1


def test_rule7_ptp_in_profit():
    # Position #2, in profit (price > cost)
    ctx = _ctx(position_number=2, current_price=130000, vwap_cost=110000, latest_swing_low=105000)
    triggered = evaluate_rules(ctx)
    rule7 = [r for r in triggered if r.rule_id == "ptp_to_swing_low"]
    assert len(rule7) == 1


def test_rule8_near_important_level():
    # Position #1, price near important level (within 2%)
    ctx = _ctx(position_number=1, current_price=119500, important_levels=[115000, 120000, 125000])
    triggered = evaluate_rules(ctx)
    rule8 = [r for r in triggered if r.rule_id == "high_entry_sell_levels"]
    assert len(rule8) == 1


def test_rule7_not_triggered_pos1():
    """Rule #7 only triggers for position #2+."""
    ctx = _ctx(position_number=1, current_price=130000, vwap_cost=110000)
    triggered = evaluate_rules(ctx)
    rule7 = [r for r in triggered if r.rule_id == "ptp_to_swing_low"]
    assert len(rule7) == 0
