#!/usr/bin/env python3
'''Segments Japanese text using the fugashi tokenizer.
Note the specifics of Japanese tokenization, where verbs are always separate to stem
and  conjugation part, as well topic or subject particles are split from the nouns.
This means that the Japanese sentences would likely be quite a bit longer than the
English ones.'''
import fugashi
from sys import stdin

tagger = fugashi.Tagger()

# https://www.dampfkraft.com/nlp/how-to-tokenize-japanese.html
for line in stdin:
    line = line.strip()
    words = [word.surface for word in tagger(line)]
    print(*words)
