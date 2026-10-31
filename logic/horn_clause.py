"""Predicate terms, facts, comparisons, and Horn clauses."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Variable:
    name: str

    def __str__(self) -> str:
        return f"?{self.name}"


@dataclass(frozen=True)
class Constant:
    value: Any

    def __str__(self) -> str:
        return repr(self.value)


Term = Variable | Constant


@dataclass(frozen=True)
class Predicate:
    name: str
    terms: tuple[Term, ...]

    def __str__(self) -> str:
        return f"{self.name}({', '.join(str(t) for t in self.terms)})"


@dataclass(frozen=True)
class ComparisonGuard:
    operator: str
    left: Any
    right: Any

    def __str__(self) -> str:
        return f"{self.operator}({self.left}, {self.right})"


@dataclass(frozen=True)
class HornClause:
    name: str
    stage: int
    head: Predicate
    body: tuple[Predicate | ComparisonGuard, ...]

    def __str__(self) -> str:
        return f"{self.name}: {self.head} :- {', '.join(str(item) for item in self.body)}"


Fact = tuple[str, tuple[Any, ...]]


def V(name: str) -> Variable:
    return Variable(name)


def C(value: Any) -> Constant:
    return Constant(value)


def P(name: str, *terms: Any) -> Predicate:
    normalized = tuple(term if isinstance(term, (Variable, Constant)) else Constant(term) for term in terms)
    return Predicate(name, normalized)
