#!/usr/bin/env python3

import sys
import time
from typing import List, Tuple, Iterable, TypeVar, Optional, TextIO
import argparse
import numpy as np
from laserembeddings import Laser
from numpy.linalg import norm
from numpy.polynomial import Polynomial
from collections import deque
from io import TextIOBase


def _compute_similarity(laser: Laser, batch: List[Tuple[str, str]], src_lang: str, tgt_lang: str) -> List[float]:
    embeddings_src = laser.embed_sentences([line[0] for line in batch], lang=src_lang)
    embeddings_tgt = laser.embed_sentences([line[1] for line in batch], lang=tgt_lang)

    return [float(sim) for sim in _cosine_sim(embeddings_src, embeddings_tgt)]


def _cosine_sim(emb1: np.ndarray, emb2: np.ndarray) -> np.ndarray:
    return np.sum(emb1 * emb2, axis=-1) / (norm(emb1, axis=-1) * norm(emb2, axis=-1))


def interpolate(sample: Iterable[Tuple[int, float]], target:float) -> int:
    poly = Polynomial.fit([duration for size, duration in sample], [size for size, duration in sample], 1)
    return int(poly(target)), poly


class NullIO(TextIOBase):
    """TextIO that does nothing, as if writing to /dev/null."""
    def write(self, data:str) -> int:
        return len(data)


T = TypeVar('T')

def chunked(iterable: Iterable[T], *, chunk_size:Optional[int]=None, chunk_time:Optional[float]=None, verbose:Optional[TextIO]=NullIO()) -> Iterable[List[T]]:
    """Self-tuning batching iterator"""
    it = iter(iterable)

    # Initial set of measurements we then interpolate from
    limit_samples = iter([8, 16, 32, 64, 128, 256])

    # Chunk size limit for the next chunk
    limit = chunk_size or next(limit_samples)

    # Measurements (limited to most recent 32)
    measurements = deque([], maxlen=32)

    while True:
        # Create a chunk
        chunk = [el for _, el in zip(range(limit), it)]

        # Measure how long it takes before we are asked for the next chunk
        yield_time = time.monotonic()
        yield chunk
        if len(chunk) < limit:
            break
        yield_duration = time.monotonic() - yield_time
        print(f"Chunk size {limit} took {yield_duration}s", file=verbose)
        measurements.append((limit, yield_duration))

        # If we're running in dynamic mode, update the chunk size limit
        if chunk_size is None and chunk_time is not None:
            try:
                # Next limit for sampling?
                limit = next(limit_samples)
            except StopIteration:
                # No, we've run all the samples. Use previous measurements
                limit, poly = interpolate(measurements, chunk_time)
                print(f'Fitted {poly}', file=verbose)

            print(f"Setting chunk size to {limit}", file=verbose)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="Filter a parallel dataset using LASER.")
    parser.add_argument("--verbose", action="store_true", help="Print tuning info")
    parser.add_argument("--batch-size", type=int, help="LASER batch size")
    parser.add_argument("--batch-latency", type=float, default=30.0, help="Tune batch size to process a batch every N seconds (defaults to 30s, ignored if --batch-size is given)")
    parser.add_argument("--src-lang", type=str, required=True, help="Two-letter source language code (ISO 639-1)")
    parser.add_argument("--tgt-lang", type=str, required=True, help="Two-letter target language code (ISO 639-1)")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--threshold", type=float, help="Minimum accepted LASER score.")
    group.add_argument("--scores", action="store_true", help="Print scores instead of lines")

    args = parser.parse_args()

    if not args.scores and args.threshold is None:
        print("Either use --threshold or --scores")

    laser = Laser()

    for batch in chunked(sys.stdin, chunk_size=args.batch_size, chunk_time=args.batch_latency, verbose=sys.stderr if args.verbose else NullIO()):
        # TODO error checking of column count?
        scores = _compute_similarity(laser, [tuple(line.split("\t")[:2]) for line in batch], args.src_lang, args.tgt_lang)

        if args.scores:
            for score in scores:
                print(score, file=sys.stdout)
        else:
            for line, score in zip(batch, scores):
                if score >= args.threshold:
                    sys.stdout.write(line)


if __name__ == "__main__":
    main()