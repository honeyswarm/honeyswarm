FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV BASE_APPS="python3.8 python3-pip git supervisor"

RUN apt-get update && apt-get install --reinstall -yqq \
      $BASE_APPS \
    && apt-get -y clean \
    && apt-get -y autoremove


#Clean up the envars
RUN unset BASE_APPS

# Symlink for Python
RUN ln -s /usr/bin/python3.8 /usr/bin/python

# Add file system
ADD docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
RUN ln -s /usr/local/bin/docker-entrypoint.sh /

# HPFeeds

# Add Honeyswarm
ADD honeyswarm /opt/honeyswarm

WORKDIR /opt/honeyswarm
RUN python -m pip install -r requirements.txt
RUN python -m pip install -r requirements-salt.txt


# Run the container


ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["flask", "run"]