const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const m=require('../../ranking-smash-ultimate/instagram.js');
const site=path.join(__dirname,'../../ranking-smash-ultimate');
const image=()=>({src:`assets/instagram/${'a'.repeat(64)}-full.webp`,thumbnail:`assets/instagram/${'b'.repeat(64)}-thumb.webp`,width:1080,height:810,thumbnailWidth:360,thumbnailHeight:270});
const post=(id='123')=>({id,type:'IMAGE',caption:'Comunidad 📸 <b>sin HTML</b>\nTorneo en Guatemala',permalink:`https://www.instagram.com/p/FAKE_${id}/`,timestamp:'2026-10-27T12:00:00Z',image:image()});
const feed=(count=1)=>({schemaVersion:1,generatedAt:'2026-10-27T13:00:00Z',posts:Array.from({length:count},(_,i)=>post(String(i+1)))});
class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.dataset={};this.hidden=false;this.className='';this.textContent='';this.isConnected=true;this.classList={values:new Set(),add(x){this.values.add(x)},remove(x){this.values.delete(x)}};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  setAttribute(k,v){this[k]=v;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  querySelector(selector){if(selector==='time')return this.find(n=>n.tagName==='time');return this.find(n=>n.className.split(' ').includes(selector.slice(1)));}
  find(fn){for(const c of this.children){if(fn(c))return c;const found=c.find(fn);if(found)return found;}return null;}
  remove(){this.removed=true;}
  focus(){this.focused=true;}
  showModal(){this.open=true;}
  close(){this.open=false;this.listeners.close?.({target:this});}
}
function dom(mode='gallery'){
  const section=new Element('main');section.dataset.instagram=mode;section.hidden=mode==='preview';
  const grid=new Element('div');grid.className='ig-grid';const empty=new Element('p');empty.className='ig-empty';section.append(grid,empty);
  const dialog=new Element('dialog');for(const cls of ['ig-close','ig-dialog-media','ig-dialog-type','ig-dialog-caption','ig-original']){const el=new Element(cls==='ig-original'?'a':'div');el.className=cls;dialog.append(el);}dialog.append(new Element('time'));
  const trigger=mode==='preview'?new Element('div'):null;
  const document={body:new Element('body'),createElement(tag){return new Element(tag)},querySelector(s){return s==='[data-instagram]'?section:trigger},getElementById(){return dialog}};
  return {document,section,grid,empty,dialog};
}
test('bounded same-origin schema, optional caption/image and accessible alt',()=>{
  assert.equal(m.normalize(feed(12)).posts.length,12);assert.equal(m.normalize(feed(13)),null);
  const f=feed();f.posts[0].image=null;f.posts[0].caption='';assert.equal(m.normalize(f).posts[0].image,null);
  assert.equal(m.alt('  Hola\n  Guate  '),'Hola Guate');assert.equal(m.alt(''),'Publicación de Ranking Smash Bros');assert.equal(Array.from(m.alt('📸'.repeat(250))).length,180);
  assert.match(m.date('2026-10-27T02:00:00Z'),/26/);
  for(const change of ['url','cdn','duplicate','type','dimensions','caption']){const f=feed(2);if(change==='url')f.posts[0].permalink='javascript:alert(1)';if(change==='cdn')f.posts[0].image.src='https://scontent.cdninstagram.com/raw';if(change==='duplicate')f.posts[1].id=f.posts[0].id;if(change==='type')f.posts[0].type='STORY';if(change==='dimensions')f.posts[0].image.width=2000;if(change==='caption')f.posts[0].caption='x'.repeat(2201);assert.equal(m.normalize(f),null,change);}
});
test('public fetch omits cookies, refuses oversized or invalid snapshots',async()=>{
  let options,url;const fetch=async(u,o)=>{url=u;options=o;return new Response(JSON.stringify(feed()))};
  assert.equal((await m.load(fetch)).posts.length,1);assert.equal(url,'./data/instagram.json');assert.equal(options.credentials,'omit');
  assert.equal(await m.load(async()=>new Response('bad',{status:404})),null);
  assert.equal(await m.load(async()=>new Response('not-json')),null);
  assert.equal(await m.load(async()=>new Response('x'.repeat(131073))),null);
});
test('homepage hides without data or on request failure, full page keeps honest empty',async()=>{
  for(const mode of ['preview','gallery'])for(const fail of [false,true]){const d=dom(mode);await m.init(d.document,{fetch:async()=>{if(fail)throw Error('offline');return new Response(JSON.stringify(feed(0)));}}).ready;assert.equal(d.grid.children.length,0);assert.equal(d.section.hidden,mode==='preview');assert.equal(d.empty.hidden,false);}
});
test('preview is deferred until near ranking bottom and draws six cards only',async()=>{
  const d=dom('preview');let calls=0,callback,observed=false,disconnected=false;
  class Observer{constructor(fn){callback=fn;}observe(){observed=true;}disconnect(){disconnected=true;}}
  const ui=m.init(d.document,{IntersectionObserver:Observer,fetch:async()=>{calls++;return new Response(JSON.stringify(feed(12)));}});
  assert.equal(calls,0);assert.equal(observed,true);callback([{isIntersecting:true}]);await ui.ready;
  assert.equal(disconnected,true);assert.equal(calls,1);assert.equal(d.grid.children.length,6);assert.equal(d.section.hidden,false);
});
test('modal uses full image only on click, caption is text, failure keeps card and focus returns',async()=>{
  const d=dom();await m.init(d.document,{fetch:async()=>new Response(JSON.stringify(feed(2)))}).ready;
  const card=d.grid.children[0],thumb=card.querySelector('.ig-photo');assert.match(thumb.src,/-thumb.webp$/);assert.equal(thumb.loading,'lazy');
  thumb.listeners.error();assert.equal(thumb.removed,true);assert.equal(d.grid.children.length,2);
  card.listeners.click();assert.equal(d.dialog.open,true);assert.equal(d.dialog.querySelector('.ig-dialog-caption').textContent,post().caption);assert.equal(d.dialog.querySelector('.ig-close').focused,true);
  const full=d.dialog.querySelector('.ig-dialog-media').querySelector('.ig-photo');assert.match(full.src,/-full.webp$/);full.listeners.error();assert.equal(full.removed,true);
  d.dialog.querySelector('.ig-close').listeners.click();assert.equal(d.dialog.open,false);assert.equal(card.focused,true);assert.equal(d.dialog.querySelector('.ig-dialog-media').children.length,0);
});
test('page uses brand, same-origin assets, lazy images and no Meta SDK/embed/cookies',()=>{
  const js=fs.readFileSync(path.join(site,'instagram.js'),'utf8'),html=fs.readFileSync(path.join(site,'instagram.html'),'utf8'),home=fs.readFileSync(path.join(site,'index.html'),'utf8');
  assert.doesNotMatch(js,/innerHTML|createElement\(['"]iframe|document.cookie|facebook\.net|fbcdn\.net|cdninstagram\.com|access_token/);
  assert.doesNotMatch(html,/iframe|support\.js|visita\.js|connect\.facebook|instagram\.com\/embed/);
  assert.ok(home.indexOf('id="desde-instagram"')>home.indexOf('id="ranking"'));assert.match(home,/data-instagram="preview"[^>]*hidden/);assert.match(html,/assets\/rsb-mark.svg/);
  assert.match(html,/rel="noopener noreferrer"/);assert.match(html,/Ver en Instagram/);assert.match(html,/ig-dialog-title/);
});
