FROM node as frontend
COPY frontend /root/frontend
WORKDIR /root/frontend
RUN npm ci && npm run build

FROM python as wheel
WORKDIR /root/
RUN mkdir frontend
COPY --from=frontend /root/frontend/dist ./frontend/dist
COPY README.md requirements.txt requirements-all.txt pyproject.toml ./
COPY opuscleaner ./opuscleaner
RUN python3 -m pip wheel -w ./wheelhouse ./

FROM python
COPY --from=wheel /root/wheelhouse/*.whl ./
RUN python3 -m pip install ./*.whl

CMD ["opuscleaner-server", "serve", "--host", "0.0.0.0"]
