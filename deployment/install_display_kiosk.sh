#!/bin/sh
set -eu
test "$(id -u)" = 0
backup=/home/arduino/.config/retail-edge/display-backups/$(date -u +%Y%m%dT%H%M%S)
mkdir -p "$backup"
for path in /usr/local/sbin/retail-display-setup /usr/local/bin/retail-queue-kiosk /usr/share/xsessions/retail-queue-kiosk.desktop /etc/lightdm/lightdm.conf.d/99-retail-queue-kiosk.conf; do
    if test -e "$path"; then cp -a "$path" "$backup/$(basename "$path")"; fi
done
install -m 755 /tmp/retail-display-setup.sh /usr/local/sbin/retail-display-setup
install -m 755 /tmp/retail-queue-kiosk.sh /usr/local/bin/retail-queue-kiosk
install -m 644 /tmp/retail-queue-kiosk.desktop /usr/share/xsessions/retail-queue-kiosk.desktop
install -m 644 /tmp/99-retail-queue-kiosk.conf /etc/lightdm/lightdm.conf.d/99-retail-queue-kiosk.conf
systemctl reset-failed lightdm.service
systemctl restart lightdm.service
printf 'Kiosk configured; previous managed files backed up in %s\n' "$backup"
