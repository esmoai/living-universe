// TIA-598 identifies individual fibers. Semantic roles are an application taxonomy.
// Hex values are display approximations, not a colorimetric conformance claim.
export const CHANNELS = [
  { id: 1, color: 'Blue', hex: '#2785ff', role: 'Observations', key: 'observations' },
  { id: 2, color: 'Orange', hex: '#ff881f', role: 'Actions', key: 'actions' },
  { id: 3, color: 'Green', hex: '#52ff71', role: 'Resources', key: 'resources' },
  { id: 4, color: 'Brown', hex: '#b97942', role: 'Identity', key: 'identity' },
  { id: 5, color: 'Slate', hex: '#9cb4c8', role: 'Schemas', key: 'schemas' },
  { id: 6, color: 'White', hex: '#f0ffff', role: 'Documents', key: 'documents' },
  { id: 7, color: 'Red', hex: '#ff354f', role: 'Alerts', key: 'alerts' },
  { id: 8, color: 'Black', hex: '#10151c', role: 'Policies', key: 'policies' },
  { id: 9, color: 'Yellow', hex: '#f4ff39', role: 'Telemetry', key: 'telemetry' },
  { id: 10, color: 'Violet', hex: '#a05aff', role: 'Knowledge', key: 'knowledge' },
  { id: 11, color: 'Rose', hex: '#ff55bd', role: 'Collaboration', key: 'collaboration' },
  { id: 12, color: 'Aqua', hex: '#35ffe2', role: 'Spatial', key: 'spatial' },
];
export const NODES = {
  core: { id: 'core', number: '00', name: 'Shared reality', title: 'The coalescence', description: 'One shared space.\nEvery capability, within reach.', position: [0, 0, 0], channel: 12 },
  intelligence: { id: 'intelligence', number: '01', name: 'Xputty AI', title: 'The knowledge field', description: 'Patterns, context, and possibility.\nInspect the shape of an inference.', position: [-9, 4.8, -6], channel: 10 },
  collaboration: { id: 'collaboration', number: '02', name: 'Collaboration', title: 'The shared presence', description: 'Many perspectives.\nOne evolving reality.', position: [9, 3.3, -6], channel: 11 },
  tools: { id: 'tools', number: '03', name: 'Tools', title: 'The action space', description: 'Connect an intention.\nDiscover a permitted capability.', position: [1, -8, -7], channel: 2 },
};
export const channelFor = id => CHANNELS.find(c => c.id === Number(id));
export const MAX_BYTES = 256 * 1024;
export function validatePayload(value) {
  let count = 0;
  function visit(item, depth) {
    if (depth > 20) throw new Error('This payload exceeds the maximum nesting depth of 20.');
    if (++count > 5000) throw new Error('This payload exceeds the maximum of 5,000 fields.');
    if (item && typeof item === 'object') Object.values(item).forEach(child => visit(child, depth + 1));
  }
  visit(value, 0);
  return value;
}
export function parsePayload(text) {
  if (new TextEncoder().encode(text).byteLength > MAX_BYTES) throw new Error('Use a JSON payload smaller than 256 KB.');
  let payload;
  try { payload = JSON.parse(text); } catch (error) { throw new Error(`Invalid JSON: ${error.message}`); }
  return validatePayload(payload);
}
export const pointerToken = key => String(key).replaceAll('~', '~0').replaceAll('/', '~1');
export function atomsOf(value, path = '') {
  if (value !== null && typeof value === 'object' && Object.keys(value).length) {
    return Object.entries(value).flatMap(([key, child]) => atomsOf(child, `${path}/${pointerToken(key)}`));
  }
  return [{ path, value }];
}
export function readPointer(value, path) {
  if (!path) return value;
  let current = value;
  for (const key of path.slice(1).split('/').map(s => s.replaceAll('~1', '/').replaceAll('~0', '~'))) {
    if (current === null || typeof current !== 'object' || !Object.hasOwn(current, key)) throw new Error('This atom is no longer available.');
    current = current[key];
  }
  return current;
}
function samplePayload(channel, index) {
  const examples = {
    1: { source: 'environment.sensor', observation: { temperature: 23.4 + index * .2, unit: 'celsius', confidence: .98 }, frame: { x: 1.2, y: .8, z: -.4 } },
    2: { capability: 'scene.place_object', input: { asset: 'spatial-marker', anchor: 'world' }, permission: { scope: 'local.scene', granted: false }, execution: 'simulation-only' },
    3: { resource: 'spatial-mesh', mediaType: 'model/gltf+json', properties: { vertices: 2048, coordinateSystem: 'right-handed', unit: 'meter' }, available: true },
    4: { subject: 'local-explorer', identity: { kind: 'demo', session: 'sandbox-01', authenticated: false }, grants: ['inspect', 'local-route'] },
    5: { schema: 'capability-packet', version: '0.1', fields: { channel: 'integer:1..12', payload: 'json', node: 'node-id' }, required: ['channel', 'payload'] },
    6: { title: 'Shared reality protocol', body: 'A packet retains its channel identity when it travels between nodes.', format: 'text/plain', revision: 1 },
    7: { event: 'threshold.example', severity: 'informational', condition: { metric: 'temperature', threshold: 30, observed: 23.4 }, active: false },
    8: { policy: 'local-sandbox', rules: { networkExecution: false, persistImports: false, inspection: true, manualRouting: true }, enforcement: 'no-connected-backend' },
    9: { source: 'demo-stream', measurements: { latency: 12, unit: 'ms', sampleWindow: 1000 }, simulated: true },
    10: { concept: 'spatial-context', relation: { subject: 'data-packet', predicate: 'belongs-to', object: 'shared-reality' }, provenance: { source: 'authored-example', modelExecuted: false } },
    11: { participant: 'example-observer', presence: { state: 'local', sharedSession: false }, event: { type: 'cursor.move', position: [0.2, 1.6, -1] } },
    12: { frame: 'world', pose: { position: { x: .25, y: 1.6, z: -2 }, rotation: { x: 0, y: 0, z: 0, w: 1 } }, units: 'meters' },
  };
  return examples[channel];
}
const names = ['Ambient observation', 'Place an object', 'Spatial mesh', 'Explorer identity', 'Packet schema', 'Reality protocol', 'Threshold signal', 'Sandbox policy', 'Stream telemetry', 'Spatial context', 'Shared presence', 'World anchor'];
export function createSamples() {
  const result = [];
  for (const node of Object.keys(NODES)) {
    for (const channel of CHANNELS) {
      for (let i = 0; i < (node === 'core' ? 3 : 1); i++) {
        result.push({ id: `sample-${node}-${channel.id}-${i}`, name: `${names[channel.id - 1]}${i ? ` ${i + 1}` : ''}`, channel: channel.id, node, source: 'sample', createdAt: '2026-10-24T12:00:00Z', payload: samplePayload(channel.id, i), history: [] });
      }
    }
  }
  return result;
}
export function makePacket({ name, channel, node, payload, source = 'local-import' }) {
  if (!channelFor(channel)) throw new Error('Choose a channel from 1 to 12.');
  if (!Object.hasOwn(NODES, node)) throw new Error('Choose an existing node.');
  validatePayload(payload);
  return { id: crypto.randomUUID(), name: String(name).trim().slice(0, 80) || 'Untitled packet', channel: Number(channel), node, source, createdAt: new Date().toISOString(), payload: structuredClone(payload), history: [] };
}
export function routeData(packet, destination, atomPath = null) {
  if (!Object.hasOwn(NODES, destination)) throw new Error('Choose an existing destination.');
  if (destination === packet.node) throw new Error('This packet is already at that node. Choose another destination.');
  const from = packet.node;
  const event = { time: new Date().toISOString(), action: atomPath === null ? 'route-packet' : 'copy-atom', from, to: destination, packetId: packet.id, packetName: packet.name, channel: packet.channel, path: atomPath };
  if (atomPath !== null) {
    const copied = makePacket({ name: `${packet.name} · atom`, channel: packet.channel, node: destination, source: 'atomic-copy', payload: { provenance: { packetId: packet.id, path: atomPath, source: from }, value: readPointer(packet.payload, atomPath) } });
    copied.history.push(event);
    return { packet: copied, event };
  }
  packet.node = destination;
  packet.history.push(event);
  return { packet, event };
}
