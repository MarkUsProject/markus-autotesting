# syntax=docker/dockerfile:1.7-labs
ARG UBUNTU_VERSION=24.04

FROM ubuntu:$UBUNTU_VERSION AS base

# Remove ubuntu user, added in the 23.04 image
RUN userdel -r ubuntu

ARG LOGIN_USER
ARG WORKSPACE

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install software-properties-common && \
    DEBIAN_FRONTEND=noninteractive add-apt-repository -y ppa:deadsnakes/ppa && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install python3.11 \
                       python3.11-venv \
                       python3.12 \
                       python3.12-venv \
                       python3.13 \
                       python3.13-venv \
                       redis-server \
                       postgresql-client \
                       libpq-dev \
                       sudo \
                       git

RUN useradd -ms /bin/bash $LOGIN_USER && \
    usermod -aG sudo $LOGIN_USER && \
    for worker in autotst0 autotst1 autotst2 autotst3; do \
        adduser --disabled-login --no-create-home $worker && \
        echo "$LOGIN_USER ALL=($worker) NOPASSWD:ALL" | EDITOR="tee -a" visudo && \
        usermod -aG $worker $LOGIN_USER; \
    done && \
    chmod a+x /home/${LOGIN_USER}

RUN mkdir -p ${WORKSPACE} && chown ${LOGIN_USER} ${WORKSPACE} && \
    mkdir -p /home/${LOGIN_USER}/markus_venv && chown ${LOGIN_USER} /home/${LOGIN_USER}/markus_venv


# Copy requirements.system files for all testers. These are copied separately from other files
# to avoid Docker cache invalidation of the subsequent RUN command if any other files are changed
# in markus-autotesting/server.
COPY --parents \
    ./autotest_server/testers/java/requirements.system \
    ./autotest_server/testers/haskell/requirements.system \
    ./autotest_server/testers/r/requirements.system \
    ./autotest_server/testers/racket/requirements.system \
    /app
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=$WORKSPACE/.stack,sharing=locked \
    find /app/autotest_server/testers -name requirements.system -exec {} \;

COPY . /app

WORKDIR /home/${LOGIN_USER}

USER ${LOGIN_USER}

CMD ["/app/.dockerfiles/cmd-dev.sh"]
