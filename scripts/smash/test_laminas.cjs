const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawnSync}=require('node:child_process');
const {createCanvas}=require('@napi-rs/canvas');
const S=require('../../ranking-smash-ultimate/laminas.js');
function fixture(size=15){return {schemaVersion:1,organizer:{name:'Organización de pruebas con un nombre muy largo de veinte letras y más',topSize:size,coorganizers:Array.from({length:10},(_,i)=>`Colaborador inventado ${i}`),seasonYear:2026,cutDate:'2026-10-04'},players:Array.from({length:size},(_,i)=>({rank:i+1,tag:i===0?'TagDeVeinteCaracter1':`Participante ${i+1}`,mains:[],setsWon:i,setsLost:2,vsTop5:i===0?null:{won:1,lost:2},results:i===0?[{name:'Un único torneo con nombre largo de pruebas',placement:3,date:'2026-09-10',wins:[]}]:[]}))};}
function render(data,format,player,images=new Map()){const result=S.draw(data,format,player,createCanvas(1,1),images);const bytes=result.canvas.toBuffer('image/png');return {...result,bytes};}
function dimensions(bytes){assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');return [bytes.readUInt32BE(16),bytes.readUInt32BE(20)];}

test('real PNG dimensions and safe text boxes in all six templates, missing mains/one tournament/no wins/20-character tag',()=>{
 const data=fixture();assert.equal([...data.players[0].tag].length,20);
 for(const format of ['h','v','s'])for(const player of [null,data.players[0]]){
  const r=render(data,format,player);assert.deepEqual(dimensions(r.bytes),S.FORMATS[format]);
  const safe=format==='h'?{left:96,right:1824,top:64,bottom:1040}:format==='s'?{left:64,right:1016,top:250,bottom:1600}:{left:64,right:1016,top:60,bottom:1306};
  for(const b of r.bounds){assert.ok(b.x>=safe.left&&b.x+b.width<=safe.right&&b.y>=safe.top&&b.y+b.height<=safe.bottom,JSON.stringify(b));assert.ok(b.size*b.lines*1.1<=b.height+1,JSON.stringify(b));}
  assert.ok(r.bounds.some(b=>b.value===`Top de ${data.organizer.name} · solo sus torneos · no es el ranking nacional · rankingsmashbros.com`));
  if(player){assert.ok(r.bounds.some(b=>b.value==='Sin personaje registrado'));assert.ok(r.bounds.some(b=>b.value==='Sin victorias destacadas'));assert.equal(r.bounds.filter(b=>b.value.endsWith('º')).length,1);}
  if(process.env.SMASH_SLIDES_ARTIFACT_DIR){fs.mkdirSync(process.env.SMASH_SLIDES_ARTIFACT_DIR,{recursive:true});fs.writeFileSync(path.join(process.env.SMASH_SLIDES_ARTIFACT_DIR,S.filename(data,player,format)),r.bytes);}
 }
});

test('all top sizes, sparse and empty top never pad nonexistent players',()=>{
 for(const size of [5,10,15])for(const length of [0,1,2,size])for(const format of ['h','v','s']){
  const data=fixture(size);data.players=data.players.slice(0,length);const r=render(data,format,null);
  const ranks=r.bounds.filter(b=>/^\d{2}$/.test(b.value)&&b.x>= (format==='h'?720:64)&&b.y>=(format==='h'?72:format==='s'?640:390));
  // Podium has ghost + badge; rest has only the badge. No phantom rows.
  assert.equal(ranks.length,Math.min(length,3)*2+Math.max(0,length-3));assert.deepEqual(dimensions(r.bytes),S.FORMATS[format]);
 }
});

test('ZIP contains full top and every actual player, exact PNG dimensions and valid CRC',async()=>{
 const data=fixture(),files=[null,...data.players].map(p=>({name:S.filename(data,p,'s'),bytes:render(data,'s',p).bytes}));
 const blob=S.zip(files),folder=fs.mkdtempSync(path.join(os.tmpdir(),'smash-slide-zip-')),file=path.join(folder,'slides.zip');
 try{
  fs.writeFileSync(file,Buffer.from(await blob.arrayBuffer()));
  const result=spawnSync('python3',['-c',`import zipfile,struct,sys
with zipfile.ZipFile(sys.argv[1]) as z:
 assert z.testzip() is None
 assert len(z.namelist()) == 16
 assert len(set(z.namelist())) == 16
 assert all(struct.unpack('>II',z.read(n)[16:24]) == (1080,1920) for n in z.namelist())
 assert any(n.startswith('01-tagdeveintecaracter1-historia') for n in z.namelist())
`,file],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);
 }finally{fs.rmSync(folder,{recursive:true,force:true});}
});

test('ZIP hard cap and names cannot produce traversal, duplicates or more than 16 entries',()=>{
 assert.throws(()=>S.zip([{name:'../x.png',bytes:new Uint8Array(1)}]));
 assert.throws(()=>S.zip(Array.from({length:17},(_,i)=>({name:`p-${i}.png`,bytes:new Uint8Array(1)}))));
 assert.throws(()=>S.zip([{name:'x.png',bytes:new Uint8Array(1)},{name:'x.png',bytes:new Uint8Array(1)}]));
 assert.throws(()=>S.zip([{name:'x.png',bytes:new Uint8Array(64*1024*1024+1)}]),/64 MiB/);
 assert.equal(S.crc32(new TextEncoder().encode('123456789')),0xcbf43926);
});

function options(extra={}) {
 const log=[],doc={fonts:{load:async v=>{log.push('font:'+v);return [{status:'loaded'}];},ready:Promise.resolve(),check:()=>true}};
 return {log,doc,cache:new Map(),fetcher:async (url)=>{log.push(url);return {ok:true,blob:async()=>new Blob(['image'])};},decode:async()=>createCanvas(10,10),...extra};
}
test('fonts checked first and only resources actually drawn are requested',async()=>{
 const data=fixture(5);data.players[0].mains=[{slug:'joker',name:'Joker',games:1},{slug:'mario',name:'Mario',games:1}];
 const opt=options(),r=await S.prepare(data,opt);assert.ok(r.images.has('logo'));assert.ok(r.images.has('joker-icon'));assert.ok(r.images.has('joker-portrait'));assert.ok(r.images.has('mario-icon'));assert.ok(!r.images.has('mario-portrait'));
 assert.ok(opt.log.slice(0,2).every(v=>v.startsWith('font:')));assert.ok(opt.log.slice(2).every(v=>v.startsWith('./assets/')));
 assert.deepEqual(S.resourceJobs(data,[null]).map(j=>j[0]),['logo','joker-icon']);
 assert.deepEqual(S.resourceJobs(data,[data.players[0]]).map(j=>j[0]),['logo','joker-portrait','mario-icon']);
 await assert.rejects(S.prepare(data,options({doc:{fonts:{load:async()=>{throw Error('offline');}}}})),/offline/);
 for(const doc of [{fonts:{load:async()=>[{status:'loaded'}],ready:Promise.resolve(),check:()=>false}},{fonts:{load:async()=>[],ready:Promise.resolve(),check:()=>true}}])await assert.rejects(S.prepare(data,options({doc})),/fuentes/);
});
test('portrait timeout uses initials and does not break a real ZIP; session resources reused',async()=>{
 const data=fixture(5);data.players[0].mains=[{slug:'joker',name:'Joker',games:1}];
 const opt=options({timeout:20});let requests=0,active=0;
 opt.fetcher=async(url,{signal})=>{requests++;if(url.endsWith('portrait.png'))return new Promise((resolve,reject)=>{active++;signal.addEventListener('abort',()=>{active--;reject(new DOMException('timeout','AbortError'));},{once:true});});return {ok:true,blob:async()=>new Blob(['image'])};};
 const r=await S.prepare(data,opt);assert.equal(r.warnings.length,1);assert.equal(active,0);assert.ok(!r.images.has('joker-portrait'));assert.ok(r.images.has('joker-icon'));
 const files=[null,...data.players].map(p=>({name:S.filename(data,p,'h'),bytes:render(data,'h',p,r.images).bytes}));assert.ok(S.zip(files).size>0);
 assert.ok(S.draw(data,'h',data.players[0],createCanvas(1,1),r.images).bounds.some(b=>b.value==='TA'));
 await S.prepare(data,opt);assert.equal(requests,4,'logo and icon reused; only missing portrait retried');
});
test('cancellation aborts all in-flight responses, schedules no pending character and retains completed images',async()=>{
 const data=fixture(5);data.players.forEach((p,i)=>p.mains=[{slug:'char'+i,name:'Inventado',games:1}]);
 const controller=new AbortController(),opt=options({signal:controller.signal});let active=0,requests=0;
 opt.fetcher=async(url,{signal})=>{requests++;if(url.includes('logo'))return {ok:true,blob:async()=>new Blob(['image'])};return new Promise((resolve,reject)=>{active++;signal.addEventListener('abort',()=>{active--;reject(new DOMException('cancel','AbortError'));},{once:true});});};
 const result=S.prepare(data,opt);setTimeout(()=>controller.abort(),20);await assert.rejects(result,{name:'AbortError'});
 assert.equal(active,0);assert.equal(requests,5,'logo plus at most four downloads');assert.equal(opt.cache.size,1);
});
test('icon errors abort peer downloads; retry keeps the successful logo',async()=>{
 const data=fixture(5);data.players[0].mains=[{slug:'joker',name:'Joker',games:1}];const opt=options();let fail=true;
 opt.fetcher=async url=>{opt.log.push(url);return {ok:!fail||!url.endsWith('icon.png'),status:503,blob:async()=>new Blob(['image'])};};
 await assert.rejects(S.prepare(data,opt),/ícono de Joker/);fail=false;await S.prepare(data,opt);
 assert.equal(opt.log.filter(v=>v.includes('logo')).length,1);
});
test('no eager slide script or decorative portrait; access stays gated by the server payload',()=>{
 const site=path.resolve(__dirname,'../../ranking-smash-ultimate');const account=fs.readFileSync(path.join(site,'cuenta.html'),'utf8');
 assert.doesNotMatch(account,/<script[^>]*laminas\.js/);assert.doesNotMatch(account,/joker-portrait\.png/);
 const source=fs.readFileSync(path.join(site,'organizador.js'),'utf8');assert.ok(source.includes("info?.state==='data'&&info.data?.slides"));
 assert.ok(!source.slice(source.indexOf('function teaserBox'),source.indexOf('function invitationBox')).includes('slideControls'));
 assert.throws(()=>S.draw(fixture(5),'x',null,createCanvas(1,1)));assert.throws(()=>S.draw(fixture(5),'h',{rank:1},createCanvas(1,1)),/ajeno/);
});

test('147 new mirrored assets are not referenced by any other page, style or script',()=>{
 const root=path.resolve(__dirname,'../..'),site=path.join(root,'ranking-smash-ultimate');
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'docs/smash/LAMINAS-ASSETS.json'),'utf8'));
 const mirrors=manifest.assets.filter(a=>a.source.startsWith('https://'));assert.equal(mirrors.length,147);
 for(const name of fs.readdirSync(site).filter(n=>/\.(html|php|css|js)$/.test(n))) {
  const source=fs.readFileSync(path.join(site,name),'utf8');for(const asset of mirrors)assert.ok(!source.includes(asset.file),`${name} eagerly references ${asset.file}`);
 }
});
