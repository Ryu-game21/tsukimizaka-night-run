// Render check for the car motion rig (used by tools/rig_check.py; runs inside the game page with internals exposed).
// Returns per-car numbers and a 3x3 contact sheet: rest pose vs the original, wheels spun, steered, body roll, tint.
async (id)=>{
const car=CARS.concat(typeof SCCARS!=="undefined"?SCCARS:[]).find(c=>c.id===id),cfg=RIGS[id];
const mk=async(rig)=>{const gl=await loadPacked(car.model.url);const root=gl.scene,f=car.model;root.scale.setScalar(f.s);
  if(f.rotY){root.rotation.y=Math.PI;root.position.set(-f.off[0]*f.s,f.off[1]*f.s,-f.off[2]*f.s);}else root.position.set(f.off[0]*f.s,f.off[1]*f.s,f.off[2]*f.s);
  root.traverse(o=>{if(o.isMesh)o.frustumCulled=false;});const w=new THREE.Group();w.add(root);let ms=0;if(rig){const t=performance.now();rigModel(w,car);ms=performance.now()-t;}return [w,ms];};
const [A]=await mk(false),[B,ms]=await mk(true),R=rigOf(B);
const W=640,H=300;
if(!window.__R){window.__R=new THREE.WebGLRenderer({preserveDrawingBuffer:true,antialias:false});}
const rd=window.__R;rd.setSize(W,H);rd.setPixelRatio(1);rd.outputEncoding=THREE.sRGBEncoding;
const sc=new THREE.Scene();sc.background=new THREE.Color(0x7d8794);
sc.add(new THREE.HemisphereLight(0xffffff,0x404050,1.1));const dl=new THREE.DirectionalLight(0xffffff,0.9);dl.position.set(3,6,4);sc.add(dl);const dl2=new THREE.DirectionalLight(0xffffff,0.5);dl2.position.set(-4,3,-5);sc.add(dl2);
const L=car.body.l||4.4;
const ortho=(side)=>{const c=new THREE.OrthographicCamera(-L*0.62,L*0.62,L*0.62*H/W+0.25,-(L*0.62*H/W)+0.25,0.1,50);c.position.set(side*10,0.75,0);c.lookAt(0,0.75,0);return c;};
const persp=(pos,tgt,fov=40)=>{const c=new THREE.PerspectiveCamera(fov,W/H,0.05,60);c.position.set(...pos);c.lookAt(...tgt);return c;};
const gl=rd.getContext(),buf=new Uint8Array(W*H*4);
const shot=(obj,cam)=>{sc.add(obj);rd.render(sc,cam);sc.remove(obj);const b=new Uint8Array(W*H*4);gl.readPixels(0,0,W,H,gl.RGBA,gl.UNSIGNED_BYTE,b);return {b,url:rd.domElement.toDataURL('image/png')};};
const diff=(a,b,mask)=>{let n=0;for(let i=0;i<W*H;i++){const k=i*4;if(Math.abs(a[k]-b[k])>10||Math.abs(a[k+1]-b[k+1])>10||Math.abs(a[k+2]-b[k+2])>10){if(!mask||mask(i%W,H-1-(i/W|0)))n++;}}return n;};
const pose=(o)=>{R.wheels.forEach((w,q)=>{w.spin.rotation.x=o.spin||0;w.steer.rotation.y=(o.restore?cfg.hubs[q][6]:0)+(w.front?(o.steer||0):0);});R.body.rotation.set(o.pitch||0,0,o.roll||0);B.updateMatrixWorld(true);};
const out={id,ms:Math.round(ms),moved:0,fixed:B.userData.rigFixed,views:{}};
out.mb=0;B.traverse(o=>{if(o.isMesh&&/rig_s/.test(o.parent&&o.parent.name)){const g=o.geometry;out.moved+=g.index?g.index.count/3:g.attributes.position.count/3;for(const k in g.attributes)out.mb+=g.attributes[k].array.byteLength;if(g.index)out.mb+=g.index.array.byteLength;}});out.mb=+(out.mb/1048576).toFixed(1);
// 1) at rest (wheels restored to the model's own angle) the rigged car must draw exactly like the original
const cams={R:ortho(1),L:ortho(-1),FQ:persp([L*0.75,1.6,L*0.95],[0,0.5,0]),RQ:persp([-L*0.75,1.4,-L*0.95],[0,0.5,0])};
let restDiff=0;pose({restore:1});
for(const [k,c] of Object.entries(cams)){const a=shot(A,c),b=shot(B,c);const d=diff(a.b,b.b);restDiff+=d;out.views['rest_'+k]=d;}
out.restDiff=restDiff;
// 2) spinning the wheels may only change pixels inside the wheel circles (side views)
pose({});const proj=(c,x,y,z)=>{const v=new THREE.Vector3(x,y,z).project(c);return [(v.x+1)/2*W,(1-v.y)/2*H];};
const imgs={};
for(const side of [1,-1]){const c=ortho(side);const a=shot(B,c);pose({spin:1.0});const b=shot(B,c);pose({});
  const circ=cfg.hubs.map(h=>{const [px,py]=proj(c,h[0],h[1],h[2]);const [qx]=proj(c,h[0],h[1],h[2]+h[3]);return [px,py,Math.abs(qx-px)];});
  const outside=diff(a.b,b.b,(x,y)=>!circ.some(([px,py,r])=>Math.hypot(x-px,y-py)<=r*1.1+1.5));
  const inside=diff(a.b,b.b,(x,y)=>circ.some(([px,py,r])=>Math.hypot(x-px,y-py)<=r*1.1+1.5));
  const area=circ.reduce((s,[,,r])=>s+Math.PI*r*r,0)/2;
  out['spinOut'+(side>0?'R':'L')]=outside;out['spinIn'+(side>0?'R':'L')]=+(inside/area).toFixed(2);
  if(side>0){imgs.sideRest=a.url;imgs.sideSpin=b.url;}}
// 3) close-ups: front-left wheel (rest / spun / steered), rear-left, and body roll from the front
const fl=cfg.hubs[2],rl=cfg.hubs[0],sx=Math.sign(fl[0])||-1;
const cw=persp([fl[0]+sx*1.9,fl[1]+0.35,fl[2]+0.7],[fl[0],fl[1],fl[2]],38);
pose({});imgs.flRest=shot(B,cw).url;pose({spin:1.2});imgs.flSpin=shot(B,cw).url;
const cs=persp([fl[0]+sx*1.6,fl[1]+1.3,fl[2]+2.4],[fl[0],fl[1],fl[2]],40);pose({steer:0.45});imgs.flSteer=shot(B,cs).url;pose({steer:-0.45});imgs.flSteer2=shot(B,cs).url;
const cr=persp([rl[0]+Math.sign(rl[0])*1.9,rl[1]+0.35,rl[2]-0.7],[rl[0],rl[1],rl[2]],38);pose({spin:1.2});imgs.rlSpin=shot(B,cr).url;
const cf=persp([0,0.8,L*1.3],[0,0.55,0],38);pose({roll:0.05,pitch:-0.03,steer:0.3});imgs.roll=shot(B,cf).url;
B.traverse(o=>{if(o.isMesh&&o.parent&&/rig_s(pin|teer)/.test(o.parent.name))o.material=new THREE.MeshLambertMaterial({color:/spin/.test(o.parent.name)?0x30d050:0xe0a020});});
const ct=persp([fl[0]+sx*1.25,fl[1]+0.1,fl[2]+1.05],[fl[0],fl[1],fl[2]],44);pose({steer:0.45});imgs.tint=shot(B,ct).url;
pose({});
// compose a sheet: 3 columns x 3 rows
const cv=document.createElement('canvas');cv.width=W*3;cv.height=H*3+0;const g=cv.getContext('2d');
const order=['sideRest','sideSpin','roll','flRest','flSpin','rlSpin','flSteer','flSteer2','tint'];
const labels={sideRest:'side rest',sideSpin:'side spin 1.0rad',roll:'roll/pitch+steer',flRest:'FL rest',flSpin:'FL spin',rlSpin:'RL spin',flSteer:'FL steer +',flSteer2:'FL steer -',tint:'tint: green spins, orange steers'};
for(let i=0;i<order.length;i++){const k=order[i];if(!k)continue;const im=new Image();im.src=imgs[k];await im.decode();g.drawImage(im,(i%3)*W,(i/3|0)*H);g.fillStyle='#000';g.font='bold 16px sans-serif';g.fillText(id+' '+labels[k],(i%3)*W+8,(i/3|0)*H+20);}
out.sheet=cv.toDataURL('image/png');
[A,B].forEach(o=>o.traverse(m=>{if(m.geometry)m.geometry.dispose();}));
return out;}
