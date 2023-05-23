FROM python:3.8-buster as app
MAINTAINER datapunt@amsterdam.nl

EXPOSE 8000

ENV PYTHONUNBUFFERED 1
ENV CONSUL_HOST=${CONSUL_HOST:-notset}
ENV CONSUL_PORT=${CONSUL_PORT:-8500}
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY certs/* /usr/local/share/ca-certificates/extras/

RUN apt-get update \
 && apt-get dist-upgrade -y \
 && apt-get install --no-install-recommends -y \
        gdal-bin \
 && pip install --upgrade pip \
 && pip install uwsgi \
 && useradd --user-group --system datapunt

# Edit the openssl.cnf file to allow a lower security level.
# This is needed to directly call the wabo data
# TODO: remove this when we get a more secure cert for the wabo server
RUN sed -i "s|MinProtocol = TLSv1.2|MinProtocol = None|g" /etc/ssl/openssl.cnf
RUN sed -i "s|CipherString = DEFAULT@SECLEVEL=2|CipherString = DEFAULT|g" /etc/ssl/openssl.cnf

RUN adduser --system datapunt

RUN mkdir -p /src && chown datapunt /src
RUN mkdir -p /deploy && chown datapunt /deploy
RUN mkdir -p /var/log/uwsgi && chown datapunt /var/log/uwsgi

WORKDIR /src
COPY requirements.txt /src/
RUN pip install --no-cache-dir -r requirements.txt
USER datapunt

COPY src /src/
COPY deploy /deploy/

CMD ["/deploy/docker-run.sh"]


# stage 2, dev
FROM app as dev

USER root
WORKDIR /app_install
ADD requirements_dev.txt requirements_dev.txt
RUN pip install -r requirements_dev.txt

WORKDIR /src
USER datapunt

# Any process that requires to write in the home dir
# we write to /tmp since we have no home dir
ENV HOME /tmp

CMD ["./manage.py", "runserver", "0.0.0.0:8000"]


# stage 3, tests
FROM dev as tests

WORKDIR /tests
COPY pyproject.toml /.
ENV COVERAGE_FILE=/tmp/.coverage
ENV PYTHONPATH=/src
