/* Accounts use the published cut for statistics; chosen characters never alter it. */
(() => {
  const $=id=>document.getElementById(id), all=selector=>[...document.querySelectorAll(selector)];
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const char=id=>CHARACTER_CATALOG.find(c=>c.characterId===String(id));
  const art=(id,kind='icon')=>{const c=char(id);return c?`<img src="${escape(c[kind])}" alt="" loading="lazy">`:'<span aria-hidden="true">?</span>';};
  const safeLink=value=>{try{const u=new URL(value);return u.protocol==='https:'&&['www.start.gg','start.gg'].includes(u.hostname)&&!u.username&&!u.password?u.href:null;}catch{return null;}};
  const date=value=>{const day=String(value||'').slice(0,10).split('-');return day.length===3?`${day[2]}/${day[1]}/${day[0]}`:'Sin fecha';};
  let data=null, scope='combined', historyFilter='all', screen='login', chosen=[], saved=[], activeSlot=0, saving=false, roles=['player'];
  const dirty=()=>AccountModel.dirty(chosen,saved);
  const view=()=>data.profile.views[scope];
  async function request(body=null) {
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),20000);
    try {
      const response=await fetch('./account-api.php',{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,
        headers:body?{'Content-Type':'application/json','X-CSRF-Token':data?.csrf||''}:{'Accept':'application/json'},body:body?JSON.stringify(body):undefined});
      const json=await response.json();
      if(!response.ok||json.ok!==true){const error=new Error(json.reason||'account_unavailable');error.status=response.status;throw error;}
      return json;
    } finally {clearTimeout(timer);}
  }
  function message(id,text,kind='') {const node=$(id);node.textContent=text;node.className=`notice ${kind}`;node.hidden=!text;node.setAttribute('role',kind==='error'?'alert':'status');}
  function setScreen(next,force=false) {
    if(saving&&!force)return false;
    if(!force&&screen==='characters'&&next!==screen&&dirty()&&!confirm('Tienes cambios sin guardar. ¿Quieres salir y descartarlos?'))return false;
    if(screen==='characters'&&next!=='characters'){chosen=[...saved];message('character-message','');}
    screen=next;
    for(const name of ['login','profile','characters'])$(`${name}-screen`).hidden=name!==next;
    $('onboarding').hidden=next!=='onboarding';$('account-error').hidden=next!=='error';$('loading').hidden=true;
    $('account-tabs').hidden=!data?.authenticated||['error','onboarding'].includes(next);
    ['profile','characters'].forEach(name=>{$(`tab-${name}`).setAttribute('aria-selected',String(name===next));$(`tab-${name}`).tabIndex=name===next?0:-1;});
    if(next==='profile')renderProfile();if(next==='characters')renderCharacters();
    return true;
  }
  function renderLogin() {
    $('oauth-csrf').value=data.csrf;$('oauth-button').disabled=!data.oauthReady;
    const state=location.hash.slice(1);
    const states={cancelado:['Cancelaste la autorización. No se completó la vinculación. Puedes intentarlo cuando quieras.',''],error:['No pudimos completar la vinculación con start.gg. Intenta de nuevo en un momento.','error'],'no-disponible':['La vinculación con start.gg todavía no está habilitada. Puedes consultar tu puesto gratis en el ranking.','']};
    if(!data.oauthReady)message('login-notice','Estamos preparando las cuentas. Mientras tanto, puedes consultar tu puesto gratis en el ranking.');
    else if(states[state])message('login-notice',...states[state]);else message('login-notice','');
    setScreen('login',true);
  }
  async function load() {
    $('loading').hidden=false;$('account-error').hidden=true;
    try {
      data=await request();
      // Display hint for the home page header only; never proof of a session.
      try{if(data.authenticated)localStorage.setItem('smashgt.cuenta',data.user.tag);else localStorage.removeItem('smashgt.cuenta');}catch{}
      if(!data.authenticated){renderLogin();return;}
      saved=[...data.user.chosen];chosen=[...saved];roles=data.user.roles.length?[...data.user.roles]:['player'];
      $('header-account').textContent=data.user.tag;$('header-account').href='./cuenta.html';
      if(!data.user.roles.length){renderOnboarding();setScreen('onboarding',true);}else setScreen('profile',true);
      if(location.hash==='#vinculada')history.replaceState(null,'','./cuenta.html');
    }catch(error){
      if(error.status===401){try{data=await request();renderLogin();}catch{setScreen('error',true);}}else setScreen('error',true);
    }
  }
  function renderOnboarding() {
    $('linked-player').textContent=`Cuenta vinculada: ${data.user.tag}. ${data.user.playerId?'Tu perfil se vinculó por el ID verificado de start.gg.':'Tu cuenta todavía no tiene un jugador vinculado en start.gg.'}`;
    all('[data-roles]').forEach(button=>{const selected=button.dataset.roles.split(',');button.setAttribute('aria-pressed',String(selected.length===roles.length&&selected.every(role=>roles.includes(role))));});
  }
  function renderProfile() {
    const v=view(), user=data.user, mains=user.chosen.length?user.chosen:v.detected.slice(0,3).map(c=>c.characterId), selected=user.chosen.length>0;
    $('account-tag').textContent=user.tag;
    $('account-role').textContent=`${user.roles.map(r=>r==='player'?'Jugador':'Organizador').join(' · ')}${user.country?' · País de perfil: '+user.country:''}`;
    $('account-avatar').innerHTML=user.avatarUrl?`<img src="${escape(user.avatarUrl)}" alt="Foto de ${escape(user.tag)}">`:escape(user.tag.slice(0,2).toUpperCase());
    const link=safeLink(user.url);$('startgg-link').hidden=!link;if(link)$('startgg-link').href=link;
    $('card-rank').textContent=v.rank??'?';const c=char(mains[0]);$('card-portrait').hidden=!c;if(c)$('card-portrait').src=c.portrait;
    $('account-season').textContent=data.profile.seasonYear;$('account-cut').textContent=date(data.profile.generatedAt);
    $('profile-mains').innerHTML=mains.length?mains.map((id,i)=>`<div class="main-row">${art(id)}<div><strong>${escape(char(id)?.name||'Personaje sin ícono disponible')}</strong><small>${i===0?'Main':'Secundario '+i}</small></div><span class="origin ${selected?'chosen':''}">${selected?'Elegido':'Detectado'}</span></div>`).join(''):'<p class="note">No hay personajes registrados. Puedes elegir los tuyos en Mis personajes.</p>';
    all('[data-scope]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.scope===scope)));
    const mv=AccountModel.movement(v), scopeName=scope==='combined'?'+ Internacional':'Solo Guatemala';
    if(v.rank!=null) {
      const gap=v.top100Points==null?null:Math.max(0,v.top100Points-v.points);
      $('account-ranking').innerHTML=`<div class="rank-heading"><div><p class="kicker muted">Puesto nacional · ${scopeName}</p><div class="rank-number"><small>#</small>${v.rank}</div><span class="movement ${mv.kind}">${escape(mv.text)}</span></div><div><div class="rank-points">${v.points}</div><p class="kicker muted">puntos Smash GT</p></div></div><p>${v.rank<=100?'<span class="top-badge">Top 100</span>':'Fuera del top 100 · '}De ${v.total} clasificados en esta vista.</p>${v.rank>100&&gap!==null?`<p class="note">Diferencia de ${gap} puntos respecto al #100. El puesto depende también del desempate.</p>`:''}`;
    } else {
      const rule=data.profile.eligibilityRules, count=v.countedEvents, sets=v.wins+v.losses;
      $('account-ranking').innerHTML=`<p class="kicker" style="color:var(--yellow)">Sin puesto · ${scopeName}</p><h2>Tu temporada<br>está por escribirse.</h2><p class="lead">No apareces en los clasificados de esta vista y corte. La actividad mínima es una parte de las reglas; también se revisan pertenencia al ranking y participación local.</p><div class="activity-progress">${[[count,rule.playerMinimumEvents,'Torneos que cuentan'],[sets,rule.playerMinimumSets,'Sets válidos registrados']].map(([n,max,label])=>`<div><p>${label}: <strong>${n}/${max}</strong></p><div class="progress" role="progressbar" aria-label="${label}" aria-valuemin="0" aria-valuemax="${max}" aria-valuenow="${Math.min(n,max)}"><span style="width:${Math.min(100,n/max*100)}%"></span></div></div>`).join('')}</div><a href="./metodologia.html">Entender los requisitos ↗</a>${scope==='guatemala'&&data.profile.views.combined.rank!=null?`<button class="outline" id="other-scope">Con + Internacional tienes el puesto #${data.profile.views.combined.rank} →</button>`:''}`;
      $('other-scope')?.addEventListener('click',()=>changeScope('combined'));
    }
    const total=v.wins+v.losses;
    $('account-stats').innerHTML=[[v.wins,'Victorias','green'],[v.losses,'Derrotas','red'],[total?Math.round(v.wins/total*100)+'%':'—','Sets ganados',''],[`${v.countedEvents} de ${v.events.length}`,'Torneos disponibles que cuentan','']].map(([n,label,color])=>`<div><strong class="${color}">${n}</strong><small>${label}</small></div>`).join('');
    $('history-coverage').textContent=data.profile.historyCoverage;renderHistory();
  }
  function changeScope(next){scope=next;historyFilter='all';renderProfile();}
  function renderHistory() {
    const v=view();
    $('history-filters').innerHTML=[['all','Todos',v.events.length],['counted','Cuentan',v.events.filter(e=>e.counts).length],['excluded','Solo asistidos',v.events.filter(e=>!e.counts).length]].map(([filter,label,n])=>`<button data-filter="${filter}" aria-pressed="${filter===historyFilter}">${label} · ${n}</button>`).join('');
    all('[data-filter]').forEach(button=>button.addEventListener('click',()=>{historyFilter=button.dataset.filter;renderHistory();}));
    const events=AccountModel.history(v,historyFilter);
    $('account-history').innerHTML=events.length?events.map(e=>{const url=safeLink(e.url);return `<article class="history-row ${e.counts?'':'excluded'}"><div><p class="note">${date(e.date)} · ${escape(e.country||'País no disponible')}</p>${url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(e.name)} ↗</a>`:`<strong>${escape(e.name)}</strong>`}<p class="note">${escape(e.eventName)}</p></div><button class="history-record" data-event="${escape(e.id)}" aria-label="Ver sets de ${escape(e.name)}">${e.wins} G – ${e.losses} P</button><span class="event-badge">${e.counts?'Cuenta':'Asistido'}</span>${e.reason?`<p class="note">No cuenta: ${escape(e.reason)}</p>`:''}</article>`;}).join(''):'<p class="empty">No hay torneos disponibles para este filtro y corte.</p>';
    all('[data-event]').forEach(button=>button.addEventListener('click',()=>openEvent(button.dataset.event)));
  }
  function openEvent(id) {
    const event=view().events.find(e=>e.id===id);$('event-title').textContent=event.name;
    const results=(event.counts?view():data.profile.views.combined).results.filter(set=>String(set.eventId)===id);
    $('event-results').innerHTML=(event.reason?`<p class="notice">${escape(event.reason)} Estos sets se muestran como historial.</p>`:'')+(results.length?results.map(set=>`<article class="event-result"><strong>${escape(set.score||'Marcador no disponible')}</strong><p>${escape(set.playerTags?.join(' vs ')||'Tags no disponibles')}</p>${safeLink(set.url)?`<a href="${escape(safeLink(set.url))}" target="_blank" rel="noopener noreferrer">Ver en start.gg ↗</a>`:''}</article>`).join(''):'<p class="note">Estos resultados están fuera de esta vista. Cambia a + Internacional para consultarlos.</p>');
    $('event-dialog').showModal();
  }
  function renderCharacters() {
    const names=['Main','Secundario 1','Secundario 2'];
    $('chosen-slots').innerHTML=names.map((label,i)=>`<div class="slot-wrap"><button class="chosen-slot ${i===0?'main':''}" data-slot="${i}" aria-pressed="${i===activeSlot}">${chosen[i]?art(chosen[i],i===0?'portrait':'icon'):''}<span><span class="kicker">${label}${i?' · opcional':''}</span><strong>${escape(char(chosen[i])?.name||'+ Agregar')}</strong><small class="origin chosen">${chosen[i]?'Elegido':'Sin elegir'}</small></span></button>${i&&chosen[i]?`<button class="remove-secondary" data-remove="${i}" aria-label="Quitar ${label}">×</button>`:''}</div>`).join('');
    all('[data-slot]').forEach(button=>button.addEventListener('click',()=>{if(saving)return;activeSlot=Number(button.dataset.slot);renderCharacters();}));
    all('[data-remove]').forEach(button=>button.addEventListener('click',()=>{if(saving)return;chosen=AccountModel.remove(chosen,Number(button.dataset.remove));renderCharacters();}));
    const detected=view().detected, games=detected.reduce((n,c)=>n+c.games,0);
    $('detected-coverage').textContent=`${scope==='combined'?'+ Internacional':'Solo Guatemala'} · Selecciones registradas en el corte. Un set sin selecciones no permite conocer el personaje.`;
    $('detected-list').innerHTML=detected.length?detected.map(c=>`<div class="detected-row">${art(c.characterId)}<div><strong>${escape(c.name)}</strong><p class="note">${c.games} games · ${games?Math.round(c.games/games*100):0}%</p><div class="progress"><span style="width:${games?c.games/games*100:0}%"></span></div></div><button class="text-button" data-use="${escape(c.characterId)}" ${!char(c.characterId)||saving?'disabled':''}>Usar</button></div>`).join(''):'<p class="empty">No hay selecciones de personajes disponibles para esta vista.</p>';
    all('[data-use]').forEach(button=>button.addEventListener('click',()=>assign(button.dataset.use)));
    $('picker-title').textContent=`Elegir para: ${names[activeSlot]}`;renderGrid();
    const count=[0,1,2].filter(i=>chosen[i]!==saved[i]).length;
    $('unsaved-label').textContent=saving?'Guardando…':count?`${count} ${count===1?'cambio sin guardar':'cambios sin guardar'}`:'Sin cambios pendientes';
    $('save-characters').disabled=saving||!dirty()||!chosen[0];$('discard-characters').disabled=saving||!dirty();
    $('save-characters').querySelector('span').textContent=saving?'Guardando…':'Guardar';
  }
  function renderGrid() {
    const query=$('character-search').value, normalized=AccountModel.normalize(query), roster=CHARACTER_CATALOG.filter(c=>AccountModel.normalize(c.name).includes(normalized));
    $('character-count').textContent=query?`${roster.length} resultados para “${query}”`:`${roster.length} personajes`;
    const detected=new Set(view().detected.map(c=>c.characterId));
    $('character-grid').innerHTML=roster.map(c=>{const position=chosen.indexOf(c.characterId);return `<button class="character-tile ${detected.has(c.characterId)?'detected':''}" data-character="${c.characterId}" aria-pressed="${position!==-1}" ${saving?'disabled':''}>${art(c.characterId)}<span>${escape(c.name)}</span>${position!==-1?`<b>${position===0?'MAIN':'SEC '+position}</b>`:''}</button>`;}).join('')||'<p class="empty">No hay personajes con ese nombre.</p>';
    all('[data-character]').forEach(button=>button.addEventListener('click',()=>assign(button.dataset.character)));
  }
  function assign(id) {
    if(saving)return;
    if(activeSlot>0&&!chosen[0]){message('character-message','Elige primero tu main.');activeSlot=0;renderCharacters();return;}
    chosen=AccountModel.assign(chosen,activeSlot,id);message('character-message','');
    if(activeSlot===0&&chosen.length<3)activeSlot=chosen.length;
    renderCharacters();$(`chosen-slots`).querySelector(`[data-slot="${activeSlot}"]`)?.focus();
  }
  $('oauth-form').addEventListener('submit',()=>{$('oauth-button').disabled=true;$('oauth-button').querySelector('span').textContent='Conectando con start.gg…';});
  $('retry-account').addEventListener('click',load);
  $('tab-profile').addEventListener('click',()=>setScreen('profile'));$('tab-characters').addEventListener('click',()=>setScreen('characters'));
  all('[role=tab]').forEach(tab=>tab.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'profile':event.key==='End'?'characters':tab.id==='tab-profile'?'characters':'profile';if(setScreen(next))$(`tab-${next}`).focus();}}));
  $('edit-characters').addEventListener('click',()=>setScreen('characters'));
  all('[data-scope]').forEach(button=>button.addEventListener('click',()=>changeScope(button.dataset.scope)));
  all('[data-roles]').forEach(button=>button.addEventListener('click',()=>{roles=button.dataset.roles.split(',');renderOnboarding();}));
  $('save-role').addEventListener('click',async()=>{const button=$('save-role');button.disabled=true;try{await request({action:'roles',roles});data.user.roles=[...roles];setScreen('profile',true);}catch{message('role-error','No se guardó tu elección. Intenta de nuevo.','error');}finally{button.disabled=false;}});
  $('change-role').addEventListener('click',()=>{renderOnboarding();setScreen('onboarding');});
  $('character-search').addEventListener('input',renderGrid);
  $('discard-characters').addEventListener('click',()=>{chosen=[...saved];message('character-message','');renderCharacters();});
  $('save-characters').addEventListener('click',async()=>{saving=true;renderCharacters();try{await request({action:'characters',characters:chosen});saved=[...chosen];data.user.chosen=[...chosen];message('character-message','Personajes guardados. Ya se ven en tu perfil. El ranking público conserva sus personajes detectados.','success');}catch{message('character-message','No se guardaron tus cambios. Siguen aquí; intenta de nuevo.','error');}finally{saving=false;renderCharacters();}});
  async function closeAccount(action) {
    if(action==='disconnect'&&!confirm('¿Desvincular tu cuenta de Smash GT? Se cerrarán tus sesiones. Puedes volver a autorizarla después.'))return;
    try{await request({action});chosen=[...saved];await load();$('header-account').textContent='Ver ranking ↗';$('header-account').href='./#ranking';}catch{message('settings-error','No pudimos completar la operación. Intenta de nuevo.','error');}
  }
  $('logout').addEventListener('click',()=>closeAccount('logout'));$('disconnect').addEventListener('click',()=>closeAccount('disconnect'));
  $('close-event').addEventListener('click',()=>$('event-dialog').close());
  window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
  document.addEventListener('error',event=>{if(event.target.tagName==='IMG'){event.target.hidden=true;const fallback=document.createElement('span');fallback.textContent='?';fallback.setAttribute('aria-label','Imagen no disponible');event.target.after(fallback);}},true);
  load();
})();
