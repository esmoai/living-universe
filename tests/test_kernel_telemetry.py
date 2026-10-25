#!/usr/bin/env python3
"""Validate actual C formatter output and QEMU gate parser, not hardware boot."""
import importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
binary=ROOT/'bin/kernel-telemetry-host-test'
subprocess.run(['cc','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g','-I',str(ROOT/'kernel/include'),str(ROOT/'tests/kernel_telemetry_host.c'),'-o',str(binary)],check=True)
out=subprocess.check_output([str(binary)],text=True)
(ROOT/'validation/kernel-telemetry-host-fixture.log').write_text(out)
lines=[json.loads(x.split('@LU1 ',1)[1]) for x in out.splitlines() if '@LU1 ' in x]
assert [p['arch'] for p in lines]==['x86-64','AArch64']
assert [p['sequence'] for p in lines]==[1,2]
assert all(p['conventional_pages']==4113 and p['user_space_isolation'] is False and p['native_tool_execution'] is False for p in lines)
spec=importlib.util.spec_from_file_location('gate',ROOT/'kernel/scripts/boot_qemu.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
checks=[]
def test(name,condition):
 checks.append({'name':name,'passed':bool(condition)});assert condition,name
for p,arch in zip(lines,['x86_64','aarch64']):
 text='@LU1 '+json.dumps(p)
 test('accept actual host formatter '+arch,gate.valid_universe_response(text,arch))
 test('reject fixture as boot '+arch,not gate.valid_universe_response('# LU_TEST_FIXTURE\n'+text,arch))
 test('reject wrong architecture '+arch,not gate.valid_universe_response(text,'aarch64' if arch=='x86_64' else 'x86_64'))
 test('reject invented isolation '+arch,not gate.valid_universe_response('@LU1 '+json.dumps(dict(p,user_space_isolation=True)),arch))
 test('reject missing field '+arch,not gate.valid_universe_response('@LU1 {}',arch))
 test('reject malformed JSON '+arch,not gate.valid_universe_response('@LU1 not-json',arch))
(ROOT/'validation/kernel-telemetry-tests.json').write_text(json.dumps({'checks':len(checks),'passed':len(checks),'scope':'actual shared C formatter under host ASan/UBSan; parser tests, NOT a firmware boot','results':checks},indent=2)+'\n')
print(f'PASS: shared C telemetry formatter + {len(checks)} gate checks. Not a boot test.')
