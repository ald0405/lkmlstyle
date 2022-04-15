from dataclasses import replace
from pathlib import Path
import pytest
import yaml
from lkmlstyle.check import choose_rules, resolve_overrides, Config
from lkmlstyle.rules import Rule, RULES_BY_CODE
from lkmlstyle.exceptions import InvalidConfig, InvalidRule


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


@pytest.fixture
def config_data() -> dict[str]:
    return {
        "ignore": ["D106", "D107"],
        "custom_rules": [
            {
                "title": "Name of count measure doesn't start with 'c_'",
                "code": "M100",
                "rationale": (
                    "You should explicitly state the aggregation type in the dimension ",
                    "name because it makes it easier for other developers and Explore "
                    "users to understand how the measure is calculated.",
                ),
                "select": ["measure"],
                "filters": [
                    {
                        "function": "block_has_valid_parameter",
                        "parameter_name": "type",
                        "value": "count",
                    }
                ],
                "filter_on": None,
                "regex": "^c_",
                "negative": False,
                "type": "PatternMatchRule",
            }
        ],
    }


def write_config(path: Path, data: dict[str]) -> None:
    with path.open("w+") as file:
        yaml.safe_dump(data, file)


@pytest.fixture
def custom_rule(rules_by_code):
    return replace(rules_by_code["D100"], select="dimension_group")


def test_resolve_overrides_should_override_with_a_custom_rule(
    custom_rule, rules_by_code, ruleset
):
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


def test_config_should_be_loaded_from_file(tmp_path, config_data):
    config_path = tmp_path / "lkmlstyle.yml"
    write_config(config_path, config_data)

    with config_path.open("r") as file:
        config = Config.from_file(file)

    assert config.ignore == ("D106", "D107")
    assert config.custom_rules
    assert config.custom_rules[0].regex == "^c_"


def test_config_from_file_with_invalid_rule_type_should_be_handled(tmp_path):
    config_yaml = """
    custom_rules:
      - title: Name of count measure doesn't start with 'c_'
        code: M100
        rationale: |
          You should explicitly state the aggregation type in the dimension name
          because it makes it easier for other developers and Explore users to understand
          how the measure is calculated.
        select:
        - measure
        filters:
        - function: block_has_valid_parameter
        parameter_name: type
        value: count
        filter_on: null
        regex: "^c_"
        negative: false
        type: NotARuleType
    """
    config_path = tmp_path / "lkmlstyle.yml"
    config_path.write_text(config_yaml)

    with pytest.raises(InvalidConfig) as exc_info:
        with config_path.open("r") as file:
            Config.from_file(file)

    assert "not a valid rule" in str(exc_info)


def test_config_from_file_with_invalid_func_should_be_handled(tmp_path):
    config_yaml = """
    custom_rules:
      - title: Name of count measure doesn't start with 'c_'
        code: M100
        rationale: |
          You should explicitly state the aggregation type in the dimension name
          because it makes it easier for other developers and Explore users to understand
          how the measure is calculated.
        select:
        - measure
        filters:
        - function: not_a_function
        parameter_name: type
        value: count
        filter_on: null
        regex: "^c_"
        negative: false
        type: PatternMatchRule
    """
    config_path = tmp_path / "lkmlstyle.yml"
    config_path.write_text(config_yaml)

    with pytest.raises(InvalidConfig) as exc_info:
        with config_path.open("r") as file:
            Config.from_file(file)

    assert "not a valid function" in str(exc_info)


def test_config_from_file_with_invalid_rule_should_be_handled(tmp_path):
    config_yaml = """
    custom_rules:
      - title: Name of count measure doesn't start with 'c_'
        rationale: |
          You should explicitly state the aggregation type in the dimension name
          because it makes it easier for other developers and Explore users to understand
          how the measure is calculated.
        select:
        - measure
        regex: "^c_"
        negative: false
        type: PatternMatchRule
    """
    config_path = tmp_path / "lkmlstyle.yml"
    config_path.write_text(config_yaml)

    with pytest.raises(InvalidRule) as exc_info:
        with config_path.open("r") as file:
            Config.from_file(file)

    assert "required keyword-only argument" in str(exc_info).lower()


def test_config_override_should_replace_existing(ruleset):
    config = Config(ruleset, select=("D100",), ignore=("M106",))
    config.override(select=("D101",), ignore=("M107",))
    assert "M107" in config.ignore
    assert "M106" not in config.ignore
    assert "D101" in config.select
    assert "D100" not in config.select


def test_config_refine_should_work(ruleset, custom_rule):
    config = Config(ignore=("D100",))
    refined = config.refine(ruleset)
    refined_codes = rules_to_codes(refined)
    assert "D100" not in refined_codes
    assert "M106" in refined_codes

    config = Config(select=("D100",))
    refined = config.refine(ruleset)
    refined_codes = rules_to_codes(refined)
    assert "D100" in refined_codes
    assert "M106" not in refined_codes

    config = Config(custom_rules=(custom_rule,))
    refined = config.refine(ruleset)
    assert custom_rule in refined
