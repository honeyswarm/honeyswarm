Installation
============

The officially supported installation process is to use the docker-compose that is shipped with the repo. 
Installing in a method other than docker-compose is left as an exercise to the user. Read the compose and the docker files for each container 
should give you a headstart. 

Docker and Compose
------------------

Install Docker and docker-compose

HoneySwarm
----------

If you want to run the latest stable release go to https://github.com/honeyswarm/honeyswarm/releases and get the latest release

If you prefer a development version to then ``git clone git@github.com:honeyswarm/honeyswarm.git``

Configuration
-------------

Copy ``honeyswarm_template.env`` to ``honeyswarm.env`` and change the default passwords and tokens as per the list below.

- SALT_SHARED_SECRET
- MONGODB_USERNAME and MONGO_INITDB_ROOT_USERNAME
- MONGODB_PASSWORD and MONGO_INITDB_ROOT_PASSWORD

Please leave all the HOST names and ports as they are pre configured. 

If you wish to change the external HTTP port from 8080 to something of your choice edit the docker-compose.yml file. 

Once you have made your changes you will need to start the application and complete the first time setup by visiting: http://honeyswarmip/installation


Starting
========
All commands must be executed from the honeyswarm directory.

To start the application in the background enter ``docker-compose up -d`` in a terminal.
To start the application in the forground with visible logging enter ``docker-compose up`` in a terminal.

Stopping
========
All commands must be executed from the honeyswarm directory.

``docker-compose down``

Backup / Restore
================

Volumes
-------

To maintain persistance of data HoneySwarm uses docker volumes. As long as you do not prune or destory these volumes you 
can start, stop and upgrade your HoneySwarm containers without losing data. 

Backup
------
For details on backing up or restoring docker volumes please refer to the docker documentation.


Update
======

If your using docker-compose you can update your installation by following these steps. 

**Note** This will take your hpfeeds broker offline for a few minutes and you will not store any incoming events. 

- ``cd`` to the honeyswarm directory
- ``docker-compose pull``
- ``docker-compose up --force-recreate --build -d``
