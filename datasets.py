import os
from itertools import groupby

def list_datasets(path):
	with os.scandir(path) as entries:
		files = [
			entry
			for entry in entries
			if entry.is_file() 
			and entry.name.endswith('.gz')
			and not entry.name.startswith('.')
		]

	return {
		name: {
			entry.name.rsplit('.', 2)[1]: entry
			for entry in files
		}
		for name, files in groupby(
			sorted(files, key=lambda entry: entry.name),
			key=lambda entry: entry.name.rsplit('.', 2)[0])
	}

if __name__ == '__main__':
	import sys, pprint
	pprint.pprint(list_datasets(sys.argv[1]))