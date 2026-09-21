from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from post_truth.models import Impact, NewsEvent


@dataclass
class DecisionNode:
    node_id: str
    label: str
    description: str
    impact: Impact = field(default_factory=Impact)
    children: list["DecisionNode"] = field(default_factory=list)

    def add_child(self, child: "DecisionNode") -> None:
        self.children.append(child)

    def remove_child(self, node_id: str) -> bool:
        for index, child in enumerate(self.children):
            if child.node_id == node_id:
                del self.children[index]
                return True
            if child.remove_child(node_id):
                return True
        return False


@dataclass
class DecisionTree:
    event: NewsEvent
    root: DecisionNode

    @classmethod
    def from_event_dict(cls, data: dict) -> "DecisionTree":
        event = NewsEvent(
            event_id=data["id"],
            title=data["title"],
            content=data["content"],
            kind=data["kind"],
            truth_level=data["truth_level"],
        )
        root = DecisionNode(
            node_id=f"{event.event_id}:root",
            label=event.title,
            description=event.content,
            impact=Impact.from_dict(data.get("root_effect")),
        )
        for decision in data.get("decisions", []):
            root.add_child(_node_from_dict(event.event_id, decision, parent_key="root"))
        return cls(event=event, root=root)

    def insert_decision(
        self,
        parent_id: str,
        node_id: str,
        label: str,
        description: str,
        impact: Impact,
    ) -> DecisionNode:
        parent = self.find(parent_id)
        if parent is None:
            raise ValueError(f"No existe el nodo padre: {parent_id}")
        if self.find(node_id) is not None:
            raise ValueError(f"Ya existe un nodo con id: {node_id}")
        child = DecisionNode(node_id, label, description, impact)
        parent.add_child(child)
        return child

    def delete_decision(self, node_id: str) -> bool:
        if node_id == self.root.node_id:
            raise ValueError("No se puede eliminar la raiz del arbol")
        return self.root.remove_child(node_id)

    def find(self, node_id: str) -> DecisionNode | None:
        for node in self.dfs_nodes():
            if node.node_id == node_id:
                return node
        return None

    def dfs_nodes(self) -> Iterable[DecisionNode]:
        yield from _dfs(self.root)

    def bfs_nodes(self) -> Iterable[DecisionNode]:
        pending: deque[DecisionNode] = deque([self.root])
        while pending:
            node = pending.popleft()
            yield node
            pending.extend(node.children)

    def path_to(self, target_id: str) -> list[DecisionNode]:
        path: list[DecisionNode] = []
        if _path_to(self.root, target_id, path):
            return path
        raise ValueError(f"No existe una trayectoria hacia: {target_id}")

    def accumulated_impact(self, target_id: str) -> Impact:
        total = Impact()
        for node in self.path_to(target_id):
            total += node.impact
        return total

    def pretty(self) -> str:
        lines: list[str] = []
        _pretty(self.root, lines, depth=0)
        return "\n".join(lines)


def load_trees(path: str | Path) -> list[DecisionTree]:
    with Path(path).open("r", encoding="utf-8") as file:
        events = json.load(file)
    return [DecisionTree.from_event_dict(event) for event in events]


def _node_from_dict(event_id: str, data: dict, parent_key: str) -> DecisionNode:
    label = data["action"]
    node_id = f"{event_id}:{parent_key}/{_slug(label)}"
    node = DecisionNode(
        node_id=node_id,
        label=label,
        description=data.get("description", ""),
        impact=Impact.from_dict(data.get("effect")),
    )
    for child in data.get("children", []):
        node.add_child(_node_from_dict(event_id, child, parent_key=node_id.split(":", 1)[1]))
    return node


def _slug(text: str) -> str:
    return (
        text.lower()
        .replace(" ", "-")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def _dfs(node: DecisionNode) -> Iterable[DecisionNode]:
    yield node
    for child in node.children:
        yield from _dfs(child)


def _path_to(node: DecisionNode, target_id: str, path: list[DecisionNode]) -> bool:
    path.append(node)
    if node.node_id == target_id:
        return True
    for child in node.children:
        if _path_to(child, target_id, path):
            return True
    path.pop()
    return False


def _pretty(node: DecisionNode, lines: list[str], depth: int) -> None:
    prefix = "  " * depth
    lines.append(f"{prefix}- {node.label} ({node.node_id})")
    for child in node.children:
        _pretty(child, lines, depth + 1)
