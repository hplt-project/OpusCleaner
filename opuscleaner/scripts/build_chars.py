"""
Extract exemplar characters from CLDR XML files. Used to populate the regexs:
opuscleaner/filters/clean_common.py

This script iterates over language files inside the CLDR `common/main/` directory,
parses each `<characters>` section in XML, and extracts the main `<exemplarCharacters>`.

CLDR:
    https://github.com/unicode-org/cldr/

Definition of the CLDR exemplar characters:
    https://github.com/unicode-org/cldr/blob/main/docs/ldml/tr35-general.md#Exemplars

The syntax:
    https://github.com/unicode-org/cldr/blob/main/docs/ldml/tr35-general.md#ExemplarSyntax

Usage:
    python opuscleaner/scripts/build_exemplar_characters.py --cldr-repo /path/to/cldr/common/main
"""

import unicodedata
import argparse
import re
from pathlib import Path
from typing import Dict
import xml.etree.ElementTree as ET

# The ICU dependency is a little finnicky to install, as the build fails on macOS.
# This file should be run from Linux or a Linux docker container.
from icu import Locale


def codeunits_to_codepoint(cp: str) -> int:
    """
    Handle high/low surrogate pairs in UTF-16 encoded strings, and decode codepoints
    outside of the basic multilingual plane.
    """
    if len(cp) == 1:
        return ord(cp)
    elif len(cp) == 2:
        high, low = ord(cp[0]), ord(cp[1])
        if 0xD800 <= high <= 0xDBFF and 0xDC00 <= low <= 0xDFFF:
            return 0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00)
        else:
            raise ValueError(f"Invalid surrogate pair: {cp!r}")
    else:
        raise ValueError(f"Expected 1 or 2 code units, got {len(cp)}: {cp!r}")


def format_char(cp: int) -> str:
    """Return character as an encoded value if it's a combining mark."""
    char = chr(cp)
    if unicodedata.category(char) in {"Mn", "Mc"}:
        if cp <= 0xFFFF:
            return f"\\u{cp:04X}"
        else:
            return f"\\U{cp:08X}"
    else:
        return re.escape(char)


def build_regex_pattern(codeunits_set: set[str]) -> str:
    """
    Convert a set of codeunits into a regex pattern built from ranges.
    """
    # Convert the code units to codepoints, and sort them by their codepoint value.
    codepoints: list[int] = sorted(codeunits_to_codepoint(cp) for cp in codeunits_set)

    if not codepoints:
        return ""

    # Compute the concurrent ranges of code points.
    ranges: list[tuple[int, int]] = []

    start: int = codepoints[0]
    end: int = start

    for cp in codepoints[1:]:
        if cp == end + 1:
            end = cp
        else:
            ranges.append((start, end))
            start = end = cp

    ranges.append((start, end))

    # Convert the ranges into the regex.
    parts: list[str] = []
    for start, end in ranges:
        if start == end:
            parts.append(format_char(start))
        else:
            parts.append(f"{format_char(start)}-{format_char(end)}")

    pattern_str = f'[{"".join(parts)}]'

    # Assert that the string actually works on all of the original characters.
    pattern = re.compile(pattern_str, re.IGNORECASE)
    for ch in codeunits_set:
        assert pattern.match(ch), f"{pattern_str} matches all codepoints: {ch}"

    return pattern_str


def parse_exemplar(text: str):
    """
    Parse the exemplar text
    e.g.
        ca: "[· aà b cç d eéè f g h iíï j k l m n oóò p q r s t uúü v w x y z]"
        de: "[aä b c d e f g h i j k l m n oö p q r s ß t uü v w x y z]"
        pt: "[a {ch} {chʼ} h i k {kʼ} l {ll} m nñ p {pʼ} q {qʼ} s t {tʼ} u w y]"
        ru: "[а б в г д её ж з и й к л м н о п р с т у ф х ц ч ш щ ъ ы ь э ю я]"
    """
    codeunits: set[str] = set()
    # This iterator works over codepoints, not code units. So the character will either
    # be a single code unit, or a low/high surrogate pair.
    for ch in text:
        if ch in {" ", "{", "}", "[", "]"}:
            # These characters are part of the unicode set syntax. It should be fine
            # to drop them, as we aren't worrying about retaining concurrent characters.
            # We only want the individual codepoints.
            continue
        codeunits.add(ch)

    return build_regex_pattern(codeunits)


def extract_exemplar_characters(cldr_repo: Path):
    result: Dict[str, str] = {}

    files = list((cldr_repo / "common/main").iterdir())
    files.sort()

    print("CHARS = {")
    for lang_file in files:
        if not lang_file.is_file() or not lang_file.suffix == ".xml":
            continue

        language = lang_file.stem

        try:
            tree = ET.parse(lang_file)
        except ET.ParseError as e:
            print(f"XML parse error in {lang_file}: {e}")
            continue

        root = tree.getroot()

        # Find <characters><exemplarCharacters> that has no `type` attribute
        characters = root.find("characters")
        if characters is None:
            continue

        exemplar = None
        for elem in characters.findall("exemplarCharacters"):
            if elem.get("type") is None:
                exemplar = elem.text
                break

        if exemplar == "↑↑↑":
            # This is an inheritance marker, just omit this as it's a more specific
            # locale, and we already have the more general language.
            # https://github.com/unicode-org/cldr/blob/0f4247e9c331ad31e9b1dc746e78e44757920cf0/docs/ldml/tr35.md#inheritance-marker
            continue

        if exemplar:
            assert "↑" not in exemplar, "No inheritance markers were found."

            lang = lang_file.stem
            result[lang] = exemplar
            regex_pattern = parse_exemplar(exemplar)
            if regex_pattern:
                assert "'" not in regex_pattern
                print("    #", Locale(language).getDisplayName())
                print(f"    '{language}': r'{regex_pattern}',")

    print("}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract exemplar characters from CLDR XML data.")
    parser.add_argument("--cldr-repo", type=str, required=True, help="Path to the cldr repo.")
    args = parser.parse_args()

    cldr_repo = Path(args.cldr_repo)
    if not cldr_repo.exists():
        raise FileNotFoundError(f"Could not find the CLDR repo: {cldr_repo}")

    extract_exemplar_characters(cldr_repo)


if __name__ == "__main__":
    main()
