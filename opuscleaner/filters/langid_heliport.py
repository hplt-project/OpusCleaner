#!/usr/bin/env python3
from sys import stdin, stdout, stderr
from typing import TextIO
import argparse

from heliport import Identifier
from iso639 import Lang

LANG_MAP = {
    "bs": "hbs",
    "hr": "hbs",
    "sr": "hbs",
    "id": "msa",
    "ms": "msa",
    "zh": "cmn",
    "fa": "pes",
}

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Langid")
    parser.add_argument("languages", default=None, type=str, nargs="+")
    parser.add_argument("--allow-notext", action="store_true", help="Allow sentences with no textual information (e.g. only punctuation, spaces and/or numbers)")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def detect_language_parallel(args: argparse.Namespace, fin: TextIO, fout: TextIO):
    detector = Identifier()
    languages = []
    for lang in args.languages:
        if len(lang) == 3:
            languages.append(lang)
        elif len(lang) == 2:
            if lang in LANG_MAP:
                languages.append(LANG_MAP[lang])
            else:
                languages.append(Lang(lang).pt3)
        else:
            raise ValueError(f"Language code format not supported: '{lang}'")

    for n, line in enumerate(fin):
        fields = line.rstrip("\r\n").split("\t")

        for field, lang in zip(fields, languages):
            try:
                detected_lang = detector.identify(field)

                # if it's zxx, means no textual info, we keep that
                if args.allow_notext and detected_lang == "zxx":
                    continue

                if detected_lang == lang:
                    continue

                if args.debug:
                    print(f"Line {n} rejected. Detected '{detected_lang}' ({confidence:0.3f}), expected '{lang}': {field}", file=stderr)
                # Break because no need to look at the other columns. Also will
                # stop the else clause from being executed!
                break
            except Exception as err:
                print(f"Line {n} rejected because error: {err}", file=stderr)
                break
        else:
            # All fields were valid, so write out the line.
            fout.write(line)
            continue


if __name__ == "__main__":
    args = parse_user_args()
    detect_language_parallel(args, stdin, stdout)
