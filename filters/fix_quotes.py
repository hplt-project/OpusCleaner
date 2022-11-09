#!/usr/bin/env python3
import sys
import re

def fix(text:str)->str:
	return re.sub(r'^[\'‘"“„](.+?)["”;]*$', r'\1', text)

for line in sys.stdin:
	fields = line.rstrip("\n").split("\t")

	fields = [fix(field).strip() for field in fields]

	if all(len(field) > 0 for field in fields):
		print("\t".join(fields))
