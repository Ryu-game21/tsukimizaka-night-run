// Headless logic tests for the game (no WebGL, no audio, no network).
// usage: node tests/run.js          -> prints PASS/FAIL lines, exit code 1 on any failure
// The game's last <script> is pulled out of site/index.html and a hook exposing internals is injected
// just before the closing "})();". THREE is stubbed except Vector3 / CatmullRomCurve3 (track maths).
const fs=require('fs'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'..','site','index.html'),'utf8');
const i0=html.lastIndexOf('<script>'),i1=html.indexOf('</script>',i0);
let src=html.slice(i0+8,i1);const end=src.lastIndexOf('})();');
src=src.slice(0,end)+`global.__t={CARS,COURSES,AI,pl,get N(){return N},get P(){return P},get TH(){return TH},get laps(){return laps},
selectCourse,selectCar,start,frame,setMode,setTM,shiftGear,setWeather,showStep,nextStep,prevStep,toMenu,startReplay,endReplay,startTutorial,
loadRp,keys,get state(){return state},get step(){return step},get sessRp(){return sessRp},get tut(){return tut},get GRIP(){return GRIP},
get BR_P(){return BR_P},get CAR(){return CAR},get rpTime(){return rpTime},get sel(){return sel},get mode(){return mode}};\n`+src.slice(end);
function U(name='u'){const f=function(){};return new Proxy(f,{
  get(t,k){if(k===Symbol.toPrimitive)return()=>0;if(k==='then')return undefined;if(k==='length')return 0;if(k===Symbol.iterator)return function*(){};return U(name+'.'+String(k));},
  set(){return true;},apply(){return U(name+'()');},construct(){return U('new '+name);} });}

class V3{constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z;}set(x,y,z){this.x=x;this.y=y;this.z=z;return this;}copy(v){return this.set(v.x,v.y,v.z);}
 subVectors(a,b){return this.set(a.x-b.x,a.y-b.y,a.z-b.z);}normalize(){const l=Math.hypot(this.x,this.y,this.z)||1;return this.set(this.x/l,this.y/l,this.z/l);}
 distanceTo(v){return Math.hypot(this.x-v.x,this.y-v.y,this.z-v.z);}applyQuaternion(){return this;}clone(){return new V3(this.x,this.y,this.z);}}
class Curve{constructor(p){this.p=p;}getSpacedPoints(n){const out=[],m=this.p.length;for(let i=0;i<=n;i++){const f=i/n*m,k=Math.floor(f)%m,t=f-Math.floor(f),a=this.p[k],b=this.p[(k+1)%m];out.push(new V3(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,a.z+(b.z-a.z)*t));}return out;}
 getLength(){let L=0;for(let i=0;i<this.p.length;i++)L+=this.p[i].distanceTo(this.p[(i+1)%this.p.length]);return L;}}
const base=U('THREE');
global.THREE=new Proxy({},{get(t,k){if(k==='Vector3')return V3;if(k==='CatmullRomCurve3')return Curve;return base[k];}});

const els={};
global.document={getElementById:id=>els[id]||(els[id]=U('#'+id)),querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>U('el'),addEventListener(){},fonts:{ready:Promise.resolve()},activeElement:null,body:U('body')};
global.window=global;global.addEventListener=()=>{};global.matchMedia=()=>({matches:false});
const LS={'fpr-player':'T'};global.localStorage={getItem:k=>k in LS?LS[k]:null,setItem(k,v){LS[k]=String(v)},removeItem(k){delete LS[k]},get length(){return Object.keys(LS).length},key:i=>Object.keys(LS)[i]};global.__LS=LS;global.requestAnimationFrame=()=>{};global.performance={now:()=>0};
global.innerWidth=1400;global.innerHeight=800;global.devicePixelRatio=1;global.navigator={};
let fails=0;const ok=(c,m)=>{console.log((c?'PASS ':'FAIL ')+m);if(!c)fails++;};
const origLog=console.log;console.error=()=>{};
try{eval(src);ok(true,'script loads');}catch(e){ok(false,'script loads: '+e.message);process.exit(1);}
global.AudioContext=function(){return U('ac');};
const t=global.__t;let now=0;const step=n=>{for(let k=0;k<n;k++){now+=16;t.frame(now);}};
const drive=(frames,v)=>{const N=t.N;let k=t.pl.idx;for(let f=0;f<frames;f++){k=(k+1)%N;const p=t.P[k];t.pl.x=p.x;t.pl.z=p.z;t.pl.th=t.TH[k];t.pl.v=v;step(1);if(t.state!=='race')break;}};
setTimeout(()=>{try{
  // menu flow
  ok(t.step==='title','starts on the title screen');
  t.nextStep();ok(t.step==='mode','title -> mode');
  for(let k=0;k<5;k++)t.nextStep();ok(t.step==='go','mode -> ... -> ready');
  t.prevStep();ok(t.step==='cond','back one step');
  // every course builds
  t.COURSES.forEach((c,k)=>{try{t.selectCourse(k);ok(t.N>100,'course builds: '+c.id);}catch(e){ok(false,'course builds: '+c.id+' '+e.message);}});
  // weather
  t.selectCourse(0);t.setWeather('clear');const g0=t.GRIP,b0=t.BR_P;t.setWeather('rain');
  ok(Math.abs(t.GRIP/g0-0.8)<1e-6&&Math.abs(t.BR_P/b0-0.85)<1e-6,'rain grip 80% / brake 85%');t.setWeather('clear');
  // race lap -> replay
  t.setMode('race');t.start();step(260);drive(Math.floor(t.N*1.3),40);
  ok(t.laps.length>=1&&!!t.sessRp,'race lap recorded with replay');
  t.startReplay(t.sessRp,'result');step(120);ok(t.state==='replay'&&t.rpTime>1,'replay plays');t.endReplay();ok(t.state==='finish','replay returns to results');
  t.toMenu('course');ok(!!t.loadRp(),'best-lap replay saved');
  // tutorial
  t.selectCourse(3);t.startTutorial();step(260);ok(t.sel===0&&t.mode==='free'&&!!t.tut,'tutorial starts on course 0, free run');
  t.toMenu('title');ok(t.sel===3&&t.mode==='race'&&!t.tut,'tutorial restores settings');
  // 0-100 km/h per car: AT must match the catalogue figure, MT with perfect shifts must match AT
  for(let ci=0;ci<t.CARS.length;ci++){const res={};
    for(const tm of ['at','mt']){t.setTM(tm);t.selectCar(ci);t.selectCourse(2);t.setMode('free');t.start();step(130);
      let tt=0,r=null;t.keys.up=1;for(let f=0;f<1200&&r==null;f++){
        if(tm==='mt'){const C=t.CAR,kmh=Math.abs(t.pl.v)*3.6;if(t.pl.gear<C.gears&&kmh>=C.gearTop[t.pl.gear-1]*0.985)t.shiftGear(1);}
        step(1);tt+=0.016;t.pl.off=0;t.pl.th=t.TH[t.pl.idx];if(t.pl.v>=27.78)r=tt;}
      t.keys.up=0;res[tm]=r;}
    const c=t.CARS[ci];
    // cars with lag:1 (e.g. 911 turbo 930) spool up from standstill on purpose, so they run ~0.8 s slower than the catalogue figure
    ok(res.at!=null&&Math.abs(res.at-c.t100)<(c.lag?1.0:0.25)&&Math.abs(res.mt-res.at)<0.1,`0-100 ${c.id}: AT ${res.at&&res.at.toFixed(2)} MT ${res.mt&&res.mt.toFixed(2)} (catalogue ${c.t100})`);}
  t.setTM('at');
}catch(e){ok(false,'exception: '+e.message+' '+e.stack.split('\n')[1]);}
origLog(fails?`\n${fails} FAILED`:'\nALL PASSED');process.exit(fails?1:0);},30);
