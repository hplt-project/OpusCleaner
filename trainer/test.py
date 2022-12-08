from typing import IO, Type
from collections import Counter
from contextlib import closing
import unittest
import tempfile
import os

from trainer import Dataset, DatasetReader, AsyncDatasetReader, CurriculumLoader, Trainer, StateTracker

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

	def test_repeating_read(self):
		# Read 3000 lines
		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader:
			counter = Counter(line for _, line in zip(range(3000), reader))

		# We should have 1000 unique lines (all lines in TEST_FILE)
		self.assertEqual(len(counter), 1000)
		# And each line should be read exactly 3 times
		self.assertEqual(set(counter[key] for key in counter.keys()), {3})
		# ideally in a different order than previous read.

	def test_shuffled_read(self):
		# Read 3000 lines
		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader:
			lines1 = [line for _, line in zip(range(1000), reader)]
			lines2 = [line for _, line in zip(range(1000), reader)]
		#	We should have read the same lines
		self.assertEqual(frozenset(lines1), frozenset(lines2))
		# but in a different order
		self.assertNotEqual(lines1, lines2)

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

	def test_resume_offset(self):
		counter = Counter()

		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader1:
			counter.update(line for _, line in zip(range(250), reader1))
			state = reader1.state()

		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader2:
			reader2.restore(state)
			counter.update(line for _, line in zip(range(750), reader2))

		# We should have read 250 + 750 lines exactly
		self.assertEqual(len(counter), 1000)
		# and they should be all read only once.
		self.assertEqual(set(counter[key] for key in counter.keys()), {1})

	def test_resume_order(self):
		counter = Counter()

		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader1, \
			closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader2:
			lines1 = [line for _, line in zip(range(250), reader1)]
			reader2.restore(reader1.state())
			lines1.extend(line for _, line in zip(range(750), reader2))

		with closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader1, \
			closing(self.reader(Dataset('test', [TEST_FILE]), seed=1234)) as reader2:
			lines2 = [line for _, line in zip(range(500), reader1)]
			reader2.restore(reader1.state())
			lines2.extend(line for _, line in zip(range(500), reader2))

		# Both reads should have the same amount and unique sentences
		self.assertEqual(len(lines1), len(lines2))
		self.assertEqual(set(lines1), set(lines2))
		# They also should have the same order
		self.assertEqual(lines1, lines2)


class TestAsyncDatasetReader(TestDatasetReader):
	reader = AsyncDatasetReader


class TestTrainer(unittest.TestCase):
	def test_resume(self):
		config = {
			'datasets': {
				'clean': 'test/data/clean',
				'medium': 'test/data/medium',
				'dirty': 'test/data/dirty'
			},
			'stages': [
				'start',
				'mid'
			],
			'start': [
				'clean 0.8',
				'medium 0.2',
				'dirty 0',
				'until clean 1'
			],
			'mid': [
				'clean 0.6',
				'medium 0.3',
				'dirty 0.1',
				'until medium 1',
			],
			'seed': 1111
		}
		
		curriculum = CurriculumLoader().load(config)

		# Reference batches (trainer runs without resuming)
		with closing(Trainer(curriculum)) as trainer_ref:
			batches_ref = list(trainer_ref.run())

		# State tracker (using tmpdir to make sure the file does not exist)
		with tempfile.TemporaryDirectory() as tmpdir:
			state_tracker = StateTracker(os.path.join(tmpdir, 'state_file'))

			# Train on trainer1
			with closing(Trainer(curriculum)) as trainer1:
				batches = [batch for _, batch in zip(range(10), state_tracker.run(trainer1))]

			# Resume on trainer2
			with closing(Trainer(curriculum)) as trainer2:
				batches.extend(state_tracker.run(trainer2))
			
		self.assertEqual(batches, batches_ref)
