from collections import deque
import logging
from typing import Union, Optional
import lkml
from lkml.visitors import BasicVisitor
from lkml.tree import SyntaxNode, SyntaxToken, ContainerNode
from lkmlstyle.rules import (
    NodeContext,
    Rule,
    RULES_BY_CODE,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logs_handler = logging.StreamHandler()
logger.addHandler(logs_handler)


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
    def __init__(self, rules: tuple[Rule, ...]):
        super().__init__()
        self.rules: tuple[Rule, ...] = rules
        self._lineage: deque = deque()  # Faster than list for append/pop
        self.violations: list[tuple] = []
        self.context = NodeContext()

    @property
    def lineage(self) -> str:
        return ".".join(self._lineage)

    @track_lineage
    def _visit(self, node: Union[SyntaxNode, SyntaxToken]) -> None:
        if isinstance(node, SyntaxToken):
            return

        if not isinstance(node, ContainerNode):
            for rule in self.rules:
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


def choose_rules(
    all_rules: dict[str, Rule],
    ignore: Optional[tuple[str, ...]] = None,
    select: Optional[tuple[str, ...]] = None,
) -> tuple[Rule, ...]:
    """Return the relevant rules given some selected and ignored rule codes."""
    if ignore and not isinstance(ignore, tuple):
        raise TypeError("Codes to ignore must be wrapped in a tuple")
    if select and not isinstance(select, tuple):
        raise TypeError("Codes to ignore must be wrapped in a tuple")

    all_codes = set(all_rules.keys())

    invalid_rules = set((ignore or tuple()) + (select or tuple())) - all_codes
    if invalid_rules:
        suffix = (
            "are not valid rule codes"
            if len(invalid_rules) > 1
            else "is not a defined rule code"
        )
        raise ValueError(f"{', '.join(invalid_rules)} {suffix}")

    codes = all_codes & set(select or all_codes) - set(ignore or tuple())
    if not codes:
        return tuple(all_rules.values())
    rules = []
    for code in codes:
        rules.append(all_rules[code])
    return tuple(rules)


def check(
    text: str,
    ignore: Optional[tuple[str, ...]] = None,
    select: Optional[tuple[str, ...]] = None,
) -> list[tuple]:
    """Validate a LookML string, given a set of rule codes to select and/or ignore."""
    tree = lkml.parse(text)
    visitor = StyleCheckVisitor(rules=choose_rules(RULES_BY_CODE, ignore, select))
    tree.accept(visitor)
    return visitor.violations
