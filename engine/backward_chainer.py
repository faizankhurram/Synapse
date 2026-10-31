"""Goal-driven backward chaining with AND/OR proof trees."""

from dataclasses import dataclass, field
from typing import Any

from engine.forward_chainer import build_rule_base
from engine.unifier import (
    evaluate_guard,
    predicate_to_fact,
    resolve,
    substitute_predicate,
    theta_repr,
    unify_predicate_with_fact,
)
from logic.horn_clause import ComparisonGuard, Fact, Predicate, Variable


@dataclass
class ProofNode:
    label: str
    status: bool
    theta: str = "{}"
    bindings: dict[str, Any] = field(default_factory=dict)
    children: list["ProofNode"] = field(default_factory=list)


class BackwardChainer:
    def __init__(self, facts: set[Fact]):
        self.facts = facts
        self.rules = build_rule_base()

    def prove(self, goal: Predicate) -> ProofNode:
        node = self._prove_predicate(goal, {}, [])
        node.label = f"{goal} -> {'PROVEN' if node.status else 'DISPROVEN'}"
        return node

    def _project_theta(self, goal: Predicate, theta: dict[str, Any]) -> dict[str, Any]:
        """Keep only bindings needed by variables that appear in this goal."""
        projected: dict[str, Any] = {}
        for term in goal.terms:
            if isinstance(term, Variable):
                value = resolve(term, theta)
                if isinstance(value, Variable):
                    continue
                projected[term.name] = value
        return projected

    def _goal_shape(self, goal: Predicate, theta: dict[str, Any]) -> Fact:
        return goal.name, tuple(resolve(term, theta) for term in goal.terms)

    def _prove_predicate(self, goal: Predicate, theta: dict[str, Any], stack: list[str]) -> ProofNode:
        local_theta = self._project_theta(goal, theta)
        grounded = predicate_to_fact(goal, local_theta)
        display = str(substitute_predicate(goal, local_theta)) if grounded else str(goal)
        key = f"{goal.name}|{display}|{theta_repr(local_theta)}"

        if grounded and grounded in self.facts:
            return ProofNode(f"Fact {display}", True, theta_repr(local_theta), dict(local_theta))

        for fact in self.facts:
            unified = unify_predicate_with_fact(goal, fact, local_theta)
            if unified is not None:
                proven = predicate_to_fact(goal, unified)
                label = f"Fact {proven[0]}{proven[1]}" if proven else f"Fact {display}"
                return ProofNode(label, True, theta_repr(unified), dict(unified))

        if key in stack:
            return ProofNode(f"Cycle blocked at {display}", False, theta_repr(local_theta), dict(local_theta))

        alternatives: list[ProofNode] = []
        goal_shape = self._goal_shape(goal, local_theta)

        # Reject goal shapes that still contain unbound variables in constant positions only after resolve.
        if any(isinstance(arg, Variable) for arg in goal_shape[1]):
            # Still allow rule application; head unification will bind them.
            pass

        for rule in self.rules:
            if rule.head.name != goal.name or len(rule.head.terms) != len(goal_shape[1]):
                continue
            head_theta = unify_predicate_with_fact(rule.head, goal_shape, local_theta)
            if head_theta is None:
                continue

            current = dict(head_theta)
            and_node = ProofNode(f"Apply {rule.name}", True, theta_repr(current), dict(current))
            for item in rule.body:
                if isinstance(item, Predicate):
                    pre = dict(current)
                    child = self._prove_predicate(item, current, stack + [key])
                    if child.status:
                        proven = predicate_to_fact(item, {**pre, **child.bindings})
                        if proven is not None:
                            merged = unify_predicate_with_fact(item, proven, pre)
                            current = merged if merged is not None else pre
                        else:
                            current = pre
                else:
                    passed, detail = evaluate_guard(item, current)
                    child = ProofNode(f"Compare {detail}", passed, theta_repr(current), dict(current))
                and_node.children.append(child)
                if not child.status:
                    and_node.status = False
                    break
            and_node.bindings = dict(current)
            and_node.theta = theta_repr(current)
            alternatives.append(and_node)
            if and_node.status:
                return ProofNode(f"Goal {display}", True, and_node.theta, dict(current), [and_node])

        if alternatives:
            return ProofNode(f"Goal {display}", False, theta_repr(local_theta), dict(local_theta), alternatives)
        return ProofNode(f"No proof for {display}", False, theta_repr(local_theta), dict(local_theta))
