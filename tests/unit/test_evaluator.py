"""
Unit Tests: Evaluator and EvaluationThresholds
Tests threshold logic and data loading without requiring MLflow or agents.
"""

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from framework.evaluation.evaluator import EvaluationThresholds, EvaluationResult


class TestEvaluationThresholds:
    def test_default_thresholds(self):
        t = EvaluationThresholds()
        assert t.correctness == 0.8
        assert t.groundedness == 0.9
        assert t.relevance == 0.8
        assert t.safety == 1.0

    def test_strict_thresholds(self):
        t = EvaluationThresholds.strict()
        assert t.correctness >= 0.9
        assert t.groundedness >= 0.95

    def test_relaxed_thresholds(self):
        t = EvaluationThresholds.relaxed()
        assert t.correctness < 0.8

    def test_none_threshold_skips_check(self):
        t = EvaluationThresholds(correctness=None, groundedness=0.9, relevance=None, safety=None)
        result = EvaluationResult(
            run_id="abc123",
            agent_name="test",
            metrics={"groundedness": 0.95},
            thresholds=t,
        )
        assert result.passed()


class TestEvaluationResult:
    def make_result(self, metrics: dict, thresholds=None) -> EvaluationResult:
        return EvaluationResult(
            run_id="test-run-id",
            agent_name="test_agent",
            metrics=metrics,
            thresholds=thresholds or EvaluationThresholds(),
        )

    def test_passes_when_all_metrics_above_threshold(self):
        result = self.make_result({
            "correctness": 0.85,
            "groundedness": 0.92,
            "relevance": 0.88,
            "safety": 1.0,
        })
        assert result.passed()

    def test_fails_when_correctness_below_threshold(self):
        result = self.make_result({
            "correctness": 0.65,
            "groundedness": 0.92,
            "relevance": 0.88,
            "safety": 1.0,
        })
        assert not result.passed()

    def test_fails_when_safety_below_threshold(self):
        result = self.make_result({
            "correctness": 0.85,
            "groundedness": 0.92,
            "relevance": 0.88,
            "safety": 0.9,  # Below 1.0
        })
        assert not result.passed()

    def test_passes_with_prefixed_metric_names(self):
        # MLflow sometimes prefixes metrics
        result = self.make_result({
            "eval.correctness": 0.85,
            "eval.groundedness": 0.92,
            "eval.relevance": 0.88,
            "eval.safety": 1.0,
        })
        assert result.passed()

    def test_summary_contains_agent_name(self):
        result = self.make_result({"correctness": 0.85, "groundedness": 0.92, "relevance": 0.88, "safety": 1.0})
        summary = result.summary()
        assert "test_agent" in summary

    def test_summary_shows_passed_status(self):
        result = self.make_result({"correctness": 0.85, "groundedness": 0.92, "relevance": 0.88, "safety": 1.0})
        assert "PASSED" in result.summary()

    def test_summary_shows_failed_status(self):
        result = self.make_result({"correctness": 0.5})
        assert "FAILED" in result.summary()


class TestEvalDatasetLoading:
    def test_load_from_list(self):
        from framework.evaluation.dataset import load_eval_dataset
        data = [
            {"request": "What is X?", "expected_response": "X is Y."},
            {"request": "How does Z work?", "expected_response": "Z works by..."},
        ]
        df = load_eval_dataset(data)
        assert len(df) == 2
        assert "request" in df.columns

    def test_load_from_jsonl(self):
        from framework.evaluation.dataset import load_eval_dataset
        with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
            f.write('{"request": "test question", "expected_response": "test answer"}\n')
            f.write('{"request": "another question", "expected_response": "another answer"}\n')
            tmp_path = f.name

        df = load_eval_dataset(tmp_path)
        assert len(df) == 2
        assert df.iloc[0]["request"] == "test question"

    def test_load_from_dataframe(self):
        from framework.evaluation.dataset import load_eval_dataset
        input_df = pd.DataFrame([{"request": "q1"}, {"request": "q2"}])
        result_df = load_eval_dataset(input_df)
        assert len(result_df) == 2

    def test_missing_request_column_raises(self):
        from framework.evaluation.dataset import load_eval_dataset
        with pytest.raises(ValueError, match="required columns"):
            load_eval_dataset([{"answer": "no request column"}])

    def test_empty_dataset_raises(self):
        from framework.evaluation.dataset import load_eval_dataset
        with pytest.raises(ValueError, match="empty"):
            with tempfile.NamedTemporaryFile(suffix=".jsonl", mode="w", delete=False) as f:
                tmp_path = f.name
            load_eval_dataset(tmp_path)

    def test_sample_returns_n_rows(self):
        from framework.evaluation.dataset import sample_eval_dataset
        df = pd.DataFrame([{"request": f"q{i}"} for i in range(100)])
        sampled = sample_eval_dataset(df, n=10)
        assert len(sampled) == 10

    def test_sample_returns_all_when_smaller_than_n(self):
        from framework.evaluation.dataset import sample_eval_dataset
        df = pd.DataFrame([{"request": "q1"}, {"request": "q2"}])
        sampled = sample_eval_dataset(df, n=20)
        assert len(sampled) == 2
