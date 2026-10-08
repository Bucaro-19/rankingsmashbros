/* Accounts use the published cut for statistics; chosen characters never alter it. */
(() => {
  const $=id=>document.getElementById(id), all=selector=>[...document.querySelectorAll(selector)];
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const char=id=>CHARACTER_CATALOG.find(c=>c.characterId===String(id));
  const art=(id,kind='icon')=>{const c=char(id);return c?`<img src="${escape(c[kind])}" alt="" loading="lazy">`:'<span aria-hidden="true">?</span>';};
  const safeLink=value=>{try{const u=new URL(value);return u.protocol==='https:'&&['www.start.gg','start.gg'].includes(u.hostname)&&!u.username&&!u.password?u.href:null;}catch{return null;}};
  const date=value=>{const day=String(value||'').slice(0,10).split('-');return day.length===3?`${day[2]}/${day[1]}/${day[0]}`:'Sin fecha';};
  let data=null, scope='combined', historyFilter='all', screen='login', chosen=[], saved=[], activeSlot=0, saving=false, roles=['player'], openEvents=new Set(), rivalOpener=null;
  const scopeName=()=>scope==='combined'?'+ Internacional':'Solo Guatemala';
  const number=value=>Number(value).toLocaleString('en');
  const initials=tag=>escape(String(tag).trim().slice(0,2).toUpperCase());
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
    for(const name of ['login','profile','characters','premium'])$(`${name}-screen`).hidden=name!==next;
    $('onboarding').hidden=next!=='onboarding';$('account-error').hidden=next!=='error';$('loading').hidden=true;
    $('account-tabs').hidden=!data?.authenticated||['error','onboarding'].includes(next);
    ['profile','characters','premium'].forEach(name=>{$(`tab-${name}`).setAttribute('aria-selected',String(name===next));$(`tab-${name}`).tabIndex=name===next?0:-1;});
    if(next==='profile')renderProfile();if(next==='characters')renderCharacters();if(next==='premium')SmashPremium.show();
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
      // A visitor arriving at the Premium address sees the plans first; paying needs an account.
      if(!data.authenticated&&location.hash.startsWith('#premium')){SmashPremium.setContext({csrf:data.csrf,authenticated:false});setScreen('premium',true);return;}
      if(!data.authenticated){renderLogin();return;}
      // Signed in again from the private panel: go back there. Only this fixed destination exists.
      try{if(sessionStorage.getItem('smashgt.volver')==='panel'){sessionStorage.removeItem('smashgt.volver');location.replace('./panel.php');return;}}catch{}
      // Signed in from the Premium plans: continue there.
      try{if(sessionStorage.getItem('smashgt.volver')==='premium'){sessionStorage.removeItem('smashgt.volver');history.replaceState(null,'','./cuenta.html#premium');}}catch{}
      saved=[...data.user.chosen];chosen=[...saved];roles=data.user.roles.length?[...data.user.roles]:['player'];
      $('header-account').textContent=data.user.tag;$('header-account').href='./cuenta.html';$('tab-panel').hidden=data.panel!==true;
      SmashPremium.setContext({csrf:data.csrf,authenticated:true,onStatus:markPremium});
      if(!data.user.roles.length){renderOnboarding();setScreen('onboarding',true);}else if(location.hash.startsWith('#premium'))setScreen('premium',true);else{setScreen('profile',true);SmashPremium.peek();}
      if(location.hash==='#vinculada')history.replaceState(null,'','./cuenta.html');
    }catch(error){
      if(error.status===401){try{data=await request();renderLogin();}catch{setScreen('error',true);}}else setScreen('error',true);
    }
  }
  function renderOnboarding() {
    const user=data.user, best=data.profile.views.combined, local=data.profile.views.guatemala, rules=data.profile.eligibilityRules;
    let sub='Sin jugador vinculado', note='Tu cuenta de start.gg no tiene sets en los torneos que seguimos. No buscamos por alias: si compites con otra cuenta de start.gg, ingresa con esa.', ring='none';
    if(user.playerId&&(best.rank!=null||local.rank!=null)){ring='found';note='';sub=`Jugador encontrado por tu ID de start.gg · #${best.rank??local.rank} en ${best.rank!=null?'+ Internacional':'Solo Guatemala'}`;}
    else if(user.playerId&&best.events.length){ring='pending';sub='Jugador encontrado · aún sin puesto';const sets=best.wins+best.losses;
      const progress=`Llevas ${best.countedEvents} ${best.countedEvents===1?'torneo que cuenta':'torneos que cuentan'} y ${sets} ${sets===1?'set válido':'sets válidos'} en ${data.profile.seasonYear}.`;
      note=AccountModel.requirements(best,rules).every(r=>r.done)?`${progress} Cumples la actividad mínima, pero todavía no apareces entre los clasificados de este corte; tu perfil explica el detalle.`
        :`${progress} Para clasificar necesitas ${rules.playerMinimumEvents} torneos y ${rules.playerMinimumSets} sets. Tu perfil ya muestra tu progreso.`;}
    $('linked-card').className=`linked-card ${ring}`;
    $('linked-card').innerHTML=`<div><span class="linked-avatar">${user.avatarUrl?`<img src="${escape(user.avatarUrl)}" alt="">`:initials(user.tag)}</span><div><span class="linked-ok">✓ Cuenta vinculada</span><strong>${escape(user.tag)}</strong><span>${escape(sub)}</span></div></div>${note?`<p>${escape(note)}</p>`:''}`;
    all('[data-role]').forEach(button=>{const on=roles.includes(button.dataset.role);button.setAttribute('aria-checked',String(on));button.querySelector('.check').textContent=on?'✓':'';});
    $('organizer-note').hidden=!roles.includes('organizer');
  }
  function renderProfile() {
    const v=view(), user=data.user, name=scopeName();
    const chosenIds=user.chosen, cardMain=chosenIds[0]??v.detected[0]?.characterId??null;
    $('account-tag').textContent=user.tag;
    const interests=user.roles.map(r=>r==='player'?'Jugador':'Organizador (por verificar)');
    $('account-role').textContent=interests.length?`Intereses: ${interests.join(' · ')}`:'Sin intereses elegidos';
    $('account-avatar').innerHTML=user.avatarUrl?`<img src="${escape(user.avatarUrl)}" alt="Foto de ${escape(user.tag)}">`:initials(user.tag);
    const link=safeLink(user.url);
    // Country is what the start.gg profile declares; it is not a verified nationality.
    $('account-facts').innerHTML=(user.country?`<div><dt>País en start.gg</dt><dd>${escape(user.country)}</dd></div>`:'')+(link?`<div><dt>Perfil público</dt><dd><a href="${escape(link)}" target="_blank" rel="noopener noreferrer">${escape(link.replace(/^https:\/\/(www\.)?/,''))} ↗</a></dd></div>`:'');
    $('account-facts').hidden=!user.country&&!link;
    $('card-rank').textContent=v.rank??'';const c=char(cardMain);$('card-portrait').hidden=!c;if(c)$('card-portrait').src=c.portrait;
    $('account-season').textContent=data.profile.seasonYear;$('account-cut').textContent=date(data.profile.generatedAt);
    $('profile-mains').innerHTML=chosenIds.length?chosenIds.map((id,i)=>`<div class="main-row">${art(id)}<div><strong>${escape(char(id)?.name||'Personaje sin ícono disponible')}</strong><small>${i===0?'Principal':'Secundario '+i}</small></div></div>`).join(''):'<p class="note">Aún no eliges personajes. Mientras tanto tu carta usa el más detectado en torneos.</p>';
    const games=v.detected.reduce((n,d)=>n+d.games,0);
    $('detected-block').hidden=!v.detected.length;$('detected-title').textContent=`Detectados · ${name}`;
    $('detected-chips').innerHTML=v.detected.map(d=>`<span class="detected-chip" title="${escape(d.name)}">${art(d.characterId)}<b>${escape(d.name)}</b><small>${games?Math.round(d.games/games*100):0}%</small></span>`).join('');
    $('player-content').hidden=!user.playerId;$('no-player').hidden=!!user.playerId;
    if(!user.playerId)return;
    all('[data-scope]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.scope===scope)));
    $('scope-status').innerHTML=`Mostrando <strong>${name}</strong> · ${scope==='combined'?'incluye torneos fuera del país.':'solo torneos en Guatemala.'} Tu puesto básico siempre es gratis.`;
    const panel=$('account-ranking');
    if(v.rank!=null) {
      const mv=AccountModel.movement(v), gap=v.top100Points==null?null:Math.max(0,v.top100Points-v.points);
      panel.setAttribute('aria-label','Puesto nacional');
      panel.innerHTML=`<div class="rank-heading"><div class="rank-main"><p class="kicker muted">Puesto nacional · ${name}</p><div class="rank-number"><small>#</small>${String(v.rank).padStart(2,'0')}</div><span class="movement ${mv.kind}">${escape(mv.text)}</span>${v.previousCutAt?`<p class="note">Comparado con el corte del ${date(v.previousCutAt)}</p>`:''}</div><div><div class="rank-points">${number(v.points)}</div><p class="kicker muted">puntos · ${name}</p></div></div>`
        +(v.rank<=100?`<p class="top-line"><span class="top-badge">Top 100</span>De ${v.total} clasificados en esta vista.</p>`
          :`<div class="gap"><div><strong>Fuera del top 100 · de ${v.total} clasificados</strong>${gap!==null?`<span>Faltan ${number(gap)} pts para el #100</span>`:''}</div>${gap!==null&&v.top100Points>0?`<div class="progress"><span style="width:${Math.min(100,Math.round(v.points/v.top100Points*100))}%"></span></div>`:''}</div>`);
    } else {
      const reqs=AccountModel.requirements(v,data.profile.eligibilityRules), none=!v.events.length, missing=reqs.filter(r=>!r.done), other=scope==='guatemala'?data.profile.views.combined:data.profile.views.guatemala;
      const text=none?'Tu jugador está vinculado, pero aún no tiene sets en torneos que cuenten esta temporada. Aparecerás al cumplir los requisitos.'
        :missing.length?`Para tener puesto en esta vista necesitas ${reqs[0].max} torneos que cuenten y ${reqs[1].max} sets válidos. Te falta: ${missing.map(r=>r.label==='Sets válidos'?`${r.missing} ${r.missing===1?'set válido':'sets válidos'}`:`${r.missing} ${r.missing===1?'torneo que cuente':'torneos que cuenten'}`).join(' y ')}.`
        :'Cumples la actividad mínima, pero no apareces entre los clasificados de esta vista y corte. También se revisan la pertenencia al ranking y la participación local.';
      panel.setAttribute('aria-label','Sin puesto');
      panel.innerHTML=`<div><p class="kicker yellow">${none||!missing.length?'Sin puesto':'Actividad insuficiente'} · ${name}</p><h2>${none?`Sin torneos en ${escape(data.profile.seasonYear)}`:missing.length?'Casi clasificas':'Sin puesto en esta vista'}</h2><p class="lead">${text}</p></div><div class="requirements">${reqs.map(r=>`<div><p><span>${r.label}</span><strong>${r.shown} / ${r.max}</strong></p><div class="pips" role="progressbar" aria-label="${r.label}" aria-valuemin="0" aria-valuemax="${r.max}" aria-valuenow="${r.shown}">${Array.from({length:r.max},(_,i)=>`<span class="${i<r.shown?'on':''}"></span>`).join('')}</div><small class="${r.done?'done':''}">${r.done?'✓ Cumplido':(r.missing===1?'Falta ':'Faltan ')+r.missing}</small></div>`).join('')}</div><a href="./metodologia.html">Entender los requisitos ↗</a>${other.rank!=null?`<button class="outline hint" id="other-scope">En ${scope==='guatemala'?'+ Internacional':'Solo Guatemala'} sí tienes puesto: #${other.rank} →</button>`:''}`;
      $('other-scope')?.addEventListener('click',()=>changeScope(scope==='guatemala'?'combined':'guatemala'));
    }
    $('account-stats').innerHTML=[[v.wins,'Sets ganados','green'],[v.losses,'Sets perdidos','red'],[v.countedEvents,'Torneos que cuentan',''],[v.events.length,'Torneos asistidos','']].map(([n,label,color])=>`<div><strong class="${color}">${n}</strong><small>${label}</small></div>`).join('');
    $('stats-note').textContent=`Ganados y perdidos: sets de torneos que cuentan en ${name}. Asistidos: tu actividad disponible en el corte ${data.profile.seasonYear}.`;
    $('history-legend').innerHTML=`<strong>Cuenta en ranking</strong>: suma en ${name}. <strong>Solo actividad</strong>: jugaste, pero no entra al cálculo de esta vista; te decimos por qué.`;
    $('history-coverage').textContent=data.profile.historyCoverage;renderHistory();
  }
  function changeScope(next){scope=next;historyFilter='all';renderProfile();}
  // Sets of one tournament as this player lived them. Events outside the view keep their sets from the combined cut.
  function eventSets(event){return (event.counts?view():data.profile.views.combined).results.filter(set=>String(set.eventId)===event.id);}
  function rivalOf(id){return id==null?null:data.profile.rivals[id]??null;}
  function renderHistory() {
    const v=view(), me=data.user.playerId;
    $('history-filters').innerHTML=[['all','Toda la actividad',v.events.length],['counted','Cuentan',v.events.filter(e=>e.counts).length],['excluded','Solo actividad',v.events.filter(e=>!e.counts).length]].map(([filter,label,n])=>`<button data-filter="${filter}" aria-pressed="${filter===historyFilter}">${label} · ${n}</button>`).join('');
    all('[data-filter]').forEach(button=>button.addEventListener('click',()=>{historyFilter=button.dataset.filter;renderHistory();}));
    const events=AccountModel.history(v,historyFilter);
    $('account-history').innerHTML=events.length?events.map(e=>{
      const url=safeLink(e.url), sets=eventSets(e), open=openEvents.has(e.id);
      const rows=open?sets.map(set=>{const rival=AccountModel.opponent(set,me), score=AccountModel.setScore(set,me), known=rivalOf(rival.id), place=known?.[scope]?.rank;
        return `<li><span class="result ${score.won?'won':'lost'}" aria-label="${score.won?'Ganado':'Perdido'}">${score.won?'G':'P'}</span><span class="versus">vs</span>${known?`<button class="rival-open" data-rival="${escape(rival.id)}" aria-label="Ver detalle de ${escape(known.tag||rival.tag)}">${known.main&&char(known.main)?art(known.main):''}<span>${escape(known.tag||rival.tag)}</span><small>${place!=null?'#'+place:'sin puesto'}</small></button>`:`<span class="rival-name">${escape(rival.tag)}</span>`}<b>${escape(score.text)}</b></li>`;}).join(''):'';
      return `<article class="history-row ${e.counts?'':'excluded'}"><div class="history-top"><div><p class="note">${date(e.date)}${e.country?' · '+escape(e.country):''}</p>${url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(e.name)} ↗</a>`:`<strong>${escape(e.name)}</strong>`}<p class="place">${escape(e.eventName)}</p></div><div class="history-record"><b>${e.wins}–${e.losses}</b><small>sets G–P</small></div><span class="event-badge">${e.counts?'Cuenta en ranking':'Solo actividad'}</span></div>${e.reason?`<p class="why">No cuenta: ${escape(e.reason)}</p>`:''}${sets.length?`<button class="sets-toggle" data-event="${escape(e.id)}" aria-expanded="${open}">${open?'Ocultar sets ▴':`Ver ${sets.length} ${sets.length===1?'set':'sets'} ▾`}</button>`:''}${open?`<ul class="set-list">${rows}</ul>`:''}</article>`;}).join('')
      :`<p class="empty">${v.events.length?'No hay torneos en este filtro.':`Aún no tienes torneos en la temporada ${escape(data.profile.seasonYear)}. Cuando juegues uno registrado en start.gg, aparecerá aquí.`}</p>`;
    all('[data-event]').forEach(button=>button.addEventListener('click',()=>{const id=button.dataset.event;if(openEvents.has(id))openEvents.delete(id);else openEvents.add(id);renderHistory();$('account-history').querySelector(`[data-event="${CSS.escape(id)}"]`)?.focus();}));
    all('[data-rival]').forEach(button=>button.addEventListener('click',()=>openRival(button.dataset.rival,button)));
  }
  function openRival(id,opener) {
    const rival=rivalOf(id), me=data.user.playerId;if(!rival)return;
    const place=rival[scope], h2h=AccountModel.headToHead(data.profile.views.combined.results,me,id), main=char(rival.main), link=safeLink(rival.url);
    $('rival-kicker').textContent=`Rival · ${scopeName()}`;$('rival-tag').textContent=rival.tag||'Rival sin alias';
    $('rival-sub').textContent=main?`Más usado en torneos: ${main.name}`:'Sin personaje detectado en el corte';
    $('rival-rank-art').textContent=place?.rank??'';$('rival-portrait').hidden=!main;if(main)$('rival-portrait').src=main.portrait;
    $('rival-cells').innerHTML=[[place?.rank!=null?'#'+place.rank:'Sin puesto','Puesto',''],[place?.points!=null?number(place.points):'—','Puntos','blue'],[`${h2h.wins}–${h2h.losses}`,'Tú vs. G–P','']].map(([n,label,color])=>`<div><strong class="${color}">${n}</strong><small>${label}</small></div>`).join('');
    $('rival-season').textContent=data.profile.seasonYear;
    $('rival-sets').innerHTML=h2h.sets.map(set=>{const score=AccountModel.setScore(set,me);return `<div><span class="result ${score.won?'won':'lost'}" aria-label="${score.won?'Ganaste':'Perdiste'}">${score.won?'G':'P'}</span><p><strong>${escape(set.tournament||'Torneo')}</strong><small>${date(set.date)}</small></p><b>${escape(score.text)}</b></div>`;}).join('')||'<p class="note">No hay sets entre ustedes en este corte.</p>';
    $('rival-link').hidden=!link;if(link)$('rival-link').href=link;
    $('rival-analyze').href=`./analisis.html?rival=${encodeURIComponent(id)}${scope==='guatemala'?'&scope=gt':''}`;
    rivalOpener=opener;$('rival-dialog').showModal();$('close-rival').focus();
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
  $('tab-profile').addEventListener('click',()=>setScreen('profile'));$('tab-characters').addEventListener('click',()=>setScreen('characters'));$('tab-premium').addEventListener('click',()=>setScreen('premium'));
  // Badge beside the alias and ring on the avatar while a paid period is running.
  function markPremium(active){document.body.classList.toggle('is-premium',active===true);document.querySelector('.premium-badge').hidden=active!==true;}
  all('[role=tab]').forEach(tab=>tab.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const order=['profile','characters','premium'],at=order.indexOf(tab.id.slice(4));const next=event.key==='Home'?order[0]:event.key==='End'?order[2]:order[(at+(event.key==='ArrowRight'?1:2))%3];if(setScreen(next))$(`tab-${next}`).focus();}}));
  $('edit-characters').addEventListener('click',()=>setScreen('characters'));
  all('[data-scope]').forEach(button=>button.addEventListener('click',()=>changeScope(button.dataset.scope)));
  all('[data-role]').forEach(button=>button.addEventListener('click',()=>{const role=button.dataset.role;roles=roles.includes(role)?roles.filter(r=>r!==role):[...roles,role].sort((a,b)=>a==='player'?-1:b==='player'?1:0);message('role-error','');renderOnboarding();}));
  $('other-account').addEventListener('click',()=>closeAccount('logout'));$('no-player-other').addEventListener('click',()=>closeAccount('logout'));
  $('save-role').addEventListener('click',async()=>{const button=$('save-role');if(!roles.length){message('role-error','Elige al menos un interés para continuar.','error');return;}button.disabled=true;try{await request({action:'roles',roles});data.user.roles=[...roles];setScreen('profile',true);}catch{message('role-error','No se guardó tu elección. Intenta de nuevo.','error');}finally{button.disabled=false;}});
  $('change-role').addEventListener('click',()=>{renderOnboarding();setScreen('onboarding');});
  $('character-search').addEventListener('input',renderGrid);
  $('discard-characters').addEventListener('click',()=>{chosen=[...saved];message('character-message','');renderCharacters();});
  $('save-characters').addEventListener('click',async()=>{saving=true;renderCharacters();try{await request({action:'characters',characters:chosen});saved=[...chosen];data.user.chosen=[...chosen];message('character-message','Personajes guardados. Ya se ven en tu perfil. El ranking público conserva sus personajes detectados.','success');}catch{message('character-message','No se guardaron tus cambios. Siguen aquí; intenta de nuevo.','error');}finally{saving=false;renderCharacters();}});
  async function closeAccount(action) {
    if(action==='disconnect'&&!confirm('¿Desvincular tu cuenta de Smash GT? Se cerrarán tus sesiones. Puedes volver a autorizarla después.'))return;
    try{await request({action});chosen=[...saved];await load();$('header-account').textContent='Ver ranking ↗';$('header-account').href='./#ranking';}catch{message('settings-error','No pudimos completar la operación. Intenta de nuevo.','error');}
  }
  $('logout').addEventListener('click',()=>closeAccount('logout'));$('disconnect').addEventListener('click',()=>closeAccount('disconnect'));
  $('close-rival').addEventListener('click',()=>$('rival-dialog').close());
  // A click on the dimmed area outside the panel closes it, like Esc.
  $('rival-dialog').addEventListener('click',event=>{if(event.target===$('rival-dialog'))$('rival-dialog').close();});
  $('rival-dialog').addEventListener('close',()=>{rivalOpener?.isConnected&&rivalOpener.focus();rivalOpener=null;});
  window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
  document.addEventListener('error',event=>{if(event.target.tagName==='IMG'){event.target.hidden=true;const fallback=document.createElement('span');fallback.textContent='?';fallback.setAttribute('aria-label','Imagen no disponible');event.target.after(fallback);}},true);
  load();
})();
