"""Test dataset management for RAGAS evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from finbot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TestCase:
    """A single evaluation test case."""

    question: str
    ground_truth: str
    expected_collection: str = "general"
    expected_route: str = "cross_department_route"
    test_roles: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResult:
    """Result of running the RAG pipeline on one test case."""

    question: str
    answer: str
    contexts: list[str] = field(default_factory=list)
    ground_truth: str = ""
    route_used: str = ""
    collections_searched: list[str] = field(default_factory=list)
    guardrail_flags: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


class EvaluationDataset:
    """Load and manage test datasets for RAGAS evaluation."""

    def __init__(self, test_dir: str | Path) -> None:
        self._test_dir = Path(test_dir).resolve()

    def load_test_set(self, collection: str | None = None) -> list[TestCase]:
        """
        Load test cases from JSON files.

        Parameters
        ----------
        collection : str, optional
            If provided, load only this collection's test set.
            If None, load all available test sets.
        """
        if not self._test_dir.exists():
            logger.warning("Test directory does not exist: %s", self._test_dir)
            return []

        test_cases: list[TestCase] = []

        if collection:
            file_path = self._test_dir / f"{collection}_test_set.json"
            if file_path.exists():
                test_cases.extend(self._load_file(file_path))
            else:
                logger.warning("Test set not found: %s", file_path)
        else:
            for file_path in sorted(self._test_dir.glob("*_test_set.json")):
                test_cases.extend(self._load_file(file_path))

        logger.info("Loaded %d test cases", len(test_cases))
        return test_cases

    def load_rbac_matrix(self) -> list[dict[str, Any]]:
        """Load the RBAC compliance test matrix."""
        matrix_path = self._test_dir.parent / "rbac_test_matrix.json"
        if not matrix_path.exists():
            logger.warning("RBAC test matrix not found: %s", matrix_path)
            return []

        with open(matrix_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("rbac_tests", [])

    def to_ragas_dataset(self, test_cases: list[TestCase], rag_results: list[RAGResult]) -> Any:
        """
        Convert test cases + RAG results into a RAGAS-compatible HuggingFace Dataset.

        Required columns: question, answer, contexts, ground_truth.
        """
        from datasets import Dataset

        rows = []
        for tc, rr in zip(test_cases, rag_results):
            rows.append(
                {
                    "question": tc.question,
                    "answer": rr.answer,
                    "contexts": rr.contexts,
                    "ground_truth": tc.ground_truth,
                }
            )

        return Dataset.from_list(rows)

    @staticmethod
    def _load_file(path: Path) -> list[TestCase]:
        """Deserialise a single test-set JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        cases = data if isinstance(data, list) else data.get("test_cases", [])
        return [
            TestCase(
                question=item["question"],
                ground_truth=item["ground_truth"],
                expected_collection=item.get("expected_collection", "general"),
                expected_route=item.get("expected_route", "cross_department_route"),
                test_roles=item.get("test_roles", {}),
                metadata=item.get("metadata", {}),
            )
            for item in cases
        ]

    @staticmethod
    def create_test_set_template(collection: str, output_path: Path) -> None:
        """Generate a template JSON file for quickly creating test cases."""
        template = {
            "test_cases": [
                {
                    "question": "Example question about " + collection,
                    "ground_truth": "Expected answer based on the source document.",
                    "expected_collection": collection,
                    "expected_route": f"{collection}_route",
                    "test_roles": {
                        "executive": "should_answer",
                        "employee": "should_deny_or_fallback",
                    },
                    "metadata": {
                        "difficulty": "easy",
                        "requires_table": False,
                        "multi_hop": False,
                    },
                }
            ]
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)
        logger.info("Template created at %s", output_path)
