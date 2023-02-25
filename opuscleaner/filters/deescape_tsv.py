#!/usr/bin/env python3
import sys

QUOTECHR = b'"'[0]

for line in sys.stdin.buffer:
	fields = line.rstrip(b"\n").split(b"\t")
	for i, field in enumerate(fields):
		if field[0] == QUOTECHR and field[-1] == QUOTECHR:
			fields[i] = field[1:-1].replace(b'""', b'"')
	sys.stdout.buffer.write(b"\t".join(fields))
	sys.stdout.buffer.write(b"\n")
