from typing import Any


def calculate_basic_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate operational metrics from reconciliation results.

    Expected fields in each result:
    - decision
    - ai_assisted
    - matched_correctly (optional, used after ground-truth comparison)
    """

    total_records = len(results)

    if total_records == 0:
        return {
            "total_records": 0,
            "matched": 0,
            "ai_assisted": 0,
            "human_review": 0,
            "exceptions": 0,
            "match_rate": 0.0,
            "exception_rate": 0.0,
        }

    matched = sum(1 for result in results if result.get("decision") == "AUTO_MATCH")

    ai_assisted = sum(
        1
        for result in results
        if result.get("ai_assisted", False)
    )

    human_review = sum(
        1
        for result in results
        if result.get("decision") == "HUMAN_REVIEW"
    )

    exceptions = sum(
        1
        for result in results
        if result.get("decision") == "EXCEPTION"
    )

    match_rate = matched / total_records
    exception_rate = exceptions / total_records

    return {
        "total_records": total_records,
        "matched": matched,
        "ai_assisted": ai_assisted,
        "human_review": human_review,
        "exceptions": exceptions,
        "match_rate": match_rate,
        "exception_rate": exception_rate,
    }


def calculate_accuracy_metrics(
    results: list[dict[str, Any]],
) -> dict[str, float]:
    """
    Calculate precision, recall and false auto-match rate.

    These require each result to contain:
    - is_correct
    - decision
    - auto_matched
    - ground_truth_status
    """

    if not results:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "false_auto_match_rate": 0.0,
        }

    correct_matches = sum(
        1
        for result in results
        if result.get("auto_matched") is True
        and result.get("is_correct") is True
    )

    predicted_matches = sum(
        1
        for result in results
        if result.get("decision") == "AUTO_MATCH"
    )

    actual_matches = sum(
        1
        for result in results
        if str(result.get("ground_truth_status", "")).startswith("matched")
    )

    incorrect_auto_matches = sum(
        1
        for result in results
        if result.get("auto_matched") is True
        and result.get("is_correct") is False
    )

    auto_matches = sum(
        1
        for result in results
        if result.get("auto_matched") is True
    )

    precision = (
        correct_matches / predicted_matches
        if predicted_matches > 0
        else 0.0
    )

    recall = (
        correct_matches / actual_matches
        if actual_matches > 0
        else 0.0
    )

    false_auto_match_rate = (
        incorrect_auto_matches / auto_matches
        if auto_matches > 0
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "false_auto_match_rate": false_auto_match_rate,
    }


def calculate_all_metrics(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Calculate all reconciliation metrics.
    """

    basic = calculate_basic_metrics(results)
    accuracy = calculate_accuracy_metrics(results)

    return {
        **basic,
        **accuracy,
    }