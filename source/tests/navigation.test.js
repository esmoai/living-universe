import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { PORTALS } from '../src/geometry.js';
import { ARRIVAL_OFFSET, createJourney, movementVector, canTypeTarget } from '../src/navigation.js';

const close = (a, b, epsilon = 1e-6) => assert.ok(a.distanceTo(b) < epsilon, `${a.toArray()} ≉ ${b.toArray()}`);

for (const portal of PORTALS) {
  test(`${portal.id}: route interpolates the mouth and reaches a complete destination chamber`, () => {
    const start = new THREE.Vector3(8, 6, 8);
    const original = start.clone();
    const { curve, end, arrivalOffset, mouthParameter, mouthProgress, duration, destinationId } = createJourney(portal, start);
    close(start, original);
    close(curve.getPointAt(0), start);
    close(curve.getPointAt(1), end.clone().add(new THREE.Vector3(...ARRIVAL_OFFSET)));
    close(arrivalOffset, new THREE.Vector3(...ARRIVAL_OFFSET));
    close(curve.getPoint(mouthParameter), new THREE.Vector3(...portal.center));
    close(curve.getPointAt(mouthProgress), new THREE.Vector3(...portal.center), 0.002);
    assert.equal(destinationId, `${portal.id}-node`);
    assert.ok(duration >= 6 && duration <= 14);
    assert.ok(end.clone().sub(new THREE.Vector3(...portal.center)).dot(new THREE.Vector3(...portal.normal)) < -18);
    assert.ok(curve.getLength() > 20);
  });

  test(`${portal.id}: distance sampling yields finite, smooth, approximately uniform motion`, () => {
    const { curve } = createJourney(portal, new THREE.Vector3(1.8, 0.9, 2));
    const samples = Array.from({ length: 201 }, (_, index) => curve.getPointAt(index / 200));
    const distances = samples.slice(1).map((point, index) => point.distanceTo(samples[index]));
    for (const point of samples) assert.ok(point.toArray().every(Number.isFinite));
    assert.ok(Math.min(...distances) > 0);
    assert.ok(Math.max(...distances) / Math.min(...distances) < 1.2, 'Arc-length motion should not accelerate at uneven control points.');
    const minMouthDistance = Math.min(...samples.map(point => point.distanceTo(new THREE.Vector3(...portal.center))));
    assert.ok(minMouthDistance < 0.11, 'The journey goes through the actual visible portal.');
  });

  test(`${portal.id}: approach clears the black orb from exterior, entered, and near-core viewpoints`, () => {
    const starts = [
      new THREE.Vector3(8, 8, 8),
      new THREE.Vector3(1.3, 0.75, 1.3),
      new THREE.Vector3(1, 1, 1).normalize().multiplyScalar(1.4),
      new THREE.Vector3(...portal.center).normalize().multiplyScalar(-1.4),
    ];
    for (const start of starts) {
      const { curve, mouthParameter } = createJourney(portal, start);
      const distances = Array.from({ length: 1001 }, (_, i) => curve.getPoint(mouthParameter * i / 1000).length());
      assert.ok(Math.min(...distances) >= 1.36, `Approach from ${start.toArray()} must stay outside the black orb.`);
      close(curve.getPointAt(0), start);
    }
  });
}

test('routes remain finite when the user starts at an approach control point', () => {
  const portal = PORTALS[0];
  const start = new THREE.Vector3(...portal.center).multiplyScalar(0.24);
  const { curve } = createJourney(portal, start);
  for (let i = 0; i <= 100; i++) assert.ok(curve.getPointAt(i / 100).toArray().every(Number.isFinite));
});

test('malformed coordinates and directions are rejected', () => {
  assert.throws(() => createJourney(null, new THREE.Vector3()), TypeError);
  assert.throws(() => createJourney(PORTALS[0], new THREE.Vector3(NaN, 0, 0)), TypeError);
  assert.throws(() => createJourney({ ...PORTALS[0], normal: [0, 0, 0] }, new THREE.Vector3()), RangeError);
});

test('free flight uses camera-relative forward and right without diagonal speed boost', () => {
  close(movementVector(0, 0, { forward: 1 }), new THREE.Vector3(0, 0, -1));
  close(movementVector(Math.PI / 2, 0, { forward: 1 }), new THREE.Vector3(-1, 0, 0));
  close(movementVector(0, 0, { right: 1 }), new THREE.Vector3(1, 0, 0));
  close(movementVector(0, 0, { up: 1 }), new THREE.Vector3(0, 1, 0));
  assert.ok(Math.abs(movementVector(0, 0, { forward: 1, right: 1, up: 1 }).length() - 1) < 1e-8);
  assert.ok(movementVector(0, Math.PI / 6, { forward: 1 }).y > 0);
});

test('editable targets retain their normal keyboard input', () => {
  assert.equal(canTypeTarget({ tagName: 'TEXTAREA' }), true);
  assert.equal(canTypeTarget({ tagName: 'input' }), true);
  assert.equal(canTypeTarget({ isContentEditable: true }), true);
  assert.equal(canTypeTarget({ tagName: 'BUTTON' }), false);
  assert.equal(canTypeTarget(null), false);
});
