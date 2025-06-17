import io
import unittest

from url_mismatch import filter_url_mismatch


class TestUrlMismatch(unittest.TestCase):
    def _test(self, line: str, **kwargs) -> bool:
        fin = io.StringIO(line)
        fout = io.StringIO()
        filter_url_mismatch(fin, fout, **kwargs)
        return fout.getvalue() == line

    def assertAccept(self, line: str, **kwargs):
        """Test that this line is accepted"""
        self.assertTrue(self._test(line, **kwargs))

    def assertReject(self, line: str, **kwargs):
        """Test that this line is rejected"""
        self.assertFalse(self._test(line, **kwargs))

    def test_match(self):
        """Exact matches should be accepted."""
        self.assertAccept('Purchase options on amazon.co.uk are great\tSomething else amazon.co.uk hello')

    def test_match_full(self):
        """Different URLs should be rejected."""
        self.assertReject('https://x.it/hello?test=1&yes=true is great\t hello https://x.com/hello?test=1&yes=true')

    def test_match_two(self):
        """Exact matches for multiple URLs should be accepted."""
        self.assertAccept('1 amazon.co.uk 2 amazon.it are great\tSomething else amazon.co.uk amazon.it hello')

    def test_mismatch(self):
        """Different URLs should be rejected."""
        self.assertReject('Purchase options on amazon.co.uk are great\tSomething else amazon.it hello')

    def test_mismatch_full(self):
        """Different URLs should be rejected."""
        self.assertReject('https://x.com/hello?test=1&yes=true is great\t hello https://x.it/hello?test=1&yes=true')

    def test_mismatch_two(self):
        """Different multiple URLs should be rejected."""
        self.assertReject('1 amazon.co.uk 2 amazon.it are great\t1 amazon.it 2 amazon.co.uk hello')

    def test_bad_end_of_sentence(self):
        """End of sentence without a space shouldn't be treated as a URL."""
        self.assertAccept('Hello world.World hello\tHello world. World hello')
