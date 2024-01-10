ARG UBUNTU_VERSION

FROM ubuntu:$UBUNTU_VERSION

RUN apt-get update -y && \
    apt-get -y install software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get install -y python3.11 python3.11-venv

COPY ./requirements.txt /requirements.txt

RUN python3.11 -m venv /markus_venv && \
    /markus_venv/bin/pip install wheel && \
    /markus_venv/bin/pip install -r /requirements.txt

WORKDIR /app

CMD /markus_venv/bin/python run.py
