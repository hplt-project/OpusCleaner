import io
import unittest

from num_mismatch import filter_numerical_mismatch

class TestNumMismatch(unittest.TestCase):
	def _test(self, line:str, ratio:float, **kwargs) -> bool:
		fin = io.StringIO(line)
		fout = io.StringIO()
		filter_numerical_mismatch(fin, fout, ratio, **kwargs)
		return fout.getvalue() == line

	def assertAccept(self, line:str, ratio:float, **kwargs):
		"""Test that this line is accepted"""
		self.assertTrue(self._test(line, ratio, **kwargs))

	def assertReject(self, line:str, ratio:float, **kwargs):
		"""Test that this line is rejected"""
		self.assertFalse(self._test(line, ratio, **kwargs))

	def test_match(self):
		"""Exact matches should be accepted."""
		self.assertAccept('There are 74 cows\t74 cows have we', 1.0)

	def test_accepted_comma_mismatch(self):
		"""Differences in the decimal separator should be accepted."""
		self.assertAccept('There are 7.4 cows\t7,4 cows have we', 1.0)

	def test_mismatch(self):
		"""Differences in the number should be rejected."""
		self.assertReject('There are 73 cows\t74 cows have we', 1.0)

	def test_ratio(self):
		"""Lowering the ratio threshold will accept mismatches"""
		line = 'There are 73 cows in 6 fields\tWe have 6 fields with 74 cows' # 2 / 3 = 0.667
		self.assertAccept(line, 0.5)
		self.assertReject(line, 1.0)

	def test_prefix_zero(self):
		"""Numbers like 06 and 6 should be the same. See #89"""
		self.assertAccept('These are the same 007 numbers\tThe number is 7', 1.0)

	def test_sign_match(self):
		"""Signs matter."""
		self.assertAccept('The current temp is -7.5 degrees\tI lost -7.5 points', 1.0)
		self.assertReject('The current temp is -7.5 degrees\tI walked 7.5 miles', 1.0)
		self.assertReject('The difference is +7.5 degrees\tI walked 7.5 miles', 1.0) # questionable?
		self.assertReject('The current temp is -7.5 degrees\tI changed the value by +7.5', 1.0)

	def test_word_boundary(self):
		self.assertAccept('I am a 30something\tThat just40 should be ignored', 1.0)
	
	def test_word_boundary_dash(self):
		self.assertAccept('-30 is the number\tThe number -30', 1.0)
		self.assertAccept('The-number-30\tThe number 30', 1.0)
		self.assertReject('Beep-30\tThe number is -30', 1.0)
