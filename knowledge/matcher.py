"""Longest-match catalog resolution for imperfect user labels."""

from __future__ import annotations


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _lcs_length(a: str, b: str) -> int:
    if not a or not b:
        return 0
    # Keep the shorter string on the row axis for a smaller DP buffer.
    if len(a) < len(b):
        a, b = b, a
    previous = [0] * (len(b) + 1)
    for char_a in a:
        current = [0]
        for j, char_b in enumerate(b, start=1):
            if char_a == char_b:
                current.append(previous[j - 1] + 1)
            else:
                current.append(max(previous[j], current[-1]))
        previous = current
    return previous[-1]


def _longest_contiguous(a: str, b: str) -> int:
    if not a or not b:
        return 0
    if len(a) > len(b):
        a, b = b, a
    best = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a) + 1):
            chunk = a[i:j]
            if chunk in b and (j - i) > best:
                best = j - i
    return best


def score_match(query: str, candidate: str) -> tuple[int, int, float]:
    """Return (lcs_len, contiguous_len, ratio) for ranking."""
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return (0, 0, 0.0)
    if q == c:
        return (len(q), len(q), 1.0)
    lcs = _lcs_length(q, c)
    contig = _longest_contiguous(q, c)
    ratio = lcs / max(len(q), len(c))
    return (lcs, contig, ratio)


def longest_match(query: str, candidates: list[str], minimum_ratio: float = 0.55) -> str | None:
    """
    Choose the catalog label with the strongest longest-match score.

    Ranking key:
      1) longest common subsequence length
      2) longest contiguous substring length
      3) LCS / max(len(query), len(candidate))
    """
    text = query.strip()
    if not text or not candidates:
        return None

    normalized = _normalize(text)
    for candidate in candidates:
        if _normalize(candidate) == normalized:
            return candidate

    best: str | None = None
    best_key: tuple[int, int, float] = (-1, -1, -1.0)
    for candidate in candidates:
        key = score_match(text, candidate)
        if key[2] < minimum_ratio and key[0] < max(6, int(0.6 * len(normalized))):
            continue
        if key > best_key:
            best_key = key
            best = candidate
    return best


def resolve_catalog_key(query: str, catalog: dict) -> str | None:
    return longest_match(query, list(catalog.keys()))
