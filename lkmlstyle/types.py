from typing import Protocol, runtime_checkable
from lkml.tree import SyntaxToken


@runtime_checkable
class HasType(Protocol):
    type: SyntaxToken
