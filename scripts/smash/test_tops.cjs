const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {validate,render}=require('../../ranking-smash-ultimate/tops.js');
const site=path.join(__dirname,'../../ranking-smash-ultimate');
const top=()=>({name:'Arena <inventada>',coorganizers:['Ana & Leo'],topSize:15,tournaments:2,cutDate:'2026-10-04',
  top:[{rank:1,alias:'Jugador <uno>'},{rank:2,alias:'Otro'},{rank:3,alias:'Tercero'}],url:'/top/arena'});
const page=()=>({ok:true,schemaVersion:1,items:[top()],nextCursor:null});
test('public card credits coorganizers and only renders a three-player preview',()=>{
  const data=validate(page());const html=render(data.items,null);
  for(const value of ['Arena &lt;inventada&gt;','Coorganizan: Ana &amp; Leo','2 torneos','04/10/2026','#1','#3','Jugador &lt;uno&gt;','/top/arena','Ver top completo'])assert.ok(html.includes(value),value);
  assert.doesNotMatch(html,/<inventada>|<uno>|#4|startgg|premium_subscriptions/);
});
test('honest empty, read failure, pagination retry and sparse podium are distinct',()=>{
  assert.match(render([],null),/Todavía no hay tops compartidos/);
  assert.match(render([],null),/Si organizas torneos, crea el tuyo desde tu cuenta/);
  assert.match(render([],null),/cuenta.html#premium/);
  assert.doesNotMatch(render([],null,false,true),/Todavía no hay tops compartidos/);
  assert.match(render([top()],'arena'),/Ver más tops/);
  assert.match(render([top()],'arena',true),/disabled/);
  assert.match(render([top()],'arena',false,true),/Los anteriores siguen visibles/);
  const empty=top();empty.top=[];assert.match(render([empty],null),/sets suficientes/);
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
