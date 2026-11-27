"""Concurrency must preserve real consultation outcomes and output order."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from run_evals_v2 import run_jobs
from protocol_v2 import run_case
from lexflow.corpus import StatuteCorpus
from lexflow.elements import ElementSchema
from lexflow.llm import NullLLM


class TestParallelEvaluation(unittest.TestCase):
    def test_isolated_sessions_preserve_order_corrections_and_scores(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root / "data/eval/labor_cases_v2.json").read_text())
        cases = [next(c for c in data["cases"] if c["id"] == cid) for cid in ("B02", "B04", "B14")]
        corpus, schema = StatuteCorpus(), ElementSchema()

        def execute(case):
            return run_case(case, "full", corpus, schema, NullLLM(), data["today"])

        serial = list(run_jobs(cases, execute, 1))
        concurrent = list(run_jobs(cases, execute, 3))
        self.assertEqual([r["case_id"] for r in concurrent], [c["id"] for c in cases])
        for expected, actual in zip(serial, concurrent):
            for key in ("status", "scores", "assertions", "failures", "usage"):
                self.assertEqual(actual[key], expected[key], (actual["case_id"], key))
