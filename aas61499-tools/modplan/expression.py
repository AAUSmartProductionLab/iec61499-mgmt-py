"""The language of a constraint: what a BasicConstraint holds (IDTA 02020; ARSO 0.11).

    <op> <operand>   op one of = != < <= > >= +=; the operand a number, true or false, or the
                     idShort of another property of the capability (a parameter or a named value)
    given            (Post) the property ends at the value the capability was given
    measured         (Post) the property ends at what the capability measured
    unchanged        (Invariant) nothing else changes the property while the capability runs

A planner achieves ``=`` and ``+=`` (it finds a capability whose Post makes them hold) and only
checks the other comparisons.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

OPERATORS = ("+=", "!=", "<=", ">=", "=", "<", ">")      # longest first, so that "<=" is not "<"
COMPARISONS = ("=", "!=", "<", "<=", ">", ">=")
WORDS = ("given", "measured", "unchanged")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
# What each kind of constraint (PropertyConditionalType) may say.
ALLOWED = {"Pre": COMPARISONS, "Post": ("=", "+=", "given", "measured"), "Invariant": (*COMPARISONS, "unchanged")}


@dataclass(frozen=True)
class Expression:
    op: str                                      # an operator, or one of WORDS
    operand: float | bool | str | None = None    # a value, or the name of a property

    @property
    def named(self) -> str | None:
        """The property the operand names, if it names one."""
        return self.operand if isinstance(self.operand, str) else None

    def __str__(self) -> str:
        if self.op in WORDS:
            return self.op
        value = str(self.operand).lower() if isinstance(self.operand, bool) else self.operand
        return f"{self.op} {value}"


def parse(text: str, kind: str | None = None) -> Expression:
    """The expression a constraint's text states; ``kind`` (Pre, Post, Invariant): it has to be one
    that kind of constraint may say. ValueError for anything else."""
    found = _parse(text.strip())
    if kind is not None and found.op not in ALLOWED[kind]:
        raise ValueError(f"a {kind} constraint cannot say {text!r}")
    return found


def _parse(text: str) -> Expression:
    if text in WORDS:
        return Expression(text)
    op = next((op for op in OPERATORS if text.startswith(op)), None)
    if op is None:
        raise ValueError(f"not a constraint: {text!r}")
    rest = text[len(op):].strip()
    if rest in ("true", "false"):
        return Expression(op, rest == "true")
    if NAME.match(rest):
        return Expression(op, rest)
    try:
        return Expression(op, float(rest))
    except ValueError:
        raise ValueError(f"not a constraint: {text!r}") from None
