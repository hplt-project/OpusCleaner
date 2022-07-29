#!/usr/bin/env python3
"""Desegments Chinese, useful for some corpora, as they arrive presegmented,
and for using after a segmentation filter. It also converts English fullstops into Chinese ones,
as well as converting final comma into Chinese fullstop."""
import re
import sys


re_space = re.compile(r"[^\S]+")
re_final_comma = re.compile(r"\.$")


for line in sys.stdin:
    line = line[:-1] #EoL
    line = line.strip()
    line.replace(' ', "")
    if line[-1] == '，':
        line = line[:-1] + "\u3002"
    if line[-1] == ',':
        line = line[:-1] + '.'
    if line[-1] == ' ':
        line = line[:-1]
    line = re_space.sub("", line)
    line = line.replace(",", "\uFF0C")
    line = re_final_comma.sub("\u3002", line)
    print(line)
