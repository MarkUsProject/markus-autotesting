ARG UBUNTU_VERSION

FROM ubuntu:$UBUNTU_VERSION as base


ARG LOGIN_USER
ARG WORKSPACE

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install software-properties-common && \
    DEBIAN_FRONTEND=noninteractive add-apt-repository -y ppa:deadsnakes/ppa && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install python3.7 \
                       python3.7-venv \
                       python3.8 \
                       python3.8-venv \
                       python3.9 \
                       python3.9-venv \
                       python3.10 \
                       python3.10-venv \
                       python3.11 \
                       python3.11-venv \
                       python3.12 \
                       python3.12-venv \
                       redis-server \
                       postgresql-client \
                       libpq-dev \
                       sudo \
                       git \
                       libfontconfig1-dev \
                       libcurl4-openssl-dev \
                       libfreetype6-dev \
                       libpng-dev \
                       libtiff5-dev \
                       libjpeg-dev \
                       libharfbuzz-dev \
                       libfribidi-dev \
                       r-base

RUN useradd -ms /bin/bash $LOGIN_USER && \
    usermod -aG sudo $LOGIN_USER && \
    for worker in autotst0 autotst1 autotst2 autotst3; do \
        adduser --disabled-login --no-create-home $worker && \
        echo "$LOGIN_USER ALL=($worker) NOPASSWD:ALL" | EDITOR="tee -a" visudo && \
        usermod -aG $worker $LOGIN_USER; \
    done

RUN chmod a+x /home/${LOGIN_USER}

COPY . /app

RUN python3.11 -m venv /markus_venv && \
    /markus_venv/bin/pip install wheel && \
    /markus_venv/bin/pip install -r /app/requirements.txt && \
    find /app/autotest_server/testers -name requirements.system -exec {} \; && \
    rm -rf /app/*

RUN echo "TZ=$( cat /etc/timezone )" >> /etc/R/Renviron.site

RUN mkdir -p ${WORKSPACE} && chown ${LOGIN_USER} ${WORKSPACE}

WORKDIR /home/${LOGIN_USER}

USER ${LOGIN_USER}

CMD /app/.dockerfiles/cmd-dev.sh
