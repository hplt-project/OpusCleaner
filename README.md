# Dependencies
(Mainly listed as shortcuts to documentation)

- [FastAPI](https://fastapi.tiangolo.com) as the base for the backend part.
- [Pydantic](https://pydantic-docs.helpmanual.io/) for conversion of untyped JSON to typed objects. And because FastAPI automatically supports it and gives you useful error messages if you mess up things.
- [Vue](https://vuejs.org/guide/introduction.html) for frontend, using native module support so no npm build step 🎉
- uvicorn to run the damn thing.

# Paths
- `data/train-parts` is scanned for datasets
- `filters` should contain filter json (but that's not implemented yet, right now it just has a hard-coded `FILTERS` dict in code)

# Installation for development
First, get some datasets together, e.g.
```sh
mkdir -p data
mtdata get -l ara-eng -tr OPUS-elrc_2922-v1-ara-eng --compress -o data
mtdata get -l fra-eng -tr OPUS-elitr-eva-v1-eng-fra --compress -o data
```

Then for development:
```sh
python3 -m venv .env
bash --init-file .env/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then go to http://127.0.0.1:8000/ for the "interface" or http://127.0.0.1:8000/docs for the API.
