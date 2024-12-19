ARG UBUNTU_VERSION=22.04

FROM ubuntu:$UBUNTU_VERSION

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install software-properties-common && \
    DEBIAN_FRONTEND=noninteractive add-apt-repository -y ppa:deadsnakes/ppa && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3.11 python3.11-venv

COPY ./requirements.txt /requirements.txt

RUN python3.11 -m venv /markus_venv && \
    /markus_venv/bin/pip install wheel && \
    /markus_venv/bin/pip install -r /requirements.txt

WORKDIR /app

CMD /markus_venv/bin/python run.py
