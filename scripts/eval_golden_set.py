"""Golden-set eval for filter-extraction quality (US-011).

Runs each query in the golden set (src/car_search/data/golden_set.json)
through the real extraction step (agent.py::extract_filters -- this hits
the live Anthropic API, so ANTHROPIC_API_KEY must be set) and reports
per-field precision/recall against the expected SearchFilters values, plus
whether the contradiction- and clarify-triggering examples behaved as
expected.

Usage:
    uv run python scripts/eval_golden_set.py [--strict]

--strict: exit non-zero if the overall F1 score is below a minimum
threshold (0.7) or any contradiction/clarify check fails -- useful in CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from car_search.agent import extract_filters, needs_clarification
from car_search.guardrails import detect_contradiction
from car_search.models import SearchFilters

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET_PATH = REPO_ROOT / "src" / "car_search" / "data" / "golden_set.json"

SCORED_FIELDS = (
    "make",
    "model",
    "body_type",
    "price_max",
    "mileage_max",
    "year_min",
    "fuel_type",
    "location",
    "radius_mi",
)

STRICT_MIN_F1 = 0.7


def _field_value(filters: SearchFilters, field: str) -> Any:
    value = getattr(filters, field)
    return value.value if hasattr(value, "value") else value


def _values_match(field: str, extracted: Any, expected: Any) -> bool:
    if field == "location":
        if expected is None:
            return extracted is None
        if extracted is None:
            return False
        e, x = expected.strip().lower(), str(extracted).strip().lower()
        return e in x or x in e
    return bool(extracted == expected)


def score_example(filters: SearchFilters, expected: dict[str, Any], tallies: dict[str, dict[str, int]]) -> None:
    for field, expected_value in expected.items():
        if field not in SCORED_FIELDS:
            continue
        extracted_value = _field_value(filters, field)
        is_match = _values_match(field, extracted_value, expected_value)
        counts = tallies.setdefault(field, {"tp": 0, "fp": 0, "fn": 0})
        if expected_value is None:
            # We expect this field to be left null; extracting something is
            # a false positive (with no corresponding false negative).
            if extracted_value is not None:
                counts["fp"] += 1
        elif is_match:
            counts["tp"] += 1
        else:
            counts["fp"] += 1
            counts["fn"] += 1


def precision_recall(counts: dict[str, int]) -> tuple[float, float, float]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    golden_set = json.loads(GOLDEN_SET_PATH.read_text())

    tallies: dict[str, dict[str, int]] = {}
    behavior_checks: list[tuple[str, bool]] = []

    for example in golden_set:
        query = example["query"]
        expected = example.get("expected", {})
        filters = extract_filters(query)
        score_example(filters, expected, tallies)

        if example.get("expect_contradiction"):
            note = detect_contradiction(query)
            behavior_checks.append((f"contradiction detected: {query!r}", note is not None))

        if example.get("expect_clarify"):
            behavior_checks.append((f"clarify triggered: {query!r}", needs_clarification(filters)))

    print(f"{'field':<12} {'precision':>10} {'recall':>10} {'f1':>10} {'support':>8}")
    f1_scores = []
    for field in SCORED_FIELDS:
        counts = tallies.get(field, {"tp": 0, "fp": 0, "fn": 0})
        support = counts["tp"] + counts["fn"]
        if support == 0 and counts["fp"] == 0:
            continue
        precision, recall, f1 = precision_recall(counts)
        f1_scores.append(f1)
        print(f"{field:<12} {precision:>10.2f} {recall:>10.2f} {f1:>10.2f} {support:>8}")

    overall_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    print(f"\nOverall (macro-avg F1): {overall_f1:.2f}")

    print("\nBehavior checks:")
    all_behavior_ok = True
    for description, passed in behavior_checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_behavior_ok = False
        print(f"  [{status}] {description}")

    if args.strict and (overall_f1 < STRICT_MIN_F1 or not all_behavior_ok):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
