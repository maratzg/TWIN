import re


LETTER_VALUES = {
    letter: value
    for letter, value in zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38],
        strict=True,
    )
}


def iso6346_status(value: str | None) -> str:
    if not value or not re.fullmatch(r"[A-Z]{3}[UJZ]\d{7}", value):
        return "structurally_invalid"
    total = 0
    for position, character in enumerate(value[:10]):
        numeric = int(character) if character.isdigit() else LETTER_VALUES[character]
        total += numeric * (2**position)
    expected = (total % 11) % 10
    return "check_digit_valid" if expected == int(value[-1]) else "check_digit_invalid"
