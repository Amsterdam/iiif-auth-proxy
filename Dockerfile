FROM amsterdam/python:3.8-buster
MAINTAINER datapunt@amsterdam.nl

EXPOSE 8000

ENV PYTHONUNBUFFERED 1
ENV CONSUL_HOST=${CONSUL_HOST:-notset}
ENV CONSUL_PORT=${CONSUL_PORT:-8500}

RUN adduser --system datapunt

RUN mkdir -p /app && chown datapunt /app
RUN mkdir -p /deploy && chown datapunt /deploy
RUN mkdir -p /var/log/uwsgi && chown datapunt /var/log/uwsgi

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
USER datapunt

COPY app /app/
COPY app/deploy /deploy/

CMD ["/deploy/docker-run.sh"]
