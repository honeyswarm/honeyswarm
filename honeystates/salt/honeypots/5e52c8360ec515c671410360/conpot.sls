# Basic Conpot Honeypot

conpot_container:
  docker_container.running:
    - name: honeypot_conpot
    - image: honeynet/conpot
    - replace: true
    - port_bindings:
      - 80:8800 
      - 502:5020
      - 102:10201
      - 161:16100
      - 478:47808
      - 623:6230
      - 21:2121
      - 69:6969
