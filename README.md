# OpusCleaner
OpusCleaner is a machine translation/language model data cleaner and training scheduler. The Training scheduler has moved to [OpusTrainer](https://github.com/hplt-project/OpusTrainer).

## Cleaner
The cleaner bit takes care of downloading and cleaning multiple different datasets and preparing them for translation.

```sh
opuscleaner-clean --parallel 4 data/train-parts/dataset.filter.json | gzip -c > clean.gz
```

### Installation for cleaning
If you just want to use OpusCleaner for cleaning, you can install it from PyPI, and then run it

```sh
pip3 install opuscleaner
opuscleaner-server
```

Then you can go to http://127.0.0.1:8000/ to show the interface.

You can also install and run OpusCleaner on a remote machine, and use [SSH local forwarding](https://www.ssh.com/academy/ssh/tunneling-example) (e.g. `ssh -L 8000:localhost:8000 you@remote.machine`) to access the interface on your local machine.

### Dependencies
(Mainly listed as shortcuts to documentation)

- [FastAPI](https://fastapi.tiangolo.com) as the base for the backend part.
- [Pydantic](https://pydantic-docs.helpmanual.io/) for conversion of untyped JSON to typed objects. And because FastAPI automatically supports it and gives you useful error messages if you mess up things.
- [Vue](https://vuejs.org/guide/introduction.html) for frontend

### Screenshots

List and categorize the datasets you are going to use for training.
[<img src="https://github.com/hplt-project/OpusCleaner/raw/main/.github/screenshots/list-datasets.png" width="100%">](https://github.com/hplt-project/OpusCleaner/blob/main/.github/screenshots/list-datasets.png)

Download more datasets right from the interface.
[<img src="https://github.com/hplt-project/OpusCleaner/raw/main/.github/screenshots/add-datasets.png" width="100%">](https://github.com/hplt-project/OpusCleaner/blob/main/.github/screenshots/add-datasets.png)

Filter each individual dataset, showing you the results immediately.
[<img src="https://github.com/hplt-project/OpusCleaner/raw/main/.github/screenshots/filter-datasets.png" width="100%">](https://github.com/hplt-project/OpusCleaner/blob/main/.github/screenshots/filter-datasets.png)

Compare the dataset at different stages of filtering to see what the impact is of each filter.
[<img src="https://github.com/hplt-project/OpusCleaner/raw/main/.github/screenshots/diff-filter-output.png" width="100%">](https://github.com/hplt-project/OpusCleaner/blob/main/.github/screenshots/diff-filter-output.png)

### Using your own data
OpusCleaner scans for datasets and finds them automatically if they're in the right format. When you download OPUS data, it will get converted to this format, and there's nothing stopping you from adding your own in the same format.

By default, it scans for files matching `data/train-parts/*.*.gz` and will derive which files make up a dataset from the filenames: `name.en.gz` and `name.de.gz` will be a dataset called _name_. The files are your standard moses format: a single sentence per line, and each Nth line in the first file will match with the Nth line of the second file.

When in doubt, just download one of the OPUS datasets through OpusCleaner, and replicate the format for your own dataset.

If you want to use another path, you can use the `DATA_PATH` environment variable to change it, e.g. run `DATA_PATH="./my-datasets/*.*.gz" opuscleaner-server`.

### Paths
- `data/train-parts` is scanned for datasets. You can change this by setting the `DATA_PATH` environment variable, the default is `data/train-parts/*.*.gz`.
- `filters` should contain filter json files. You can change the `FILTER_PATH` environment variable, the default is `<PYTHON_PACKAGE>/filters/*.json`.


### Installation for development
For building from source (i.e. git, not anything downloaded from Pypi) you'll need to have node + npm installed.

```sh
python3 -m venv .env
bash --init-file .env/bin/activate
pip install -e .
```

Finally you can run `opuscleaner-server` as normal. The `--reload` option will cause it to restart when any of the python files change.

```sh
opuscleaner-server serve --reload
```

Then go to http://127.0.0.1:8000/ for the "interface" or http://127.0.0.1:8000/docs for the API.

### Frontend development

If you're doing frontend development, try also running:

```sh
cd frontend
npm run dev
```

Then go to http://127.0.0.1:5173/ for the "interface".

This will put vite in hot-reloading mode for easier Javascript dev. All API requests will be proxied to the python server running in 8000, which is why you need to run both at the same time.

## Filters

If you want to use LASER, you will also need to download its assets:

```sh
python -m laserembeddings download-models
```

## Packaging

Run `npm build` in the `frontend/` directory first, and then run `hatch build .` in the project directory to build the wheel and source distribution.

To push a new release to Pypi from Github, tag a commit with a `vX.Y.Z` version number (including the `v` prefix). Then publish a release on Github. This should trigger a workflow that pushes a sdist + wheel to pypi.

# Acknowledgements

This project has received funding from the European Union’s Horizon Europe research and innovation programme under grant agreement No 101070350 and from UK Research and Innovation (UKRI) under the UK government’s Horizon Europe funding guarantee [grant number 10052546]
