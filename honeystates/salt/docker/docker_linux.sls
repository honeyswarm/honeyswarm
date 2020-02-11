python38:
  pkg.installed:
    - pkgs:
      - python3.8
      - python3-pip
    - reload_modules: True

dockerpy:
  pip.installed:
    - name: docker
    - reload_modules: True

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
    - reload_modules: True

docker:
  service:
    - running
    - enable: True
    - reload: True