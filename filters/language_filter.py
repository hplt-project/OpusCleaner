#!/usr/bin/env python3
import os
import sys
from sys import stdin, stdout, stderr
from typing import BinaryIO, List
from more_itertools import chunked
import requests
import argparse

import pycld2

# The filename has to have a different name than 'fasttext', otherwise we can't import the module correctly
import fasttext

from fastspell import FastSpell

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

LANG_UNKNOWN = "un" # Unknown language code, used for fastspell

def parse_user_args():
    """Parse the arguments necessary for this filter"""
    parser = argparse.ArgumentParser(description="Langid")
    parser.add_argument("languages", default="en en", type=str, nargs="+")
    parser.add_argument("--allow-similar", action="store_true")
    parser.add_argument("--allow-unknown", action="store_true")
    parser.add_argument("--library", default="cld2", type=str)
    parser.add_argument("--source-lang", type=str)
    parser.add_argument("--target-lang", type=str)
    parser.add_argument("--model-type", type=str,
        help="Either 'small' or 'large'. See https://fasttext.cc/docs/en/language-identification.html for more info.",)
    parser.add_argument("--batch-size", type=int, default=16, help="Size of the batch to send the data to fasttext.")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()

def language_filter_cld2(args: argparse.Namespace, fin: BinaryIO, fout: BinaryIO):
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


def download_model(model_type: str):
    """
    Downloads the fasttext model for language identification to local directory. Either the large one or the small one.
    """
    if model_type == "small":
        url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
    elif model_type == "large":
        url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
    else:
        raise TypeError("Fasttext model type has to be either 'small' or 'large'.")
    file_name = model_type + ".bin"
    # Do not download twice
    if os.path.exists(file_name):
        return
    response = requests.get(url)
    with open(file_name, "wb") as handle:
        handle.write(response.content)


def verify_lang(model: fasttext.FastText._FastText, texts: List[str], desired_lang: str, debug: bool) -> List[bool]:
    # Langs is a list of list - for each row we get a list of identified languages, sorted by their probability.
    # Future work - using `model.predict(texts, k=10)` get the 10 most probable languages
    #   and do some clever filtering based on the distribution.
    langs, probs = model.predict(texts)

    if debug:
        sys.stderr.write(f"LANGUAGES\t{[lang[0] for lang in langs]}\n")
    return [row_langs[0] == desired_lang for row_langs in langs]


def language_filter_fasttext(args: argparse.Namespace):
    # Fastext way to encode language codes
    source_lang = "__label__" + args.source_lang
    target_lang = "__label__" + args.target_lang
    download_model(args.model_type)
    # Disable fasttext to notify us about loading the model
    fasttext.FastText.eprint = lambda x: None
    model = fasttext.load_model(f"{args.model_type}.bin")
    for batch in chunked(sys.stdin, args.batch_size):
        # Remove newlines
        batch = [row.rstrip("\n") for row in batch]
        sources, targets = zip(*[row.split("\t", 1) for row in batch])
        sources_ok = verify_lang(model, list(sources), source_lang, args.debug)
        targets_ok = verify_lang(model, list(targets), target_lang, args.debug)
        for row, source_ok, target_ok in zip(batch, sources_ok, targets_ok):
            if source_ok and target_ok:
                sys.stdout.write(row + "\n")
                

def language_filter_fastspell(args: argparse.Namespace):
    # FastSpell implementation taken from bicleaner hardrules
    # https://github.com/bitextor/bicleaner-hardrules/blob/master/hardrules/hardrules.py
    # 238
    
    # Load FastSpell
    lang_src = args.languages[0]
    lang_trg = args.languages[1]
    
    fastspell_src = FastSpell.FastSpell(lang_src, mode="aggr")
    fastspell_trg = FastSpell.FastSpell(lang_trg, mode="aggr")
    
    for line in stdin:
        
        fields = line.strip().split('\t')
        src = fields[-2].strip()
        trg = fields[-1].strip()
    
        check_src_lang = (fastspell_src.getlang(src) == lang_src)
        check_trg_lang = (fastspell_trg.getlang(trg) == lang_trg)
    
        if check_src_lang and check_trg_lang:
            stdout.write(line)
        else:
            if args.debug:
                stderr.write(f"LANGUAGES\t{[lang[0] for lang in langs]}\n")
    

if __name__ == "__main__":
    args = parse_user_args()
    
    if args.library == 'cld2':
        language_filter_cld2(args, stdin.buffer, stdout.buffer)
    elif args.library == 'fasttext':
        language_filter_fasttext(args)
    elif args.library == 'fastspell':
        language_filter_fastspell(args)