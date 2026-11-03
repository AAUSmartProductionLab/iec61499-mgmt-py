"""Structured Text conditions and expressions of a module spec (precondition, postcondition,
invariant, arg, after), evaluated in Python as the generated module evaluates them in IEC 61499.

The subset the specs use: numbers, TRUE and FALSE, names (an item's inputs, the skill's
parameters), NOT and unary minus, * / MOD, + -, < > <= >=, = <>, AND (&), XOR, OR, parentheses, and
ABS, MIN, MAX and SQRT. An expression is parsed once into a function of the names' values, in ST's
order of precedence; nothing is handed to ``eval``.
"""
from __future__ import annotations

from functools import lru_cache
import math
import operator
import re
from typing import Any, Callable, Mapping

TOKEN = re.compile(r"\s*(?:(\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)"
                   r"|([A-Za-z_][A-Za-z0-9_]*)|(<>|<=|>=|[-+*/()<>=,&]))")
KEYWORDS = {"AND", "OR", "XOR", "NOT", "MOD", "TRUE", "FALSE"}
FUNCTIONS: dict[str, Callable] = {"ABS": abs, "MIN": min, "MAX": max, "SQRT": math.sqrt}

Expression = Callable[[Mapping[str, Any]], Any]


def tokens(text: str) -> list[tuple[str, Any]]:
    """("num", value), ("word", keyword or function, upper case), ("name", name) or ("op", symbol)."""
    out, at, text = [], 0, text.strip()
    while at < len(text):
        found = TOKEN.match(text, at)
        if not found or found.end() == at:
            raise ValueError(f"Not Structured Text: {text!r} at {text[at:]!r}")
        number, name, op = found.groups()
        if number is not None:
            out.append(("num", float(number)))
        elif name is not None:
            word = name.upper()
            out.append(("word", word) if word in KEYWORDS or word in FUNCTIONS else ("name", name))
        else:
            out.append(("op", op))
        at = found.end()
    return out


class Parser:
    """Recursive descent, from the weakest operator (OR) to the strongest (NOT, unary minus)."""

    def __init__(self, text: str):
        self.text, self.items, self.at = text, tokens(text), 0

    def peek(self) -> tuple[str | None, Any]:
        return self.items[self.at] if self.at < len(self.items) else (None, None)

    def expect(self, kind: str, value: Any) -> None:
        if self.peek() != (kind, value):
            raise ValueError(f"{self.text!r}: expected {value!r}")
        self.at += 1

    def parse(self) -> Expression:
        found = self.binary(0)
        if self.at != len(self.items):
            raise ValueError(f"{self.text!r}: unexpected {self.items[self.at][1]!r}")
        return found

    LEVELS: list[dict[tuple[str, str], Callable]] = [
        {("word", "OR"): lambda a, b: bool(a) or bool(b)},
        {("word", "XOR"): lambda a, b: bool(a) != bool(b)},
        {("word", "AND"): lambda a, b: bool(a) and bool(b), ("op", "&"): lambda a, b: bool(a) and bool(b)},
        {("op", "="): operator.eq, ("op", "<>"): operator.ne},
        {("op", "<"): operator.lt, ("op", ">"): operator.gt, ("op", "<="): operator.le, ("op", ">="): operator.ge},
        {("op", "+"): operator.add, ("op", "-"): operator.sub},
        {("op", "*"): operator.mul, ("op", "/"): operator.truediv, ("word", "MOD"): operator.mod},
    ]

    def binary(self, level: int) -> Expression:
        if level == len(self.LEVELS):
            return self.unary()
        left = self.binary(level + 1)
        while (op := self.LEVELS[level].get(self.peek())) is not None:
            self.at += 1
            right = self.binary(level + 1)
            left = (lambda f, g, o: lambda v: o(f(v), g(v)))(left, right, op)
        return left

    def unary(self) -> Expression:
        if self.peek() == ("word", "NOT"):
            self.at += 1
            inner = self.unary()
            return lambda v: not inner(v)
        if self.peek() == ("op", "-"):
            self.at += 1
            inner = self.unary()
            return lambda v: -inner(v)
        return self.primary()

    def primary(self) -> Expression:
        kind, value = self.peek()
        self.at += 1
        if kind == "num":
            return lambda v: value
        if kind == "word" and value in ("TRUE", "FALSE"):
            constant = value == "TRUE"
            return lambda v: constant
        if kind == "word" and value in FUNCTIONS:
            self.expect("op", "(")
            args = [self.binary(0)]
            while self.peek() == ("op", ","):
                self.at += 1
                args.append(self.binary(0))
            self.expect("op", ")")
            function = FUNCTIONS[value]
            return lambda v: function(*(a(v) for a in args))
        if kind == "name":
            return lambda v: v[value]
        if (kind, value) == ("op", "("):
            inner = self.binary(0)
            self.expect("op", ")")
            return inner
        raise ValueError(f"{self.text!r}: unexpected {value!r}")


@lru_cache(maxsize=None)
def compile_st(text: str) -> Expression:
    """The function of the names' values that ``text`` computes."""
    return Parser(text).parse()


def evaluate(text: str, values: Mapping[str, Any]) -> Any:
    return compile_st(text)(values)
