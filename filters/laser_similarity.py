#!/usr/bin/env python3

import sys
from typing import List, Tuple
import argparse

import numpy as np
from laserembeddings import Laser
from numpy.linalg import norm

from more_itertools import chunked


def _compute_similarity(laser: Laser, batch: List[Tuple[str, str]], src_lang: str, tgt_lang: str) -> List[float]:
    embeddings_src = laser.embed_sentences([line[0] for line in batch], lang=src_lang)
    embeddings_tgt = laser.embed_sentences([line[1] for line in batch], lang=tgt_lang)

    return [float(sim) for sim in _cosine_sim(embeddings_src, embeddings_tgt)]


def _cosine_sim(emb1: np.ndarray, emb2: np.ndarray) -> np.ndarray:
    return np.sum(emb1 * emb2, axis=-1) / (norm(emb1, axis=-1) * norm(emb2, axis=-1))


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="Filter a parallel dataset using LASER.")
    parser.add_argument("--threshold", type=float, default=0.5, help="Minimum accepted LASER score.")
    parser.add_argument("--batch-size", type=int, default=32, help="LASER batch size")
    parser.add_argument("--src-lang", type=str, required=True, help="Two-letter source language code (ISO 639-1)")
    parser.add_argument("--tgt-lang", type=str, required=True, help="Two-letter target language code (ISO 639-1)")

    args = parser.parse_args()
    
    laser = Laser()

    for batch in chunked(sys.stdin, args.batch_size):
        # TODO error checking of column count?
        scores = _compute_similarity(laser, [line.split("\t") for line in batch], args.src_lang, args.tgt_lang)

        for line, score in zip(batch, scores):
            if score >= args.threshold:
                sys.stdout.write(line)


if __name__ == "__main__":
    main()