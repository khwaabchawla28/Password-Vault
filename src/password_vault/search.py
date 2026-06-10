"""
search.py

Fuzzy entry lookup — find entries even when the user doesn't type
the exact name.

Matching strategy (in order):
  1. Exact match       — "github" matches "github"
  2. Prefix match      — "git" matches "github" and "gitlab"
  3. Substring match   — "hub" matches "github"
  4. Fuzzy match       — "ghb" matches "github" (subsequence)

Returns all matches so the caller can disambiguate.
"""

from dataclasses import dataclass


@dataclass
class SearchResult:
    """Result of a fuzzy search."""

    name: str
    match_type: str  # "exact", "prefix", "substring", "fuzzy"


def fuzzy_search(query: str, entries: list[str]) -> list[SearchResult]:
    """Search entries with fuzzy matching.

    Parameters
    ----------
    query : str
        The search term typed by the user.
    entries : list[str]
        Available entry names in the vault.

    Returns
    -------
    list[SearchResult]
        Matches sorted by relevance (exact first, then prefix,
        substring, fuzzy). Empty list if no matches.
    """
    if not query or not entries:
        return []

    query_lower = query.lower()
    results: list[SearchResult] = []

    # Pass 1: exact match
    for name in entries:
        if name.lower() == query_lower:
            results.append(SearchResult(name=name, match_type="exact"))

    if results:
        return results

    # Pass 2: prefix match
    for name in entries:
        if name.lower().startswith(query_lower):
            results.append(SearchResult(name=name, match_type="prefix"))

    if results:
        return results

    # Pass 3: substring match
    for name in entries:
        if query_lower in name.lower():
            results.append(SearchResult(name=name, match_type="substring"))

    if results:
        return results

    # Pass 4: fuzzy (subsequence) match
    for name in entries:
        if _is_subsequence(query_lower, name.lower()):
            results.append(SearchResult(name=name, match_type="fuzzy"))

    return results


def _is_subsequence(query: str, target: str) -> bool:
    """Check if query is a subsequence of target.

    "ghb" is a subsequence of "github" because g...h...b
    appears in order (characters don't need to be adjacent).
    """
    qi = 0
    for ch in target:
        if qi < len(query) and ch == query[qi]:
            qi += 1
    return qi == len(query)
