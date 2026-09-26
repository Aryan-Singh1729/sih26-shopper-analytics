"""Read-only display and kiosk prerequisites probe for the UNO Q."""
import json,shutil,subprocess
from pathlib import Path

def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=15)
    return {'code':result.returncode,'output':result.stdout.strip(),'error':result.stderr.strip()}

processes=run(['ps','-eo','pid,comm,args'])['output'].splitlines()
names=('chromium','Xorg','Xwayland','weston','lightdm','gdm','xfce','openbox')
print(json.dumps({
    'display_outputs':[{'connector':p.name,'status':(p/'status').read_text().strip(),'modes':(p/'modes').read_text().splitlines()} for p in Path('/sys/class/drm').glob('card*-*') if (p/'status').exists()],
    'programs':{name:shutil.which(name) for name in ('chromium','Xorg','xinit','startx','xauth','openbox','weston','xrandr')},
    'desktop_processes':[line for line in processes if any(name in line for name in names)],
    'display_sockets':[str(p) for p in Path('/tmp/.X11-unix').glob('*')],
    'display_manager':run(['systemctl','status','display-manager','--no-pager']),
    'disk':run(['df','-h','/']),
    'memory':run(['free','-m']),
    'listeners':run(['ss','-ltn']),
    'xwrapper':Path('/etc/X11/Xwrapper.config').read_text() if Path('/etc/X11/Xwrapper.config').exists() else None
},indent=2))
