const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const site=path.join(__dirname,'../../ranking-smash-ultimate');
function harness(fetch,desktop=false){
  const nodes=new Map();
  const get=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,textContent:'',innerHTML:'',listeners:{},addEventListener(e,f){this.listeners[e]=f;},focus(){this.focused=true;},click(){this.clicked=true;},querySelector(){return null;}});return nodes.get(id);};
  const context={document:{getElementById:get},window:{matchMedia:()=>({matches:desktop})},AbortController,setTimeout,clearTimeout,Intl,Date,URL,fetch};
  vm.runInNewContext(fs.readFileSync(path.join(site,'characters.js'),'utf8'),context);
  vm.runInNewContext(fs.readFileSync(path.join(site,'mi-torneo.js'),'utf8'),context);
  return {get,api:context.window.SmashMyTournament};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const member=(tag,id,isMe=false)=>({tag,playerId:id,seed:2,rank:null,isMe,characters:null,analysisUrl:id?`./analisis.html?rival=${id}`:null,prepareUrl:id?`./preparar.html?rival=${id}`:null});
function fixture(){
  const me=member('Yo','1',true),first=member('Trivi','4'),reference=member('Soarin RD','2');
  return {ok:true,status:'ready',upcoming:true,capturedAt:'2026-10-17T20:30:00Z',event:{name:'LEGENDS7',discipline:'Ultimate Singles',country:'SV',url:'https://www.start.gg/tournament/legends7'},pools:[{phase:'Pools',group:'B4',start:{timestamp:null},firstSet:{opponent:first,opponentConfirmed:true,round:'Winners Round 1',time:{timestamp:null}},probablePath:[],strongest:reference,strongestBasis:'seed',members:[me,first,reference],bracket:null}]};
}
async function ready(data=fixture(),desktop=false){const h=harness(async()=>({ok:true,json:async()=>data}),desktop);h.api.setContext({authenticated:true});h.api.show();await tick();return h;}
function button(dataset){return {dataset,closest(){return this;},hasAttribute(){return false;}};}
test('anonymous never fetches; authenticated request cannot select a player; logout clears and aborts',async()=>{
  let calls=0,signal;const h=harness(async(url,opts)=>{calls++;assert.equal(url,'./mi-torneo-api.php');assert.equal(opts.cache,'no-store');assert.equal(opts.credentials,'same-origin');signal=opts.signal;return {ok:true,json:async()=>({ok:true,status:'not_registered',event:{name:'LEGENDS7'}})};});
  h.api.setContext({authenticated:false});assert.equal(calls,0);h.api.setContext({authenticated:true});h.api.show();await tick();assert.match(h.get('my-tournament-body').innerHTML,/No apareces inscrito en Legends 7/);h.api.setContext({authenticated:false});assert.equal(h.get('my-tournament').hidden,true);assert.equal(h.get('my-tournament-body').textContent,'');assert.equal(signal.aborted,true);
});
test('hidden account tab requests no portrait markup; only displayed fighters use local art',async()=>{
  const data=fixture();data.pools[0].members[0].characters={source:'profile',mains:[{characterId:'1302'}]};data.pools[0].firstSet.opponent.characters={source:'detected',mains:[{characterId:'1319'},{characterId:'1302'}]};data.pools[0].strongest.characters={source:'detected',mains:[{characterId:'1280'}]};
  const h=harness(async()=>({ok:true,json:async()=>data}));h.api.setContext({authenticated:true});await tick();assert.equal(h.get('my-tournament-body').innerHTML,'');assert.equal(h.get('my-tournament-banner').hidden,false);
  h.api.show();assert.equal(h.get('my-tournament-banner').hidden,true);const html=h.get('my-tournament-body').innerHTML;assert.match(html,/assets\/characters\/mario-portrait.png/);assert.match(html,/Main detectado/);assert.match(html,/Elegido en tu perfil/);assert.ok(!html.includes('donkey_kong-portrait'));assert.ok(!html.includes('raw.githubusercontent'));assert.match(html,/no sabemos con cuál jugará/);
});
test('null schedules and missing characters are honest; tags and URLs cannot inject HTML',async()=>{
  const data=fixture();const m=data.pools[0].firstSet.opponent;m.tag='<script>mal</script>';m.analysisUrl='javascript:alert(1)';data.event.url='https://evil.example';
  const h=await ready(data),html=h.get('my-tournament-body').innerHTML;assert.match(html,/Horario aún no publicado/);assert.match(html,/seed más alto/);assert.match(html,/Sin personaje registrado/);assert.ok(!html.includes('<script>mal'));assert.match(html,/&lt;script&gt;/);assert.ok(!html.includes('javascript:'));assert.ok(!h.get('my-tournament-event').innerHTML.includes('evil.example'));assert.match(h.get('my-tournament-updated').textContent,/los horarios los define el organizador/);
});
test('first-set actions keep the actual opponent independent from the strongest rival',async()=>{
  const html=(await ready()).get('my-tournament-body').innerHTML;
  const first=html.split('class="mt-next-footer"')[1].split('</section>')[0];
  assert.match(first,/href="\.\/analisis\.html\?rival=4">Analizar a Trivi</);assert.match(first,/href="\.\/preparar\.html\?rival=4">Prepara el set contra Trivi</);assert.ok(!first.includes('rival=2'));assert.ok(!first.includes('Soarin'));
  const reference=html.split('class="mt-reference"')[1];assert.match(reference,/href="\.\/analisis\.html\?rival=2">Analizar a Soarin RD</);assert.match(reference,/puede ser distinto del que te toca ahora/);
});
test('unknown or unlinked opponent never falls back to reference; probable rival is not confirmed',async()=>{
  for(const opponent of [null,member('Sin perfil',null)]){const data=fixture();data.pools[0].firstSet.opponent=opponent;const html=(await ready(data)).get('my-tournament-body').innerHTML;const first=html.split('class="mt-next-footer"')[1].split('</section>')[0];assert.ok(!first.includes('<a '));assert.ok(!first.includes('rival=2'));}
  const data=fixture();data.pools[0].firstSet.opponentConfirmed=false;const html=(await ready(data)).get('my-tournament-body').innerHTML;assert.match(html,/Posible rival · según seeds/);assert.match(html,/No es un cruce confirmado/);
});
test('pool fallback is never labeled a scheduled set; matching timezones collapse; differing zones stay visible',async()=>{
  const data=fixture(),pool=data.pools[0],t={timestamp:1792857600,guatemala:'24/10/2026 10:00',local:'24/10/2026 10:00',timezone:'America/El_Salvador',source:'pool'};
  pool.start=t;pool.firstSet.time=t;let html=(await ready(data)).get('my-tournament-body').innerHTML;assert.match(html,/no es la hora de tu set/);assert.match(html,/Sin programar/);assert.match(html,/igual a la hora local de El Salvador/);
  pool.firstSet.time={...t,source:'set_or_round',local:'24/10/2026 11:00',timezone:'America/Panama'};html=(await ready(data)).get('my-tournament-body').innerHTML;assert.match(html,/Tu set · horario de set\/ronda/);assert.match(html,/24\/10\/2026 11:00/);assert.match(html,/America\/Panama/);
});
test('real graph uses only supplied nodes and edges; keyboard switches to the complete text list',async()=>{
  const data=fixture(),pool=data.pools[0],me=pool.members[0],op=pool.firstSet.opponent;
  pool.bracket={sets:[{id:'a',round:1,label:'Winners Round 1',side:'W',isMine:true,onProbablePath:true,finished:false,time:null,slots:[{index:0,member:me},{index:1,member:op}]},{id:'b',round:2,label:'Winners Final',side:'W',isMine:false,onProbablePath:true,finished:false,time:null,slots:[{index:0,member:null,from:{setId:'a',outcome:'winner'}},{index:1,member:null}]}]};
  const h=await ready(data,true);let html=h.get('my-tournament-body').innerHTML;assert.match(html,/aria-selected="true"[^>]*data-mt-view="graph"/);assert.match(html,/<path class="mt-edge-mine"/);assert.match(html,/Ganador de W1/);assert.match(html,/Por confirmar/);assert.ok(!html.includes('0–0</'));assert.match(html,/role="region" tabindex="0"/);
  let prevented=false;h.get('my-tournament-body').listeners.keydown({target:button({mtView:'graph'}),key:'End',preventDefault(){prevented=true;},stopPropagation(){}});html=h.get('my-tournament-body').innerHTML;assert.equal(prevented,true);assert.match(html,/aria-selected="true"[^>]*data-mt-view="list"/);assert.match(html,/Trivi \(seed 2\)/);assert.equal(h.get('mt-view-list').focused,true);
  const mobile=await ready(data);assert.match(mobile.get('my-tournament-body').innerHTML,/aria-selected="true"[^>]*data-mt-view="path"/);
});
test('partial graph exposes only the path, with no invented bracket tabs',async()=>{
  const h=await ready();const html=h.get('my-tournament-body').innerHTML;assert.match(html,/bracket completo de este pool todavía no está disponible/);assert.ok(!html.includes('data-mt-view="graph"'));
});
test('error offers retry; late requests cannot restore data from another account',async()=>{
  let complete;const h=harness(()=>new Promise(resolve=>complete=resolve));h.api.setContext({authenticated:true});h.api.show();h.api.setContext({authenticated:false});complete({ok:true,json:async()=>fixture()});await tick();assert.equal(h.get('my-tournament-body').textContent,'');
  const bad=harness(async()=>{throw Error();});bad.api.setContext({authenticated:true});bad.api.show();await tick();assert.equal(bad.get('my-tournament-retry').hidden,false);assert.match(bad.get('my-tournament-body').innerHTML,/role="alert"/);assert.equal(typeof bad.get('my-tournament-retry').listeners.click,'function');
});
test('empty states have no fictitious fights, and banner opens the dedicated tab',async()=>{
  for(const status of ['snapshot_unavailable','registrations_unavailable','not_registered','pools_unpublished']){const d=fixture();d.status=status;d.pools=[];const h=await ready(d);assert.match(h.get('my-tournament-body').innerHTML,/mt-notice/);assert.ok(!h.get('my-tournament-body').innerHTML.includes('mt-portrait'));}
  const h=await ready();h.get('my-tournament-banner-link').listeners.click();assert.equal(h.get('tab-tournament').clicked,true);assert.equal(h.get('my-tournament').focused,true);
});
test('portrait failure restores initials without losing the character identity',async()=>{
  const h=await ready();let removed=false,restored=false;const origin={textContent:'Main detectado'};
  const image={tagName:'IMG',classList:{contains:n=>n==='mt-portrait'},parentElement:{classList:{remove:n=>restored=n==='mt-has-portrait'},querySelector:()=>origin},remove(){removed=true;}};
  h.get('my-tournament-body').listeners.error({target:image});assert.equal(removed,true);assert.equal(restored,true);assert.match(origin.textContent,/Main detectado · retrato no disponible/);
});
test('retry restores focus to the tournament after a successful recovery',async()=>{
  let fail=true;const h=harness(async()=>{if(fail)throw Error();return {ok:true,json:async()=>fixture()};});
  h.api.setContext({authenticated:true});h.api.show();await tick();fail=false;await h.get('my-tournament-retry').listeners.click();assert.equal(h.get('my-tournament-retry').hidden,true);assert.equal(h.get('my-tournament').focused,true);assert.match(h.get('my-tournament-body').innerHTML,/Trivi/);
});
test('several published phases switch only between the supplied own pools',async()=>{
  const data=fixture();data.pools.push({...data.pools[0],phase:'Segunda fase',group:'D2',members:[member('Yo','1',true),member('Otra fase','5')]});
  const h=await ready(data);assert.match(h.get('my-tournament-body').innerHTML,/data-mt-pool="1"/);
  h.get('my-tournament-body').listeners.click({target:button({mtPool:'1'})});const html=h.get('my-tournament-body').innerHTML;assert.match(html,/Segunda fase/);assert.match(html,/Otra fase/);assert.match(html,/aria-pressed="true"/);
});
test('account integrates a dedicated accessible tab and no provider or paid request',()=>{
  const html=fs.readFileSync(path.join(site,'cuenta.html'),'utf8');assert.match(html,/id="my-tournament"[^>]*tabindex="-1"/);assert.match(html,/id="tab-tournament"[^>]*aria-controls="tournament-screen"/);assert.match(html,/id="tournament-screen"[^>]*aria-labelledby="tab-tournament"/);assert.match(html,/mi-torneo.js/);assert.match(html,/mi-torneo.css/);
  const js=fs.readFileSync(path.join(site,'mi-torneo.js'),'utf8');for(const forbidden of ['start.gg/gql','premium-api.php','analisis-api.php','support.js'])assert.ok(!js.includes(forbidden));
});
