#!/usr/bin/env python3
"""
Removes patterns that occur usually only in the source or in the target. There are two way to set up a pattern:
 - a two columns type - pattern tab replacement, which is applied to both source and target
 - a three columns tpye - pattern_on_both_cols tab pattern tab replacement
    The `pattern_on_both_cols` is matched against tab separated source and target.
    If it matches then the `pattern` is replaced in both columns.

You can check the three column filter from the examples by running
```
mtdata get -l ces-eng -tr ELRC-czech_supreme_audit_office_2018_reports-1-ces-eng  --compress -o data
```
and using the `remove_frequent_patterns` filter.
Then e.g. the line containing `Increasing support for informal carers,` will not start with `• `,
because the source doesn't start with a bullet either.
"""

from dataclasses import dataclass
import re
import sys
import argparse
from typing import List, Optional


@dataclass
class Pattern:
    group_match: re.Pattern
    replacement: str
    pattern_on_both_cols: Optional[re.Pattern] = None


def load_patterns(file_path: str) -> List[Pattern]:
    with open(file_path) as f:
        # Skip comment lines
        lines = [line.rstrip("\n") for line in f.readlines() if line[0] != "#"]
        patterns = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) == 2:
                patterns.append(Pattern(group_match=re.compile(parts[0]), replacement=parts[1]))
            elif len(parts) == 3:
                patterns.append(Pattern(pattern_on_both_cols=re.compile(parts[0]), group_match=re.compile(parts[1]), replacement=parts[2]))
            else:
                raise ValueError(f"Patterns have to have 2 or 3 columns, but got {len(parts)}")
        return patterns


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--pattern-file", type=str, help="Path to the file with patterns.")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    patterns = load_patterns(args.pattern_file)

    for line in sys.stdin:
        line = line.rstrip("\n")
        source, target = line.split("\t", 1)
        for pattern in patterns:
            # Either pattern_on_both_cols is not set or it matches the whole line
            if pattern.pattern_on_both_cols is None or pattern.pattern_on_both_cols.match(line):
                source = pattern.group_match.sub(pattern.replacement, source)
                target = pattern.group_match.sub(pattern.replacement, target)
        sys.stdout.write(f"{source}\t{target}\n")


if __name__ == "__main__":
    main()
