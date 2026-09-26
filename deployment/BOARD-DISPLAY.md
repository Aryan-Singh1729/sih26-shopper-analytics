# UNO Q footfall display

The UNO Q's connected DP-1 display is configured for a 1280×720 Chromium kiosk
session showing the footfall dashboard at `http://127.0.0.1:8081/?kiosk=1`.
Its central camera occupies most of the display, with today's arrivals and
clock on the left and current-hour arrivals and busiest hour on the right.
LightDM automatically logs in as `arduino` to launch it. This removes the
physical login prompt; anyone with physical access to the board can access that
account. The setup does not expose the laptop dashboard to the LAN.

The dashboard and person detector continue to run on the laptop. The board
reaches the laptop's loopback-only dashboards (8081 and 8082) and detector (9011)
through SSH reverse tunnels:

```powershell
ssh -N -T -i 'C:\Users\hp\.ssh\retail-display-key' `
  -o IdentitiesOnly=yes -o BatchMode=yes -o ExitOnForwardFailure=yes `
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3 `
  -R 127.0.0.1:8081:127.0.0.1:8081 `
  -R 127.0.0.1:8082:127.0.0.1:8082 `
  -R 127.0.0.1:9011:127.0.0.1:9011 `
  arduino@10.143.116.243
```

The tunnel must be running whenever the board display is used. It does not
automatically reconnect after a board or laptop restart. The key is kept outside
the repository with Windows access limited to the laptop user; do not commit it
or put the SSH password in a saved script. If the
laptop, dashboard, or tunnel is unavailable, the kiosk waits or shows a
connection error instead of live video.

Footfall session files are `deployment/retail-footfall-kiosk*` and
`zz-retail-footfall-kiosk.conf`. The previous queue session remains installed
in `deployment/retail-queue-kiosk*` and `99-retail-queue-kiosk.conf`. Existing
managed files were backed up on the board
under `/home/arduino/.config/retail-edge/display-backups/` before installation.
The original `/etc/lightdm/lightdm.conf.d/50-robot-display.conf` and its hook
were left in place; the footfall override changes only the session selection.

For diagnosis over SSH:

```sh
cat /sys/class/drm/card0-DP-1/status
DISPLAY=:0 XAUTHORITY=/home/arduino/.Xauthority xrandr --current
systemctl is-active lightdm.service retail-entrance-counter.service
curl -I http://127.0.0.1:8081/
```

If `DP-1` says `disconnected`, check monitor power and cable. A browser process
can be running even while the connector is disconnected; this is not proof that
anything is visible on the physical screen. Once the display reconnects, use
`xrandr` to select 1280×720 or restart LightDM if needed. Restarting LightDM
interrupts the visible session but does not delete data.
