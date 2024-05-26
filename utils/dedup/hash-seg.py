#!/usr/bin/env python3
from argparse import ArgumentParser
from unicodedata import category as cat
from unidecode import unidecode
from xxhash import xxh64
import sys

parser = ArgumentParser()
parser.add_argument("-a", "--aggressive", action="store_true", default=False)
args = parser.parse_args()

# Translate table to remove non alphabetic characters
tbl = [chr(i) for i in range(sys.maxunicode) if not cat(chr(i)).startswith("L")]
remove_non_alpha = str.maketrans("", "", "".join(tbl))


def main():
    shashes, thashes = set(), set()
    for line in sys.stdin:
        sline = line.rstrip("\n")
        parts = sline.split("\t")
        src = parts[0]
        trg = parts[1]

        if args.aggressive:
            src = unidecode(src.lower().translate(remove_non_alpha))
            trg = unidecode(trg.lower().translate(remove_non_alpha))

        src_hash = xxh64(src).hexdigest()
        trg_hash = xxh64(trg).hexdigest()

        sys.stdout.write(f"{sline}\t{src_hash}\t{trg_hash}\n")


if __name__ == "__main__":
    main()
