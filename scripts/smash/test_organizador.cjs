const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function ui(file, response){
  const handlers={}, requests=[];
  const root={innerHTML:'',addEventListener:(kind,fn)=>handlers[kind]=fn,querySelector:()=>null,querySelectorAll:()=>[]};
  const sandbox={document:{getElementById:()=>root},URL,URLSearchParams,AbortController,setTimeout,clearTimeout,
    location:{href:'http://127.0.0.1/cuenta.html#torneos',search:'',hash:'#torneos'},history:{replaceState(){}},
    sessionStorage:{getItem:()=>null,removeItem(){},setItem(){}},navigator:{},confirm:()=>true,CSS:{escape:s=>s}};
  sandbox.fetch=async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>response};};
  const context=vm.createContext(sandbox);
  const name=file==='premium.js'?'SmashPremium':'SmashOrganizador';
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../ranking-smash-ultimate',file),'utf8')+`;globalThis.app=${name};`,context);
  return {root,handlers,requests,app:context.app};
}
const blocked=(state='premium')=>({ok:true,authenticated:true,csrf:'invented-csrf',state,role:'owner',
  contexts:[{id:'1',role:'owner',name:'Arena de prueba'}],expiredAt:'2026-01-01T00:00:00Z',
  teaser:{headline:{kind:'latest_counted_tournament',name:'Copa <local>',date:'2026-09-27',url:'https://www.start.gg/tournament/copa-local'},
    locked:{tournaments:4,countedTournaments:2,rankedPlayers:21,validSets:30}}});
const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('premium feature follows catalog readiness, not payment availability',async()=>{
  const u=ui('premium.js',{ok:true,authenticated:true,available:true,premium:{premium:false}});
  u.app.setContext({authenticated:true,organizerReady:false});await u.app.show();
  assert.match(u.root.innerHTML,/Top por organizador <em>Próximamente/);
  assert.doesNotMatch(u.root.innerHTML,/href="\.\/cuenta.html#torneos"/);
  u.app.setContext({organizerReady:true});await u.app.show();
  assert.match(u.root.innerHTML,/<strong>Top por organizador<\/strong>/);
  assert.match(u.root.innerHTML,/href="\.\/cuenta.html#torneos"/);
  u.app.setContext({organizerReady:false});await u.app.show();
  assert.match(u.root.innerHTML,/Top por organizador <em>Próximamente/);
});
test('free and expired screens render the single real finding and counts, escaped',async()=>{
  for(const state of ['premium','expired']){
    const u=ui('organizador.js',blocked(state));await u.app.show();
    assert.match(u.root.innerHTML,/Hallazgo principal · gratis/);
    assert.match(u.root.innerHTML,/Copa &lt;local&gt;/);
    assert.match(u.root.innerHTML,/21 jugadores con sets suficientes/);
    assert.match(u.root.innerHTML,/30 sets válidos/);
    assert.doesNotMatch(u.root.innerHTML,/o-row|data-act="size"|data-act="public"|data-act="review"|<script|blur/);
  }
});
test('no counting tournaments is an honest empty teaser, not a fabricated result',async()=>{
  const data=blocked();data.teaser={headline:null,locked:{tournaments:0,countedTournaments:0,rankedPlayers:0,validSets:0}};
  const u=ui('organizador.js',data);await u.app.show();
  assert.match(u.root.innerHTML,/Aún no hay un torneo que cuente/);
  assert.match(u.root.innerHTML,/0 sets válidos/);
  assert.doesNotMatch(u.root.innerHTML,/Copa|o-row/);
});
test('a coorganizer can leave without premium; the name is credited',async()=>{
  const data=blocked();data.role='member';data.contexts=[{id:'1',name:'Arena <amiga>',role:'member'}];
  const u=ui('organizador.js',data);await u.app.show();
  assert.match(u.root.innerHTML,/Eres coorganizador de Arena &lt;amiga&gt;/);
  assert.match(u.root.innerHTML,/data-act="leave"/);
  assert.doesNotMatch(u.root.innerHTML,/data-act="size"|data-act="invite"/);
});
test('clipboard missing has a manual fallback and does not throw',async()=>{
  const data={...blocked(),state:'data',members:[],publicUrl:'https://rankingsmashbros.com/top/arena',data:{
    organizer:{name:'Arena',slug:'arena',topSize:5,publicEnabled:true},seasonYear:2026,events:[],top:[],rest:[],coorganizers:[],sizes:[5,10,15],
    summary:{eventsCounted:1,periodFrom:'2026-01-01',periodTo:'2026-01-01',cutDate:'2026-10-04'},minRule:'2 sets'}};
  const u=ui('organizador.js',data);await u.app.show();
  assert.doesNotThrow(()=>u.handlers.click({target:{closest:()=>({dataset:{act:'copy',copy:data.publicUrl}})}}));
  assert.match(u.root.innerHTML,/Selecciona la dirección y cópiala a mano/);
});
test('admin reviews show requester, confirmation and rejection validation entry',async()=>{
  const data=blocked();data.pendingReviews=[{id:'7',organizer:'Arena',requestedBy:'Persona <invitada>',tournament:'Copa',url:'https://www.start.gg/tournament/copa',sentAt:'2026-10-01',inCatalog:true}];
  const u=ui('organizador.js',data);await u.app.show();
  assert.match(u.root.innerHTML,/Enviada por Persona &lt;invitada&gt;/);
  assert.match(u.root.innerHTML,/maxlength="255"/);
  assert.match(u.root.innerHTML,/data-act="resolve"/);
  u.handlers.click({target:{closest:()=>({dataset:{act:'resolve',id:'7',approve:'1'}})}});await settle();
  const body=JSON.parse(u.requests.find(r=>r.options.body)?.options.body);
  assert.equal(body.action,'resolve');assert.equal(body.claim,'7');assert.equal(body.approve,true);
});
