#!/bin/sh
# API only listens on localhost, so only Kong can reach it.
cd /srv/api
/opt/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
exec /docker-entrypoint.sh kong docker-start
