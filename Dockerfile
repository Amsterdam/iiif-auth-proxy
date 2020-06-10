FROM amsterdam/python:3.8-buster
MAINTAINER datapunt@amsterdam.nl

EXPOSE 8000

# stunnel4 is for adding the client side certificate to the wabo requests
RUN apt update -y && \
    apt install -y --no-install-recommends stunnel4 && \
    rm -rf /var/lib/apt/lists/*


ENV PYTHONUNBUFFERED 1
ENV CONSUL_HOST=${CONSUL_HOST:-notset}
ENV CONSUL_PORT=${CONSUL_PORT:-8500}

RUN adduser --system datapunt

RUN mkdir -p /src && chown datapunt /src
RUN mkdir -p /deploy && chown datapunt /deploy
RUN mkdir -p /var/log/uwsgi && chown datapunt /var/log/uwsgi

WORKDIR /src
COPY requirements.txt /src/
RUN pip install --no-cache-dir -r requirements.txt
USER datapunt

COPY src /src/
COPY src/deploy /deploy/

CMD ["/deploy/docker-run.sh"]
