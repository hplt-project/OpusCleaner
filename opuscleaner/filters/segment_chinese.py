#!/usr/bin/env python3
from sys import stdin
import spacy_pkuseg as pkuseg

seg = pkuseg.pkuseg() #load the default model
for line in stdin:
    text = seg.cut(line.strip())
    print(" ".join(text))
