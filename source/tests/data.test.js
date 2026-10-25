import test from 'node:test';
import assert from 'node:assert/strict';
import { CHANNELS, parsePayload, atomsOf, readPointer, makePacket, routeData, createSamples } from '../src/data.js';
test('fiber sequence and unique channel IDs follow the twelve-fiber ordering', () => {
  assert.deepEqual(CHANNELS.map(c => c.color), ['Blue','Orange','Green','Brown','Slate','White','Red','Black','Yellow','Violet','Rose','Aqua']);
  assert.equal(new Set(CHANNELS.map(c=>c.id)).size,12);
});
test('import rejects invalid, oversized, excessively deep, and excessively broad JSON', () => {
  assert.throws(()=>parsePayload('{broken}'), /Invalid JSON/);
  assert.throws(()=>parsePayload(JSON.stringify('x'.repeat(262144))), /256 KB/);
  assert.throws(()=>parsePayload('['.repeat(22)+'0'+']'.repeat(22)), /depth/);
  assert.throws(()=>parsePayload(JSON.stringify(Array(5001).fill(1))), /5,000/);
  assert.equal(parsePayload('null'), null);
});
test('atomic paths preserve unusual keys, arrays, nulls, and empty objects', () => {
  const payload = { 'a/b': { '~key': [null, 7] }, empty: {} };
  assert.deepEqual(atomsOf(payload).map(a=>a.path), ['/a~1b/~0key/0','/a~1b/~0key/1','/empty']);
  assert.equal(readPointer(payload, '/a~1b/~0key/1'), 7);
  assert.throws(()=>readPointer(payload, '/constructor'), /no longer/);
});
test('packet handoff preserves channel and provenance; atomic dissemination copies only selected value', () => {
  const packet = makePacket({name:'test',channel:12,node:'core',payload:{position:{x:3,y:7},private:'unselected'}});
  const atom = routeData(packet,'tools','/position/x');
  assert.equal(packet.node,'core');
  assert.equal(atom.packet.payload.value,3);
  assert.equal(atom.packet.payload.private,undefined);
  assert.equal(atom.packet.channel,12);
  const full = routeData(packet,'intelligence');
  assert.equal(full.packet,packet);
  assert.equal(packet.node,'intelligence');
  assert.equal(packet.history[0].from,'core');
  assert.throws(()=>routeData(packet,'intelligence'), /already/);
  assert.throws(()=>routeData(packet,'unknown'), /existing/);
});
test('sample workspace has four inspectable nodes and thirty-six core packets',()=>{
  const packets=createSamples();
  assert.equal(new Set(packets.map(p=>p.node)).size,4);
  assert.equal(packets.filter(p=>p.node==='core').length,36);
  assert.ok(packets.every(p=>p.source==='sample' && atomsOf(p.payload).length));
});
