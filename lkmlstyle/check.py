from collections import deque
from typing import Union
import lkml
from lkml.visitors import BasicVisitor
from lkml.tree import (
    SyntaxNode,
    SyntaxToken,
)
from lkmlstyle.rules import Rule, default_rules


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

    @property
    def lineage(self) -> str:
        return ".".join(self._lineage)

    @track_lineage
    def _visit(self, node: Union[SyntaxNode, SyntaxToken]) -> None:
        if isinstance(node, SyntaxToken):
            return
        for rule in self.rules:
            if self._is_selected(rule):
                self._test_rule(rule, node)

        if node.children:
            for child in node.children:
                child.accept(self)

    def _is_selected(self, rule: Rule) -> bool:
        return self.lineage.endswith(rule.select)

    def _test_rule(self, rule: Rule, node: SyntaxNode) -> None:
        if rule.applies_to(node) and not rule.followed_by(node):
            self.violations.append((rule.code, rule.title, node.line_number))


def check(text: str) -> list[tuple]:
    tree = lkml.parse(text)
    visitor = StyleCheckVisitor(rules=default_rules)
    tree.accept(visitor)
    return visitor.violations
