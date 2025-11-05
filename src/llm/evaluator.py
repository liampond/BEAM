
"""
Evaluation utilities for comparing LLM responses to expected answers.

Includes normalization and a few simple strategies: exact match, fuzzy text
matching, regex match, and numeric tolerance. Designed to be small and
expandable.
"""
import re
import string
from difflib import SequenceMatcher
from typing import Tuple



def normalize_answer(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, remove punctuation, collapse whitespace."""
    if text is None:
        return ""
    text = text.strip().lower()

    # Replace exact abbreviations using word-boundary regex 
    text = re.sub(r"\bmaj\.?\b", "major", text)
    text = re.sub(r"\bmin\.?\b", "minor", text)

    # Remove punctuation except slash and # (keeps time signatures and accidentals)
    keep = "/#"
    text = ''.join(ch for ch in text if ch.isalnum() or ch.isspace() or ch in keep)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def exact_match(expected: str, response: str) -> Tuple[bool, float]:
    e = normalize_answer(expected)
    r = normalize_answer(response)
    return (e == r, 1.0 if e == r else 0.0)


def fuzzy_match(expected: str, response: str, threshold: float = 0.85) -> Tuple[bool, float]:
    e = normalize_answer(expected)
    r = normalize_answer(response)
    if not e or not r:
        return (False, 0.0)
    ratio = SequenceMatcher(None, e, r).ratio()
    return (ratio >= threshold, ratio, {"expected_norm": e, "response_norm": r, "ratio": ratio})


def regex_match(pattern: str, response: str) -> Tuple[bool, float]:
    try:
        prog = re.compile(pattern, re.IGNORECASE)
    except re.error:
        # If pattern isn't a valid regex, fall back to equality
        return exact_match(pattern, response)

    r_norm = normalize_answer(response)
    m = prog.search(r_norm)
    return (m is not None, 1.0 if m else 0.0, {"pattern": pattern})


def numeric_tolerance(expected: str, response: str, tol: float = 1e-6) -> Tuple[bool, float]:
    num_re = re.compile(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?")
    me = num_re.search(expected)
    mr = num_re.search(response)
    if not me or not mr:
        return (False, 0.0)
    try:
        ne = float(me.group(0))
        nr = float(mr.group(0))
    except Exception:
        return (False, 0.0)
    ok = abs(ne - nr) <= tol
    score = 1.0 if ok else max(0.0, 1.0 - abs(ne - nr) / max(abs(ne), 1.0))
    return (ok, score)


def evaluate_response(expected: str, response: str, question_type: str = "general", strategy: str = None) -> Tuple[bool, float]:
    """Return (is_correct, score).

    The strategy param can force a particular method: 'exact', 'fuzzy', 'regex', 'numeric'.
    Otherwise a simple mapping from question_type is used.
    """
    if strategy == "exact":
        return exact_match(expected, response)
    if strategy == "regex":
        res = regex_match(expected, response)
        if isinstance(res, tuple) and len(res) >= 2:
            return res[0], float(res[1])
        return (False, 0.0)
    if strategy == "numeric":
        return numeric_tolerance(expected, response)

    # Default mapping
    if question_type in ("notation", "key", "time"):
        return exact_match(expected, response)
    if question_type == "numeric":
        return numeric_tolerance(expected, response)
    # Fallback to fuzzy. fuzzy_match may return (bool, score, details)
    res = fuzzy_match(expected, response)
    if isinstance(res, tuple) and len(res) >= 2:
        return res[0], float(res[1])
    return (False, 0.0)
