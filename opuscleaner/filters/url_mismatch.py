#!/usr/bin/env python3
"""
Filter out sentence-pairs whose URLs are not an *exact ordered match*.

Example:
    cat corpus.tsv | ./url_mismatch.py > kept.tsv
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import List, TextIO

# RFC-3986ish, scheme is optional
URL_REGEX = re.compile(
    r"""
        \b
        (?: (?P<scheme>[a-z][a-z0-9+.-]*) :// )?           # optional scheme
        (?: (?P<userinfo>[a-zA-Z0-9._~%!$&'()*+,;=:-]+) @ )?  # optional user-info
        (?P<host>                                          # host = DNS | IPv4 | IPv6
              (?: (?:[a-zA-Z0-9-]{1,63}\.)+ [a-zA-Z]{2,63} )
            | (?: \d{1,3}\.){3}\d{1,3}
            | \[ [0-9a-fA-F:.]+ \]
        )
        (?: : (?P<port>\d{2,5}) )?                         # optional port
        (?P<path> (?: / [a-zA-Z0-9._~%!$&'()*+,;=:@-]* )* ) # path
        (?: \? (?P<query>[a-zA-Z0-9._~%!$&'()*+,;=:@/?-]*) )? # query
        (?: \# (?P<fragment>[a-zA-Z0-9._~%!$&'()*+,;=:@/?-]*) )? # fragment
        \b
    """,
    re.X | re.I,
)

# Pattern that marks a *false* URL because of a sentence border inside the host
DOT_CAP_INSIDE = re.compile(r'[a-z0-9]\.[A-Z]')


def extract_url_list(text: str) -> List[str]:
    """
    Return a list of  **excluding** any match
    whose host contains 'xx.Capital', which is treated as a sentence-border artefact.
    """
    urls: List[str] = []
    for m in URL_REGEX.finditer(text):
        host = m.group('host')
        if DOT_CAP_INSIDE.search(host):
            # Likely 'Hello.World' joining two sentences → skip
            continue
        urls.append(m.group(0))
    return urls


def filter_url_mismatch(fin: TextIO, fout: TextIO, *, debug: bool = False) -> None:
    """
    Keep a line only if the URL *lists* in the first two columns are identical
    (or both empty).  Any discrepancy in count, content, or order → drop.
    """
    for line in fin:
        cols = line.rstrip("\r\n").split("\t")
        assert len(cols) >= 2, "Input must have at least two tab-separated columns"

        urls_left = extract_url_list(cols[0])
        urls_right = extract_url_list(cols[1])

        # If both sides contain URLs, require an exact ordered match
        if urls_left or urls_right:
            if urls_left != urls_right:
                if debug:
                    print(f"L: {urls_left}  R: {urls_right} Line: {line.rstrip()}", file=sys.stderr)
                continue  # mismatch → reject line

        fout.write(line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Keep only sentence pairs whose URL lists match exactly."
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print URLs from deleted lines"
    )
    args = parser.parse_args()

    filter_url_mismatch(sys.stdin, sys.stdout, debug=args.debug)
