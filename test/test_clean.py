import sys
import os
import unittest
import subprocess
import json
from typing import List
from pathlib import Path
from tempfile import NamedTemporaryFile


TEST_CWD = Path(os.path.join(os.path.dirname(__file__), 'deeper'))

FILES = [
	"bible-uedin-v1.de-en.de.gz",
	"bible-uedin-v1.de-en.en.gz"
]


class TestClean(unittest.TestCase):
	def _run(self, args:List[str]):
		proc = subprocess.Popen(
			args=[sys.executable, '-m', 'opuscleaner.clean'] + args,
			cwd=TEST_CWD, # so it can find filters
			env={
				'PYTHONPATH': os.path.join(os.path.dirname(__file__), '..') # so it can find opuscleaner code
			},
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE)

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

			for mode in [[], ['--parallel', '1']]:
				with self.subTest(mode=mode):
					out, err, retval = self._run([*mode, fh.name])
					self.assertEqual(out.count(b'\n'), 0)
					self.assertNotEqual(retval, 0)
