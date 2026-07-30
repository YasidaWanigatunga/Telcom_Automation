"""Command-line adapter around the decision engine.

This module is deliberately thin: it parses arguments, reads input,
calls the engine, and writes JSON. All decision logic lives in
`engine.py` and `checks/`, so swapping this for an HTTP handler
requires no change to the core.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

from .config import ConfigError, load_rules
from .engine import DecisionEngine
from .models import Decision, DecisionResult, SiteData

DEFAULT_RULES = Path("config/rules.yaml")

# Exit codes let this compose in a shell pipeline or a CI job.
EXIT_CODES: dict[Decision, int] = {
    Decision.APPROVED: 0,
    Decision.NEEDS_REVIEW: 1,
    Decision.REJECTED: 2,
}
EXIT_USAGE_ERROR = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capacity-engine",
        description="Decide whether a mobile site qualifies for a capacity upgrade.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Path to a site JSON file (an object or an array of objects). "
             "Use '-' or omit to read from stdin.",
    )
    parser.add_argument(
        "-r", "--rules",
        type=Path,
        default=DEFAULT_RULES,
        help=f"Path to the operator rules file (default: {DEFAULT_RULES})",
    )
    parser.add_argument(
        "-c", "--compact",
        action="store_true",
        help="Emit single-line JSON instead of indented output.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Log check-level detail to stderr.",
    )
    return parser


def _read_payload(source: str) -> Any:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text("utf-8")
    return json.loads(raw)


def _worst(results: Sequence[DecisionResult]) -> Decision:
    """For a batch, the exit code reflects the least favourable outcome."""
    order = [Decision.APPROVED, Decision.NEEDS_REVIEW, Decision.REJECTED]
    return max((r.decision for r in results), key=order.index, default=Decision.APPROVED)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # Configuration and input errors are the operator's problem, so they
    # get a clean message on stderr rather than a traceback.
    try:
        rules = load_rules(args.rules)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        payload = _read_payload(args.input)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not read input: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    records = payload if isinstance(payload, list) else [payload]

    try:
        sites = [SiteData(**record) for record in records]
    except Exception as exc:  # pydantic ValidationError
        print(f"error: invalid site payload: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    engine = DecisionEngine(rules)
    results = [engine.evaluate(site) for site in sites]

    output: Any = (
        [r.model_dump(mode="json") for r in results]
        if isinstance(payload, list)
        else results[0].model_dump(mode="json")
    )
    print(json.dumps(output, indent=None if args.compact else 2))

    return EXIT_CODES[_worst(results)]


if __name__ == "__main__":
    raise SystemExit(main())