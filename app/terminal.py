import subprocess
RISKY=['del ','erase ','rmdir ','format ','shutdown','reg delete','diskpart','remove-item','git push --force']
def run_command(command,activity,approved=False):
    if any(x in command.lower() for x in RISKY) and not approved: raise PermissionError('Risky command blocked. Explicit approval required.')
    activity.emit('TERMINAL -> '+command)
    p=subprocess.run(command,shell=True,capture_output=True,text=True,timeout=120)
    out=(p.stdout or '')+('\\n'+p.stderr if p.stderr else '')
    activity.emit(f'TERMINAL -> exit code {p.returncode}')
    return p.returncode,out[-12000:]
