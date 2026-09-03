import pandas as pd
import pytest

from evaluation.evaluator import compare_with_ground_truth
from evaluation.metrics import calculate_accuracy_metrics


def _truth(rows):
	return pd.DataFrame(rows)


def test_ground_truth_comparison_checks_status_and_bank_id():
	results = [
		{
			"payment_id": "PAY-1",
			"bank_transaction_id": "BANK-1",
			"decision": "AUTO_MATCH",
			"auto_matched": True,
		},
		{
			"payment_id": "PAY-2",
			"bank_transaction_id": None,
			"decision": "EXCEPTION",
			"auto_matched": False,
		},
	]
	truth = _truth(
		[
			{"payment_id": "PAY-1", "expected_status": "matched", "bank_transaction_ids": "BANK-1"},
			{"payment_id": "PAY-2", "expected_status": "missing_bank_transaction", "bank_transaction_ids": ""},
		]
	)

	evaluated = compare_with_ground_truth(results, truth)

	assert [row["is_correct"] for row in evaluated] == [True, True]
	assert evaluated[0]["ground_truth_bank_ids"] == ["BANK-1"]


def test_precision_counts_only_correct_predicted_matches():
	results = [
		{"decision": "AUTO_MATCH", "auto_matched": True, "is_correct": True},
		{"decision": "AUTO_MATCH", "auto_matched": True, "is_correct": False},
		{"decision": "HUMAN_REVIEW", "auto_matched": False, "is_correct": True},
	]

	assert calculate_accuracy_metrics(
		results + [
			{"ground_truth_status": "matched", "decision": "AUTO_MATCH", "auto_matched": True, "is_correct": True},
		]
	)["precision"] == 2 / 3


def test_recall_counts_correct_matches_over_actual_matches():
	results = [
		{"decision": "AUTO_MATCH", "auto_matched": True, "is_correct": True, "ground_truth_status": "matched"},
		{"decision": "HUMAN_REVIEW", "auto_matched": False, "is_correct": False, "ground_truth_status": "matched"},
		{"decision": "EXCEPTION", "auto_matched": False, "is_correct": True, "ground_truth_status": "missing_bank_transaction"},
	]

	assert calculate_accuracy_metrics(results)["recall"] == 0.5


def test_false_auto_match_rate_uses_incorrect_auto_matches():
	results = [
		{"decision": "AUTO_MATCH", "auto_matched": True, "is_correct": True},
		{"decision": "AUTO_MATCH", "auto_matched": True, "is_correct": False},
		{"decision": "HUMAN_REVIEW", "auto_matched": False, "is_correct": False},
	]

	assert calculate_accuracy_metrics(results)["false_auto_match_rate"] == 0.5


def test_duplicate_payment_output_is_rejected():
	results = [
		{"payment_id": "PAY-1", "decision": "EXCEPTION"},
		{"payment_id": "PAY-1", "decision": "HUMAN_REVIEW"},
	]
	truth = _truth([{"payment_id": "PAY-1", "expected_status": "missing_bank_transaction", "bank_transaction_ids": ""}])

	with pytest.raises(ValueError, match="duplicate payment IDs"):
		compare_with_ground_truth(results, truth)


def test_missing_ground_truth_is_rejected():
	results = [{"payment_id": "PAY-2", "decision": "EXCEPTION"}]
	truth = _truth([{"payment_id": "PAY-1", "expected_status": "matched", "bank_transaction_ids": "BANK-1"}])

	with pytest.raises(ValueError, match="Missing ground truth"):
		compare_with_ground_truth(results, truth)