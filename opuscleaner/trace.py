#!/usr/bin/python3
import sys
import json
import time
import os
from typing import Dict, Tuple, List, Union, IO, Iterator, Optional
from uuid import UUID
from rich.live import Live
from rich.tree import Tree
from rich.text import Text


def follow_file(fh:IO[str]) -> Iterator[Optional[str]]:
	while True:
		pos = fh.tell()

		# Did file get truncated?
		if pos > os.fstat(fh.fileno()).st_size:
			fh.seek(0)
			continue

		line = fh.readline()

		if line:
			yield line
		else:
			fh.seek(pos)
			yield None


def follow_path(filename:str) -> Iterator[Optional[str]]:
	while True:
		with open(filename, 'r') as fh:
			for line in follow_file(fh):
				if line is not None:
					yield line
					continue

				try:
					if not os.path.isfile(filename) or os.stat(filename).st_ino != os.fstat(fh.fileno()).st_ino:
						break # File changed, break the for loop
				except OSError:
					break # failure due to file deletion, also break for loop

				yield None


Entry = Tuple[Dict,List['Entry']]

class Trace:
	records: Dict[str,Entry]

	roots: List[Entry]

	def __init__(self):
		self.records = dict()
		self.roots = []

	def append(self, record:dict):
		if record['id'] not in self.records:
			self.records[record['id']] = ({}, [])
			if record.get('parent') is None:
				self.roots.append(self.records[record['id']])
			else:
				self.records[record['parent']][1].append(self.records[record['id']])
		self.records[record['id']][0].update(record)


trace = Trace()


def render_branch(branch:Entry) -> Tree:
	record, children = branch

	label = Text(overflow='ellipsis', no_wrap=True)
	label.append(record.get('name', 'nameless'),
		style='bold' if record.get('start') and not record.get('end') else '')

	
	# if record.get('time') is not None:
	# 	label.append(' ' + json.dumps(record['time']))

	if record.get('error') is not None:
		label.append(' ' + record['error'], style='bold red')

	extra = set(record.keys()) - {'name', 'error', 'id', 'parent', 'start', 'end'}
	if extra:
		label.append(' ' + json.dumps({k:record[k] for k in extra}))

	node = Tree(label)
	for child in children:
		node.add(render_branch(child))
	return node


def render_tree() -> Union[Tree,Text]:
	if len(trace.roots) < 1:
		return Text(f'Too few roots ({len(trace.records)=})')
	elif len(trace.roots) > 1:
		return Text(f'Too many roots')
	return render_branch(trace.roots[0])


with Live(render_tree(), screen=True) as live:
	for line in follow_path(sys.argv[1]):
		if line is None:
			time.sleep(0.1)
			continue
		record = json.loads(line)
		trace.append(record)
		live.update(render_tree())