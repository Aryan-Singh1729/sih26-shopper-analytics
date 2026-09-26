#!/bin/sh
# LightDM supplies display authorization. Use an advertised monitor mode.
/usr/bin/xrandr --output DP-1 --mode 1280x720 --primary || /usr/bin/xrandr --output DP-1 --auto --primary
