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
        line = line.strip()

        if collapse:
            line = collapse_whitespace(line)

        sys.stdout.write(f"{line}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collapse", action="store_true",
        help="Collapse whitespace groups into single spaces")
    args = parser.parse_args()
    clean(args.collapse)
