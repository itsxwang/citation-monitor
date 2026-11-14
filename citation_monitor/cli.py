"""CLI: python -m citation_monitor init|run|report --config brand.yaml [--demo]"""
from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_config
from .pipeline import report_pipeline, run_pipeline

TEMPLATE = None  # set at bottom to avoid a circular import with the template text


def _print_summary(s: dict) -> None:
    print("")
    print("─" * 62)
    print(f"Run complete  ·  week {s.get('week')}  ·  mode: {str(s.get('mode', '')).upper()}")
    if s.get("engines"):
        print(f"Engines: {', '.join(s['engines'])}")
    if "citation_rate" in s:
        print(f"Brand citation rate: {s['citation_rate']:.1f}%   share of voice: {s['sov']:.1f}%"
              + (f"  (Δ {s['sov_delta']:+.1f} pts)" if s.get('sov_delta') else ""))
    if s.get("top_competitor"):
        print(f"Top cited competitor: {s['top_competitor']}")
    if s.get("gained") is not None:
        print(f"Changes: +{s.get('gained', 0)} gained / -{s.get('lost', 0)} lost")
    if s.get("tokens_est"):
        print(f"Tokens used (est.): {s.get('tokens_est', 0):,}")
    print(f"Digest:  {s['md_path']}")
    print(f"         {s['html_path']}")
    print("─" * 62)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="citation-monitor",
        description="Weekly AI answer-citation monitor with a customer-ready digest. "
                    "Crypto-native, $19/mo product for indie SaaS founders.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="write a starter brand.yaml (StableDesk sample — edit it)")
    p_init.add_argument("path", nargs="?", default="brand.yaml")

    p_run = sub.add_parser("run", help="run one monitoring cycle and write the weekly digest")
    p_run.add_argument("--config", default="brand.yaml")
    p_run.add_argument("--demo", action="store_true", help="force demo mode: replay recorded fixtures, zero API calls")
    p_run.add_argument("--out", default=None, help="override output directory")
    p_run.add_argument("--limit", type=int, default=None, help="only run the first N prompts")

    p_report = sub.add_parser("report", help="re-render the digest from stored runs (no API calls)")
    p_report.add_argument("--config", default="brand.yaml")
    p_report.add_argument("--out", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "init":
        import os
        if os.path.exists(args.path):
            print(f"refusing to overwrite existing {args.path} — delete it or choose another path")
            return 1
        from .config import TEMPLATE as _T
        with open(args.path, "w", encoding="utf-8") as fh:
            fh.write(_T)
        print(f"wrote starter config: {args.path}")
        print("next: edit brand name/competitors/prompts, then:")
        print("  python -m citation_monitor run --config brand.yaml --demo   # zero-key demo")
        print("  python -m citation_monitor run --config brand.yaml          # live (needs GROQ_API_KEY etc.)")
        return 0

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "run":
        summary = run_pipeline(cfg, demo=args.demo, out_dir=args.out, limit=args.limit)
        _print_summary(summary)
        return 0

    if args.cmd == "report":
        summary = report_pipeline(cfg, out_dir=args.out)
        _print_summary(summary)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
