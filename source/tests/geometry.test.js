import test from 'node:test';
import assert from 'node:assert/strict';
import { PORTALS, HALF, portalPoint, portalRadius, wallPoint, SPEED, V } from '../src/geometry.js';
test('only the bottom and two rear walls exist',()=>{
  assert.equal(PORTALS.length,3);
  assert.deepEqual(wallPoint('rear-left',1,2),[-HALF,1,2]);
  assert.deepEqual(wallPoint('rear-right',1,2),[1,2,-HALF]);
  assert.deepEqual(wallPoint('bottom',1,2),[1,-HALF,2]);
  assert.throws(()=>wallPoint('front-left',1,2));
});
test('portal mouth lies exactly on its wall and fits inside the cube',()=>{
  for(const p of PORTALS)for(let i=0;i<100;i++){
    const point=portalPoint(p,0,i/100*Math.PI*2);
    assert.ok(Math.abs(point.clone().sub(V(...p.center)).dot(V(...p.normal)))<1e-10);
    assert.ok(point.toArray().every(x=>Math.abs(x)<=HALF));
  }
});
test('wormholes continuously narrow and connect the walls inward to the globe',()=>{
  for(let i=1;i<=100;i++)assert.ok(portalRadius(i/100)<portalRadius((i-1)/100));
  for(const p of PORTALS)assert.ok(portalPoint(p,1,0).length()<2.28);
});
test('globe and portals oppose the clockwise fluid; every portal faces the initial camera',()=>{
  assert.ok(SPEED.globe>0&&SPEED.portals>0&&SPEED.fluid<0);
  const cameraDirection=V(1,1,1).normalize();
  for(const p of PORTALS){assert.ok(V(...p.normal).dot(cameraDirection)>0);assert.ok(V(...p.u).cross(V(...p.v)).equals(V(...p.normal)));}
});
