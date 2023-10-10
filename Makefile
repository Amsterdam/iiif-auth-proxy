# This Makefile is based on the Makefile defined in the Python Best Practices repository:
# https://git.datapunt.amsterdam.nl/Datapunt/python-best-practices/blob/master/dependency_management/
.PHONY: app manifests push deploy

dc = docker compose
run = $(dc) run --rm

REGISTRY ?= localhost:5000
ENVIRONMENT ?= local
VERSION ?= latest
HELM_ARGS = manifests/chart \
	-f manifests/values.yaml \
	-f manifests/env/${ENVIRONMENT}.yaml \
	--set image.tag=${VERSION} \
	--set image.registry=${REGISTRY}


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


lint:                               ## Execute lint checks
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

deploy: manifests
	helm upgrade --install iiif-auth-proxy $(HELM_ARGS) $(ARGS)

destroy:
	helm uninstall iiif-auth-proxy

manifests:
	helm template iiif-auth-proxy $(HELM_ARGS) $(ARGS)

update-chart:
	rm -rf manifests/chart
	git clone --branch 1.7.0 --depth 1 git@github.com:Amsterdam/helm-application.git manifests/chart
	rm -rf manifests/chart/.git
