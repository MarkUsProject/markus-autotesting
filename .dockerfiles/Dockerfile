ARG UBUNTU_VERSION

FROM ubuntu:$UBUNTU_VERSION

ARG LOGIN_USER

RUN apt-get update && \
    apt-get -y install sudo

# Create a directory for the app code (keep the name generic)
RUN mkdir -p /app

RUN useradd -ms /bin/bash $LOGIN_USER && \
    usermod -aG sudo $LOGIN_USER && \
    echo "$LOGIN_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee "/etc/sudoers.d/$LOGIN_USER"

USER $LOGIN_USER

WORKDIR /app
