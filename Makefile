# This Makefile is based on the Makefile defined in the Python Best Practices repository:
# https://git.datapunt.amsterdam.nl/Datapunt/python-best-practices/blob/master/dependency_management/
.PHONY: app push deploy

dc = docker compose
run = $(dc) run --rm

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
	pip-compile --upgrade --output-file requirements_dev.txt --allow-unsafe requirements_dev.in

upgrade: requirements install       ## Run 'requirements' and 'install' targets

migrations:
	$(dc) run --rm app python manage.py makemigrations

migrate:
	$(dc) run --rm app python manage.py migrate

build:
	$(dc) build --progress=plain

push: build
	$(dc) push

app:
	$(dc) up app

dev:
	$(run) --service-ports dev

test: lint
	$(run) test pytest $(ARGS)

lintfix:             ## Execute lint fixes
	$(run) test black /src/$(APP) /tests/$(APP)
	$(run) test autoflake /src --recursive --in-place --remove-unused-variables --remove-all-unused-imports --quiet
	$(run) test isort /src/$(APP) /tests/$(APP)

lint:                ## Execute lint checks
	$(run) test black --check /src/$(APP) /tests/$(APP)
	$(run) test autoflake /src --check --recursive --quiet
	$(run) test isort --diff --check /src/$(APP) /tests/$(APP)

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
