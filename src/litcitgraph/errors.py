class NoFuzzyMatchError(Exception):
    """Raised when no fuzzy match is found for a given string."""


class TooManyFuzzyMatchesError(Exception):
    """Raised when too many fuzzy matches are found for a given string."""
