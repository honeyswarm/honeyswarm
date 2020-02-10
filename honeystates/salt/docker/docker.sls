python38:
  pkg.installed:
    - pkgs:
      - python3.8
      - python3-pip

dockerpy:
  cmd.run:
    - name: python3 -m pip install --upgrade pip docker
    #- require:
    #  - pkgs: python3.8


  # There seems to be an issue with the pip package on some systems
  # An importable Python 2 pip module is required
  #pip.installed:
  #  - name: docker
  #  - require:
  #    - pkg: python3-pip

import-docker-key:
  cmd.run:
    - names:
      - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
      - sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
      - apt-get update -yyq
    - creates: /etc/docker.lock

/etc/docker.lock:
  file.managed:
    - source: salt://docker/docker.lock

install_docker:
  pkg.installed:
    - pkgs:
      - apt-transport-https
      - ca-certificates
      - gnupg-agent
      - software-properties-common
      - docker-ce
      - docker-ce-cli
      - containerd.io

docker:
  service:
    - running
    - enable: True
    - reload: True