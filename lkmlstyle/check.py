from collections import deque
from typing import Union, Optional
import lkml
from lkml.visitors import BasicVisitor
from lkml.tree import SyntaxNode, SyntaxToken, ContainerNode
from lkmlstyle.rules import (
    Rule,
    OrderRule,
    RULES_BY_CODE,
)


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
        self.violations: list[str] = []
        self.prev: Optional[SyntaxNode] = None

    @property
    def lineage(self) -> str:
        return ".".join(self._lineage)

    @track_lineage
    def _visit(self, node: Union[SyntaxNode, SyntaxToken]) -> None:
        if isinstance(node, SyntaxToken):
            return

        if not isinstance(node, ContainerNode):
            for rule in self.rules:
                if self._select_current_node(rule):
                    if rule.applies_to(node):
                        if isinstance(rule, OrderRule):
                            violates = not rule.followed_by(node, self.prev)
                        else:
                            violates = not rule.followed_by(node)

                        if violates:
                            self.violations.append(
                                (rule.code, rule.title, node.line_number)
                            )
                    # TODO: This needs to be tracked by rule
                    self.prev = node

        if node.children:
            for child in node.children:
                child.accept(self)

    def _select_current_node(self, rule: Rule) -> bool:
        return self.lineage.endswith(rule.select)


def ignore_rules(codes: Optional[tuple[str]]) -> tuple[Rule]:
    if not codes:
        return tuple(RULES_BY_CODE.values())
    rules = RULES_BY_CODE.copy()
    for code in codes:
        del rules[code]
    return tuple(rules.values())


def check(text: str, ignore: Optional[tuple[str]]) -> list[tuple]:
    tree = lkml.parse(text)
    visitor = StyleCheckVisitor(rules=ignore_rules(ignore))
    tree.accept(visitor)
    return visitor.violations
