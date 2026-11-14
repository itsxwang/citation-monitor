import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestDemoPipelineEndToEnd(unittest.TestCase):
    def test_full_demo_run(self):
        """Zero-key demo run: fixtures -> analyze -> store -> diff -> digest."""
        import shutil

        from citation_monitor.config import load_config
        from citation_monitor.pipeline import report_pipeline, run_pipeline
        from citation_monitor import store

        tmp = tempfile.mkdtemp(prefix="cm-test-")
        try:
            cfg = load_config(str(ROOT / "brand.yaml"))
            cfg.run.storage = os.path.join(tmp, "history.db")
            cfg.run.output_dir = os.path.join(tmp, "out")

            summary = run_pipeline(cfg, demo=True, log=lambda *a, **k: None)
            self.assertEqual(summary["mode"], "demo")
            self.assertGreater(summary["n_rows"], 0)
            md, html = Path(summary["md_path"]), Path(summary["html_path"])
            self.assertTrue(md.exists())
            self.assertTrue(html.exists())
            text = md.read_text(encoding="utf-8")
            self.assertIn("DEMO DATA", text)
            # history: previous fixture week + this week
            conn = store.connect(cfg.run.storage)
            runs = store.history(conn)
            self.assertEqual(len(runs), 2)
            # re-running demo same week must NOT duplicate the seeded previous run
            run_pipeline(cfg, demo=True, log=lambda *a, **k: None)
            conn2 = store.connect(cfg.run.storage)
            self.assertEqual(len(store.history(conn2)), 3)  # prev + 2 identical week runs

            # report re-renders from storage without any engine calls
            rep = report_pipeline(cfg, log=lambda *a, **k: None)
            self.assertTrue(Path(rep["html_path"]).exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_degrades_to_demo_without_keys(self):
        from citation_monitor import engines as eng_mod
        from citation_monitor.config import load_config

        cfg = load_config(str(ROOT / "brand.yaml"))
        saved = {}
        for var in ("GROQ_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
                    "OPENROUTER_API_KEY", "PERPLEXITY_API_KEY"):
            saved[var] = os.environ.pop(var, None)
        try:
            log_lines = []
            engines_list, mode, prev_fix = eng_mod.build_engines(
                cfg, demo=False, log=log_lines.append)
            self.assertEqual(mode, "demo")
            self.assertGreaterEqual(len(engines_list), 1)
            self.assertTrue(any("no API keys found" in ln for ln in log_lines))
            self.assertIsNotNone(prev_fix)
        finally:
            for var, val in saved.items():
                if val is not None:
                    os.environ[var] = val

    def test_live_build_selects_only_keyed_engines(self):
        from citation_monitor import engines as eng_mod
        from citation_monitor.config import load_config

        cfg = load_config(str(ROOT / "brand.yaml"))
        os.environ["GROQ_API_KEY"] = "test-key-123"
        try:
            engines_list, mode, _ = eng_mod.build_engines(cfg, demo=False, log=lambda *a: None)
            self.assertEqual(mode, "live")
            names = [e.name for e in engines_list]
            self.assertIn("groq", names)
            self.assertNotIn("gemini", names)  # no GEMINI_API_KEY -> skipped gracefully
            self.assertNotIn("openrouter", names)
        finally:
            os.environ.pop("GROQ_API_KEY", None)

    def test_demo_engine_ask_replays_fixture(self):
        from citation_monitor.engines import _demo_engines, system_prompt
        from citation_monitor.config import load_config
        from citation_monitor.prompts import build_prompts

        cfg = load_config(str(ROOT / "brand.yaml"))
        prompts = build_prompts(cfg)
        demo = _demo_engines(cfg)
        self.assertEqual(len(demo), 2)
        out = demo[0].ask(prompts[0].text, system_prompt(prompts[0].locale))
        self.assertTrue(out.strip())
        with self.assertRaises(Exception):
            demo[0].ask("a prompt that has no fixture recorded", system_prompt("en"))


if __name__ == "__main__":
    unittest.main()
