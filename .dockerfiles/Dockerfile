ARG UBUNTU_VERSION

FROM ubuntu:$UBUNTU_VERSION

ARG LOGIN_USER

RUN apt-get update && \
    apt-get -y install sudo && \
    apt-get -y install openssh-server

RUN mkdir /var/run/sshd && chmod 755 /var/run/sshd

# Create a directory for the app code (keep the name generic)
RUN mkdir -p /app

RUN useradd -ms /bin/bash $LOGIN_USER && \
    usermod -aG sudo $LOGIN_USER && \
    echo "$LOGIN_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee "/etc/sudoers.d/$LOGIN_USER"

RUN mkdir /ssh_pub_key && touch /ssh_pub_key/authorized_keys

USER $LOGIN_USER
RUN mkdir /home/$LOGIN_USER/.ssh && \
    chown $LOGIN_USER. /home/$LOGIN_USER/.ssh && \
    chmod 700 /home/$LOGIN_USER/.ssh && \
    ln -s /ssh_pub_key/authorized_keys /home/$LOGIN_USER/.ssh/authorized_keys

WORKDIR /app
