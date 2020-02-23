# Basic PyRDP Honeypot

# We use a Volume mount till i can write a HPFeeds publisher for it. 

# Add Pillar - {{salt['pillar.get']('WINDOWSTARGET')}}

# Add the config file
create_dir:
  file.directory:
    - name: /etc/pyrdp
    - dir_mode: 777
    - file_mode: 777

pyrdp_container:
  docker_container.running:
    - name: honeypot_pyrdp
    - image: gosecure/pyrdp
    - replace: true
    - port_bindings:
      - 3389:3389
    - binds: /etc/pyrdp/:/home/pyrdp/pyrdp_output
    - command: pyrdp-mitm.py 192.168.1.161
