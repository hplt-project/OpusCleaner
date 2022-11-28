from typing import IO, Type
from collections import Counter
from contextlib import closing
import unittest
import tempfile
import os

from trainer import Dataset, DatasetReader, AsyncDatasetReader

TEST_FILE: str

def setUpModule():
	global TEST_FILE
	fd, TEST_FILE = tempfile.mkstemp(text=True)
	
	with open(fd, 'w') as fh:
		for n in range(1000):
			fh.write(f'line{n}\n')


def tearDownModule():
	os.unlink(TEST_FILE)


class TestDatasetReader(unittest.TestCase):
	testset: IO[str]

	reader: Type[DatasetReader] = DatasetReader

	def test_read(self):
		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader:
			counter = Counter(line for _, line in zip(range(3000), reader))

		self.assertEqual(len(counter), 1000)
		self.assertEqual(set(counter[key] for key in counter.keys()), {3})

	def test_offsets(self):
		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader:
			for _ in zip(range(500), reader):
				pass

			self.assertEqual(reader.epoch, 0)
			self.assertEqual(reader.line, 500)

			for _ in zip(range(1250), reader):
				pass

			self.assertEqual(reader.epoch, 1)
			self.assertEqual(reader.line, 750)

	def test_resume(self):
		counter = Counter()

		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader1:
			counter.update(line for _, line in zip(range(250), reader1))
			state = reader1.state()

		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader2:
			reader2.restore(state)
			counter.update(line for _, line in zip(range(750), reader2))

		self.assertEqual(len(counter), 1000)
		self.assertEqual(set(counter[key] for key in counter.keys()), {1})

class TestAsyncDatasetReader(TestDatasetReader):
	reader = AsyncDatasetReader