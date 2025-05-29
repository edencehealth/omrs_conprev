FROM python:3.11-alpine
LABEL maintainer="edenceHealth <info@edence.health>"

COPY requirements.txt /

ARG AG="apt-get -yq --no-install-recommends"
ARG DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
  apk add --update-cache \
    mariadb-connector-c \
  ; \
  apk add --virtual build-dependencies \
    gcc \
    mariadb-connector-c-dev \
    musl-dev \
  ; \
  pip install -r /requirements.txt; \
  pip cache purge; \
  apk del build-dependencies; \
  rm -rf \
    /var/cache/apk/* \
    ~/.cache \
  ;

WORKDIR /app
COPY src/omrs_conprev /app/omrs_conprev
ENV PYTHONPATH="/app"

VOLUME [ "/output" ]
WORKDIR /output
ENTRYPOINT ["python3", "-m", "omrs_conprev"]
