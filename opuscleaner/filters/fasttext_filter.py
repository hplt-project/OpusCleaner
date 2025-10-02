#!/usr/bin/env python3
import os
import sys
import argparse
from typing import List

# The filename has to have a different name than 'fasttext', otherwise we can't import the module correctly
import fasttext
import iso639

from more_itertools import chunked
import requests


def download_model(model_type: str):
    """
    Downloads the fasttext model for language identification to local directory. Either the large one or the small one.
    """
    if model_type == "small":
        url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
    elif model_type == "large":
        url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
    elif model_type == "openlid-v2":
        url = "https://huggingface.co/laurievb/OpenLID-v2/resolve/main/model.bin"
    elif model_type == "nllb":
        url = "https://dl.fbaipublicfiles.com/nllb/lid/lid218e.bin"
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
    # Split by fourth field separated by _, which is compatible with lid176 models and nllb
    # for nllb we don't take into account script
    return [row_langs[0].split('_')[4] == desired_lang for row_langs in langs]


def get_langcode(model_type, lang):
    '''
    Convert to 3-letter language codes for nllb model
    '''
    if model_type in ("small", "large"):
        return lang

    # Map to 3-letter codes that are not direct in iso639
    # because the 2-letter is mapped to a macrolang code
    LANG_MAP = {
        "ar": "arb",
        "fa": "pes",
        "id": "ind",
        "ms": "zsm",
    }

    if lang in LANG_MAP:
        return LANG_MAP[lang]

    return iso639.Lang(lang).pt3


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--source-lang", type=str, help="Code of the desired source language.")
    parser.add_argument("--target-lang", type=str, help="Code of the desired target language.")
    parser.add_argument("--batch-size", type=int, default=16, help="Size of the batch to send the data to fasttext.")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--model-type",
        type=str,
        help="Either 'small', 'large' or 'nllb'. See https://fasttext.cc/docs/en/language-identification.html for more info.",
    )
    args = parser.parse_args()
    # Fastext way to encode language codes
    source_lang = get_langcode(args.model_type, args.source_lang)
    target_lang = get_langcode(args.model_type, args.target_lang)
    source_lang, target_lang
    download_model(args.model_type)
    # Disable fasttext to notify us about loading the model
    fasttext.FastText.eprint = lambda x: None
    model = fasttext.load_model(f"{args.model_type}.bin")
    for batch in chunked(sys.stdin, args.batch_size):
        # Remove newlines
        batch = [row.rstrip("\r\n") for row in batch]
        sources, targets = zip(*[row.split("\t", 1) for row in batch])
        sources_ok = verify_lang(model, list(sources), source_lang, args.debug)
        targets_ok = verify_lang(model, list(targets), target_lang, args.debug)
        for row, source_ok, target_ok in zip(batch, sources_ok, targets_ok):
            if source_ok and target_ok:
                sys.stdout.write(row + "\n")
            elif args.debug:
                sys.stderr.write(f"Discarded: {row}\n")


if __name__ == "__main__":
    main()
