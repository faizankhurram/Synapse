"""Directed labeled semantic network for hardware and game concepts."""

from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Iterable


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str


@dataclass
class SemanticNetwork:
    nodes: set[str] = field(default_factory=set)
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, node: str) -> None:
        self.nodes.add(node)

    def add_edge(self, source: str, relation: str, target: str) -> None:
        self.nodes.update([source, target])
        self.edges.append(Edge(source, relation, target))

    def outgoing(self, node: str, relation: str | None = None) -> list[Edge]:
        return [e for e in self.edges if e.source == node and (relation is None or e.relation == relation)]

    def traverse(self, source: str, relation: str) -> list[str]:
        return [edge.target for edge in self.outgoing(source, relation)]

    def is_instance_of(self, sub: str, super_node: str) -> bool:
        agenda = deque([sub])
        seen = set()
        while agenda:
            node = agenda.popleft()
            if node == super_node:
                return True
            if node in seen:
                continue
            seen.add(node)
            agenda.extend(edge.target for edge in self.outgoing(node, "is-a"))
        return False


def build_semantic_network(system, games: dict, diagnostics: Iterable[str]) -> SemanticNetwork:
    net = SemanticNetwork()
    for cls in ("CPU", "GPU", "RAM", "Motherboard", "Storage", "PowerSupply"):
        net.add_edge(cls, "is-a", "Component")
        net.add_edge(cls, "part-of", "SystemConfiguration")
    net.add_edge("PerformanceDiagnostic", "is-a", "DiagnosticState")
    for slot, cls in (
        ("cpu", "CPU"),
        ("gpu", "GPU"),
        ("ram", "RAM"),
        ("motherboard", "Motherboard"),
        ("storage", "Storage"),
        ("psu", "PowerSupply"),
    ):
        instance = system.values[slot]
        net.add_edge(instance.instance_id, "is-a", cls)
        net.add_edge(instance.instance_id, "part-of", system.instance_id)
    net.add_edge(system.instance_id, "is-a", "SystemConfiguration")
    net.add_edge(system.values["cpu"].instance_id, "physically_fits", system.values["motherboard"].instance_id)
    net.add_edge(system.values["ram"].instance_id, "standard_matches", system.values["motherboard"].instance_id)
    for game_id in games:
        net.add_edge(game_id, "is-a", "GameTitle")
        net.add_edge(system.instance_id, "evaluates_against", game_id)
    for diagnostic in diagnostics:
        net.add_edge(system.instance_id, "exhibits_state", diagnostic)
        net.add_edge(diagnostic, "is-a", "PerformanceDiagnostic")
    return net
