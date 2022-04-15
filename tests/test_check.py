from dataclasses import replace
import pytest
from lkmlstyle.check import choose_rules, resolve_overrides
from lkmlstyle.rules import Rule, RULES_BY_CODE


@pytest.fixture
def rules_by_code():
    return {
        k: v for k, v in RULES_BY_CODE.items() if k in ("M106", "D100", "M110", "V100")
    }


@pytest.fixture
def ruleset(rules_by_code):
    return tuple(rules_by_code.values())


def rules_to_codes(rules: tuple[Rule]) -> tuple[str, ...]:
    return tuple(rule.code for rule in rules)


def test_resolve_overrides_should_override_with_a_custom_rule(rules_by_code, ruleset):
    custom_rule = replace(rules_by_code["D100"], select="dimension_group")
    resolved = resolve_overrides(ruleset, custom_rules=(custom_rule,))
    assert rules_by_code["M106"] in resolved
    assert rules_by_code["D100"] not in resolved
    assert custom_rule in resolved


def test_resolve_overrides_should_extend_with_a_new_rule(rules_by_code, ruleset):
    new_rule = replace(rules_by_code["D100"], code="D99999")
    resolved = resolve_overrides(ruleset, custom_rules=(new_rule,))
    assert rules_by_code["M106"] in resolved
    assert rules_by_code["D100"] in resolved
    assert new_rule in resolved


def test_choose_rules_ignore_should_exclude_rules(ruleset):
    chosen = choose_rules(ruleset, ignore=("M106",))
    assert "M106" not in rules_to_codes(chosen)
    assert "D100" in rules_to_codes(chosen)
    chosen = choose_rules(ruleset, ignore=("M106", "D100"))
    assert "M106" not in rules_to_codes(chosen)
    assert "D100" not in rules_to_codes(chosen)
    assert "M110" in rules_to_codes(chosen)


def test_choose_rules_select_should_exclude_other_rules(ruleset):
    chosen = choose_rules(ruleset, select=("V100",))
    assert "D100" not in rules_to_codes(chosen)
    assert "V100" in rules_to_codes(chosen)
    chosen = choose_rules(ruleset, select=("V100", "D100"))
    assert "V100" in rules_to_codes(chosen)
    assert "D100" in rules_to_codes(chosen)
    assert "M110" not in rules_to_codes(chosen)


def test_choose_rules_ignore_should_have_precedence(ruleset):
    chosen = choose_rules(ruleset, select=("V100", "D100"), ignore=("D100",))
    assert "D100" not in rules_to_codes(chosen)
    assert "V100" in rules_to_codes(chosen)
