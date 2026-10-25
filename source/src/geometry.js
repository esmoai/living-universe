import * as THREE from 'three';

export const HALF=3;
export const GLOBE_RADIUS=2.28;
export const PORTALS=[
  {id:'rear-left',center:[-HALF,1,1],normal:[1,0,0],u:[0,1,0],v:[0,0,1]},
  {id:'rear-right',center:[1,1,-HALF],normal:[0,0,1],u:[1,0,0],v:[0,1,0]},
  {id:'bottom',center:[1,-HALF,1],normal:[0,1,0],u:[0,0,1],v:[1,0,0]},
];
export const SPEED={globe:.21,portals:.35,fluid:-.37};
export const V=(x=0,y=0,z=0)=>new THREE.Vector3(x,y,z);
export const TAU=Math.PI*2;
export function spectrum(t){return new THREE.Color().setHSL(((t%1)+1)%1,1,.52);}
export function portalCenter(portal,t){return V(...portal.center).multiplyScalar(1-.64*t);}
export function portalRadius(t){return .13+1.65*Math.pow(1-t,2.15);}
export function portalPoint(portal,t,angle){return portalCenter(portal,t).addScaledVector(V(...portal.u),Math.cos(angle)*portalRadius(t)).addScaledVector(V(...portal.v),Math.sin(angle)*portalRadius(t));}
export function random(seed=12345){return()=>{seed|=0;seed=seed+0x6d2b79f5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
export function wallPoint(wall,a,b){if(wall==='rear-left')return[-HALF,a,b];if(wall==='rear-right')return[a,b,-HALF];if(wall==='bottom')return[a,-HALF,b];throw new Error('Only the two rear walls and bottom exist.');}
export function travelCurve(portal,start,end){const center=V(...portal.center),normal=V(...portal.normal);return new THREE.CatmullRomCurve3([start,center.clone().multiplyScalar(.56),center.clone(),center.clone().addScaledVector(normal,-1.9),end||center.clone().addScaledVector(normal,-4.8)]);}
