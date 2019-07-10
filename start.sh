#!/bin/sh

exec /usr/bin/gunicorn -b 0.0.0.0:5000 --access-logfile - "karmabot:create_app()"
