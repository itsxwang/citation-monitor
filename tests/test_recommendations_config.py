import re
import tempfile
import unittest
from pathlib import Path

from citation_monitor.config import load_config
from citation_monitor.recommendations import build_recommendations
from citation_monitor.scoring import score_run

ROOT = Path(__file__).resolve().parent.parent


def _demo_context():
    """Build (score, diff) from the shipped demo fixtures — no API calls."""
    import json
    from citation_monitor.pipeline import _rows_from_fixture
    from citation_monitor.engines import _demo_engines
    from citation_monitor.prompts import build_prompts
    from citation_monitor import diff as diff_mod

    cfg = load_config(str(ROOT / "brand.yaml"))
    prompts = build_prompts(cfg)
    engines = _demo_engines(cfg)
    cur = json.loads((ROOT / "citation_monitor/fixtures/demo_current.json").read_text(encoding="utf-8"))
    prev = json.loads((ROOT / "citation_monitor/fixtures/demo_previous.json").read_text(encoding="utf-8"))
    cur_rows = _rows_from_fixture(engines, prompts, cur, cfg)
    prev_rows = _rows_from_fixture(engines, prompts, prev, cfg)
    return cfg, score_run(cur_rows), diff_mod.diff_runs(cur_rows, prev_rows)


class TestRecommendations(unittest.TestCase):
    def test_exactly_three_prioritized(self):
        cfg, score, d = _demo_context()
        recs = build_recommendations(score, d, cfg.brand.name, [c.name for c in cfg.competitors])
        self.assertEqual(len(recs), 3)
        self.assertEqual([r.priority for r in recs], ["P1", "P2", "P3"])
        for r in recs:
            self.assertTrue(r.title)
            self.assertTrue(r.why)
            self.assertGreaterEqual(len(r.actions), 3)

    def test_first_run_still_three(self):
        cfg, score, _ = _demo_context()
        recs = build_recommendations(score, {"first_run": True, "gained": [], "lost": []},
                                     cfg.brand.name, [c.name for c in cfg.competitors])
        self.assertEqual(len(recs), 3)

    def test_targets_deduped(self):
        cfg, score, d = _demo_context()
        recs = build_recommendations(score, d, cfg.brand.name, [c.name for c in cfg.competitors])
        for r in recs:
            self.assertEqual(len(r.targets), len(set(r.targets)))

    def test_no_geo_terminology(self):
        # product copy must never use the softening 'GEO' term
        cfg, score, d = _demo_context()
        recs = build_recommendations(score, d, cfg.brand.name, [c.name for c in cfg.competitors])
        blob = " ".join(r.title + " " + r.why + " " + " ".join(r.actions) for r in recs).lower()
        self.assertNotIn(" geo ", f" {blob} ".replace("\n", " "))


class TestDigestOutput(unittest.TestCase):
    def test_markdown_has_exactly_three_recommendations(self):
        from citation_monitor.digest_markdown import render_md
        from citation_monitor.pipeline import _collect_snippets

        cfg, score, d = _demo_context()
        recs = build_recommendations(score, d, cfg.brand.name, [c.name for c in cfg.competitors])
        snippets = _collect_snippets(
            [dict(r, brand_pos=0, raw_text="StableDesk cited here") for r in score["prompts"]],
            cfg.brand.name) if False else {}
        md = render_md(cfg.brand, "2026-W99", "demo", score, d, recs, [], snippets)
        self.assertEqual(len(re.findall(r"^### \d+\. \[P\d\]", md, flags=re.M)), 3)
        self.assertIn("DEMO DATA", md)
        self.assertNotIn(" GEO ", md)

    def test_html_single_file(self):
        from citation_monitor.digest_html import render_html

        cfg, score, d = _demo_context()
        recs = build_recommendations(score, d, cfg.brand.name, [c.name for c in cfg.competitors])
        html = render_html(cfg.brand, "2026-W99", "demo", score, d, recs, [], {})
        self.assertTrue(html.lstrip().startswith("<!DOCTYPE html>"))
        self.assertEqual(html.count("class='rec'"), 3)
        self.assertNotIn("src=\"http", html)      # no external assets
        self.assertNotIn("<script", html)         # no javascript


class TestConfig(unittest.TestCase):
    def test_repo_brand_yaml_loads(self):
        cfg = load_config(str(ROOT / "brand.yaml"))
        self.assertEqual(cfg.brand.name, "StableDesk")
        self.assertGreaterEqual(len(cfg.competitors), 3)
        self.assertGreaterEqual(len(cfg.prompts_raw), 30)
        self.assertIn("es", cfg.brand.locales)

    def test_mini_yaml_matches_pyyaml(self):
        from citation_monitor.config import TEMPLATE, _mini_yaml
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        a = yaml.safe_load(TEMPLATE)
        b = _mini_yaml(TEMPLATE)
        self.assertEqual(a, b)

    def test_missing_config_friendly_error(self):
        from citation_monitor.config import ConfigError
        with self.assertRaises(ConfigError):
            load_config(str(ROOT / "does-not-exist.yaml"))

    def test_init_template_roundtrip(self):
        from citation_monitor.config import TEMPLATE, load_config
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "brand.yaml"
            p.write_text(TEMPLATE, encoding="utf-8")
            cfg = load_config(str(p))
            self.assertEqual(cfg.brand.name, "StableDesk")


if __name__ == "__main__":
    unittest.main()
