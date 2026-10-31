"""Most General Unifier and comparison evaluators."""

from __future__ import annotations

from typing import Any

from logic.horn_clause import ComparisonGuard, Constant, Fact, Predicate, Variable


Substitution = dict[str, Any]


def is_variable(value: Any) -> bool:
    return isinstance(value, Variable)


def resolve(term: Any, theta: Substitution) -> Any:
    if isinstance(term, Constant):
        return term.value
    if isinstance(term, Variable):
        value = theta.get(term.name, term)
        if isinstance(value, Variable) and value.name != term.name:
            return resolve(value, theta)
        return value
    if isinstance(term, tuple):
        op = term[0]
        if op == "add":
            return resolve(term[1], theta) + resolve(term[2], theta)
        if op == "sub":
            return resolve(term[1], theta) - resolve(term[2], theta)
        if op == "mul":
            return resolve(term[1], theta) * resolve(term[2], theta)
        if op == "abs":
            return abs(resolve(term[1], theta))
    return term


def bind(var: Variable, value: Any, theta: Substitution) -> Substitution | None:
    current = theta.get(var.name)
    if current is not None:
        return unify_values(current, value, theta)
    if isinstance(value, Variable) and value.name in theta:
        return bind(var, theta[value.name], theta)
    extended = dict(theta)
    extended[var.name] = value
    return extended


def unify_values(left: Any, right: Any, theta: Substitution) -> Substitution | None:
    left = resolve(left, theta)
    right = resolve(right, theta)
    if isinstance(left, Variable):
        return bind(left, right, theta)
    if isinstance(right, Variable):
        return bind(right, left, theta)
    return theta if left == right else None


def unify_predicate_with_fact(predicate: Predicate, fact: Fact, theta: Substitution | None = None) -> Substitution | None:
    theta = {} if theta is None else dict(theta)
    fact_name, fact_args = fact
    if predicate.name != fact_name or len(predicate.terms) != len(fact_args):
        return None
    for term, value in zip(predicate.terms, fact_args):
        theta = unify_values(term, value, theta)
        if theta is None:
            return None
    return theta


def substitute_predicate(predicate: Predicate, theta: Substitution) -> Predicate:
    return Predicate(predicate.name, tuple(Constant(resolve(term, theta)) for term in predicate.terms))


def predicate_to_fact(predicate: Predicate, theta: Substitution) -> Fact | None:
    values = []
    for term in predicate.terms:
        value = resolve(term, theta)
        if isinstance(value, Variable):
            return None
        values.append(value)
    return predicate.name, tuple(values)


def _fmt(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.2f}" if not value.is_integer() else str(int(value))
    return str(value)


def evaluate_guard(guard: ComparisonGuard, theta: Substitution) -> tuple[bool, str]:
    left = resolve(guard.left, theta)
    right = resolve(guard.right, theta)
    symbols = {"Equal": "==", "GreaterOrEqual": ">=", "GreaterThan": ">", "LessOrEqual": "<="}
    symbol = symbols[guard.operator]
    if isinstance(left, Variable) or isinstance(right, Variable):
        return False, f"{left} {symbol} {right} unresolved"
    if left is None or right is None:
        return False, f"{_fmt(left)} {symbol} {_fmt(right)}"
    if guard.operator == "Equal":
        result = left == right
    elif guard.operator == "GreaterOrEqual":
        result = left >= right
    elif guard.operator == "GreaterThan":
        result = left > right
    elif guard.operator == "LessOrEqual":
        result = left <= right
    else:
        raise ValueError(f"Unknown comparison operator: {guard.operator}")
    return result, f"{_fmt(left)} {symbol} {_fmt(right)}"


def theta_repr(theta: Substitution) -> str:
    if not theta:
        return "{}"
    return "{" + ", ".join(f"?{key}: {value!r}" for key, value in sorted(theta.items())) + "}"
