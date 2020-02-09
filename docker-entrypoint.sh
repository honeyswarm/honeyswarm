#!/bin/bash

# This is required for the apache wsgi handling
echo "export MONGODB_HOST=$MONGODB_HOST" >> /etc/apache2/envvars
echo "export MONGODB_DATABASE=$MONGODB_DATABASE" >> /etc/apache2/envvars
echo "export MONGODB_USERNAME=$MONGODB_USERNAME" >> /etc/apache2/envvars
echo "export MONGODB_PASSWORD=$MONGODB_PASSWORD" >> /etc/apache2/envvars

echo "export SALT_SHARED_SECRET=$SALT_SHARED_SECRET" >> /etc/apache2/envvars
touch /tmp/blah
#tail -f /tmp/blah

exec "$@"