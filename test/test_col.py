import sys
import unittest
import subprocess
from typing import List, Tuple
from textwrap import dedent

from opuscleaner.config import COL_PY


TEST_INPUT = "".join(
    [
        "Hello\tHallo\n",
        "Goodbye\tBye\n",
        "Beep\t\n",
        "\t\n",
        "beep\tboop\n",
        "\tboop\n",
    ]
)


TEST_INPUT_SANE = "".join(
    [
        "Hello\tHallo\n",
        "Goodbye\tTot ziens\n",
        "Monitor\tComputerscherm\n",
        "Outside world\tBuitenwereld\n",
    ]
)


TEST_INPUT_COL_MISSING = "".join([*TEST_INPUT, "single-col\n", *TEST_INPUT_SANE])

TEST_INPUT_COL_OVERFLOW = "".join(
    [*TEST_INPUT, "triple-col\ttriple-col\ttriple-col\n", *TEST_INPUT_SANE]
)


class TestCol(unittest.TestCase):
    def _run(self, args: List[str], input: str) -> Tuple[str, str, int]:
        proc = subprocess.Popen(
            COL_PY + args,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate(input)
        proc.stdin.close()
        proc.wait()
        return out, err, proc.returncode

    def test_reproduce_sane(self):
        """Sane input should not be a problem."""
        reproduce = dedent("""
			import sys
			for line in sys.stdin:
				sys.stdout.write(line)
		""")

        out, err, retval = self._run(
            ["0", sys.executable, "-u", "-c", reproduce], TEST_INPUT_SANE
        )
        self.assertEqual(out, TEST_INPUT_SANE)
        (self.assertEqual(err, ""),)
        self.assertEqual(retval, 0)

    def test_reproduce_streaming(self):
        """Test that subprocess that reads one line, writes one line, works"""
        reproduce = dedent("""
			import sys
			for line in sys.stdin:
				sys.stdout.write(line)
		""")

        out, err, retval = self._run(
            ["0", sys.executable, "-u", "-c", reproduce], TEST_INPUT
        )
        self.assertEqual(out, TEST_INPUT)
        (self.assertEqual(err, ""),)
        self.assertEqual(retval, 0)

    def test_reproduce_buffering(self):
        """Test that a subprocess that reads the entire input to memory before generating output works."""
        reproduce = dedent("""
			import sys
			sys.stdout.write(sys.stdin.read())
		""")

        for colset in ("0", "1", "0,1"):
            with self.subTest(colset=colset):
                out, err, retval = self._run(
                    [colset, sys.executable, "-c", reproduce], TEST_INPUT
                )
                self.assertEqual(out, TEST_INPUT)
                (self.assertEqual(err, ""),)
                self.assertEqual(retval, 0)

    def test_overproduce(self):
        """Test that an overproducing program is caught"""
        overproduce = dedent("""
			import sys
			for line in sys.stdin:
				sys.stdout.write(line)
				sys.stdout.write(line)
		""")

        out, err, retval = self._run(
            ["0", sys.executable, "-c", overproduce], TEST_INPUT
        )
        self.assertIn("subprocess produced more lines of output than it was given", err)
        self.assertNotEqual(retval, 0)

    def test_underproduce(self):
        """Test that an underproducing program is caught"""
        underproduce = dedent("""
			import sys
			for n, line in enumerate(sys.stdin):
				if n % 2 == 0:
					sys.stdout.write(line)
		""")

        out, err, retval = self._run(
            ["0", sys.executable, "-c", underproduce], TEST_INPUT
        )
        self.assertIn("subprocess produced fewer lines than it was given", err)
        self.assertNotEqual(retval, 0)

    def test_error_incorrect_subprocess(self):
        """Test that an unclean exit from a subprocess is caught."""
        underproduce = dedent("""
			import sys
			sys.exit(42)
		""")

        out, err, retval = self._run(
            ["0", sys.executable, "-c", underproduce], TEST_INPUT
        )
        self.assertEqual(retval, 42)

    def test_error_correct_subprocess(self):
        """Test that an unclean exit from a subprocess is caught even if the output looks sane."""
        underproduce = dedent("""
			import sys
			for line in sys.stdin:
				sys.stdout.write(line)
			sys.exit(42)
		""")

        out, err, retval = self._run(
            ["0", sys.executable, "-c", underproduce], TEST_INPUT
        )
        self.assertEqual(retval, 42)
        self.assertIn("subprocess exited with status code 42", err)

    def test_error_col_missing(self):
        """A missing column in the input should raise an error"""
        reproduce = dedent("""
			import sys
			for line in sys.stdin:
				sys.stdout.write(line)
		""")

        out, err, retval = self._run(
            ["1", sys.executable, "-u", "-c", reproduce], TEST_INPUT_COL_MISSING
        )
        self.assertEqual(retval, 1)
        self.assertIn("line contains a different number of fields", err)

    def test_error_col_overflow(self):
        """A line with too many columns should raise an error"""
        reproduce = dedent("""
			import sys
			for line in sys.stdin:
				sys.stdout.write(line)
		""")

        out, err, retval = self._run(
            ["1", sys.executable, "-u", "-c", reproduce], TEST_INPUT_COL_OVERFLOW
        )
        self.assertEqual(retval, 1)
        self.assertIn("line contains a different number of fields", err)
