import pytest
from lkmlstyle.check import choose_rules
from lkmlstyle.rules import Rule, RULES_BY_CODE


@pytest.fixture
def all_rules():
    return {
        k: v for k, v in RULES_BY_CODE.items() if k in ("M106", "D100", "M110", "V100")
    }


def rules_to_codes(rules: tuple[Rule]) -> tuple[str, ...]:
    return tuple(rule.code for rule in rules)


def test_ignore_should_exclude_rules(all_rules):
    chosen = choose_rules(all_rules, ignore=("M106",))
    print(rules_to_codes(chosen))
    assert "M106" not in rules_to_codes(chosen)
    assert "D100" in rules_to_codes(chosen)
    chosen = choose_rules(all_rules, ignore=("M106", "D100"))
    assert "M106" not in rules_to_codes(chosen)
    assert "D100" not in rules_to_codes(chosen)
    assert "M110" in rules_to_codes(chosen)


def test_select_should_exclude_rules(all_rules):
    chosen = choose_rules(all_rules, select=("V100",))
    assert "D100" not in rules_to_codes(chosen)
    assert "V100" in rules_to_codes(chosen)
    chosen = choose_rules(all_rules, select=("V100", "D100"))
    assert "V100" in rules_to_codes(chosen)
    assert "D100" in rules_to_codes(chosen)
    assert "M110" not in rules_to_codes(chosen)


def test_ignore_should_have_precedence(all_rules):
    chosen = choose_rules(all_rules, select=("V100", "D100"), ignore=("D100",))
    assert "D100" not in rules_to_codes(chosen)
    assert "V100" in rules_to_codes(chosen)
