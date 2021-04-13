ARG UBUNTU_VERSION

FROM ubuntu:$UBUNTU_VERSION

RUN apt-get update -y && apt-get install -y python3 python3-venv

COPY ./requirements.txt /requirements.txt

RUN python3 -m venv /markus_venv && \
    /markus_venv/bin/pip install -r /requirements.txt

WORKDIR /app

CMD /markus_venv/bin/python run.py
