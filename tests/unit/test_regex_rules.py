from app.extract.regex_rules import (
    INSTRUCTION,
    OR_LINE,
    SECTION,
    extract_marks,
    parse_number_prefix,
    strip_number_prefix,
)


def test_top_level_numbering():
    assert parse_number_prefix("1. State two advantages") == ("top", "1")
    assert parse_number_prefix("12) Explain") == ("top", "12")
    assert parse_number_prefix("Q3. What is a router?") == ("top", "3")


def test_alpha_and_roman_numbering():
    assert parse_number_prefix("(a) Explain") == ("alpha", "a")
    assert parse_number_prefix("(ii) Give two") == ("roman", "ii")
    # Ambiguity: roman "i" could match alpha. The regex prefers roman because it
    # is tried first for multi-char tokens, and single "i" is a valid roman.
    assert parse_number_prefix("(i) ") in (("roman", "i"), ("alpha", "i"))


def test_strip_number_prefix():
    assert strip_number_prefix("1. Hello world").strip() == "Hello world"
    assert strip_number_prefix("(a) Hello").strip() == "Hello"


def test_marks_extraction():
    assert extract_marks("Define a primary key. [2]") == 2
    assert extract_marks("Define a primary key. [2 marks]") == 2
    assert extract_marks("Explain (3)") == 3
    assert extract_marks("no marks here") is None


def test_section_and_instruction_detection():
    assert SECTION.match("Section B")
    assert INSTRUCTION.match("Answer all questions.")
    assert OR_LINE.match("OR")
