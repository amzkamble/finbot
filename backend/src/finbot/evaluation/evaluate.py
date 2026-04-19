"""RAGAS evaluation runner for the RAG pipeline."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from finbot.evaluation.dataset import EvaluationDataset, RAGResult, TestCase
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EvaluationReport:
    """Full evaluation report with RAGAS + custom metrics."""

    timestamp: str = ""
    model: str = ""
    embedding_model: str = ""
    total_test_cases: int = 0
    ragas_metrics: dict[str, float] = field(default_factory=dict)
    per_collection_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    routing_metrics: dict[str, Any] = field(default_factory=dict)
    rbac_metrics: dict[str, Any] = field(default_factory=dict)
    performance_metrics: dict[str, float] = field(default_factory=dict)
    failure_cases: list[dict[str, Any]] = field(default_factory=list)


class RAGEvaluator:
    """
    Orchestrate RAGAS evaluation: run the pipeline over test cases,
    compute metrics, and generate reports.
    """

    def __init__(
        self,
        rag_chain: Any = None,
        query_router: Any = None,
        output_dir: str | Path = "evaluation/results",
    ) -> None:
        self._chain = rag_chain
        self._router = query_router
        self._output_dir = Path(output_dir).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def run_pipeline_on_test_set(
        self,
        test_cases: list[TestCase],
        role: str,
    ) -> list[RAGResult]:
        """Run the RAG pipeline on every test case and collect results."""
        results: list[RAGResult] = []

        for i, tc in enumerate(test_cases):
            logger.info("Evaluating case %d/%d: %s", i + 1, len(test_cases), tc.question[:60])
            start = time.time()

            try:
                # Route the query
                if self._router:
                    route_result = self._router.classify(tc.question, role)
                    route_name = route_result.route_name
                    collections = route_result.target_collections
                else:
                    route_name = "unknown"
                    collections = []

                # Run the RAG chain
                if self._chain:
                    rag_response = self._chain.run(
                        query=tc.question,
                        user_role=role,
                        target_collections=collections or None,
                    )
                    answer = rag_response.answer
                    contexts = rag_response.contexts
                else:
                    answer = ""
                    contexts = []

                elapsed = (time.time() - start) * 1000

                results.append(
                    RAGResult(
                        question=tc.question,
                        answer=answer,
                        contexts=contexts,
                        ground_truth=tc.ground_truth,
                        route_used=route_name,
                        collections_searched=collections,
                        latency_ms=elapsed,
                    )
                )

            except Exception as exc:
                logger.error("Pipeline failed for '%s': %s", tc.question[:40], exc)
                results.append(
                    RAGResult(
                        question=tc.question,
                        answer=f"ERROR: {exc}",
                        ground_truth=tc.ground_truth,
                        latency_ms=(time.time() - start) * 1000,
                    )
                )

        return results

    def evaluate(
        self,
        test_cases: list[TestCase],
        role: str = "executive",
    ) -> EvaluationReport:
        """
        Run full evaluation: pipeline → RAGAS metrics → custom metrics → report.
        """
        from datetime import datetime, timezone

        from finbot.config.settings import get_settings

        settings = get_settings()

        # 1. Run pipeline
        rag_results = self.run_pipeline_on_test_set(test_cases, role)

        # 2. Compute RAGAS metrics
        ragas_metrics = self._compute_ragas_metrics(test_cases, rag_results)

        # 3. Compute routing accuracy
        routing_metrics = self._compute_routing_metrics(test_cases, rag_results)

        # 4. Compute latency percentiles
        latencies = [r.latency_ms for r in rag_results if r.latency_ms > 0]
        performance = {}
        if latencies:
            latencies.sort()
            performance = {
                "latency_p50_ms": round(latencies[len(latencies) // 2], 0),
                "latency_p95_ms": round(latencies[int(len(latencies) * 0.95)], 0),
                "latency_p99_ms": round(latencies[int(len(latencies) * 0.99)], 0),
            }

        # 5. Collect failure cases
        failures = self._collect_failures(test_cases, rag_results, ragas_metrics)

        report = EvaluationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=settings.llm_model,
            embedding_model=settings.embedding_model,
            total_test_cases=len(test_cases),
            ragas_metrics=ragas_metrics,
            routing_metrics=routing_metrics,
            performance_metrics=performance,
            failure_cases=failures,
        )

        # Save report
        self._save_report(report)

        return report

    def evaluate_rbac_compliance(
        self,
        rbac_tests: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Run RBAC-specific tests to verify access control enforcement.
        """
        if not self._router:
            logger.warning("No router available for RBAC evaluation")
            return {"compliance_rate": 0.0, "error": "No router configured"}

        total = len(rbac_tests)
        passed = 0
        failures = []

        for test in rbac_tests:
            question = test["question"]
            role = test["role"]
            expected = test.get("expected_collections_searched", [])

            route_result = self._router.classify(question, role)
            actual = set(route_result.target_collections)
            expected_set = set(expected)

            if actual == expected_set or (not expected_set):
                passed += 1
            else:
                failures.append(
                    {
                        "question": question,
                        "role": role,
                        "expected": list(expected_set),
                        "actual": list(actual),
                    }
                )

        return {
            "compliance_rate": round(passed / total, 2) if total else 0.0,
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "failures": failures,
        }

    # ── Private helpers ─────────────────────────────────────────────────

    def _compute_ragas_metrics(
        self,
        test_cases: list[TestCase],
        rag_results: list[RAGResult],
    ) -> dict[str, float]:
        """Compute RAGAS metrics using the ragas library."""
        try:
            from ragas import evaluate
            from ragas.metrics import (
                answer_correctness,
                answer_relevancy,
                answer_similarity_metric,
                context_precision,
                context_recall,
                faithfulness,
            )

            dataset_manager = EvaluationDataset(test_dir="")
            dataset = dataset_manager.to_ragas_dataset(test_cases, rag_results)

            metrics = [
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall,
                answer_correctness,
            ]

            result = evaluate(dataset=dataset, metrics=metrics)

            return {k: round(v, 4) for k, v in result.items() if isinstance(v, (int, float))}

        except ImportError:
            logger.warning("RAGAS not installed — skipping RAGAS metrics")
            return {"note": "ragas library not available"}
        except Exception as exc:
            logger.error("RAGAS evaluation failed: %s", exc)
            return {"error": str(exc)}

    @staticmethod
    def _compute_routing_metrics(
        test_cases: list[TestCase],
        rag_results: list[RAGResult],
    ) -> dict[str, Any]:
        """Compare routed routes with expected routes."""
        correct = 0
        per_route: dict[str, dict[str, int]] = {}

        for tc, rr in zip(test_cases, rag_results):
            expected = tc.expected_route
            actual = rr.route_used

            if expected not in per_route:
                per_route[expected] = {"correct": 0, "total": 0}
            per_route[expected]["total"] += 1

            if actual == expected:
                correct += 1
                per_route[expected]["correct"] += 1

        total = len(test_cases)
        return {
            "overall_accuracy": round(correct / total, 2) if total else 0.0,
            "per_route_accuracy": {
                route: round(data["correct"] / data["total"], 2) if data["total"] else 0.0
                for route, data in per_route.items()
            },
        }

    @staticmethod
    def _collect_failures(
        test_cases: list[TestCase],
        rag_results: list[RAGResult],
        ragas_metrics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Identify test cases that performed poorly."""
        failures = []
        for tc, rr in zip(test_cases, rag_results):
            if rr.answer.startswith("ERROR:") or not rr.answer.strip():
                failures.append(
                    {
                        "question": tc.question,
                        "expected": tc.ground_truth[:200],
                        "actual": rr.answer[:200],
                        "failure_type": "pipeline_error",
                    }
                )
        return failures

    def _save_report(self, report: EvaluationReport) -> None:
        """Save the evaluation report as JSON."""
        output_path = self._output_dir / f"eval_report_{report.timestamp[:10]}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, default=str)
        logger.info("Evaluation report saved to %s", output_path)
