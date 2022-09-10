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
```sh
python3 -m venv .env
bash --init-file .env/bin/activate
pip install -r requirements.txt

mkdir -p data
mtdata get -l ara-eng -tr OPUS-elrc_2922-v1-ara-eng --compress -o data
mtdata get -l fra-eng -tr OPUS-elitr_eca-v1-eng-fra --compress -o data

cd frontend
npm clean-install
npm run build
cd ..

./main.py serve --reload
```

If you're doing frontend developemnt, try also running:
```sh
cd frontend
npm run dev
```

This will put vite in hot-reloading mode for easier javascript dev. All api requests will be proxied to the `main.py serve` running in 8000.

If you want to use LASER, you will also need to download its assets:

```sh
python -m laserembeddings download-models
```

Then go to http://127.0.0.1:8000/ for the "interface" or http://127.0.0.1:8000/docs for the API.
