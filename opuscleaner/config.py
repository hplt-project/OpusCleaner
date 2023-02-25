import os
import sys

# Path to data files. Expects to find files named `$DATASET.$LANG.gz`.
DATA_PATH = os.getenv('DATA_PATH', 'data/train-parts/*.*.gz')

# Path to the file that defines the categories, and which dataset belongs to 
# which.
CATEGORIES_PATH = os.path.join(os.path.dirname(DATA_PATH), 'categories.json')

DEFAULT_CATEGORIES = [
	{'name': 'clean'},
	{'name': 'medium'},
	{'name': 'dirty'}
]

# TODO: Derive this from DATA_PATH. The `train-parts` is a mtdata compatibility
# thing. I'm now used to also have a data/clean directory there, so keeping it.
DOWNLOAD_PATH = 'data/train-parts'

# glob expression that looks for the filter files. Unfortunately you can't use
# commas and {} in this expression. TODO: fix that, you should be able to name
# multiple paths.
FILTER_PATH = os.path.join(os.path.dirname(__file__), 'filters/*.json')

# col.py is used to apply a monolingual filter to a bilingual dataset. Needs
# to be absolute since filters can run from different cwds.
COL_PY = [sys.executable, '-m', 'opuscleaner.col']

# Program used to derive a sample from the dataset. Will be called like
# `./sample.py -n $SAMPLE_SIZE ...file-per-lang.gz`. Absolute because filters
# can specify their own `cwd`.
SAMPLE_PY = [sys.executable, '-m', 'opuscleaner.sample']

# Size of each of the three sections (head, random sample of middle, tail) of
# the dataset sample that we operate on.
SAMPLE_SIZE = int(os.getenv('SAMPLE_SIZE', '1000'))
