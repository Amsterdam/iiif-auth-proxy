# This Makefile is based on the Makefile defined in the Python Best Practices repository:
# https://git.datapunt.amsterdam.nl/Datapunt/python-best-practices/blob/master/dependency_management/
.PHONY: app push deploy

UID:=$(shell id --user)
GID:=$(shell id --group)

dc = docker compose
run = $(dc) run --remove-orphans --rm -u ${UID}:${GID}
manage = $(run) dev python manage.py

help:                               ## Show this help.
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

pip-tools:
	pip install pip-tools

install: pip-tools                  ## Install requirements and sync venv with expected state as defined in requirements.txt
	pip-sync requirements_dev.txt

requirements: pip-tools             ## Upgrade requirements (in requirements.in) to latest versions and compile requirements.txt
	## The --allow-unsafe flag should be used and will become the default behaviour of pip-compile in the future
	## https://stackoverflow.com/questions/58843905
	pip-compile --upgrade --output-file requirements.txt --allow-unsafe requirements.in
	pip-compile --upgrade --output-file requirements_linting.txt --allow-unsafe requirements_linting.in
	pip-compile --upgrade --output-file requirements_dev.txt --allow-unsafe requirements_dev.in

upgrade: requirements install       ## Run 'requirements' and 'install' targets

migrations:
	$(manage) makemigrations

migrate:
	$(manage) migrate

build:
	$(dc) build --progress=plain

push: build
	$(dc) push

app:
	$(dc) up app

dev:
	$(run) --service-ports dev

dev-consume-zips:
	$(manage) consume_zips

test:
	$(run) test pytest $(ARGS)

lintfix:             ## Execute lint fixes
	$(run) linting black /app/src/$(APP) /app/tests/$(APP)
	$(run) linting autoflake /app/src --recursive --in-place --remove-unused-variables --remove-all-unused-imports --quiet
	$(run) linting isort /app/src/$(APP) /app/tests/$(APP)

lint:                ## Execute lint checks
	$(run) linting black --check /app/src/$(APP) /app/tests/$(APP)
	$(run) linting autoflake /app/src --check --recursive --quiet
	$(run) linting isort --diff --check /app/src/$(APP) /app/tests/$(APP)

pdb:
	$(run) test pytest --pdb $(ARGS)

clean:
	$(dc) down -v

bash:
	$(run) dev bash

env:
	env | sort

trivy: 								## Detect image vulnerabilities
	$(dc) build app
	trivy image --ignore-unfixed docker-registry.data.amsterdam.nl/datapunt/iiif-auth-proxy
