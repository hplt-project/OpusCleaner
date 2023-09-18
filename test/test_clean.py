import sys
import os
import unittest
import subprocess
import json
import gzip
from typing import List
from pathlib import Path
from contextlib import ExitStack
from tempfile import TemporaryFile, NamedTemporaryFile


TEST_CWD = Path(os.path.join(os.path.dirname(__file__), 'deeper'))

FILES = [
	"bible-uedin-v1.de-en.de.gz",
	"bible-uedin-v1.de-en.en.gz"
]

SCENARIOS = {
	'single': [],
	'parallel': ['--parallel', '2', '--batch-size', '32000'], # parallel
}


class TestClean(unittest.TestCase):
	def _run(self, args:List[str], **kwargs):
		proc = subprocess.Popen(
			args=[sys.executable, '-m', 'opuscleaner.clean'] + args,
			cwd=TEST_CWD, # so it can find filters
			env={
				'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..') # so it can find opuscleaner code
			},
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			**kwargs)

		out, err = proc.communicate()
		proc.wait()
		return out, err, proc.returncode

	def test_simple(self):
		"""Test that clean runs"""
		config = {
			"version": 1,
			"files": FILES,
			"filters": [
				{
					"filter": "deescape_tsv",
					"parameters": {},
					"language": None
				}
			]
		}
		with NamedTemporaryFile(mode='w', dir=TEST_CWD / 'data/train-parts') as fh:
			json.dump(config, fh)
			fh.flush()
			for mode in [[], ['--parallel', '1']]:
				with self.subTest(mode=mode):
					out, err, retval = self._run([*mode, fh.name])
					self.assertEqual(out.count(b'\n'), 62195)
					self.assertEqual(retval, 0)

	def test_filter_fail(self):
		"""Test that clean returns a non-zero exit code if a filter fails"""
		config = {
			"version": 1,
				"files": FILES,
				"filters": [
					{
						"filter": "fail",
						"parameters": {
							"EXITCODE": "42"
						},
						"language": "de"
					}
				]
		}
		with NamedTemporaryFile(mode='w', dir=TEST_CWD / 'data/train-parts') as fh:
			json.dump(config, fh)
			fh.flush()

			for mode, args in SCENARIOS.items():
				with self.subTest(mode=mode):
					out, err, retval = self._run([*args, fh.name])
					self.assertEqual(out.count(b'\n'), 0)
					self.assertNotEqual(retval, 0)

	def test_stdin(self):
		"""Test that clean runs"""
		config = {
			"version": 1,
			"files": FILES,
			"filters": [
				{
					"filter": "deescape_tsv",
					"parameters": {},
					"language": None
				}
			]
		}
		with NamedTemporaryFile(mode='w', dir=TEST_CWD / 'data/train-parts') as fconf:
			json.dump(config, fconf)
			fconf.flush()
			with TemporaryFile('w+b') as fdata:
				# Concatenate the dataset together as if it was made with `paste <(gzip -cd a) <(gzip -cd b)`
				with ExitStack() as ctx:
					fhs = [
						ctx.enter_context(gzip.open(TEST_CWD / 'data/train-parts' / filename))
						for filename in FILES
					]
					fdata.writelines(
						b"\t".join(col.rstrip(b"\r\n") for col in line) + b"\n"
						for line in zip(*fhs)
					)
				fdata.flush()

				for mode, args in SCENARIOS.items():
					with self.subTest(mode=mode):
						# Reset dataset input
						fdata.seek(0)

						# Run cleaner with `--input -` and pass the data through stdin
						proc_clean = subprocess.Popen(
							args=[sys.executable, '-m', 'opuscleaner.clean', *args, '--input', '-', fconf.name, 'de', 'en'],
							cwd=TEST_CWD,
							env={
								'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..') # so it can find opuscleaner code
							},
							stdin=fdata,
							stdout=subprocess.PIPE,
							stderr=subprocess.PIPE)

						out, err = proc_clean.communicate()
						retval = proc_clean.wait()

						# Help with debugging
						if retval != 0:
							print(err, file=sys.stderr)

						self.assertEqual(out.count(b'\n'), 62195)
						self.assertEqual(retval, 0)