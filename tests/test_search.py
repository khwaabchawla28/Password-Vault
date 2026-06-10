"""Tests for the fuzzy search module."""

import pytest

from password_vault.search import SearchResult, fuzzy_search


class TestFuzzySearch:
    def test_exact_match(self):
        results = fuzzy_search("github", ["github", "gitlab", "bitbucket"])
        assert len(results) == 1
        assert results[0].name == "github"
        assert results[0].match_type == "exact"

    def test_exact_match_case_insensitive(self):
        results = fuzzy_search("GitHub", ["github", "gitlab"])
        assert len(results) == 1
        assert results[0].name == "github"
        assert results[0].match_type == "exact"

    def test_prefix_match(self):
        results = fuzzy_search("git", ["github", "gitlab", "bitbucket"])
        assert len(results) == 2
        assert all(r.match_type == "prefix" for r in results)
        names = [r.name for r in results]
        assert "github" in names
        assert "gitlab" in names

    def test_substring_match(self):
        results = fuzzy_search("hub", ["github", "gitlab", "bitbucket"])
        assert len(results) == 1
        assert results[0].name == "github"
        assert results[0].match_type == "substring"

    def test_fuzzy_subsequence_match(self):
        results = fuzzy_search("ghb", ["github", "gitlab", "bitbucket"])
        assert len(results) >= 1
        assert results[0].name == "github"
        assert results[0].match_type == "fuzzy"

    def test_no_match(self):
        results = fuzzy_search("xyz", ["github", "gitlab"])
        assert len(results) == 0

    def test_empty_query(self):
        results = fuzzy_search("", ["github"])
        assert len(results) == 0

    def test_empty_entries(self):
        results = fuzzy_search("github", [])
        assert len(results) == 0

    def test_exact_takes_priority(self):
        """Exact match should return before prefix/substring."""
        results = fuzzy_search("git", ["git", "github", "gitlab"])
        assert results[0].name == "git"
        assert results[0].match_type == "exact"

    def test_prefix_before_substring(self):
        """Prefix matches should return before substring matches."""
        results = fuzzy_search("git", ["github", "digit", "legit"])
        # "github" is prefix, "digit" and "legit" contain "git" as substring
        prefix_matches = [r for r in results if r.match_type == "prefix"]
        substring_matches = [r for r in results if r.match_type == "substring"]
        assert len(prefix_matches) > 0
        # Prefix results come first
        first_prefix_idx = next(i for i, r in enumerate(results) if r.match_type == "prefix")
        first_sub_idx = next((i for i, r in enumerate(results) if r.match_type == "substring"), len(results))
        assert first_prefix_idx < first_sub_idx
