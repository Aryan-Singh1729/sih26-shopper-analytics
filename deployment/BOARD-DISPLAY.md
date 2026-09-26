# UNO Q queue display

The UNO Q's connected DP-1 display is configured for a 1280×720 Chromium kiosk
session showing only the checkout dashboard at `http://127.0.0.1:8082/?kiosk=1`.
LightDM automatically logs in as `arduino` to launch it. This removes the
physical login prompt; anyone with physical access to the board can access that
account. The setup does not expose the laptop dashboard to the LAN.

The dashboard and person detector continue to run on the laptop. The board
reaches the laptop's loopback-only dashboard (8082) and detector (9011)
through SSH reverse tunnels:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -ssh -N -batch `
  -R 127.0.0.1:8082:127.0.0.1:8082 `
  -R 127.0.0.1:9011:127.0.0.1:9011 `
  -hostkey 'SHA256:5MjJUO0I5zx8kobSOXrN7oRGCF+8TMLlYG9t5p6D2TA' `
  arduino@10.143.116.243
```

The tunnel must be running whenever the board display is used. It does not
automatically reconnect after a board or laptop restart. Do not put the
SSH password in a saved script; use an SSH key or interactive prompt. If the
laptop, dashboard, or tunnel is unavailable, the kiosk waits or shows a
connection error instead of live video.

Setup files are in `deployment/retail-queue-kiosk*`, `99-retail-queue-kiosk.conf`,
and `retail-display-setup.sh`. Existing managed files were backed up on the board
under `/home/arduino/.config/retail-edge/display-backups/` before installation.
The original `/etc/lightdm/lightdm.conf.d/50-robot-display.conf` and its
`robot-display-setup` hook were left in place; the later kiosk file overrides
only the display setup and session settings.

For diagnosis over SSH:

```sh
cat /sys/class/drm/card0-DP-1/status
DISPLAY=:0 XAUTHORITY=/home/arduino/.Xauthority xrandr --current
systemctl is-active lightdm.service retail-entrance-counter.service
curl -I http://127.0.0.1:8082/
```

If `DP-1` says `disconnected`, check monitor power and cable. A browser process
can be running even while the connector is disconnected; this is not proof that
anything is visible on the physical screen. Once the display reconnects, use
`xrandr` to select 1280×720 or restart LightDM if needed. Restarting LightDM
interrupts the visible session but does not delete data.
