from collections import deque
from dataclasses import dataclass
import logging
import yaml
import lkml
from lkml.visitors import BasicVisitor
from lkml.tree import SyntaxNode, SyntaxToken, ContainerNode
from lkmlstyle.rules import (
    NodeContext,
    Rule,
    ALL_RULES,
)
from lkmlstyle.exceptions import InvalidConfig, InvalidRuleCode

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logs_handler = logging.StreamHandler()
logger.addHandler(logs_handler)


def resolve_overrides(
    ruleset: tuple[Rule, ...], custom_rules: tuple[Rule, ...]
) -> tuple[Rule, ...]:
    """Override and extend a ruleset with custom rules by code."""
    resolved = list(custom_rules)
    custom_rule_codes = [rule.code for rule in custom_rules]
    for rule in ruleset:
        if rule.code not in custom_rule_codes:
            resolved.append(rule)
    return tuple(resolved)


def choose_rules(
    ruleset: tuple[Rule, ...],
    ignore: tuple[str, ...] | None = None,
    select: tuple[str, ...] | None = None,
) -> tuple[Rule, ...]:
    """Return the relevant rules given some selected and ignored rule codes."""
    if ignore and not isinstance(ignore, tuple):
        raise TypeError("Codes to ignore must be wrapped in a tuple")
    if select and not isinstance(select, tuple):
        raise TypeError("Codes to select must be wrapped in a tuple")

    rules_by_code = {rule.code: rule for rule in ruleset}
    codeset = set(rules_by_code.keys())

    invalid_rules = set((ignore or tuple()) + (select or tuple())) - codeset
    if invalid_rules:
        suffix = (
            "are not valid rule codes"
            if len(invalid_rules) > 1
            else "is not a defined rule code"
        )
        raise InvalidRuleCode(f"{', '.join(invalid_rules)} {suffix}")

    codes = codeset & set(select or codeset) - set(ignore or tuple())
    if not codes:
        return ruleset
    rules = []
    for code in codes:
        rules.append(rules_by_code[code])
    return tuple(rules)


@dataclass
class Config:
    custom_rules: tuple[Rule, ...] | None = None
    select: tuple[str, ...] | None = None
    ignore: tuple[str, ...] | None = None

    @classmethod
    def from_file(cls, fp):
        config = yaml.safe_load(fp)

        if config is None:
            raise ValueError("Config loaded from file is None")

        # Create a mapping from rule name to rule class
        name_to_rule: dict[str, type] = {
            c.__name__: c for c in set(c.__class__ for c in ALL_RULES)
        }

        # Override rule definitions with custom rules
        custom_rules: list[Rule] = []
        for rule in config.pop("custom_rules", []):
            try:
                name: str = rule.pop("type")
            except KeyError:
                raise InvalidConfig(
                    "All custom rules must be defined with a 'type' key, "
                    "for example: 'type: PatternMatchRule'"
                )

            try:
                rule_cls: type = name_to_rule[name]
            except KeyError:
                raise InvalidConfig(
                    f"Rule type '{name}' is not a valid rule. "
                    f"Valid rules are: {', '.join(name_to_rule.keys())}",
                )

            try:
                custom_rule = rule_cls.from_dict(rule)
            except KeyError as error:
                raise InvalidConfig(str(error)) from error

            custom_rules.append(custom_rule)

        select = tuple(config.pop("select", []))
        ignore = tuple(config.pop("ignore", []))

        return cls(tuple(custom_rules), select, ignore, **config)

    def override(
        self,
        select: tuple[str, ...] | None = None,
        ignore: tuple[str, ...] | None = None,
    ) -> None:
        """Replace the config with other ignores or selections."""
        self.select = tuple(select) if select else self.select
        self.ignore = tuple(ignore) if ignore else self.ignore

    def refine(self, ruleset: tuple[Rule, ...]) -> tuple[Rule, ...]:
        """Override, ignore, and select rules from an existing ruleset."""
        if self.custom_rules:
            ruleset = resolve_overrides(ruleset, self.custom_rules)

        return choose_rules(ruleset, self.ignore, self.select)


def parse_config() -> Config | None:
    """Attempt to load config from file."""
    try:
        with open("lkmlstyle.yaml", "r") as file:
            return Config.from_file(file)
    except FileNotFoundError:
        return None


def track_lineage(method):
    def wrapper(self, node, *args, **kwargs):
        try:
            node_type = node.type.value
        except AttributeError:
            node_type = None

        if node_type is not None:
            self._lineage.append(node_type)

        method(self, node, *args, **kwargs)

        if node_type is not None:
            self._lineage.pop()

    return wrapper


class StyleCheckVisitor(BasicVisitor):
    def __init__(self, ruleset: tuple[Rule, ...]):
        super().__init__()
        self.ruleset = ruleset
        self._lineage: deque = deque()  # Faster than list for append/pop
        self.violations: list[tuple] = []
        self.context = NodeContext()

    @property
    def lineage(self) -> str:
        return ".".join(self._lineage)

    @track_lineage
    def _visit(self, node: SyntaxNode | SyntaxToken) -> None:
        if isinstance(node, SyntaxToken):
            return

        if not isinstance(node, ContainerNode):
            for rule in self.ruleset:
                if rule.applies_to(node, self.lineage):
                    logger.debug(f"Checking if {repr(node)} follows {repr(rule)}")
                    follows, self.context = rule.followed_by(node, self.context)
                    if not follows:
                        self.violations.append(
                            (
                                rule.code,
                                rule.title,
                                rule.rationale,
                                node.line_number,
                            )
                        )
                # Set if node matches selectors even if it doesn't match filters
                if rule.selects(self.lineage):
                    self.context.previous_node[rule.code] = node

        if node.children:
            for child in node.children:
                child.accept(self)


def check(text: str, ruleset: tuple[Rule, ...]) -> list[tuple]:
    """Validate a LookML string, given a set of rule codes to select and/or ignore."""
    visitor = StyleCheckVisitor(ruleset)
    tree = lkml.parse(text)
    tree.accept(visitor)
    return visitor.violations
