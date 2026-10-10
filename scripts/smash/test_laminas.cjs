const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawnSync}=require('node:child_process');
const {createCanvas}=require('@napi-rs/canvas');
const S=require('../../ranking-smash-ultimate/laminas.js');
function fixture(size=15){return {schemaVersion:1,organizer:{name:'Organización de pruebas con un nombre muy largo de veinte letras y más',topSize:size,coorganizers:Array.from({length:10},(_,i)=>`Colaborador inventado ${i}`),seasonYear:2026,cutDate:'2026-10-04'},players:Array.from({length:size},(_,i)=>({rank:i+1,tag:i===0?'TagDeVeinteCaracter1':`Participante ${i+1}`,mains:[],setsWon:i,setsLost:2,vsTop5:i===0?null:{won:1,lost:2},results:i===0?[{name:'Un único torneo con nombre largo de pruebas',placement:3,date:'2026-09-10',wins:[]}]:[]}))};}
function render(data,format,player){const result=S.draw(data,format,player,createCanvas(1,1));const bytes=result.canvas.toBuffer('image/png');return {...result,bytes};}
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

test('fonts are loaded and checked before drawing, only same-origin project images are requested',async()=>{
 const log=[],doc={fonts:{load:async v=>{log.push('font:'+v);return [{status:'loaded'}];},ready:Promise.resolve(),check:()=>true}};
 class Img{set src(v){log.push(v);this.width=10;this.height=10;this.onload();}}
 const data=fixture(5);data.players[0].mains=[{slug:'joker',name:'Joker',games:1}];
 const images=await S.prepare(data,doc,Img);assert.ok(images.has('logo'));assert.ok(images.has('joker-icon'));
 assert.ok(log.slice(0,2).every(v=>v.startsWith('font:')));assert.ok(log.slice(2).every(v=>v.startsWith('./assets/')));
 await assert.rejects(S.prepare(data,{fonts:{load:async()=>{throw Error('offline');}}},Img),/offline/);
 await assert.rejects(S.prepare(data,{fonts:{load:async()=>[{status:'loaded'}],ready:Promise.resolve(),check:()=>false}},Img),/fuentes/);
 await assert.rejects(S.prepare(data,{fonts:{load:async()=>[],ready:Promise.resolve(),check:()=>true}},Img),/fuentes/);
});

test('download controls require server-provided slides; labels escape markup and there is no export in the free teaser',()=>{
 assert.equal(S.controls(null),'');assert.equal(S.controls({...fixture(5),players:[]}), '');
 const data=fixture(5);data.players[0].tag='<script>inventado';assert.ok(!S.controls(data).includes('<script>'));
 const source=fs.readFileSync(path.resolve(__dirname,'../../ranking-smash-ultimate/organizador.js'),'utf8');
 assert.ok(source.includes("info?.state==='data'&&info.data?.slides"));
 assert.ok(!source.slice(source.indexOf('function teaserBox'),source.indexOf('function invitationBox')).includes('SmashLaminas'));
 assert.throws(()=>S.draw(fixture(5),'x',null,createCanvas(1,1)));assert.throws(()=>S.draw(fixture(5),'h',{rank:1},createCanvas(1,1)),/ajeno/);
});
