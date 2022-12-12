#!/usr/bin/env python3
import sys
with open('/tmp/test', 'w', encoding='utf-8') as outfile:
    for line in sys.stdin:
        outfile.write(line)
        outfile.flush()
