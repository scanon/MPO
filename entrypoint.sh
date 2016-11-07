#!/bin/bash
#
myfp=`which $0`
mydir=`dirname $myfp`
. $mydir/functions.sh

PYTHONPATH=$mydir/db:$mydir/server

if [ "$1" = "api" ] ; then
  #this ignores any environmental variable, so you have to give it on the commandline
  MPO_API_MOUNT=${MPO_API_MOUNT:-'/'} #was /test-api but doesn't work yet

  MPO_DB_HOST=${MPO_DB_HOST:-db}
  MPO_DB_DB=${MPO_DB_DB:-mpoDB}
  MPO_DB_USER=${MPO_DB_USER:-mpoadmin}
  MPO_DB_PWD=${MPO_DB_PWD:-mpo2013}
  MPO_DB_CONNECTION=${MPO_DB_CONNECTION:-host=\'$MPO_DB_HOST\' dbname=\'$MPO_DB_DB\' user=\'$MPO_DB_USER\' password=\'$MPO_DB_PWD\'}

  MPO_API_SERVER_PORT=${MPO_API_SERVER_PORT:-8443}
  MPO_API_SERVER_CERT=${MPO_API_SERVER_CERT:-$mydir/mpo.psfc.mit.edu.crt}
  MPO_API_SERVER_KEY=${MPO_API_SERVER_KEY:-$mydir/mpo.psfc.mit.edu.key}
  MPO_CA_CERT=${MPO_CA_CERT:-\!$mydir/mpo.psfc.mit.edu-ca.crt}
  export UDP_EVENTS=yes
  key_check $MPO_API_SERVER_KEY

  export MPO_DB_CONNECTION
  export PYTHONPATH

  MPO_EDITION="TEST"
  export MPO_EDITION
  export THREAD_OPT=--enable-threads
  

  echo "$MPO_DB_CONNECTION"
  uwsgi $GEVENT_OPT $THREAD_OPT $VIRTPATH --https \
      "0.0.0.0:$MPO_API_SERVER_PORT,$MPO_API_SERVER_CERT,$MPO_API_SERVER_KEY,HIGH,$MPO_CA_CERT" \
      --wsgi-file $mydir/server/api_server.py  --callable app 

elif [ "$1" = "web" ] ; then
  echo "Starting web server"
  MPO_API_SERVER=${MPO_API_SERVER:-https://api:8443/}
  MPO_API_VERSION=v0
  export MPO_API_SERVER MPO_API_VERSION
  MPO_WEB_SERVER_PORT=${MPO_WEB_SERVER_PORT:-9443}
  MPO_WEB_CLIENT_CERT=${MPO_WEB_CLIENT_CERT:-$mydir/MPO-UI-SERVER.crt}
  MPO_WEB_CLIENT_KEY=${MPO_WEB_CLIENT_KEY:-$mydir/MPO-UI-SERVER.key}
  MPO_WEB_SERVER_CERT=${MPO_WEB_SERVER_CERT:-$mydir/mpo.psfc.mit.edu.crt}
  MPO_WEB_SERVER_KEY=${MPO_WEB_SERVER_KEY:-$mydir/mpo.psfc.mit.edu.key}
  MPO_CA_CERT=${MPO_CA_CERT:-\!$mydir/mpo.psfc.mit.edu-ca.crt}

  MPO_EVENT_SERVER=${MPO_EVENT_SERVER:-http://localhost:9444/mdsplusWsgi/event}
  key_check $MPO_WEB_CLIENT_KEY
  key_check $MPO_WEB_SERVER_KEY

  export MPO_API_SERVER MPO_EVENT_SERVER MPO_WEB_CLIENT_CERT MPO_WEB_CLIENT_KEY
  export PYTHONPATH

  export THREAD_OPT=--enable-threads

  #Let web server know we are running under WSGI
  export MPO_WEB_SERVER=uwsgi

  uwsgi $GEVENT_OPT $THREAD_OPT $VIRTPATH --https  \
            "0.0.0.0:$MPO_WEB_SERVER_PORT,$MPO_WEB_SERVER_CERT,$MPO_WEB_SERVER_KEY,HIGH,$MPO_CA_CERT" \
            --wsgi-file $mydir/server/web_server.py  --callable app

elif [ "$1" = "init" ] ; then
  echo "Initializing Database"
  export PGPASSWORD=$POSTGRES_PASSWORD
  createdb -h db -U postgres mpoDB
  echo "create user mpoadmin createdb superuser;"|psql -h db -U postgres
  psql -h db -d mpoDB -U postgres -f /src/db/create_tables.sql
else
  bash
fi
