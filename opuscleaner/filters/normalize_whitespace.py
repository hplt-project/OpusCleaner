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

    for i, line in enumerate(sys.stdin):
        fields = line.split("\t")

        if len(fields) == 1:
            src = fields[0].strip()
            trg = None
        elif len(fields) == 2:
            src = fields[0].strip()
            trg = fields[1].strip()
        else:
            raise ValueError(f"Too many tabs on input line {i + 1}")

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
