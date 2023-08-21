#!/usr/bin/env python3
import sys

QUOTECHR = ord('"')

for line in sys.stdin.buffer:
	fields = line.rstrip(b"\r\n").split(b"\t")
	for i, field in enumerate(fields):
		if len(field) > 0 and field[0] == QUOTECHR and field[-1] == QUOTECHR:
			fields[i] = field[1:-1].replace(b'""', b'"')
	sys.stdout.buffer.write(b"\t".join(fields))
	sys.stdout.buffer.write(b"\n")
