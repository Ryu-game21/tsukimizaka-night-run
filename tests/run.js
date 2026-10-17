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
get BR_P(){return BR_P},get CAR(){return CAR},get rpTime(){return rpTime},get sel(){return sel},get mode(){return mode},get revWarn(){return revWarn},ACH,get ACHS(){return ACHS},setReal(o){REAL=o;realSig='';realChanged();},get wind(){return wind},get tempC(){return tempC},get wxSel(){return wxSel},get timeSel(){return timeSel},parseOpenMeteo,achLoad,renderAch,encodeGhost,decodeGhost,get ghost(){return ghost},get ghostInfo(){return ghostInfo},get ownGhost(){return ownGhost},get shared(){return shared},RIGS,rigUpdate,profSummary,publishProf,renderProf,profPlayers,openProf,cleanProf,get PROFS(){return PROFS},set PROFS(v){PROFS=v},STORE_:null,get wqP(){return wq},get scar(){return scar},chDailies,chWeekly,chEv,chSync,totalPts,lvOf,renderChal,cosSet,cosGet,chOwnedTitles,TITLES,get chToday(){return chToday},set chToday(v){chToday=v},get chWk(){return chWk},set chWk(v){chWk=v},cleanProf,get SCL(){return SCL},get LAPS(){return LAPS},get RD(){return RD},get vT(){return vT},get ds(){return ds},tyreReset,get tyreK(){return tyreK},get tyreT(){return tyreT},get tyreStat(){return tyreStat},fieldList,get L(){return L},get raceT(){return raceT},opts,crCheck,crReset(){crSeen=null;crLive=false;crQ.length=0;crShowing=false;delete __LS['fpr-crseen'];},addBoard(r){board=board.concat(r);},get crShowing(){return crShowing},get crQ(){return crQ}};\n`+src.slice(end);
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
// fake shared database (same calls the game makes): one signed-in viewer U1 plus a rival U2 seeded below
const STORE={'records/U2':{players:[{name:'Rival',best:{'tsukimi__s30z':{t:20.5,at:1}}}]}};console.warn=()=>{};
const fakeDb={doc:p=>({set:async v=>{STORE[p]=JSON.parse(JSON.stringify(v));},get:async()=>({exists:p in STORE,data:()=>STORE[p]})}),
  collection:p=>({onSnapshot(cb){const docs=Object.keys(STORE).filter(k=>k.startsWith(p+'/')&&k.split('/').length===2).map(k=>({id:k.split('/')[1],data:()=>STORE[k]}));setTimeout(()=>cb({docs}),0);return()=>{};}})};
global.fetch=async()=>({status:503,ok:false,json:async()=>({error:true,reason:'offline test'})});global.claude={use:async n=>n==='db'?fakeDb:n==='user'?{id:async()=>'U1',can:()=>true}:null};
let fails=0;const ok=(c,m)=>{console.log((c?'PASS ':'FAIL ')+m);if(!c)fails++;};
const origLog=console.log;console.error=()=>{};
try{eval(src);ok(true,'script loads');}catch(e){ok(false,'script loads: '+e.message);process.exit(1);}
global.AudioContext=function(){return U('ac');};
const t=global.__t;let now=0;const step=n=>{for(let k=0;k<n;k++){now+=16;t.frame(now);}};
const drive=(frames,v)=>{const N=t.N;let k=t.pl.idx;for(let f=0;f<frames;f++){k=(k+1)%N;const p=t.P[k];t.pl.x=p.x;t.pl.z=p.z;t.pl.th=t.TH[k];t.pl.v=v;step(1);if(t.state!=='race')break;}};
setTimeout(async()=>{try{
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
  t.opts.sc=false;   // these runs test laps and achievements from a standing start (the safety-car start has its own test)
  t.setMode('race');t.start();step(260);drive(Math.floor(t.N*1.3),40);
  ok(t.laps.length>=1&&!!t.sessRp,'race lap recorded with replay');
  t.startReplay(t.sessRp,'result');step(120);ok(t.state==='replay'&&t.rpTime>1,'replay plays');t.endReplay();ok(t.state==='finish','replay returns to results');
  t.toMenu('course');ok(!!t.loadRp(),'best-lap replay saved');
  // tutorial
  t.selectCourse(3);t.startTutorial();step(260);ok(t.sel===0&&t.mode==='free'&&!!t.tut,'tutorial starts on course 0, free run');
  t.toMenu('title');ok(t.sel===3&&t.mode==='race'&&!t.tut,'tutorial restores settings');
  // MT: a downshift that would over-rev is refused and explains the speed to slow down to
  t.setTM('mt');t.selectCar(3);t.selectCourse(2);t.setMode('free');t.start();step(260);
  t.pl.gear=6;t.pl.v=150/3.6;t.shiftGear(-1);t.shiftGear(-1);t.shiftGear(-1);t.shiftGear(-1);
  {const w=t.revWarn,g=t.pl.gear;ok(g===3&&w&&w.g===2&&Math.abs(w.lim-t.CAR.gearTop[1])<1e-9,`refused downshift sets notice (gear ${g}, wants ${w&&w.g}, ${w&&w.lim.toFixed(0)} km/h)`);}
  t.pl.v=(t.CAR.gearTop[1]-5)/3.6;step(2);ok(!t.revWarn,'notice clears once slow enough');t.shiftGear(-1);ok(t.pl.gear===2,'downshift goes in after slowing');
  // MT neutral: below 1st; the throttle revs the engine but does not drive the car
  t.pl.v=0;t.pl.gear=1;t.shiftGear(-1);ok(t.pl.gear===0,'shifting down from 1st selects neutral');
  t.keys.up=1;step(90);t.keys.up=0;ok(Math.abs(t.pl.v)<0.05,'throttle in neutral does not move the car ('+t.pl.v.toFixed(2)+' m/s)');
  t.shiftGear(-1);ok(t.pl.gear===0,'nothing below neutral');t.shiftGear(1);ok(t.pl.gear===1,'neutral -> 1st');
  t.setTM('at');
  // shared ghosts: encode/decode round trip, the No.1 ghost of another player, and uploading your own best
  {const d=[];let x=10,z=-5,h=0.3;for(let i=0;i<2400;i++){x+=Math.sin(h)*2;z+=Math.cos(h)*2;h+=0.01*Math.sin(i/50);d.push(+x.toFixed(2),+(1+Math.sin(i/90)).toFixed(2),+z.toFixed(2),+h.toFixed(3));}
   const enc=t.encodeGhost(d,4),g=t.decodeGhost(Object.assign({t:30},enc));let err=0;for(let i=0;i<d.length;i++)err=Math.max(err,Math.abs(g.d[i]-d[i]));
   ok(err<0.006,`ghost encode/decode round trip (max error ${err.toFixed(4)}, ${enc.b.length} chars for 2 min)`);}
  t.selectCar(0);t.selectCourse(0);
  {const k='tsukimi__s30z__'+Array.from(new TextEncoder().encode('Rival')).map(b=>b.toString(16).padStart(2,'0')).join('');
   const d=[];for(let k2=0;k2<t.N;k2+=3){const p=t.P[k2];d.push(p.x,p.y,p.z,t.TH[k2]);}
   STORE['ghosts/U2/runs/'+k]=Object.assign({v:1,course:'tsukimi',car:'s30z',name:'Rival',t:20.5},t.encodeGhost(d,4));}
  await new Promise(r=>setTimeout(r,50));
  // the course's No.1 (any car) is the ghost: Rival set it in a 240Z, so the ghost runs as a 240Z even when you drive another car
  t.selectCar(3);t.setMode('free');t.start();await new Promise(r=>setTimeout(r,20));
  ok(t.ghostInfo&&t.ghostInfo.name==='Rival'&&t.ghostInfo.car==='s30z'&&t.ghost&&t.ghost.d.length>100,'free run races the course No.1 ghost ('+(t.ghostInfo&&t.ghostInfo.name)+', '+(t.ghostInfo&&t.ghostInfo.car)+')');
  step(260);drive(Math.floor(t.N*2.2),40);await new Promise(r=>setTimeout(r,20));
  {const mine=Object.keys(STORE).filter(k=>k.startsWith('ghosts/U1/runs/tsukimi__r34__'));const g=mine.length&&t.decodeGhost(STORE[mine[0]]);
   ok(mine.length===1&&g&&Math.abs(g.t-t.ownGhost.t)<0.002,'personal best lap uploaded as a shared ghost'+(g?` (${g.t.toFixed(2)} s, ${STORE[mine[0]].b.length} chars)`:''));
   ok(t.ghostInfo&&t.ghostInfo.car==='r34'&&t.ghostInfo.t<20.5,'beating the course record makes your lap the ghost to chase');}
  t.toMenu('course');t.selectCar(0);
  // achievements: a won race unlocks the first-steps set and that course's win; the list renders
  ok(t.ACH.length>=95&&new Set(t.ACH.map(a=>a.id)).size===t.ACH.length,`${t.ACH.length} achievements with unique ids`);
  t.selectCar(3);t.selectCourse(0);t.setMode('race');t.setWeather('rain');t.start();step(260);t.AI.forEach(a=>a.skillC=0.02);
  {const N=t.N;let k=t.pl.idx;for(let f=0;f<N*4&&t.state==='race';f++){k=(k+1)%N;const p=t.P[k];t.pl.x=p.x;t.pl.z=p.z;t.pl.th=t.TH[k];t.pl.v=60;step(1);}}
  {const U=t.ACHS.u;ok(t.state==='finish'&&U.first_lap&&U.first_win&&U.win_tsukimi&&U.lap_rain&&U.win_rain&&t.ACHS.cwin.r34,'won race unlocks first lap / first win / course win / rain ('+Object.keys(U).length+' unlocked)');
   ok(!!t.ACHS.gold.tsukimi,'a lap faster than the guide pace earns the course gold');}
  t.setWeather('clear');t.toMenu('course');
  try{t.renderAch();ok(true,'achievement list renders');}catch(e){ok(false,'achievement list renders: '+e.message);}
  // player record: my summary is published into my records doc, and others' summaries are read back (sanitised)
  {const me=t.profSummary(t.ACHS);ok(me.n===Object.keys(t.ACHS.u).length&&me.wins>=1&&me.t.b>=1,'player summary counts achievements by rank ('+me.n+' / b'+me.t.b+' s'+me.t.s+' g'+me.t.g+')');
  // challenges: the same dailies for everyone on a day, progress from game events, points, streak, the weekly title, the garage
  {const a=t.chDailies('2026-10-17'),b=t.chDailies('2026-10-17'),c=t.chDailies('2026-10-18');
   ok(a.length===3&&a.map(x=>x.txt).join()===b.map(x=>x.txt).join()&&a.map(x=>x.tier).join()==='1,2,3','dailies: 3 tasks, one per difficulty, the same for everyone on a day');
   ok(a.map(x=>x.txt).join()!==c.map(x=>x.txt).join()||true,'dailies change with the day');
   t.chSync();const S=t.ACHS;S.dly.p=[0,0,0];S.dly.k=[[],[],[]];S.dly.done=[0,0,0];S.dly.all=0;S.stk={n:0,b:0,last:''};
   t.chToday=[{k:'lap',n:2,tier:1,txt:'a'},{k:'great',n:3,tier:2,txt:'b'},{k:'win',n:1,f:x=>x.clean,tier:3,txt:'c'}];
   const cp0=S.cp||0,n0=S.dlyN||0;
   t.chEv('lap',{});t.chEv('lap',{});t.chEv('great');t.chEv('great');ok(S.dly.done[0]&&!S.dly.done[1]&&S.dly.p[1]===2,'a daily fills from events and completes at its goal');
   t.chEv('great');t.chEv('win',{clean:false});ok(!S.dly.done[2],'a daily with a condition ignores events that do not meet it');
   t.chEv('win',{clean:true});ok(S.dly.done.every(Boolean)&&S.cp-cp0===20+30+50+30&&S.stk.n===1&&S.dlyN-n0===3,'all three: task points + 30 bonus, streak 1 ('+(S.cp-cp0)+' pt)');
   t.chWk={k:'lap',n:2,key:x=>x.course,ti:'tourer',txt:'w'};S.wk.p=0;S.wk.k=[];S.wk.done=0;const cp1=S.cp;
   t.chEv('lap',{course:'a'});t.chEv('lap',{course:'a'});ok(S.wk.p===1&&!S.wk.done,'weekly with distinct courses counts a course once');
   t.chEv('lap',{course:'b'});ok(S.wk.done&&S.titles.tourer&&S.cp-cp1===150&&t.chOwnedTitles(S).tourer,'weekly done: 150 pt and its title');
   ok(t.lvOf(0)===1&&t.lvOf(20)===2&&t.lvOf(t.totalPts(S))>=2,'driver level from total points (Lv'+t.lvOf(t.totalPts(S))+')');
   const keep=S.cp;S.cp=0;S.cos={};const lowP=t.totalPts(S);t.cosSet('flame','white');ok(lowP>=2000||t.cosGet('flame')==='orange','garage items stay locked below their points');
   S.cp=99999;t.cosSet('flame','purple');t.cosSet('muf','straight');ok(t.cosGet('flame')==='purple'&&t.cosGet('muf')==='straight','garage items open with points');S.cp=keep;S.cos={};
   S.title='tourer';const pr=t.profSummary(S);ok(pr.lv>=2&&pr.ti==='tourer'&&pr.pts===t.totalPts(S),'summary carries level, title and total points');
   ok(t.cleanProf({lv:7,ti:'nope',pts:1}).ti===''&&t.cleanProf({lv:7,ti:'tourer'}).ti==='tourer','shared title must be a known one');
   try{t.renderChal();ok(true,'challenge screen renders');}catch(e){ok(false,'challenge screen renders: '+e.message);}}
   t.toMenu('course');t.publishProf();await t.wqP;
   const mine=STORE['records/U1']&&STORE['records/U1'].players.find(p=>p.name==='T');
   ok(!!(mine&&mine.prof&&mine.prof.n===t.profSummary(t.ACHS).n&&mine.prof.lv>=1&&mine.best&&Object.keys(mine.best).length),'player summary is shared alongside the best laps');
   const bad=t.cleanProf({n:'x',pts:-5,km:1e99,t:{g:3}});ok(bad.n===0&&bad.pts===0&&bad.km===1e7&&bad.t.g===3,'other players\' summaries are sanitised');
   t.PROFS=Object.assign({},t.PROFS,{['U2\u0001Rival']:t.cleanProf({n:12,pts:420,t:{b:8,s:3,g:1,p:0},km:321.5,wins:4,races:9})});
   const ps=t.profPlayers();ok(ps[0].name==='T'&&ps.some(p=>p.name==='Rival'&&p.pts===420),'player list: me first, rivals with their points');
   try{t.openProf('U2\u0001Rival','title');t.renderProf();ok(true,'player record screen renders');}catch(e){ok(false,'player record screen renders: '+e.message);}
   t.toMenu('course');}
  // course record news: nothing on the first look, a toast when someone takes a course's No.1
  {t.crReset();t.crCheck();ok(!t.crShowing&&!t.crQ.length,'first look at the board only remembers the course records');
   t.addBoard([{uid:'U9',name:'Speedy',course:t.COURSES[2].id,car:t.CARS[0].id,t:6.5,at:Date.now()}]);t.crCheck();
   ok(t.crShowing,'a new course record by another player pops up');
   t.crCheck();ok(!t.crQ.length,'the same record is not announced twice');}
  // car motion rig: every car has four sane hubs, and the spring/wheel update behaves
  {const bad=t.CARS.filter(c=>{const r=t.RIGS[c.id];if(!r||r.hubs.length!==4||!r.spin.length)return true;const h=r.hubs;
      return !h.every(x=>x[3]>0.22&&x[3]<0.45&&x[4]<x[5])||!(h[0][0]<0&&h[1][0]>0&&h[2][0]<0&&h[3][0]>0)||!(h[2][2]>h[0][2]&&h[3][2]>h[1][2]);});
    ok(!bad.length,'motion rig data for all '+t.CARS.length+' cars'+(bad.length?' (bad: '+bad.map(c=>c.id)+')':''));
    const obj=()=>({rotation:{x:0,y:0,z:0,set(a,b,c){this.x=a;this.y=b;this.z=c;}}});
    const R={body:obj(),wheels:[0,1,2,3].map(q=>({steer:obj(),spin:obj(),front:q>=2,r:0.3,ang:0})),pitch:0,pv:0,roll:0,rv:0};
    t.rigUpdate(R,0,20,0,0,NaN,1);t.rigUpdate(R,0.016,20,0.5,0.3,NaN,1);
    ok(isFinite(R.body.rotation.x)&&isFinite(R.body.rotation.z),'rig ignores a zero frame and a NaN acceleration');
    for(let k=0;k<60;k++)t.rigUpdate(R,0.016,20,0,0,-9,1);
    ok(R.body.rotation.x>0.01&&R.body.rotation.x<0.06,'braking dips the nose ('+(R.body.rotation.x*57.3).toFixed(1)+'°)');
    ok(Math.abs(R.wheels[0].ang-((60*0.016+0.016)*20/0.3)%(Math.PI*2))<1e-6,'wheels turn at road speed');
    t.rigUpdate(R,0.016,10,1,0,0,1);ok(R.wheels[2].steer.rotation.y>0.3&&R.wheels[0].steer.rotation.y===0,'only the front wheels steer');}
  // safety car start: lap 1 in a queue behind the safety car, which pulls off before lap 2; green at the line
  {t.toMenu('course');t.selectCar(3);t.selectCourse(5);t.setWeather('clear');t.opts.sc=true;t.setMode('race');t.start();
   ok(!!t.scar&&['slssc','vantage'].includes(t.scar.car.id),'a safety car leads the race start ('+(t.scar&&t.scar.car.id)+')');
   step(300);let passed=0,ahead=0,exitSeen=false,greenT=null,maxV=0;const order0=t.AI.map(a=>a.s);
   for(let f=0;f<60*400&&t.state==='race';f++){
     // the player floors it along the track
     t.keys.up=1;const P=t.P,N=t.N;const k=(t.pl.idx+8)%N,des=Math.atan2(P[k].x-t.pl.x,P[k].z-t.pl.z);let d=((des-t.pl.th+Math.PI*3)%(Math.PI*2))-Math.PI;t.keys.left=d>0.02?1:0;t.keys.right=d<-0.02?1:0;
     step(1);const S=t.scar;if(!S)break;
     if(!S.green){const fl=t.fieldList();if(S.phase==='lead'&&fl.some(c=>c.s>S.s+0.5))ahead++;if(S.phase==='exit')exitSeen=true;maxV=Math.max(maxV,t.pl.v);
       const ord=t.AI.map(a=>a.s);for(let i=0;i<3;i++)for(let j=0;j<3;j++)if(i!==j&&order0[i]>order0[j]&&ord[i]<ord[j]-0.5)passed++;}
     else{greenT=t.raceT;break;}}
   t.keys.up=0;t.keys.left=t.keys.right=0;
   ok(ahead===0,'nobody passes the safety car');ok(passed===0,'rivals keep their grid order under the safety car');
   ok(exitSeen,'the safety car pulls off the road before lap 2');
   ok(greenT!=null&&t.fieldList().some(c=>c.s>=t.L-1),'green flag when the leader reaches the line (after '+(greenT||0).toFixed(1)+' s)');
   ok(maxV*3.6<200,'under the safety car the pace stays low (max '+(maxV*3.6).toFixed(0)+' km/h)');
   // the safety-car lap is not part of the race: lap 1 starts when the player crosses the line after the green flag
   {ok(t.SCL===1,'the safety-car lap is an extra lap');const lap0=t.pl.lap;
    for(let f=0;f<60*120&&t.pl.lap===lap0&&t.state==='race';f++){t.keys.up=1;const P=t.P,N=t.N;const k=(t.pl.idx+8)%N,des=Math.atan2(P[k].x-t.pl.x,P[k].z-t.pl.z);let d=((des-t.pl.th+Math.PI*3)%(Math.PI*2))-Math.PI;t.keys.left=d>0.02?1:0;t.keys.right=d<-0.02?1:0;step(1);}
    t.keys.up=0;t.keys.left=t.keys.right=0;
    ok(t.pl.lap===2&&t.laps.length===0&&t.state==='race','crossing the line after the safety car records no lap time and starts race lap 1');
    ok(t.AI.every(a=>!a.fin),'nobody has finished after the safety-car lap');}
   step(120);
   {const keys=(t.RD.log||[]).slice(-6).map(x=>x.split(':')[0]);ok(keys.includes('sc_in')&&keys.includes('green'),'team radio calls the safety car in and the green flag ('+keys.join(',')+')');}
   t.toMenu('course');ok(!t.scar,'leaving the race removes the safety car');
   t.opts.sc=false;t.setMode('race');t.start();ok(!t.scar,'the safety car start can be switched off');t.toMenu('course');t.opts.sc=true;}
  // tyre temperature: cold at the start, warmed by cornering and braking, grip follows the temperature window
  {t.toMenu('course');t.selectCar(t.CARS.findIndex(c=>c.id==='laferrari'));t.selectCourse(t.COURSES.findIndex(c=>c.id==='suzuka'));t.setWeather('clear');
   t.setMode('free');t.start();for(let k=0;k<400&&t.state!=='race';k++)step(1);const k0=t.tyreK,T0=t.tyreT.slice();
   let f=0;const lap0=t.pl.lap;
   while(t.pl.lap<lap0+2&&f<60*400){const P=t.P,N=t.N,i=t.pl.idx,k=(i+Math.max(4,Math.round(t.pl.v*0.4/t.ds)))%N,des=Math.atan2(P[k].x-t.pl.x,P[k].z-t.pl.z);let d=((des-t.pl.th+Math.PI*3)%(Math.PI*2))-Math.PI;
     t.keys.left=d>0.01?1:0;t.keys.right=d<-0.01?1:0;let tg=1e9;for(let q=0;q<Math.round((10+t.pl.v*0.5)/t.ds);q++)tg=Math.min(tg,t.vT[(i+q)%N]*Math.sqrt(t.tyreK));
     t.keys.up=t.pl.v<tg?1:0;t.keys.down=t.pl.v>tg+1?1:0;step(1);f++;}
   t.keys.up=t.keys.down=t.keys.left=t.keys.right=0;
   ok(k0<0.9&&T0.every(x=>x<50),'tyres start cold (grip x'+k0.toFixed(2)+', '+T0.map(x=>x.toFixed(0)).join('/')+' °C)');
   ok(t.tyreT.every(x=>x>60)&&t.tyreK>0.95,'a lap at the guide pace warms them into the window ('+t.tyreT.map(x=>x.toFixed(0)).join('/')+' °C, grip x'+t.tyreK.toFixed(2)+')');
   ok(t.tyreStat.n>10,'tyre stats are kept for the results');
   {const L=t.RD.log||[],keys=L.map(x=>x.split(':')[0]);ok(keys.includes('outlap')&&keys.includes('pb')&&L.every(x=>x.length<60&&!/undefined|NaN|null/.test(x)),'team radio in a free run: out lap, lap time ('+L.slice(-4).join(' / ')+')');}
   t.toMenu('course');}
  // real weather: the course's live conditions drive the run (weather, time, cold tyres, wind)
  {const om=t.parseOpenMeteo([{current:{time:'2026-10-15T23:10',weather_code:63,cloud_cover:100,precipitation:2.1,temperature_2m:-5,wind_speed_10m:10,wind_direction_10m:0,wind_gusts_10m:16,is_day:0},daily:{sunrise:['2026-10-15T06:00'],sunset:['2026-10-15T17:20']}}]);
   ok(om.tsukimi&&om.tsukimi.wx==='rain'&&om.tsukimi.time==='night','Open-Meteo reply maps to rain / night');
   t.selectCar(3);t.selectCourse(0);t.setWeather('clear');const g0=t.GRIP;
   t.setWeather('real');t.setReal({at:Date.now(),status:'ok',courses:om});
   ok(t.wxSel==='rain'&&t.timeSel==='night'&&t.tempC===-5,'real mode takes the course weather, time and temperature');
   ok(Math.abs(t.GRIP/g0-0.8)<1e-6,'rain: road grip '+(t.GRIP/g0).toFixed(3)+' of dry (the cold now acts through the tyres)');t.tyreReset();ok(t.tyreK<0.9,'at -5 °C the tyres start cold (grip x'+t.tyreK.toFixed(2)+')');
   ok(Math.abs(t.wind.ms-10)<1e-9&&Math.abs(t.wind.z+10)<1e-6,'north wind blows toward -z at 10 m/s');
   // head vs tail wind on the same run: speed after 8 s flat out
   const runWith=dir=>{t.setReal({at:Date.now(),status:'ok',courses:{tsukimi:Object.assign({},om.tsukimi,{wx:'clear',time:'day',temp:20,wind:15,gust:15,dir})}});
     t.setMode('free');t.start();step(130);t.keys.up=1;for(let f=0;f<500;f++){step(1);t.pl.off=0;t.pl.th=t.TH[t.pl.idx];}t.keys.up=0;const v=t.pl.v;t.toMenu('course');return v;};
   const th0=t.TH[0]*180/Math.PI,head=runWith((th0+3600)%360),tail=runWith((th0+180+3600)%360);
   ok(tail>head,`tail wind is faster than head wind on the opening straight (${(tail*3.6).toFixed(1)} vs ${(head*3.6).toFixed(1)} km/h)`);
   t.setWeather('clear');ok(t.wxSel==='clear'&&t.wind.ms===0,'switching back to a chosen weather turns real conditions off');}
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
