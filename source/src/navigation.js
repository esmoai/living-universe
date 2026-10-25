import * as THREE from 'three';

/** Where a journey puts the viewer relative to the next chamber's center. */
export const ARRIVAL_OFFSET = Object.freeze([2.4, 1.4, 2.4]);

function finiteVector(value, name) {
  if (!value?.isVector3 && (!Array.isArray(value) || value.length !== 3)) {
    throw new TypeError(`${name} must contain three finite coordinates.`);
  }
  const v = value?.isVector3 ? value.clone() : new THREE.Vector3(...value);
  if (![v.x, v.y, v.z].every(Number.isFinite)) {
    throw new TypeError(`${name} must contain three finite coordinates.`);
  }
  return v;
}

/** Keep the approach on a spherical shell around the opaque central orb. */
function approachPoints(start, mouth) {
  const shellRadius = 2.2;
  const startRadius = start.length();
  const startDirection = startRadius > 1e-8 ? start.clone().divideScalar(startRadius) : new THREE.Vector3(1, 0, 0);
  const mouthDirection = mouth.clone().normalize();
  const angle = Math.acos(THREE.MathUtils.clamp(startDirection.dot(mouthDirection), -1, 1));
  const points = [start];

  // Already aligned with the mouth: don't turn back inward and loop around.
  if (angle < 0.12 && startRadius >= shellRadius) return points;

  // Several collinear radial points prevent a long exterior segment from
  // pulling the following curved spline inward. Near-orb starts move outward
  // before beginning their turn; they are never sent through the black core.
  const radialSteps = Math.max(1, Math.min(24, Math.ceil(Math.abs(startRadius - shellRadius) / 0.75)));
  for (let i = 1; i <= radialSteps; i++) {
    points.push(startDirection.clone().multiplyScalar(THREE.MathUtils.lerp(startRadius, shellRadius, i / radialSteps)));
  }
  const rotation = new THREE.Quaternion().setFromUnitVectors(startDirection, mouthDirection);
  const arcSteps = Math.max(1, Math.ceil(angle / (Math.PI / 18)));
  for (let i = 1; i <= arcSteps; i++) {
    const step = new THREE.Quaternion().slerp(rotation, i / arcSteps);
    points.push(startDirection.clone().applyQuaternion(step).multiplyScalar(shellRadius));
  }
  points.push(mouthDirection.clone().multiplyScalar(2.65));
  return points;
}

/**
 * Construct a continuous route in the CURRENT chamber's local coordinates.
 * Render another complete chamber with its root at `end` during travel.
 * Advance with curve.getPointAt(progress), NOT curve.getPoint(progress), to
 * move by arc length. `end` is a chamber center, not a camera destination:
 * the final camera position is `end + ARRIVAL_OFFSET`. At completion the
 * scene may subtract `end` from both camera and scene roots to rebase locally.
 * The mouth is an interpolated control point. Beyond it, the route bends
 * through a connecting tunnel and enters a destination cube's open side.
 */
export function createJourney(portal, startVector3) {
  if (!portal || typeof portal.id !== 'string' || !portal.id.trim()) {
    throw new TypeError('A portal with an id is required.');
  }
  const start = finiteVector(startVector3, 'startVector3');
  const mouth = finiteVector(portal.center, 'portal.center');
  const normal = finiteVector(portal.normal, 'portal.normal');
  const u = finiteVector(portal.u, 'portal.u');
  const v = finiteVector(portal.v, 'portal.v');
  if (normal.lengthSq() < 1e-12 || u.lengthSq() < 1e-12 || v.lengthSq() < 1e-12) {
    throw new RangeError('Portal directions must have non-zero length.');
  }
  normal.normalize();
  u.normalize();
  v.normalize();
  const outward = normal.negate();
  const end = mouth.clone().addScaledVector(outward, 20)
    .addScaledVector(u, 2.2).addScaledVector(v, 1.6);
  const arrivalOffset = new THREE.Vector3(...ARRIVAL_OFFSET);
  const arrival = end.clone().add(arrivalOffset);
  const entry = end.clone().addScaledVector(arrivalOffset, 2.4);
  const candidates = [
    ...approachPoints(start, mouth),
    mouth,
    mouth.clone().addScaledVector(outward, 2.5),
    mouth.clone().addScaledVector(outward, 7).addScaledVector(u, 0.7).addScaledVector(v, 0.4),
    mouth.clone().addScaledVector(outward, 13).addScaledVector(u, 2.8).addScaledVector(v, 0.9),
    entry,
    arrival,
  ];
  // Avoid adjacent duplicates when a caller is already at an approach point.
  const points = candidates.filter((point, index) => index === 0 || point.distanceToSquared(candidates[index - 1]) > 1e-12);
  const curve = new THREE.CatmullRomCurve3(points, false, 'centripetal');
  curve.arcLengthDivisions = 1200;
  curve.updateArcLengths();
  const length = curve.getLength();
  const mouthIndex = points.findIndex(point => point.distanceToSquared(mouth) < 1e-12);
  const mouthParameter = mouthIndex / (points.length - 1);
  const lengths = curve.getLengths();
  const arcIndex = mouthParameter * curve.arcLengthDivisions;
  const low = Math.floor(arcIndex);
  const high = Math.min(lengths.length - 1, low + 1);
  const mouthDistance = THREE.MathUtils.lerp(lengths[low], lengths[high], arcIndex - low);

  return {
    curve,
    end,
    destinationId: `${portal.id}-node`,
    duration: THREE.MathUtils.clamp(length / 4.2, 6, 14),
    arrivalOffset,
    mouthParameter,
    mouthProgress: mouthDistance / length,
  };
}

/** Direction for free flight; input components are forward/right/up. */
export function movementVector(yaw, pitch, input = {}) {
  if (![yaw, pitch].every(Number.isFinite)) throw new TypeError('Camera angles must be finite.');
  const forward = Number(input.forward || 0);
  const right = Number(input.right || 0);
  const up = Number(input.up || 0);
  if (![forward, right, up].every(Number.isFinite)) throw new TypeError('Movement inputs must be finite.');
  const orientation = new THREE.Quaternion().setFromEuler(new THREE.Euler(pitch, yaw, 0, 'YXZ'));
  const direction = new THREE.Vector3(right, 0, -forward).applyQuaternion(orientation);
  direction.y += up;
  if (direction.lengthSq() > 1) direction.normalize();
  return direction;
}

/** Ignore flight shortcuts while a text-editable element has focus. */
export function canTypeTarget(target) {
  if (!target) return false;
  const tag = String(target.tagName || '').toUpperCase();
  return target.isContentEditable === true || ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag);
}
