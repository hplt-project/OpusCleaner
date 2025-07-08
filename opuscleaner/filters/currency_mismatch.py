#!/usr/bin/env python3
"""
Compare currencies (symbols and ISO codes) on both sides.
Filter mismatches and optionally try fixing the target currency where possible.

Example:
    cat corpus.tsv | ./currency_mismatch.py --debug --fix > kept.tsv
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from typing import List, TextIO

from babel.numbers import list_currencies, get_currency_symbol


def build_currency_map() -> dict[str, set[str]]:
    """Return ``{currency ID → set(ISO codes)}`` built from CLDR/Babel.

    *currency* is a generic symbol (e.g. ``€``) or an ISO code (``EUR``).
    """
    cmap = defaultdict(set)

    for iso in list_currencies():
        cmap[iso].add(iso)  # ISO code itself
        sym = get_currency_symbol(iso, "en")
        # this captures all currencies that use $ (CA$ etc.)
        if '$' in sym:
            cmap['$'].add(iso)
        cmap[sym].add(iso)

    return dict(cmap)


def compile_currency_regex(currencies: List[str]):
    """
    Compile a  regex that finds any currency symbol or ISO code near numbers,
        but safely ignores text where those strings are just a part of another word.
    """
    escaped = sorted(map(re.escape, currencies), key=len, reverse=True)
    number = r'\d[\d.,]*'  # 5   1,234.56   9.99
    cur_ids = '|'.join(escaped)  # same escaped ISO/symbol list as before

    pattern = re.compile(
        rf"""(?x)
            (?<![A-Za-z])                  # no letter on the left
            (?:
                (?P<tok1>{cur_ids})\s*{number}    # token before number
              |
                {number}\s*(?P<tok2>{cur_ids})    # number before token
            )
            (?![A-Za-z])                   # no letter on the right
        """
    )

    return re.compile(pattern)


CMAP = build_currency_map()
RGX = compile_currency_regex(list(CMAP.keys()))


def _kind(cur: str) -> str:
    """Return ``'symbol'`` if currency has **no letters**, else ``'code'``."""
    return "symbol" if not any(c.isalpha() for c in cur) else "code"


def check_row(
        src: str,
        trg: str,
        fix: bool = False,
        debug: bool = False,
):
    """Validate and fixes a sentence pair.

    Returns ``(flag: bool, fixed_trg: str)``.

    * **flag == True** when either
        – the two sentences include *different* currencies or the order doesn't match
        – they include the same currencies but use different styles (e.g. symbol and ISO code)

    * When ``fix`` is **True** and the styles of mismatched currencies match, the target is replaced with the source
    """
    src_curs = [t1 or t2 for t1, t2 in RGX.findall(src)]
    trg_curs = [t1 or t2 for t1, t2 in RGX.findall(trg)]
    src_isos = [CMAP[cur] for cur in src_curs]
    trg_isos = [CMAP[cur] for cur in trg_curs]
    src_styles = [_kind(cur) for cur in src_curs]
    trg_styles = [_kind(cur) for cur in trg_curs]

    flag = False
    if src_isos != trg_isos or src_styles != trg_styles:
        flag = True

    new_trg = None
    # Optional auto‑fix of the simplest case (single instance, different ISO codes, same style)
    # It's possible to fix it when the styles also don't match but it leads to incorrect formatting,
    # for example 5 USD -> 5 $ instead of $5
    if fix and flag and len(src_curs) == len(trg_curs) == 1 and src_styles[0] == trg_styles[0]:
        new_trg = trg.replace(trg_curs[0], src_curs[0])

    if flag and debug:
        print(f"L: {src_curs}  R: {trg_curs} LINE: {src}\t{trg}{' FIXED: ' + new_trg if new_trg else ''}",
              file=sys.stderr)

    return flag, new_trg


def filter_currency_mismatch(fin: TextIO, fout: TextIO, debug: bool = False, fix: bool = False) -> None:
    for line in fin:
        cols = line.rstrip("\r\n").split("\t")
        assert len(cols) >= 2, "Input must have at least two tab-separated columns"

        src, trg = cols[0], cols[1]
        flag, fixed = check_row(src, trg, fix=fix, debug=debug)

        if not flag:
            fout.write(line)
        elif fix and fixed:
            fout.write(f"{src}\t{fixed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare currencies (symbols and ISO codes) on both sides. Optionally try fixing the target currency where possible."
    )
    parser.add_argument(
        "--debug", action="store_true", help="Output deleted lines and extracted currencies to stderr"
    )
    parser.add_argument(
        "--fix", action="store_true", help="Attempt fixing target sentence where possible"
    )
    args = parser.parse_args()

    filter_currency_mismatch(sys.stdin, sys.stdout, debug=args.debug, fix=args.fix)
