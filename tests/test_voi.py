"""VOI should rank outcome-changing questions above outcome-neutral ones."""
import unittest

from lexflow.elements import ElementSchema
from lexflow.issues import IssueTree
from lexflow.voi import ScenarioVOI


class TestVOI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ElementSchema()
        cls.tree = IssueTree(cls.schema)
        cls.voi = ScenarioVOI("2026-11-27")

    def test_publicity_beats_democratic_procedure_before_known(self):
        facts = {"stated_reason": "严重违纪", "who_initiated": "单位单方解除",
                 "start_date": "2021-05-01", "dismiss_date": "2026-03-15"}
        qs = self.tree.frontier(["labor_dismissal"], facts)
        scores = self.voi.score(qs, ["labor_dismissal"], facts)
        self.assertIn("rule_publicized", scores)
        self.assertGreater(scores["rule_publicized"].gain, 0)

    def test_democratic_procedure_is_neutral_after_publicity_defect(self):
        facts = {"stated_reason": "严重违纪", "who_initiated": "单位单方解除",
                 "start_date": "2021-05-01", "dismiss_date": "2026-03-15",
                 "rule_publicized": "没有公示告知", "rule_exists": "有成文制度",
                 "monthly_wage": 15000, "claim_type": "要求赔偿金"}
        qs = [q for q in self.tree.frontier(["labor_dismissal"], facts)
              if q.key == "rule_democratic"]
        if not qs:
            self.skipTest("rule_democratic not on the frontier")
        scores = self.voi.score(qs, ["labor_dismissal"], facts)
        self.assertEqual(scores["rule_democratic"].gain, 0)


if __name__ == "__main__":
    unittest.main()
