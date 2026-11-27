"""Element-tree traversal: conditional branches and adaptive questions."""
import unittest

from lexflow.elements import ElementSchema
from lexflow.issues import IssueTree


class TestIssueTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = ElementSchema()
        cls.tree = IssueTree(cls.schema)

    def keys(self, facts, claims=("labor_dismissal",)):
        return [q.key for q in self.tree.frontier(list(claims), facts)]

    def test_serious_misconduct_branch(self):
        facts = {"stated_reason": "严重违纪", "who_initiated": "单位单方解除",
                 "start_date": "2021-05-01", "dismiss_date": "2026-03-15"}
        keys = self.keys(facts)
        self.assertIn("rule_publicized", keys)
        self.assertIn("misconduct_proof", keys)
        self.assertNotIn("training_or_transfer", keys)
        self.assertNotIn("notice_30d", keys)

    def test_incompetence_branch(self):
        facts = {"stated_reason": "不胜任工作", "who_initiated": "单位单方解除",
                 "start_date": "2021-05-01", "dismiss_date": "2026-03-15"}
        keys = self.keys(facts)
        self.assertIn("training_or_transfer", keys)
        self.assertIn("notice_30d", keys)
        self.assertNotIn("rule_publicized", keys)

    def test_resignation_skips_union(self):
        facts = {"stated_reason": "其他或说不清", "who_initiated": "劳动者辞职",
                 "start_date": "2021-05-01", "dismiss_date": "2026-03-15"}
        keys = self.keys(facts)
        self.assertNotIn("union_notified", keys)
        self.assertIn("forced_resignation_reason", keys)

    def test_no_overtime_skips_hours(self):
        facts = {"overtime_exists": "没有"}
        keys = self.keys(facts, claims=("labor_overtime",))
        self.assertNotIn("overtime_hours_weekday", keys)
        self.assertNotIn("overtime_hours_rest", keys)

    def test_chain_has_three_levels(self):
        facts = {"stated_reason": "严重违纪", "who_initiated": "单位单方解除",
                 "start_date": "2021-05-01", "dismiss_date": "2026-03-15",
                 "rule_publicized": "没有公示告知"}
        chain = self.tree.chain(["labor_dismissal"], facts)
        self.assertEqual(chain[0]["claim"], "labor_dismissal")
        self.assertTrue(any(e["label"] == "解除理由与程序合法性"
                            for e in chain[0]["elements"]))
        statuses = {e["id"]: e["status"] for e in chain[0]["elements"]}
        self.assertEqual(statuses["dismissal_act"], "satisfied")

    def test_coverage_excludes_conditional(self):
        facts = {"stated_reason": "严重违纪", "who_initiated": "单位单方解除"}
        cov = self.tree.coverage(["labor_dismissal"], facts)
        self.assertGreater(cov["total"], 0)
        self.assertLess(cov["known"], cov["total"])


if __name__ == "__main__":
    unittest.main()
