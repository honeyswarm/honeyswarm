#!/usr/bin/env sh
curl -o bootstrap-salt.sh -L https://bootstrap.saltstack.com
sudo sh bootstrap-salt.sh -A {{honeyswarm_host}} -i {{salt_minion_id}}