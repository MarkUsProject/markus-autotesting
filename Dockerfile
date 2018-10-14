FROM ubuntu:18.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      vim python3.7 python3.7-venv python3.7-distutils \
      redis-server openssh-server sudo runit git gcc libc6-dev wget curl zip unzip && \
    rm -rf /var/lib/apt/lists/*

RUN sed -i 's/root.*/root\tALL=(ALL:ALL) NOPASSWD:ALL\nmarkusserver\tALL=(ALL:ALL) NOPASSWD:ALL/g' /etc/sudoers && \
    chmod 750 /etc/sudoers

# reasonable docker defaults for the config
RUN mkdir -p /home/markusserver/work && \
    for user in markusserver $(bash -c "echo markusworker-{1..10}"); do \
      useradd -d "/home/${user}" -s /bin/bash "${user}" && \
      mkdir -p /home/${user}/ && \
      chown -R ${user}:${user} /home/${user}; \
    done
   
# configure redis
ADD redis.runit /etc/service/redis/run
RUN chmod 755 /etc/service/redis/run && \
    sed -i 's/port.*/# do not listen on a port\nport 0/g' /etc/redis/redis.conf && \
    sed -i 's/# unixsocket/unixsocket/g' /etc/redis/redis.conf && \
    sed -i 's/daemonize.*/daemonize no/g' /etc/redis/redis.conf && \
    mkdir -p /var/run/redis && \
    chmod 700 /var/run/redis && \
    chown -R markusserver:markusserver /etc/redis/ /var/log/redis/ /var/lib/redis/ /var/run/redis/

# configure openssh-server
ADD openssh.runit /etc/service/openssh/run
RUN chmod 755 /etc/service/openssh/run

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
CMD ["/entrypoint.sh"]

WORKDIR /opt/app/

#TODO HACK: The setup.sh script runs iptables regardless of if we are using a socket or not,
# out out for now.
RUN echo '#!/usr/bin/env bash\n true' > /usr/local/bin/iptables && chmod 755 /usr/local/bin/iptables

COPY . .

RUN sed -i 's/SERVER_USER.*/SERVER_USER = "markusserver"/g' server/config.py
RUN sed -i 's~WORKSPACE_DIR.*~WORKSPACE_DIR = "/home/markusserver/work/"~g' server/config.py
RUN sed -i 's/WORKER_USERS.*/WORKER_USERS = "'"$(bash -c "echo markusworker-{1..10}")"'"/g' server/config.py
RUN sed -i 's~REDIS_CONNECTION_KWARGS.*~REDIS_CONNECTION_KWARGS = {"unix_socket_path": "/var/run/redis/redis-server.sock"}~g' server/config.py

