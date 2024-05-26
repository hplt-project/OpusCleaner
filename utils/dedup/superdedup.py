#!/usr/bin/env python
import sys
import os
import pickle


def main():
    shashes, thashes = set(), set()
    # Try to old existing hashes
    if os.path.isfile("shashes.pickle"):
        with open("shashes.pickle", "rb") as f:
            shashes = pickle.load(f)
    if os.path.isfile("thashes.pickle"):
        with open("thashes.pickle", "rb") as f:
            thashes = pickle.load(f)
    for line in sys.stdin:
        parts = line.rstrip("\n").split("\t")

        src_hash = parts[2]
        trg_hash = parts[3]

        if src_hash not in shashes and trg_hash not in thashes:
            sys.stdout.write(line)
        shashes.add(src_hash)
        thashes.add(trg_hash)
    # Write a list of seen hashes
    with open("shashes.pickle", "wb") as f:
        pickle.dump(shashes, f)
    with open("thashes.pickle", "wb") as f:
        pickle.dump(thashes, f)


if __name__ == "__main__":
    main()
