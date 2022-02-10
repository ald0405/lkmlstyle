# TODO: Support line numbers and context preview for errors
# TODO: Support rules as YAML
# TODO: Support ordering rule type
# TODO: Support whitespace rule type
# TODO: Support file-based rules
# TODO: Write test cases for each rule

import yaml
from collections import deque
from dataclasses import dataclass
from functools import partial
from typing import Callable, Optional, Union
import re
import lkml
from lkml.visitors import BasicVisitor
from lkml.tree import (
    BlockNode,
    SyntaxNode,
    PairNode,
    ContainerNode,
    SyntaxToken,
)


@dataclass(frozen=True)
class Rule:
    title: str
    code: str
    select: str
    filters: tuple[partial[bool], ...]

    def applies_to(self, node: SyntaxNode) -> bool:
        return all(is_filter_valid(node) for is_filter_valid in self.filters)

    def followed_by(self, node: SyntaxNode) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class PatternMatchRule(Rule):
    regex: str
    negative: Optional[bool] = False

    def __post_init__(self):
        # Why? https://docs.python.org/3/library/dataclasses.html#frozen-instances
        object.__setattr__(self, "pattern", re.compile(self.regex))

    def _matches(self, string: str) -> bool:
        matched = bool(self.pattern.search(string))
        return not matched if self.negative else matched

    def followed_by(self, node: SyntaxNode) -> bool:
        if isinstance(node, PairNode):
            value = node.value.value
        elif isinstance(node, BlockNode):
            value = node.name.value
        else:
            return True
        return self._matches(value)


@dataclass(frozen=True)
class ParameterRule(Rule):
    criteria: tuple[partial[bool]]
    negative: Optional[bool] = False

    def followed_by(self, node: SyntaxNode) -> bool:
        matched = self.criteria(node)
        return not matched if self.negative else matched


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
    def __init__(self, rules: tuple[PatternMatchRule, ...]):
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

    def _test_rule(self, rule: PatternMatchRule, node: SyntaxNode) -> None:
        if rule.applies_to(node) and not rule.followed_by(node):
            self.violations.append(f"[{rule.code}] {rule.title}")


def node_has_valid_class(node: SyntaxNode, node_type: type) -> bool:
    return isinstance(node, node_type)


def node_has_valid_type(node: SyntaxNode, value: str) -> bool:
    return node.type.value == value


def pair_has_valid_value(pair: PairNode, value: str) -> bool:
    return pair.value.value == value


def node_has_at_least_one_valid_child(node: SyntaxNode, is_valid: Callable) -> bool:
    for child in node.children:
        if isinstance(child, ContainerNode):
            if node_has_at_least_one_valid_child(child, is_valid):
                return True
        elif is_valid(child):
            return True
    return False


def block_has_valid_parameter(
    block: BlockNode,
    parameter_name: str,
    value: Optional[str] = None,
    negative: Optional[bool] = False,
) -> bool:
    # TODO: Make sure this actually works
    if not isinstance(block, BlockNode):
        return False

    def is_valid_param(node: SyntaxNode) -> bool:
        if not isinstance(node, PairNode):
            return False
        elif not node_has_valid_type(node, parameter_name):
            return False
        elif value and not pair_has_valid_value(node, value):
            return False
        else:
            return True

    valid = node_has_at_least_one_valid_child(block, is_valid_param)
    return not valid if negative else valid


count_measure_prefix = PatternMatchRule(
    title="Name of count measure doesn't start with 'count_'",
    code="M100",
    select="measure",
    filters=(partial(block_has_valid_parameter, parameter_name="type", value="count"),),
    regex=r"^count_",
)

sum_measure_prefix = PatternMatchRule(
    title="Name of sum measure doesn't start with 'total_'",
    code="M101",
    select="measure",
    filters=(partial(block_has_valid_parameter, parameter_name="type", value="sum"),),
    regex=r"^total_",
)

avg_measure_prefix = PatternMatchRule(
    title="Name of average measure doesn't start with 'avg_'",
    code="M102",
    select="measure",
    filters=(partial(block_has_valid_parameter, parameter_name="type", value="sum"),),
    regex=r"^avg_",
)

yesno_dimension_prefix = PatternMatchRule(
    title="Yesno dimension doesn't start with 'is_' or 'has_'",
    code="D100",
    select="dimension",
    filters=(partial(block_has_valid_parameter, parameter_name="type", value="yesno"),),
    regex=r"^(?:is|has)_",
)

table_ref_in_measure = PatternMatchRule(
    title="Measure contains '${TABLE}' reference",
    code="M110",
    select="measure.sql",
    filters=tuple(),
    regex=r"\$\{TABLE\}",
    negative=True,
)

wildcard_include = PatternMatchRule(
    title="Don't include all views",
    code="V100",
    select="include",
    filters=tuple(),
    regex=r"^\*\.view",
    negative=True,
)

default_dimension_type = PatternMatchRule(
    title="Unnecessary type specification for string dimension",
    code="D101",
    select="dimension.type",
    filters=tuple(),
    regex=r"^string$",
    negative=True,
)

dimension_group_suffix = PatternMatchRule(
    title="Dimension group name ends with redundant word",
    code="D200",
    select="dimension_group",
    filters=tuple(),
    regex=r"_(?:at|date|time)$",
    negative=True,
)

explicit_fields_for_explore = ParameterRule(
    title="Explore doesn't declare fields",
    code="E100",
    select="explore",
    filters=(),
    criteria=partial(block_has_valid_parameter, parameter_name="fields"),
)

# This probably is not the ideal behavior, it enforces strict title case, when in
# reality people probably still want to lowercase words like 'and', 'is', 'or', etc.
labels_are_title_cased = PatternMatchRule(
    title="Label is not title-cased",
    code="G100",
    select="label",
    filters=tuple(),
    regex=r"^(?:[A-Z][^\s]*\s?)+$",
)

non_hidden_dimensions_have_description = ParameterRule(
    title="Non-hidden dimension missing description",
    code="D110",
    select="dimension",
    filters=tuple(
        [
            partial(
                block_has_valid_parameter,
                parameter_name="hidden",
                value="yes",
                negative=True,
            )
        ],
    ),
    criteria=partial(block_has_valid_parameter, parameter_name="description"),
)

view_has_primary_key = ParameterRule(
    title="View must define at least one primary key dimension",
    code="V110",
    select="view",
    filters=tuple(),
    criteria=partial(
        node_has_at_least_one_valid_child,
        is_valid=partial(
            block_has_valid_parameter, parameter_name="primary_key", value="yes"
        ),
    ),
)

primary_key_dimensions_hidden = ParameterRule(
    title="Primary key dimension not hidden",
    code="D102",
    select="dimension",
    filters=tuple(
        [partial(block_has_valid_parameter, parameter_name="primary_key", value="yes")],
    ),
    criteria=partial(
        block_has_valid_parameter, parameter_name="hidden", value="yes", negative=True
    ),
)

default_rules = (
    view_has_primary_key,
    count_measure_prefix,
    sum_measure_prefix,
    avg_measure_prefix,
    yesno_dimension_prefix,
    table_ref_in_measure,
    wildcard_include,
    labels_are_title_cased,
    dimension_group_suffix,
    primary_key_dimensions_hidden,
)

with open("test.view.lkml", "r") as file:
    tree = lkml.parse(file.read())

visitor = StyleCheckVisitor(rules=(primary_key_dimensions_hidden,))
tree.accept(visitor)

for violation in visitor.violations:
    print(violation)
