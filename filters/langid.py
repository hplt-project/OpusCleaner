#!/usr/bin/env python3
from sys import stdin, stdout, stderr
from typing import BinaryIO
import argparse

import pycld2

# Similar languages, taken from 
# https://github.com/mbanon/fastspell/blob/main/fastspell/config/similar.yaml
SIMILAR = {
    "ca": {"es", "ca"},
    "bg": {"mk", "bg"},
    "bs": {"bs", "hr", "me", "sr"},
    "cs": {"sk", "cs"},
    "da": {"da", "nb"},
    "es": {"es", "gl", "ca"},
    "gl": {"es", "pt", "gl"},
    "hr": {"bs", "hr", "me", "sr"},
    "me": {"bs", "hr", "me", "sr"},
    "mk": {"bg", "mk"},
    "nb": {"nn", "da", "nb"},
    "nl": {"nl", "af"}, # Maybe also Frisian (fy) and French (fr) because of
                        # short sentences are often misidentified as one of
                        # those (and honestly cld2 has probably been trained
                        # with a lot of Dutch in their Frisian corpora.)
    "nn": {"nb", "da", "nn"},
    "sk": {"cs", "sk"},
    "sr": {"bs", "hr", "me", "sr"},
}

LANG_UNKNOWN = "un"

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Langid")
    parser.add_argument("languages", default=None, type=str, nargs="+")
    parser.add_argument("--allow-similar", action="store_true")
    parser.add_argument("--allow-unknown", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def detect_language_parallel(args: argparse.Namespace, fin: BinaryIO, fout: BinaryIO):
    for n, line in enumerate(fin):
        fields = line.rstrip(b"\n").split(b"\t")

        for field, lang in zip(fields, args.languages):
            try:
                isReliable, _, [(_, detected_lang, _, _), *_] = pycld2.detect(field)

                # Accept field if reliable and detected language
                if isReliable and detected_lang == lang:
                    continue

                # Accept field if reliable and similar language detected
                if isReliable and args.allow_similar and detected_lang in SIMILAR[lang]:
                    continue

                # Accept field if not reliable but we allow failed detections
                if not isReliable and args.allow_unknown:
                    continue

                if args.debug:
                    print(f"Line {n} rejected. Detected '{detected_lang}', expected '{lang}': {field.decode()}", file=stderr)
                
                # Break because no need to look at the other columns. Also will
                # stop the else clause from being executed!
                break
            except Exception as err:
                if not args.allow_unknown:
                    print(f"Line {n} rejected because error: {err}", file=stderr)
                    break
        else:
            # All fields were valid, so write out the line.
            fout.write(line)
            continue


if __name__ == "__main__":
    args = parse_user_args()
    detect_language_parallel(args, stdin.buffer, stdout.buffer)
