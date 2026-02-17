ARG PYTHON_VERSION=3.13

# Builder
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED 1

RUN set -eux && \
    python -m ensurepip --upgrade && \
    apt-get update && apt-get install -y \
      gcc  \
      libjpeg-dev \
      libtiff5-dev \
      libfreetype6-dev \
      zlib1g-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app/install

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


FROM python:${PYTHON_VERSION}-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED 1

ENV CONSUL_HOST=${CONSUL_HOST:-notset}
ENV CONSUL_PORT=${CONSUL_PORT:-8500}

ARG USE_JWKS_TEST_KEY=true

RUN set -eux && \
    python -m ensurepip --upgrade && \
    apt-get update && apt-get install -y \
        libgeos3.11.1 \
        gdal-bin && \
    useradd --user-group --system datapunt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Edit the openssl.cnf file to allow a lower security level.
# This is needed to directly call the wabo data
# TODO: remove this when we get a more secure cert for the wabo server
RUN sed -i "s|MinProtocol = TLSv1.2|MinProtocol = None|g" /etc/ssl/openssl.cnf
RUN sed -i "s|CipherString = DEFAULT@SECLEVEL=2|CipherString = DEFAULT|g" /etc/ssl/openssl.cnf

# Copy the Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin

WORKDIR /app
COPY src src

WORKDIR /app/src
ARG SECRET_KEY=collectstatic
RUN python manage.py collectstatic --no-input

USER datapunt

CMD ["uwsgi", "--ini", "/app/src/main/uwsgi.ini"]


# stage 2, dev
FROM app AS dev

USER root
WORKDIR /app/install

COPY requirements_dev.txt requirements_dev.txt

RUN pip install --no-cache-dir -r requirements_dev.txt

WORKDIR /app/src
USER datapunt

# Any process that requires to write in the home dir
# we write to /tmp since we have no home dir
ENV HOME /tmp

CMD ["./manage.py", "runserver", "0.0.0.0"]


# stage 3, tests
FROM dev AS tests

WORKDIR /app
COPY . .

USER datapunt

ENV COVERAGE_FILE=/tmp/.coverage

CMD ["pytest"]

# linting
FROM python:${PYTHON_VERSION}-slim-bookworm AS linting

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements_linting.txt
