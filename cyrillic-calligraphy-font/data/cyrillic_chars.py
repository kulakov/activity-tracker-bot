"""
Cyrillic character sets for font generation.

Defines the complete set of Cyrillic characters to generate,
organized by category for systematic processing.
"""

# Russian uppercase letters (А-Я)
CYRILLIC_UPPER = list("АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")

# Russian lowercase letters (а-я)
CYRILLIC_LOWER = list("абвгдежзийклмнопрстуфхцчшщъыьэюя")

# Digits
DIGITS = list("0123456789")

# Basic punctuation needed for a functional font
PUNCTUATION = list(".,;:!?-–—()«»\"'…")

# Special characters
SPECIAL = list("Ёё")

# Combined full character set
ALL_CHARS = CYRILLIC_UPPER + CYRILLIC_LOWER + SPECIAL + DIGITS + PUNCTUATION

# Character groups for batch processing
CHAR_GROUPS = {
    "upper": CYRILLIC_UPPER + list("ЁЪ"),
    "lower": CYRILLIC_LOWER + list("ёъ"),
    "digits": DIGITS,
    "punctuation": PUNCTUATION,
}

# Unicode code points for reference
UNICODE_RANGES = {
    "cyrillic_basic": (0x0400, 0x04FF),
    "cyrillic_supplement": (0x0500, 0x052F),
}


def get_char_hex(char: str) -> str:
    """Get Unicode hex representation of a character."""
    return f"U+{ord(char):04X}"


def get_all_chars_with_codes() -> list[tuple[str, str]]:
    """Return all characters with their Unicode codes."""
    return [(c, get_char_hex(c)) for c in ALL_CHARS]


if __name__ == "__main__":
    print(f"Total characters to generate: {len(ALL_CHARS)}")
    print()
    for group_name, chars in CHAR_GROUPS.items():
        print(f"{group_name} ({len(chars)}): {''.join(chars)}")
    print()
    print("Full set:")
    for char, code in get_all_chars_with_codes():
        print(f"  {char} -> {code}")
