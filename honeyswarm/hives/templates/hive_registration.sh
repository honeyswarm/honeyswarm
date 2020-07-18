#!/usr/bin/env sh

# This forces Python3 instal
# For supported versions - https://github.com/saltstack/salt-bootstrap#python-3-support

curl -o bootstrap-salt.sh -L https://bootstrap.saltstack.com
sudo sh bootstrap-salt.sh -x python3 -A {{honeyswarm_host}} -i {{salt_minion_id}}