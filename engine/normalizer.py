"""Canonical normalization helpers for financial reconciliation inputs."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Any

import pandas as pd


_WHITESPACE = re.compile(r"\s+")
_NON_ALPHANUMERIC = re.compile(r"[^\w]+", re.UNICODE)
_NON_IDENTIFIER = re.compile(r"[^0-9A-Z]+")
_CURRENCY_SYMBOLS = re.compile(r"[^0-9.\-+(), ]+")
_CENT = Decimal("0.01")


def _is_null(value: Any) -> bool:
	"""Return whether *value* is a scalar null value, including pandas nulls."""
	if value is None:
		return True
	if isinstance(value, (list, tuple, dict, set)):
		return False
	try:
		result = pd.isna(value)
	except (TypeError, ValueError):
		return False
	return isinstance(result, bool) and result


def _normalized_text(value: Any) -> str | None:
	"""Convert a non-null value to case-folded, Unicode-normalized text."""
	if _is_null(value):
		return None
	text = unicodedata.normalize("NFKC", str(value)).casefold().strip()
	return _WHITESPACE.sub(" ", text) or None


def normalize_transaction_reference(value: Any) -> str | None:
	"""Normalize a transaction reference into a compact alphanumeric key.

	Null-like values and empty strings return ``None``. Separators such as
	spaces, slashes, and hyphens are removed, while letters and digits are
	preserved in a case-insensitive form.
	"""
	text = _normalized_text(value)
	if text is None:
		return None
	return _NON_IDENTIFIER.sub("", text.upper()) or None


def normalize_merchant_name(value: Any) -> str | None:
	"""Normalize a merchant name for consistent comparison and fuzzy matching."""
	text = _normalized_text(value)
	if text is None:
		return None
	text = _NON_ALPHANUMERIC.sub(" ", text)
	return _WHITESPACE.sub(" ", text).strip() or None


def normalize_invoice_id(value: Any) -> str | None:
	"""Normalize an invoice identifier by removing formatting separators."""
	text = _normalized_text(value)
	if text is None:
		return None
	return _NON_IDENTIFIER.sub("", text.upper()) or None


def normalize_date(value: Any) -> date | None:
	"""Convert a date-like value to a calendar date, returning ``None`` if invalid."""
	if _is_null(value):
		return None
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	try:
		parsed = pd.to_datetime(value, errors="coerce")
	except (TypeError, ValueError, OverflowError):
		return None
	if pd.isna(parsed):
		return None
	return parsed.date()


def normalize_monetary_value(value: Any) -> Decimal | None:
	"""Convert a monetary value to a two-decimal ``Decimal``.

	Currency symbols and thousands separators are accepted. Parenthesized
	values are interpreted as negative amounts; invalid or null values return
	``None``.
	"""
	if _is_null(value):
		return None
	if isinstance(value, bool):
		return None
	if isinstance(value, Decimal):
		amount = value
	else:
		text = str(value).strip()
		if not text:
			return None
		negative = text.startswith("(") and text.endswith(")")
		text = _CURRENCY_SYMBOLS.sub("", text).replace(",", "").strip("() ")
		if not text:
			return None
		try:
			amount = Decimal(text)
		except InvalidOperation:
			return None
		if negative:
			amount = -amount
	if not amount.is_finite():
		return None
	return amount.quantize(_CENT, rounding=ROUND_HALF_EVEN)
