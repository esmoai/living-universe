#!/usr/bin/env python3
"""Real loopback integration tests for the native read-only observer."""
import hashlib, json, os, re, select, socket, subprocess, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
BINARY = Path(os.environ.get('LU_TEST_BINARY', str(ROOT/'bin/living-universe-observer-linux')))
results=[]
def check(name, condition):
    results.append({'name':name,'passed':bool(condition)})
    if not condition: raise AssertionError(name)
with tempfile.TemporaryDirectory(prefix='lu-observer-test-') as tmp:
    tmp=Path(tmp); log=tmp/'chosen.log'; log.write_text('# LU_TEST_FIXTURE - not an actual boot log\n@LU1 {"v":1,"source":"c-native-kernel","arch":"AArch64","event":"boot.snapshot","stage":0,"sequence":1,"firmware_exited":true,"user_space_isolation":false,"native_tool_execution":false,"conventional_pages":100,"memory_map_bytes":1024,"descriptor_size":48}\n')
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1',0)); port=reserve.getsockname()[1]
    proc=subprocess.Popen([str(BINARY),'--web',str(ROOT/'LivingUniverse.html'),'--log',str(log),'--port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        text=b''; deadline=time.monotonic()+5
        while b'Do not share' not in text and time.monotonic()<deadline:
            if proc.poll() is not None: raise RuntimeError(proc.stderr.read().decode())
            if select.select([proc.stdout],[],[],.2)[0]: text+=os.read(proc.stdout.fileno(),8192)
        match=re.search(rb'#key=([a-f0-9]{64})',text); check('OS-generated session key emitted',bool(match)); token=match.group(1).decode()
        host=f'127.0.0.1:{port}'
        def raw(request):
            with socket.create_connection(('127.0.0.1',port),timeout=5) as s:
                s.settimeout(5); s.sendall(request); s.shutdown(socket.SHUT_WR); data=b''
                while True:
                    try: part=s.recv(32768)
                    except ConnectionResetError: break
                    if not part: break
                    data+=part
            head,_,body=data.partition(b'\r\n\r\n'); status=int(head.split(b' ')[1]); return status,head,body
        def get(path='/api/snapshot',extras=None,method='GET',hostname=host):
            headers=[f'Host: {hostname}']+ (extras or [])
            return raw((f'{method} {path} HTTP/1.1\r\n'+'\r\n'.join(headers)+'\r\n\r\n').encode())
        status,headers,body=get('/');check('serves only selected HTML byte-for-byte',status==200 and hashlib.sha256(body).digest()==hashlib.sha256((ROOT/'LivingUniverse.html').read_bytes()).digest())
        check('CSP and no-store security headers',b"frame-ancestors 'none'" in headers and b'Cache-Control: no-store' in headers)
        check('no CORS allowance',b'Access-Control-Allow-Origin' not in headers)
        check('missing token denied',get()[0]==403)
        check('wrong token denied',get(extras=['X-Universe-Key: '+'0'*64])[0]==403)
        status,_,body=get(extras=['X-Universe-Key: '+token]);data=json.loads(body)
        check('authorized native observation',status==200 and data['schema']=='living-universe.bridge' and data['read_only'] is True)
        check('no native execution authority',data['execution_available'] is False and data['filesystem_write_available'] is False)
        check('reported metrics are bounded process observations',data['uptime_ms']>=0 and data['cpu_time_ms']>=0 and data['host_os']=='Linux')
        check('chosen log is readable with authentication',data['serial_log']==log.read_text())
        check('session key not echoed in data',token not in body.decode())
        check('foreign Origin denied despite correct token',get(extras=['X-Universe-Key: '+token,'Origin: https://example.invalid'])[0]==403)
        check('null Origin denied',get(extras=['X-Universe-Key: '+token,'Origin: null'])[0]==403)
        check('same Origin accepted',get(extras=['X-Universe-Key: '+token,'Origin: http://'+host])[0]==200)
        check('foreign Host denied',get(hostname='attacker.invalid')[0]==403)
        check('duplicate Host rejected',get(extras=['Host: '+host])[0]==400)
        check('duplicate token rejected',get(extras=['X-Universe-Key: '+token,'X-Universe-Key: '+token])[0]==400)
        check('duplicate Origin rejected',get(extras=['Origin: http://'+host,'Origin: http://'+host])[0]==400)
        for path in ['/../../etc/passwd','/%2e%2e/etc/passwd','/api/execute','/api/snapshot?path=/etc/passwd','/reference/Kernel_v0.2_original.zip']:
            check('reject unexpected path '+path,get(path,extras=['X-Universe-Key: '+token])[0]==404)
        for method in ['POST','PUT','DELETE','OPTIONS','CONNECT']:
            check('reject method '+method,get(method=method,extras=['X-Universe-Key: '+token])[0]==405)
        check('request body rejected',get(extras=['Content-Length: 20'])[0]==400)
        check('chunked request rejected',get(extras=['Transfer-Encoding: chunked'])[0]==400)
        check('header folding rejected',get(extras=[' X-Bad: data'])[0]==400)
        check('embedded NUL rejected',raw(f'GET / HTTP/1.1\r\nHost: {host}\x00\r\n\r\n'.encode())[0]==400)
        check('oversized headers rejected',get(extras=['X-Large: '+'A'*9000])[0]==400)
        check('request pipelining rejected',raw((f'GET / HTTP/1.1\r\nHost: {host}\r\n\r\nGET / HTTP/1.1\r\nHost: {host}\r\n\r\n').encode())[0]==400)
        check('incomplete request rejected',raw(b'GET / HTTP/1.1\r\nHost:')[0]==400)
        # Explicitly selected logs can be appended; no path supplied over HTTP.
        with log.open('a') as f:f.write('appended evidence\n')
        check('pre-opened log follows append',json.loads(get(extras=['X-Universe-Key: '+token])[2])['serial_log'].endswith('appended evidence\n'))
        log.write_bytes(b'X'*200000)
        large=json.loads(get(extras=['X-Universe-Key: '+token])[2]);check('serial reads capped at 128 KiB',large['log_tail_only'] and len(large['serial_log'])==128*1024)
        # Deterministic malformed request corpus; not a security audit or escape test.
        for n in range(80):
            bad=(b'GET / HTTP/1.1\r\nHost: '+host.encode()+b'\r\nX-Test: '+bytes([n%31+1])+b'\r\n\r\n')
            status,_,_=raw(bad)
            if n%31+1 in (9,): continue  # optional whitespace may be valid
            check(f'malformed control header {n}',status in [400,403])
        check('server survives malformed-input corpus',get(extras=['X-Universe-Key: '+token])[0]==200)
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        stderr=proc.stderr.read().decode(errors='replace')
        if 'AddressSanitizer' in stderr or 'runtime error:' in stderr:raise AssertionError(stderr)
    symlink=tmp/'link.html';symlink.symlink_to(ROOT/'LivingUniverse.html')
    r=subprocess.run([str(BINARY),'--web',str(symlink)],capture_output=True,timeout=5);check('rejects symlink web input',r.returncode==2)
    fifo=tmp/'pipe';os.mkfifo(fifo)
    r=subprocess.run([str(BINARY),'--web',str(fifo)],capture_output=True,timeout=5);check('rejects nonregular file without blocking',r.returncode==2)
    for invalid in ['0','80','65536','-1','8765oops','999999999']:
        r=subprocess.run([str(BINARY),'--port',invalid],cwd=ROOT,capture_output=True,timeout=5);check('reject invalid port '+invalid,r.returncode==2)
report={'binary':str(BINARY.relative_to(ROOT)),'tests':len(results),'passed':sum(x['passed'] for x in results),'results':results,'scope':'actual Linux process and loopback sockets; authored serial fixture; not a sandbox security audit'}
output=ROOT/'validation'/('bridge-sanitizer-tests.json' if 'asan' in BINARY.name else 'bridge-tests.json')
output.write_text(json.dumps(report,indent=2)+'\n');print(f"PASS: {len(results)} native bridge checks. Report: {output.name}")
