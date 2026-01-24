FROM ubuntu:latest
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

COPY scripts/install.sh /tmp/install.sh
RUN chmod +x /tmp/install.sh && /tmp/install.sh

WORKDIR /app
CMD ["/bin/bash"]