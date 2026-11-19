import unittest

from citation_monitor.diff import diff_runs
from citation_monitor.scoring import score_run


def row(engine="groq", prompt="p1", brand=True, comps=("BitPay",), style="best_tool",
        locale="en", text="answer"):
    return {
        "engine": engine, "model": "m", "prompt_id": prompt, "prompt_text": prompt,
        "locale": locale, "style": style, "raw_text": text,
        "brand_mentioned": brand, "brand_pos": 0 if brand else -1,
        "brand_alias": "StableDesk" if brand else "", "brand_fuzzy": False,
        "competitors": [{"name": c, "pos": 1, "alias": c, "fuzzy": False,
                         "snippet": "..."} for c in comps],
        "tokens_est": 100, "error": None,
    }


class TestScoring(unittest.TestCase):
    def test_citation_rate_and_sov(self):
        rows = [
            row(brand=True, comps=("BitPay", "Coinbase Commerce")),   # sov 1/3
            row(brand=True, comps=()),                                # sov 1.0
            row(brand=False, comps=("BitPay",)),                      # sov 0.0
            row(brand=False, comps=()),                               # no entities -> skipped
        ]
        s = score_run(rows)
        self.assertAlmostEqual(s["citation_rate"], 50.0)
        # mean of (1/3, 1.0, 0.0) = 4/9
        self.assertAlmostEqual(s["sov"], 4 / 9 * 100.0, places=6)

    def test_per_engine(self):
        rows = [
            row(engine="groq", brand=True, comps=()),
            row(engine="groq", brand=False, comps=("BitPay",)),
            row(engine="gemini", brand=False, comps=("BitPay",)),
        ]
        s = score_run(rows)
        self.assertAlmostEqual(s["engines"]["groq"]["citation_rate"], 50.0)
        self.assertAlmostEqual(s["engines"]["gemini"]["citation_rate"], 0.0)
        self.assertAlmostEqual(s["engines"]["groq"]["sov"], 50.0)

    def test_failed_calls_are_excluded_from_scores(self):
        """A 429/503 is not evidence the brand was absent: keep it out of metrics."""
        failed_429 = dict(row(brand=False, comps=("BitPay",)))
        failed_429.update({"raw_text": "", "error": "[gemini] 429"})
        failed_503 = dict(row(brand=False, comps=()))
        failed_503.update({"raw_text": "", "error": "[gemini] 503"})
        rows = [row(brand=True, comps=("BitPay",)), failed_429, failed_503]
        s = score_run(rows)
        self.assertEqual(s["n_rows"], 1)
        self.assertEqual(s["n_attempted"], 3)
        self.assertEqual(s["n_failed"], 2)
        self.assertAlmostEqual(s["citation_rate"], 100.0)
        self.assertAlmostEqual(s["engines"]["groq"]["n"], 1)

    def test_prompt_aggregation_and_styles(self):
        rows = [
            row(prompt="p1", style="pricing", brand=False, comps=("BitPay",)),
            row(prompt="p1", engine="gemini", style="pricing", brand=True, comps=()),
            row(prompt="p2", style="how_to", brand=False, comps=()),
        ]
        s = score_run(rows)
        by_id = {p["prompt_id"]: p for p in s["prompts"]}
        self.assertTrue(by_id["p1"]["brand_any"])
        self.assertFalse(by_id["p2"]["brand_any"])
        self.assertAlmostEqual(s["style_stats"]["pricing"]["n"], 1)
        self.assertAlmostEqual(s["style_stats"]["how_to"]["brand"], 0)
        self.assertIn("BitPay", s["competitors"])

    def test_empty(self):
        s = score_run([])
        self.assertEqual(s["sov"], 0.0)
        self.assertEqual(s["citation_rate"], 0.0)


class TestDiff(unittest.TestCase):
    def test_gained_lost(self):
        prev = [
            row(engine="groq", prompt="p1", brand=False, comps=("BitPay",)),
            row(engine="groq", prompt="p2", brand=True, comps=("BitPay",)),
        ]
        cur = [
            row(engine="groq", prompt="p1", brand=True, comps=("BitPay",)),
            row(engine="groq", prompt="p2", brand=False, comps=("BitPay",)),
        ]
        d = diff_runs(cur, prev)
        self.assertFalse(d["first_run"])
        self.assertEqual([g["prompt_text"] for g in d["gained"]], ["p1"])
        self.assertEqual([g["prompt_text"] for g in d["lost"]], ["p2"])
        self.assertEqual(d["competitor_deltas"], {"BitPay": 0})

    def test_stable_not_reported(self):
        prev = [row(brand=True, comps=("BitPay",))]
        cur = [row(brand=True, comps=("BitPay",))]
        d = diff_runs(cur, prev)
        self.assertEqual(d["gained"], [])
        self.assertEqual(d["lost"], [])

    def test_first_run(self):
        d = diff_runs([row()], None)
        self.assertTrue(d["first_run"])
        self.assertEqual(d["gained"], [])
        self.assertEqual(d["lost"], [])
        self.assertEqual(d["prev_summary"], None)

    def test_sov_delta_sign(self):
        prev = [row(brand=False, comps=("BitPay", "Coinbase Commerce"))] * 4
        cur = [row(brand=True, comps=("BitPay",))] * 4
        d = diff_runs(cur, prev)
        self.assertGreater(d["sov_delta"], 0)
        self.assertGreater(d["citation_delta"], 0)

    def test_engine_key_mismatch_ignored(self):
        prev = [row(engine="gemini", prompt="p1", brand=False)]
        cur = [row(engine="groq", prompt="p1", brand=True)]
        d = diff_runs(cur, prev)
        self.assertEqual(d["gained"], [])  # different (engine, prompt) key -> no pair


if __name__ == "__main__":
    unittest.main()
