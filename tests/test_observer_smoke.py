#!/usr/bin/env python3
"""Portable real-process smoke test for Linux and Windows, without privileged access."""
import argparse, json, queue, re, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary',type=Path,required=True)
parser.add_argument('--web',type=Path,required=True)
args=parser.parse_args()
results=[]
def check(name,value):
    results.append({'name':name,'passed':bool(value)})
    if not value: raise AssertionError(name)
with socket.socket() as s:
    s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='lu smoke ') as temp:
    log=Path(temp)/'selected log.txt';log.write_text('Explicitly selected smoke-test fixture\n')
    command=[str(args.binary.resolve()),'--web',str(args.web.resolve()),'--log',str(log),'--port',str(port)]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    lines=queue.Queue()
    def read_lines():
        for line in iter(process.stdout.readline,b''): lines.put(line.decode('utf-8',errors='replace'))
    threading.Thread(target=read_lines,daemon=True).start()
    try:
        key=None; deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            try: line=lines.get(timeout=.2)
            except queue.Empty:
                if process.poll() is not None: break
                continue
            match=re.search(r'#key=([a-f0-9]{64})',line)
            if match: key=match.group(1);break
        check('observer announces a per-launch key',key is not None)
        base='http://127.0.0.1:'+str(port)
        def get(path,headers=None):
            try:
                with urlopen(Request(base+path,headers=headers or {}),timeout=5) as response:
                    return response.status,response.read()
            except HTTPError as error: return error.code,error.read()
        status,body=get('/')
        check('serves selected HTML exactly',status==200 and body==args.web.read_bytes())
        check('unauthenticated observations denied',get('/api/snapshot')[0]==403)
        status,body=get('/api/snapshot',{'X-Universe-Key':key}); data=json.loads(body)
        check('authorized observation succeeds',status==200 and data.get('read_only') is True)
        check('native OS identity matches',data.get('host_os')==('Windows' if sys.platform=='win32' else 'Linux'))
        check('native execution unavailable',data.get('execution_available') is False)
        check('host writes unavailable',data.get('filesystem_write_available') is False)
        check('only chosen log returned',data.get('serial_log')==log.read_text())
        check('cross-origin denied',get('/api/snapshot',{'X-Universe-Key':key,'Origin':'https://example.invalid'})[0]==403)
        check('no arbitrary file endpoint',get('/etc/passwd')[0]==404)
        check('key not echoed in snapshot',key.encode() not in body)
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill();process.wait()
        process.stdout.close()
report={'platform':sys.platform,'checks':len(results),'passed':sum(x['passed'] for x in results),'results':results}
(ROOT/'validation').mkdir(exist_ok=True)
(ROOT/'validation'/('observer-smoke-'+sys.platform+'.json')).write_text(json.dumps(report,indent=2)+'\n')
print('PASS:',len(results),'real-process observer checks on',sys.platform)
