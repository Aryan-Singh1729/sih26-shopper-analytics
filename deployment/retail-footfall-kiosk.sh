#!/bin/sh
# Runs as the normal arduino desktop user, with Chromium's sandbox enabled.
set -eu
/usr/bin/xset s off 2>/dev/null || true
/usr/bin/xset -dpms 2>/dev/null || true
/usr/bin/xfwm4 --compositor=off --daemon 2>/dev/null || true
until /usr/bin/python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8081/",timeout=2).close()' 2>/dev/null; do
    sleep 2
done
exec /usr/bin/chromium --kiosk --no-first-run --no-default-browser-check \
    --disable-session-crashed-bubble --password-store=basic \
    --user-data-dir=/home/arduino/.config/retail-edge/footfall-kiosk-browser \
    --window-position=0,0 --window-size=1280,720 \
    'http://127.0.0.1:8081/?kiosk=1'
