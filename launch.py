"""Bounded local service start/stop helper."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import time
import urllib.request

from app_config import ROOT, PORT
PID = ROOT / 'server.pid'
URL = f'http://127.0.0.1:{PORT}'


def alive():
    try:
        with urllib.request.urlopen(URL+'/api/state',timeout=2) as response:
            return response.status==200
    except OSError:
        return False


if len(sys.argv)>1 and sys.argv[1]=='stop':
    if not PID.exists():
        print('没有后台服务记录。')
        raise SystemExit(0)
    pid=int(PID.read_text())
    result=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True,timeout=5)
    if str(ROOT/'server.py') not in result.stdout:
        print('服务已停止或进程记录失效，不操作其他进程。')
        raise SystemExit(0)
    req=urllib.request.Request(URL+'/api/cancel',data=b'{}',headers={'Content-Type':'application/json'})
    try:
        urllib.request.urlopen(req,timeout=5).close()
    except OSError:
        pass
    os.kill(pid,signal.SIGTERM)
    print('试听实验室已停止。')
elif alive():
    print('试听实验室已在运行：'+URL)
else:
    with (ROOT/'server.log').open('a') as log:
        proc=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=ROOT,
                              stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
    PID.write_text(str(proc.pid))
    for _ in range(30):
        if alive():
            print('Qwen: '+URL+'/qwen\nIndexTTS: '+URL+'/index\nSpark: '+URL+'/spark\nPID: '+str(proc.pid))
            break
        if proc.poll() is not None:
            raise SystemExit('启动失败，请查看 server.log')
        time.sleep(.5)
    else:
        proc.terminate()
        raise SystemExit('启动等待超时，请查看 server.log')
