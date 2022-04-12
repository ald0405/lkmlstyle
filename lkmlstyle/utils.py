from functools import partial
from typing import Callable
from lkml.tree import SyntaxNode, PairNode, BlockNode
from lkmlstyle.types import HasType


def find_child_by_type(node: SyntaxNode, node_type: str) -> SyntaxNode | None:
    for child in node.children or []:
        if isinstance(child, HasType) and child.type.value == node_type:
            return child
    return None


def find_descendant_by_lineage(node: SyntaxNode, lineage: str) -> SyntaxNode | None:
    child = node
    for generation in lineage.split("."):
        match = find_child_by_type(child, node_type=generation)
        if match is None:
            return None
        else:
            child = match

    return child


def node_has_valid_class(node: SyntaxNode, node_type: type) -> bool:
    return isinstance(node, node_type)


def node_has_valid_type(node: HasType, value: str) -> bool:
    return node.type.value == value


def pair_has_valid_value(pair: PairNode, value: str) -> bool:
    return pair.value.value == value


def node_has_at_least_one_valid_child(
    node: SyntaxNode, is_valid: Callable[..., bool]
) -> bool:
    if node.children is None:
        return False
    for child in node.children or []:
        if is_valid(child):
            return True
    return False


def block_has_valid_parameter(
    block: BlockNode,
    parameter_name: str,
    value: str | None = None,
    negative: bool | None = False,
) -> bool:
    # TODO: Make sure this actually works
    if not isinstance(block, BlockNode):
        return False

    def is_valid_param(node: HasType) -> bool:
        # Only consider nodes that define a type attribute
        if not isinstance(node, HasType):
            return False
        if not node_has_valid_type(node, parameter_name):
            return False

        if value:
            # Can only test value for PairNodes
            if not isinstance(node, PairNode):
                return False
            if not pair_has_valid_value(node, value):
                return False

        return True

    valid = node_has_at_least_one_valid_child(block, is_valid_param)
    return not valid if negative else valid


def block_has_any_valid_parameter(block: BlockNode, parameters: dict) -> bool:
    return any(
        block_has_valid_parameter(block, name, value)
        for name, value in parameters.items()
    )


def node_has_at_least_one_child_with_valid_parameter(
    node: SyntaxNode, parameter_name: str, value: str | None = None
):
    return node_has_at_least_one_valid_child(
        node,
        is_valid=partial(
            block_has_valid_parameter, parameter_name=parameter_name, value=value
        ),
    )
