const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {validate,render,init}=require('../../ranking-smash-ultimate/tops.js');
const site=path.join(__dirname,'../../ranking-smash-ultimate');
const top=()=>({name:'Arena <inventada>',coorganizers:['Ana & Leo'],topSize:15,tournaments:2,cutDate:'2026-10-04',
  top:[{rank:1,alias:'Jugador <uno>'},{rank:2,alias:'Otro'},{rank:3,alias:'Tercero'}],url:'/top/arena'});
const page=()=>({ok:true,schemaVersion:1,items:[top()],nextCursor:null});
test('public card credits coorganizers and only renders a three-player preview',()=>{
  const data=validate(page());const html=render(data.items,null);
  for(const value of ['Arena &lt;inventada&gt;','Ana &amp; Leo','2 torneos','04/10/2026','Puesto </span>1','Puesto </span>3','Jugador &lt;uno&gt;','/top/arena','Ver top completo'])assert.ok(html.includes(value),value);
  assert.doesNotMatch(html,/<inventada>|<uno>|#4|startgg|premium_subscriptions/);
});
test('honest empty, read failure, pagination retry and sparse podium are distinct',()=>{
  assert.match(render([],null),/Todavía no hay tops compartidos/);
  assert.match(render([],null).replace(/<[^>]*>/g,''),/Si organizas torneos, crea el tuyo desde tu cuenta/);
  assert.match(render([],null),/cuenta.html#premium/);
  assert.doesNotMatch(render([],null,false,true),/Todavía no hay tops compartidos/);
  assert.match(render([top()],'arena'),/Ver más tops/);
  assert.match(render([top()],'arena',true),/disabled/);
  assert.match(render([top()],'arena',false,true),/Los que ya ves siguen aquí/);
  const empty=top();empty.top=[];assert.match(render([empty],null),/sets válidos/);
});
test('client rejects fields beyond public contract, unsafe links and cursor loops',()=>{
  const invalid=[];
  const extra=page();extra.items[0].email='private@example.test';invalid.push(extra);
  const payment=page();payment.premium=true;invalid.push(payment);
  const url=page();url.items[0].url='javascript:alert(1)';invalid.push(url);
  const chars=page();chars.items[0].top[0].playerId='secret';invalid.push(chars);
  const cursor=page();cursor.nextCursor='other';invalid.push(cursor);
  const many=page();many.items=Array.from({length:13},top);invalid.push(many);
  for(const value of invalid)assert.throws(()=>validate(value));
  const valid=page();valid.nextCursor='arena';assert.equal(validate(valid),valid);
});
test('publication entry uses existing components and fixed notice, without tracking or example data',()=>{
  const html=fs.readFileSync(path.join(site,'tops.html'),'utf8');
  for(const value of ['torneos.css','tops.css','tops.js','cabecera.js','no es el ranking nacional','20 jugadores activos','Pagar no da puntos ni cambia puestos','noscript'])assert.ok(html.includes(value),value);
  assert.doesNotMatch(html,/visita.js|support.js|Arena inventada/);
  const scripts=fs.readFileSync(path.join(site,'tops.js'),'utf8');assert.match(scripts,/credentials:'omit'/);
  assert.doesNotMatch(scripts,/account-api|start\.gg|recurrente-webhook|POST/);
});
test('all existing page footers link to the directory and the principal menus include Tops',()=>{
  const pages=['index.html','metodologia.html','encuesta.php','analisis.html','preparar.html','torneos.html','cuenta.html','analisis-top20.html','analisis-torneos.html','opiniones.php','panel.php','top.php','terminos.html','reembolsos.html','tops.html'];
  for(const page of pages){
    const text=fs.readFileSync(path.join(site,page),'utf8');
    assert.match(text.split('<footer')[1],/href="\/tops.html">Tops de organizadores<\/a>/,page);
    if(text.includes('aria-label="Principal"'))assert.match(text.split('</header>')[0],/href="\.\/tops.html"/,page);
  }
});

test('handoff skeletons, coorganizer disclosure and real sparse previews',()=>{
  assert.equal((render([],null,true).match(/class="tops-skeleton"/g)||[]).length,6);
  const item=top();item.coorganizers=Array.from({length:10},(_,i)=>'Persona '+i);
  const html=render([item],'arena',true);
  assert.match(html,/Ver los 10 coorganizadores/);assert.match(html,/Persona 0, Persona 1 y 8 más/);
  assert.equal((html.match(/class="tops-skeleton"/g)||[]).length,3);
  for(const count of [0,1,2]){item.top=item.top.slice(0,count);const h=render([item],null);assert.equal((h.match(/class="tops-position"/g)||[]).length,count);if(count)assert.match(h,/por ahora/);else assert.match(h,/todavía no tiene jugadores/);item.top=top().top;}
  assert.doesNotMatch(html,/Mostrando \d+ de|portrait|points|avatar|mainName/);
});
test('failed next page retains cards and cursor, retry focuses first new card',async()=>{
  let html='',focus=null,release;
  const root={setAttribute(){},get innerHTML(){return html},set innerHTML(v){html=v},querySelector(selector){return {addEventListener(){},focus(){focus=selector}}}};
  const doc={getElementById(){return root}};
  const calls=[];let count=0;
  const request=async(url,options)=>{calls.push([url,options.credentials]);count++;if(count===1)return {ok:true,json:async()=>({...page(),nextCursor:'arena'})};if(count===2)await new Promise(resolve=>release=resolve);if(count===2)return {ok:false};const item=top();item.name='Segundo';item.url='/top/segundo';return {ok:true,json:async()=>({...page(),items:[item]})};};
  const view=init(doc,request);await view.ready;
  const pending=view.load();assert.match(html,/Cargando más tops/);assert.match(html,/Arena &lt;inventada&gt;/);release();await pending;
  assert.match(html,/Los que ya ves siguen aquí/);assert.match(html,/Arena &lt;inventada&gt;/);
  await view.load();assert.match(html,/Segundo/);assert.equal(focus,'#top-segundo');
  assert.deepEqual(calls.map(([url])=>url),['./tops-api.php','./tops-api.php?after=arena','./tops-api.php?after=arena']);assert.ok(calls.every(([,credentials])=>credentials==='omit'));
});
