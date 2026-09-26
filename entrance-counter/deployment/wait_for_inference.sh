#!/bin/sh
set -u

attempt=0
while [ "$attempt" -lt 60 ]; do
  if curl --silent --fail --max-time 2 http://127.0.0.1:9001/ >/dev/null 2>&1; then
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 1
done

echo "Roboflow Inference did not become ready within 60 seconds" >&2
exit 1
