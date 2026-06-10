"""
generator.py

Cryptographically secure password generation.

Uses the `secrets` module (not `random`) because:
  - random is fast and predictable — fine for games, terrible for passwords
  - secrets pulls from the OS cryptographic source — unpredictable by design

The generator guarantees at least one character from each enabled pool,
then fills the remaining length from the combined pool, and shuffles
everything with a Fisher-Yates shuffle using secrets.randbelow().
"""

import secrets

from password_vault.constants import (
    DEFAULT_GENERATED_PASSWORD_LENGTH,
    DIGITS,
    LOWERCASE_LETTERS,
    MINIMUM_GENERATED_PASSWORD_LENGTH,
    SAFE_SYMBOLS,
    UPPERCASE_LETTERS,
)


class PasswordTooShortError(ValueError):
    """Raised when the requested password length is below the safe minimum."""


def generate_password(
    length: int = DEFAULT_GENERATED_PASSWORD_LENGTH,
    *,
    use_lowercase: bool = True,
    use_uppercase: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
) -> str:
    """Generate a cryptographically secure random password.

    Guarantees at least one character from each enabled pool. Without
    this, a 12-char password might randomly end up all lowercase,
    failing most "must contain a digit" rules.

    Parameters
    ----------
    length : int
        Password length. Must be >= MINIMUM_GENERATED_PASSWORD_LENGTH
        and >= the number of enabled pools.
    use_lowercase, use_uppercase, use_digits, use_symbols : bool
        Which character pools to include. At least one must be True.

    Returns
    -------
    str
        A random password of exactly `length` characters.

    Raises
    ------
    PasswordTooShortError
        If length is too short.
    ValueError
        If every pool flag is False.
    """
    if length < MINIMUM_GENERATED_PASSWORD_LENGTH:
        raise PasswordTooShortError(
            f"Password length must be >= "
            f"{MINIMUM_GENERATED_PASSWORD_LENGTH}, got {length}"
        )

    # Build enabled pools
    pools: list[str] = []
    if use_lowercase:
        pools.append(LOWERCASE_LETTERS)
    if use_uppercase:
        pools.append(UPPERCASE_LETTERS)
    if use_digits:
        pools.append(DIGITS)
    if use_symbols:
        pools.append(SAFE_SYMBOLS)

    if not pools:
        raise ValueError("At least one character pool must be enabled.")

    if length < len(pools):
        raise PasswordTooShortError(
            f"Password length {length} is too short to include at least "
            f"one character from each of the {len(pools)} enabled pools."
        )

    # Combined pool for filling remaining characters
    combined = "".join(pools)

    # Start with one guaranteed character from each pool
    chars: list[str] = [secrets.choice(pool) for pool in pools]

    # Fill the rest from the combined pool
    for _ in range(length - len(chars)):
        chars.append(secrets.choice(combined))

    # Fisher-Yates shuffle with cryptographic randomness
    # Without this, the first len(pools) characters would always be
    # one from each pool in order — predictable.
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]

    return "".join(chars)
