import unittest
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from post_truth.decision_tree import load_trees
from post_truth.models import Impact


class DecisionTreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = load_trees(ROOT_DIR / "data" / "events.json")[0]

    def test_loads_tree_from_json(self) -> None:
        self.assertEqual(self.tree.event.event_id, "colegio-cerrado")
        self.assertGreaterEqual(len(self.tree.root.children), 4)

    def test_dfs_visits_root_first(self) -> None:
        nodes = list(self.tree.dfs_nodes())
        self.assertEqual(nodes[0].node_id, self.tree.root.node_id)
        self.assertIn("Verificar", [node.label for node in nodes])

    def test_bfs_visits_first_level_before_grandchildren(self) -> None:
        labels = [node.label for node in self.tree.bfs_nodes()]
        apology_index = labels.index("Pedir disculpas")
        report_index = labels.index("Reportar")
        self.assertLess(report_index, apology_index)

    def test_accumulated_impact_uses_path(self) -> None:
        verify_node = next(
            node for node in self.tree.dfs_nodes() if node.label == "Publicar aclaracion"
        )
        impact = self.tree.accumulated_impact(verify_node.node_id)
        self.assertGreater(impact.verified_information, 12)
        self.assertLess(impact.misinformation, -8)

    def test_insert_and_delete_decision(self) -> None:
        child = self.tree.insert_decision(
            parent_id=self.tree.root.node_id,
            node_id="colegio-cerrado:root/contrastar-fuentes",
            label="Contrastar fuentes",
            description="Se comparan varias fuentes antes de publicar.",
            impact=Impact(verified_information=4, trust=2, score=5),
        )
        self.assertIsNotNone(self.tree.find(child.node_id))
        self.assertTrue(self.tree.delete_decision(child.node_id))
        self.assertIsNone(self.tree.find(child.node_id))


if __name__ == "__main__":
    unittest.main()
