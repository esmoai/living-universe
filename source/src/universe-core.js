import { CHANNELS, NODES, createSamples, validatePayload, parsePayload, atomsOf, readPointer } from './data.js';

export const LIMITS = Object.freeze({ packets: 160, fileBytes: 262144, blobBytes: 1048576, workspaceBytes: 8388608, frames: 64, note: 2000 });
export const QUALITIES = ['simulated', 'imported', 'observed', 'reported', 'derived', 'unknown'];
export const encoder = new TextEncoder();
export const utf8 = value => encoder.encode(JSON.stringify(value, null, 2));
export const stamp = () => new Date().toISOString();
export const uid = () => globalThis.crypto?.randomUUID?.() || `local-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
export const hashText = text => { let h = 2166136261; for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16).padStart(8, '0'); };
export function bytesToBase64(bytes) { let s = ''; for (let i = 0; i < bytes.length; i += 8192) s += String.fromCharCode(...bytes.subarray(i, i + 8192)); return btoa(s); }
export function base64ToBytes(text) { if (typeof text !== 'string' || text.length > Math.ceil(LIMITS.fileBytes / 3) * 4 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(text)) throw Error('Invalid or oversized byte attachment.'); const s = atob(text); return Uint8Array.from(s, c => c.charCodeAt(0)); }
export async function sha256(bytes) { if (!globalThis.crypto?.subtle) return null; const hash = await crypto.subtle.digest('SHA-256', bytes); return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2, '0')).join(''); }
export function bitAt(bytes, index) { if (!Number.isInteger(index) || index < 0 || index >= bytes.length * 8) throw Error('Bit is outside the available bytes.'); return (bytes[Math.floor(index / 8)] >> (7 - index % 8)) & 1; }
export function boundJSON(value) { validatePayload(value); if (utf8(value).length > LIMITS.fileBytes) throw Error('Payload exceeds 256 KiB.'); return value; }
function freeze(value) { if (value && typeof value === 'object' && !Object.isFrozen(value)) { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
function short(value, max = 160) { return String(value ?? '').slice(0, max); }
export function normalizePacket(p) {
  if (!p || typeof p !== 'object' || Array.isArray(p)) throw Error('Invalid object record.');
  if (typeof p.id !== 'string' || !p.id || p.id.length > 180) throw Error('Invalid object identity.');
  if (!CHANNELS.some(c => c.id === p.channel) || !Object.hasOwn(NODES, p.node)) throw Error('Unknown channel or destination.');
  if (!QUALITIES.includes(p.quality)) throw Error('Missing evidence classification.');
  if (p.payload === undefined) throw Error('An object needs a payload.');
  const payload = structuredClone(boundJSON(p.payload));
  const provenance = p.provenance && typeof p.provenance === 'object' ? p.provenance : {};
  return freeze({ id: p.id, name: short(p.name || 'Untitled object', 100), channel: p.channel, node: p.node, quality: p.quality,
    createdAt: short(p.createdAt || stamp(), 50), payload, source: short(p.source || 'unknown'),
    provenance: { description: short(provenance.description || p.source || 'Unknown source', 600),
      digest: typeof provenance.digest === 'string' && /^[a-f0-9]{64}$/.test(provenance.digest) ? provenance.digest : null,
      parentId: short(provenance.parentId, 180), pointer: short(provenance.pointer, 500), recorded: Boolean(provenance.recorded) },
    note: short(p.note, LIMITS.note), pinned: Boolean(p.pinned),
    blobId: typeof p.blobId === 'string' && /^[a-z0-9-]{1,100}$/.test(p.blobId) ? p.blobId : null,
    revision: Number.isSafeInteger(p.revision) && p.revision > 0 ? p.revision : 1 });
}
export function samples() { return createSamples().map(p => normalizePacket({ ...p, quality: 'simulated', provenance: { description: 'Authored example from the supplied Source / Destination project. Not a sensor or a connected service.' } })); }

export class UniverseStore extends EventTarget {
  constructor({ seed = true } = {}) { super(); this.packets = seed ? samples() : []; this.blobs = new Map(); this.frames = []; this.cursor = null; this.undoStack = []; this.redoStack = []; this.capture('Opened local workspace', 'open'); }
  get isRecall() { return this.cursor !== null; }
  get view() { return this.isRecall ? this.frames[this.cursor].packets : this.packets; }
  get(id) { return this.view.find(p => p.id === id); }
  emit() { this.dispatchEvent(new Event('change')); }
  assertLive() { if (this.isRecall) throw Error('Recall is read-only. Return to the present before making changes.'); }
  capture(label, kind = 'edit') { this.frames.push(Object.freeze({ time: stamp(), label: short(label, 180), kind, packets: Object.freeze([...this.packets]) })); if (this.frames.length > LIMITS.frames) this.frames.shift(); }
  commit(next, label, kind = 'edit', undoable = true) {
    this.assertLive(); if (next.length > LIMITS.packets) throw Error('Workspace limit: 160 objects. Start a new workspace or export first.');
    const ids = new Set(); for (const p of next) { if (ids.has(p.id)) throw Error('Duplicate object identity.'); ids.add(p.id); }
    if (undoable) { this.undoStack.push(this.packets); if (this.undoStack.length > 24) this.undoStack.shift(); this.redoStack = []; }
    this.packets = next; this.capture(label, kind); this.emit();
  }
  add(p, label = 'Imported an object') { const packet = normalizePacket(p); this.commit([...this.packets, packet], label, 'import'); return packet; }
  update(id, changes, label) { const p = this.packets.find(p => p.id === id); if (!p) throw Error('Object unavailable.'); const n = normalizePacket({ ...p, ...changes, id: p.id, revision: p.revision + 1 }); this.commit(this.packets.map(p => p.id === id ? n : p), label); return n; }
  route(id, node) { if (!Object.hasOwn(NODES, node)) throw Error('Unknown destination.'); const p = this.get(id); if (p?.node === node) throw Error('Already in that chamber.'); return this.update(id, { node }, `Moved ${p?.name || 'object'} to ${NODES[node].name} (workspace only)`); }
  annotate(id, note) { return this.update(id, { note }, 'Saved a local annotation'); }
  pin(id) { const p = this.get(id); return this.update(id, { pinned: !p.pinned }, p.pinned ? 'Unpinned an object' : 'Pinned an object'); }
  cloneAtom(id, pointer, node) { const p = this.get(id); if (!p) throw Error('Object unavailable.'); return this.add({ id: uid(), name: `${p.name} / fragment`, channel: p.channel, node, quality: 'derived', source: 'local-fragment', payload: readPointer(p.payload, pointer), provenance: { description: 'Exact JSON value copied from an inspected object. No native execution.', parentId: p.id, pointer } }, 'Curated an exact data fragment'); }
  undo() { this.assertLive(); if (!this.undoStack.length) throw Error('Nothing to undo.'); this.redoStack.push(this.packets); this.packets = this.undoStack.pop(); this.capture('Undid a local edit', 'undo'); this.emit(); }
  redo() { this.assertLive(); if (!this.redoStack.length) throw Error('Nothing to redo.'); this.undoStack.push(this.packets); this.packets = this.redoStack.pop(); this.capture('Redid a local edit', 'redo'); this.emit(); }
  recall(index) { if (!Number.isInteger(index) || index < 0 || index >= this.frames.length) throw Error('No recorded frame at that index.'); this.cursor = index; this.emit(); }
  present() { this.cursor = null; this.emit(); }
  snapshot() { this.assertLive(); this.capture('Manual observation bookmark', 'bookmark'); this.emit(); }
  upsertObservation(p, label = 'Recorded an observation') { this.assertLive(); const packet = normalizePacket(p); const old = this.packets.find(x => x.id === packet.id); const next = old ? this.packets.map(x => x.id === packet.id ? packet : x) : [...this.packets, packet]; this.commit(next, label, 'observe', false); }
  async importBytes(name, bytes, node = 'core', channel = 6) {
    this.assertLive(); if (!(bytes instanceof Uint8Array) || bytes.length > LIMITS.fileBytes) throw Error('Select a file no larger than 256 KiB.');
    if (!Object.hasOwn(NODES, node)) throw Error('Unknown destination.');
    const digest = await sha256(bytes); this.assertLive();
    const blobId = digest || uid().toLowerCase(); const existing = this.blobs.get(blobId);
    const total = [...this.blobs.values()].reduce((n, b) => n + b.size, 0);
    if (!existing && total + bytes.length > LIMITS.blobBytes) throw Error('Raw byte limit: 1 MiB per workspace. Export and open a new workspace.');
    let payload; let parsed = false;
    const text = new TextDecoder().decode(bytes);
    if (/\.json$/i.test(name)) { payload = parsePayload(text); parsed = true; }
    else payload = { filename: short(name), byteLength: bytes.length, encoding: 'raw file bytes', preview: text.slice(0, 1200), previewIsTextOnly: true };
    const p = normalizePacket({ id: uid(), name, channel, node, quality: 'imported', source: 'user-selected-file', payload,
      blobId, provenance: { description: parsed ? 'Parsed JSON and original bytes from the file you selected. No upload.' : 'Original bytes from the file you selected. Text preview is not an encoding assertion.', digest } });
    if (!existing) this.blobs.set(blobId, Object.freeze({ size: bytes.length, base64: bytesToBase64(bytes) }));
    try { this.add(p, `Imported ${short(name, 70)} locally`); } catch (e) { if (!existing) this.blobs.delete(blobId); throw e; }
    return p;
  }
  bytesFor(p, pointer = null) { if (pointer === null && p.blobId && this.blobs.has(p.blobId)) return { bytes: base64ToBytes(this.blobs.get(p.blobId).base64), label: 'Original selected-file bytes' }; return { bytes: utf8(pointer === null ? p.payload : readPointer(p.payload, pointer)), label: 'UTF-8 JSON representation; not process memory' }; }
  exportObject() {
    const pool = [], ids = new Map(); const index = p => { if (!ids.has(p)) { ids.set(p, pool.length); pool.push(p); } return ids.get(p); };
    const frames = this.frames.map(f => ({ time: f.time, label: f.label, kind: f.kind, objects: f.packets.map(index) }));
    const current = this.packets.map(index);
    return { schema: 'living-universe.workspace', version: 1, exportedAt: stamp(), authority: 'none; workspace data only', pool, frames, current, blobs: Object.fromEntries(this.blobs) };
  }
  exportText() { const text = JSON.stringify(this.exportObject()); if (encoder.encode(text).length > LIMITS.workspaceBytes) throw Error('Workspace export exceeds 8 MiB. Reduce imported data before saving.'); return text; }
  importWorkspace(text) {
    if (encoder.encode(text).length > LIMITS.workspaceBytes) throw Error('Workspace exceeds 8 MiB.');
    const data = JSON.parse(text); if (data?.schema !== 'living-universe.workspace' || data.version !== 1) throw Error('Unsupported workspace format.');
    if (!Array.isArray(data.pool) || data.pool.length > 4096 || !Array.isArray(data.frames) || data.frames.length > LIMITS.frames || !Array.isArray(data.current)) throw Error('Invalid workspace bounds.');
    const pool = data.pool.map(p => normalizePacket({ ...p, provenance: { ...p.provenance, recorded: true } }));
    const resolve = refs => { if (!Array.isArray(refs) || refs.length > LIMITS.packets || refs.some(i => !Number.isInteger(i) || i < 0 || i >= pool.length)) throw Error('Invalid snapshot reference.'); const ps = refs.map(i => pool[i]); if (new Set(ps.map(p => p.id)).size !== ps.length) throw Error('Duplicate object identity in snapshot.'); return Object.freeze(ps); };
    const frames = data.frames.map(f => Object.freeze({ time: short(f.time, 50), label: short(f.label, 180), kind: short(f.kind, 30), packets: resolve(f.objects) }));
    const packets = resolve(data.current); const blobs = new Map(); let total = 0;
    for (const [id, b] of Object.entries(data.blobs || {})) { if (!/^[a-z0-9-]{1,100}$/.test(id)) throw Error('Invalid byte identity.'); const bytes = base64ToBytes(b.base64); total += bytes.length; if (total > LIMITS.blobBytes || b.size !== bytes.length) throw Error('Invalid byte attachment size.'); blobs.set(id, Object.freeze({ size: bytes.length, base64: b.base64 })); }
    for (const p of pool) if (p.blobId && !blobs.has(p.blobId)) throw Error('Missing byte attachment.');
    this.packets = [...packets]; this.frames = frames; this.blobs = blobs; this.cursor = null; this.undoStack = []; this.redoStack = []; this.capture('Restored workspace; evidence is recorded, not live', 'restore'); this.emit();
  }
  diagnose() { const p = this.view; return [
    { title: 'Evidence stays explicit', value: `${p.filter(x => x.quality === 'simulated').length} simulated / ${p.filter(x => x.quality !== 'simulated').length} other records`, ok: true },
    { title: 'Identity uniqueness', value: `${new Set(p.map(x => x.id)).size} unique identities`, ok: new Set(p.map(x => x.id)).size === p.length },
    { title: 'Recorded memory', value: `${this.frames.length} of ${LIMITS.frames} retained states; oldest rolls off`, ok: true },
    { title: 'External authority', value: 'No execution, host-file mutation, or device control is exposed.', ok: true },
    { title: 'Kernel boundary', value: 'Stage 0 only. Isolation and scheduling are NOT implemented.', ok: false },
    { title: 'Storage', value: 'Session memory by default. Use explicit Save locally or Export.', ok: true }
  ]; }
}
export function kernelRecords(text) {
  if (encoder.encode(text).length > LIMITS.fileBytes) throw Error('Serial input exceeds 256 KiB.');
  const records = [], errors = []; const seen = new Set();
  const fixture = /^# LU_TEST_FIXTURE\b/m.test(text);
  for (const line of text.split(/\r?\n/)) {
    const start = line.indexOf('@LU1 '); if (start < 0) continue;
    const raw = line.slice(start + 5).trim();
    try {
      const p = JSON.parse(raw); if (p?.v !== 1 || p.source !== 'c-native-kernel' || !['x86-64', 'AArch64'].includes(p.arch) || p.stage !== 0 || p.event !== 'boot.snapshot') throw Error('Unrecognized kernel record.');
      if (p.user_space_isolation !== false || p.native_tool_execution !== false || p.firmware_exited !== true) throw Error('Record claims unsupported Stage 0 capabilities.');
      for (const k of ['sequence', 'conventional_pages', 'memory_map_bytes', 'descriptor_size']) if (!Number.isSafeInteger(p[k]) || p[k] < 0) throw Error(`Invalid ${k}.`);
      boundJSON(p); const key = `${p.arch}-${hashText(raw)}`; if (seen.has(key)) continue; seen.add(key);
      records.push(normalizePacket({ id: `kernel-${key}`, name: `${p.arch} / kernel handoff`, node: 'core', channel: 9, quality: fixture ? 'simulated' : 'reported', source: fixture ? 'authored-test-fixture' : 'kernel-serial', createdAt: stamp(), payload: p,
        provenance: { description: (fixture ? 'AUTHORED TEST FIXTURE, not a real boot. ' : '') + 'Stage 0 serial report. Firmware-map values are not a live allocator. This log is not cryptographically authenticated.' } }));
    } catch (e) { errors.push(short(e.message)); }
  }
  return { records: records.slice(-24), errors };
}
export function permissionFor(action) { return ['inspect', 'curate', 'route-local', 'snapshot', 'export'].includes(action) ? { allowed: true, boundary: 'local workspace only' } : { allowed: false, boundary: 'No executor or authority exists for this request.' }; }
export { CHANNELS, NODES, atomsOf, readPointer };
