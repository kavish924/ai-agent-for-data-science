"""Run the M8 evaluation (Spec 10 NFR-09..12).

Usage (from backend/):
    python -m eval.run                 # offline: deterministic RuleBasedLLM, no key needed
    python -m eval.run --live          # real Gemini (GEMINI_API_KEY in the repo-root .env)
    python -m eval.run --only titanic.csv --perf-rows 0
    python -m eval.run --live --cache eval/cache --min-interval 6   # record/replay (NFR-13)
    python -m eval.run --live --cache eval/cache --replay-only      # rerun with zero API calls
    python -m eval.run --golden eval/benchmark/build/golden.json --perf-rows 0   # benchmark (NFR-17)

Writes eval/results/<offline|live>.json and .md. Storage is a temporary directory, so
the eval never touches the app's real sessions.
"""

from __future__ import annotations

import argparse
import platform
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.llm.fake import RuleBasedLLM

from . import harness, metrics


def resolve_data_dir(golden_path: Path, data_dir: Path | None) -> Path:
    """NFR-17: CSVs live in --data-dir, else next to the golden file (samples/ for the built-in one)."""
    if data_dir is not None:
        return data_dir
    if golden_path.resolve() == (harness.EVAL_DIR / "golden.json").resolve():
        return harness.SAMPLES
    return golden_path.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="use real Gemini instead of the offline fake")
    parser.add_argument("--only", action="append", help="dataset file name (repeatable)")
    parser.add_argument("--perf-rows", type=int, default=settings.max_rows,
                        help=f"rows for the performance fixture (default {settings.max_rows}; 0 skips)")
    parser.add_argument("--no-replay", action="store_true", help="skip the reproducibility replay")
    parser.add_argument("--out", type=Path,
                        help="results folder (default eval/results, or <golden folder>/results)")
    parser.add_argument("--golden", type=Path, default=harness.EVAL_DIR / "golden.json",
                        help="golden file to score (default: the samples' eval/golden.json)")
    parser.add_argument("--data-dir", type=Path, help="folder of the golden file's CSVs")
    parser.add_argument("--cache", type=Path, help="record/replay LLM answers in this directory (NFR-13)")
    parser.add_argument("--run-tag", default="", help="part of the cache key, to keep repeated runs distinct")
    parser.add_argument("--replay-only", action="store_true", help="with --cache: a miss fails, no API call")
    parser.add_argument("--min-interval", type=float, default=0.0,
                        help="with --cache: seconds between provider calls (free-tier pacing)")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.live and not settings.gemini_api_key:
        print("--live needs GEMINI_API_KEY (in the repo-root .env)")
        return 2

    golden = harness.load_golden(args.golden)
    data_dir = resolve_data_dir(args.golden, args.data_dir)
    if args.out is None:  # never overwrite the committed sample results with a benchmark run
        args.out = (harness.EVAL_DIR / "results" if data_dir == harness.SAMPLES
                    else args.golden.parent / "results")
    names = args.only or list(golden)
    unknown = [n for n in names if n not in golden]
    if unknown:
        print(f"no golden entry for {unknown}; known: {list(golden)}")
        return 2

    provider = "live" if args.live else "offline"
    # ignore_cleanup_errors: the rotating log handler keeps app.log open on Windows
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings.storage_root = Path(tmp) / "storage"
        settings.db_path = settings.storage_root / "app.db"
        settings.llm_provider = "gemini" if args.live else "offline"
        from app.main import create_app
        from app.routers.plans import get_llm

        app = create_app()
        llm = RuleBasedLLM() if not args.live else get_llm()
        cached = None
        if args.cache and llm is not None:
            from .llm_cache import CachingLLM

            llm = cached = CachingLLM(llm, args.cache, run_tag=args.run_tag,
                                      replay_only=args.replay_only, min_interval_s=args.min_interval)
        app.dependency_overrides[get_llm] = lambda: llm
        with TestClient(app) as client:
            datasets = []
            for name in names:
                print(f"[..] {name}", flush=True)
                result = harness.run_dataset(client, name, golden[name], replay=not args.no_replay,
                                             data_dir=data_dir)
                datasets.append(result)
                sc = result.get("score") or {}
                mark = "ok" if result["status"] == "ok" else "FAIL"
                print(f"[{mark}] {name}: sensible={sc.get('sensible')} "
                      f"approved={sc.get('approved')}/{sc.get('proposed')} "
                      f"total={result['timings_ms']['total']} ms", flush=True)
            perf = harness.perf_baseline(client, args.perf_rows) if args.perf_rows else None

    report = {
        "provider": provider,
        "model": settings.gemini_model if args.live else RuleBasedLLM.model,
        "summary": metrics.summarize(datasets),
        "datasets": datasets,
        "perf": perf,
        "llm_cache": cached.stats() if cached else None,
        "run_tag": args.run_tag or None,
        "golden": str(args.golden),
        "environment": f"Python {platform.python_version()} on {platform.system()} {platform.release()}",
    }
    json_path, md_path = harness.write_results(report, args.out)
    print(harness.to_markdown(report))
    print(f"wrote {json_path} and {md_path}")
    ok = all(d["status"] == "ok" for d in datasets)
    repro = all(r[k] is not False for d in datasets if (r := d.get("reproducibility"))
                for k in ("cleaned_csv", "charts", "model_scores", "report_rerender", "report_cross_session"))
    return 0 if ok and repro else 1


if __name__ == "__main__":
    sys.exit(main())
