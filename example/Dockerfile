FROM ubuntu:18.04
ADD https://dl.google.com/android/repository/sdk-tools-linux-4333796.zip /tmp/android-sdk.zip

FROM ubuntu:18.04
ADD https://services.gradle.org/distributions/gradle-4.10.2-bin.zip /tmp/gradle.zip

FROM markus-autotester

RUN apt-get update && \
    apt-get -y --no-install-recommends install openjdk-8-jdk && \
    rm -rf /var/lib/apt/lists/*

COPY --from=1 /tmp/gradle.zip /tmp/gradle.zip
RUN cd /tmp && unzip gradle.zip && \
    mv gradle-4.10.2 /opt/gradle && \
    ln -s /opt/gradle/bin/gradle /usr/local/bin/ && \
    rm /tmp/gradle.zip

COPY --from=0 /tmp/android-sdk.zip /opt/android-sdk/android-sdk.zip
RUN cd /opt/android-sdk && unzip android-sdk.zip && rm -f android-sdk.zip && \
   ln -s /opt/android-sdk/tools/bin/* /usr/local/bin/ && \
   yes | sdkmanager --licenses
   
COPY android-project /tmp/android-project
RUN cd /tmp/android-project && \
    gradle wrapper && \
    gradle build


RUN rm -rf /tmp/android-project/app/build && \
    rm -rf /tmp/android-project/app/src/main && \
    cp -r /root/.gradle /root/.android /tmp/ && \
    find /tmp/.gradle/ /tmp/android-project/ /tmp/.android/ ! -perm -a+r -exec chmod a+r {} \; && \
    find /tmp/.gradle/ /tmp/android-project/ /tmp/.android/ -type d ! -perm -a+x -exec chmod a+x {} \;

    

ADD authorized_keys /home/markusserver/.ssh/authorized_keys
RUN chown -R markusserver:markusserver /home/markusserver && \
    chmod 600 /home/markusserver/.ssh/authorized_keys


