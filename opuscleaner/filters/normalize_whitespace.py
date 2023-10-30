#!/usr/bin/env python3
"""Normalize whitespace filter.

Strips all leading and trailing whitespaces. Optionally, collapses all groups
of whitespaces into a single space

"""
import argparse
import sys


def collapse_whitespace(s):
    """Collapses whitespace groups into a single space."""
    return " ".join(s.split())


def clean(collapse):
    """Runs the filter."""

    for line in sys.stdin:
        fields = line.strip().split("\t")

        if len(fields) == 1:
            src = fields[0].strip()
            trg = None
        else:
            # Similar to max_length filter, here we throw away potential
            # newlines.
            src = fields[0].strip()
            trg = fields[1].strip()

        if collapse:
            src = collapse_whitespace(src)
            if trg is not None:
                trg = collapse_whitespace(trg)

        if trg is not None:
            sys.stdout.write(f"{src}\t{trg}\n")
        else:
            sys.stdout.write(f"{src}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collapse", action="store_true",
        help="Collapse whitespace groups into single spaces")
    args = parser.parse_args()
    clean(args.collapse)
