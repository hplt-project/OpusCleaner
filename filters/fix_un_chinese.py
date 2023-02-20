#!/usr/bin/env python3
"""Legacy fix_un.py from Barry. Need to fix it up a bit."""
import re
import sys


re_final_comma = re.compile(r"\.$")


for line in sys.stdin:
    line = line[:-1] #EoL
    line = line.strip()
    if line[-1] == '，':
        line = line[:-1] + "\u3002"
    line = line.replace(",", "\uFF0C")
    line = re_final_comma.sub("\u3002", line)
    print(line)
