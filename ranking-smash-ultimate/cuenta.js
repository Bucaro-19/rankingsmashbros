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
    if(screen==='organizer'&&next!==screen)SmashOrganizador.stopSlides();
    screen=next;
    for(const name of ['login','profile','characters','premium','organizer','tournament'])$(`${name}-screen`).hidden=name!==next;
    $('onboarding').hidden=next!=='onboarding';$('account-error').hidden=next!=='error';$('loading').hidden=true;
    $('account-tabs').hidden=!data?.authenticated||['error','onboarding'].includes(next);
    ['profile','characters','premium','organizer','tournament'].forEach(name=>{$(`tab-${name}`).setAttribute('aria-selected',String(name===next));$(`tab-${name}`).tabIndex=name===next?0:-1;});
    window.SmashMyTournament?.show(next==='tournament');
    if(next==='profile')renderProfile();if(next==='characters')renderCharacters();if(next==='premium')SmashPremium.show();if(next==='organizer')SmashOrganizador.show();
    // Keep the active account tab visible on narrow screens.
    {const tab=$(`tab-${next}`),row=tab?.parentElement;if(tab&&row&&!$('account-tabs').hidden)row.scrollLeft=Math.max(0,tab.offsetLeft-row.offsetLeft-12);}
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
    window.SmashMyTournament?.setContext({authenticated:false});
    try {
      data=await request();
      window.SmashMyTournament?.setContext({authenticated:data.authenticated===true,csrf:data.csrf});
      SmashPremium.setContext({csrf:data.csrf,authenticated:data.authenticated===true,admin:data.panel===true,organizerReady:data.organizerReady===true});
      // Display hint for the home page header only; never proof of a session.
      try{if(data.authenticated)localStorage.setItem('smashgt.cuenta',data.user.tag);else localStorage.removeItem('smashgt.cuenta');}catch{}
      // A visitor arriving at the Premium address sees the plans first; paying needs an account.
      if(!data.authenticated&&location.hash.startsWith('#premium')){SmashPremium.setContext({csrf:data.csrf,authenticated:false});setScreen('premium',true);return;}
      // The organizer tab explains itself before signing in, and an invitation says who invites.
      const wantsOrganizer=data.organizerReady===true&&(location.hash==='#torneos'||new URLSearchParams(location.search).has('invita'));
      $('tab-organizer').hidden=data.organizerReady!==true;
      if(!data.authenticated&&wantsOrganizer){SmashOrganizador.setContext({csrf:data.csrf,authenticated:false});setScreen('organizer',true);return;}
      if(!data.authenticated){renderLogin();return;}
      if(data.user.playerId && data.profile.views.guatemala.rank == null) scope='guatemala';
      // Signed in again from the private panel: go back there. Only this fixed destination exists.
      try{if(sessionStorage.getItem('smashgt.volver')==='panel'){sessionStorage.removeItem('smashgt.volver');location.replace('./panel.php');return;}}catch{}
      // Signed in from the Premium plans: continue there.
      try{if(sessionStorage.getItem('smashgt.volver')==='premium'){sessionStorage.removeItem('smashgt.volver');history.replaceState(null,'','./cuenta.html#premium');}}catch{}
      let backToOrganizer=wantsOrganizer;
      try{if(sessionStorage.getItem('smashgt.volver')==='torneos'){sessionStorage.removeItem('smashgt.volver');backToOrganizer=true;}}catch{}
      SmashOrganizador.setContext({csrf:data.csrf,authenticated:true,goTo:name=>{if(setScreen(name))$(`tab-${name}`).focus();}});
      saved=[...data.user.chosen];chosen=[...saved];roles=data.user.roles.length?[...data.user.roles]:['player'];
      $('header-account').textContent=data.user.tag;$('header-account').href='./cuenta.html';$('tab-panel').hidden=data.panel!==true;$('tab-opinions').hidden=data.panel!==true;$('opinions-csrf').value=data.csrf;
      SmashPremium.setContext({csrf:data.csrf,authenticated:true,onStatus:markPremium,admin:data.panel===true});
      if(!data.user.roles.length){renderOnboarding();setScreen('onboarding',true);}else if(location.hash.startsWith('#premium'))setScreen('premium',true);else if(backToOrganizer){setScreen('organizer',true);SmashPremium.peek();}else{setScreen('profile',true);SmashPremium.peek();}
      if(location.hash==='#vinculada')history.replaceState(null,'','./cuenta.html');
    }catch(error){
      window.SmashMyTournament?.setContext({authenticated:false});
      if(error.status===401){try{data=await request();renderLogin();}catch{setScreen('error',true);}}else setScreen('error',true);
    }
  }
  function renderOnboarding() {
    const user=data.user, best=data.profile.views.combined, local=data.profile.views.guatemala, rules=data.profile.eligibilityRules;
    let sub='Sin jugador vinculado', note='Tu cuenta de start.gg no tiene sets en los torneos que seguimos. No buscamos por alias: si compites con otra cuenta de start.gg, ingresa con esa.', ring='none';
    if(user.playerId&&(best.rank!=null||local.rank!=null)){ring='found';note='';sub=`Jugador encontrado por tu ID de start.gg · #${best.rank??local.rank} en ${best.rank!=null?'+ Internacional':'Solo Guatemala'}`;}
    else if(user.playerId&&best.events.length){ring='pending';sub='Jugador encontrado · aún sin puesto';const activity=AccountModel.activity(best),sets=activity.wins+activity.losses;
      const progress=`Llevas ${activity.countedEvents} ${activity.countedEvents===1?'torneo que cuenta':'torneos que cuentan'} y ${sets} ${sets===1?'set válido':'sets válidos'} en ${data.profile.seasonYear}.`;
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
    panel.removeAttribute('aria-labelledby');
    panel.classList.toggle('rank-panel-local-progress',scope==='guatemala'&&v.rank==null);
    if(v.rank!=null) {
      const mv=AccountModel.movement(v), gap=v.top100Points==null?null:Math.max(0,v.top100Points-v.points);
      panel.setAttribute('aria-label','Puesto nacional');
      panel.innerHTML=`<div class="rank-heading"><div class="rank-main"><p class="kicker muted">Puesto nacional · ${name}</p><div class="rank-number"><small>#</small>${String(v.rank).padStart(2,'0')}</div><span class="movement ${mv.kind}">${escape(mv.text)}</span>${v.previousCutAt?`<p class="note">Comparado con el corte del ${date(v.previousCutAt)}</p>`:''}</div><div><div class="rank-points">${number(v.points)}</div><p class="kicker muted">puntos · ${name}</p></div></div>`
        +(v.rank<=100?`<p class="top-line"><span class="top-badge">Top 100</span>De ${v.total} clasificados en esta vista.</p>`
          :`<div class="gap"><div><strong>Fuera del top 100 · de ${v.total} clasificados</strong>${gap!==null?`<span>Faltan ${number(gap)} pts para el #100</span>`:''}</div>${gap!==null&&v.top100Points>0?`<div class="progress"><span style="width:${Math.min(100,Math.round(v.points/v.top100Points*100))}%"></span></div>`:''}</div>`);
    } else if(scope==='guatemala') {
      renderLocalProgress(panel,v);
    } else {
      const reqs=AccountModel.requirements(v,data.profile.eligibilityRules), none=!v.events.length, onlyExcluded=!none&&!v.events.some(e=>e.counts), missing=reqs.filter(r=>!r.done), other=scope==='guatemala'?data.profile.views.combined:data.profile.views.guatemala;
      // No data is not proof of not playing: coverage depends on what start.gg publishes and what we capture.
      const text=none?`No encontramos sets tuyos de ${escape(data.profile.seasonYear)} en los torneos que capturamos de start.gg. Eso no quiere decir que no hayas jugado: si falta un torneo, puede ser un hueco de nuestra cobertura.`
        :onlyExcluded?'Registramos tu participación, pero ninguno de esos torneos cuenta para el ranking en esta vista. En tu historial verás el motivo de cada uno.'
        :missing.length?`Para tener puesto en esta vista necesitas ${reqs[0].max} torneos que cuenten y ${reqs[1].max} sets válidos. Te falta: ${missing.map(r=>r.label==='Sets válidos'?`${r.missing} ${r.missing===1?'set válido':'sets válidos'}`:`${r.missing} ${r.missing===1?'torneo que cuente':'torneos que cuenten'}`).join(' y ')}.`
        :'Cumples la actividad mínima, pero no apareces entre los clasificados de esta vista y corte. También se revisan la pertenencia al ranking y la participación local.';
      panel.setAttribute('aria-label','Sin puesto');
      panel.innerHTML=`<div><p class="kicker yellow">${none||onlyExcluded||!missing.length?'Sin puesto':'Actividad insuficiente'} · ${name}</p><h2>${none?'Sin torneos en nuestros datos':onlyExcluded?'Tus torneos aún no cuentan':missing.length?'Casi clasificas':'Sin puesto en esta vista'}</h2><p class="lead">${text}</p></div><div class="requirements">${reqs.map(r=>`<div><p><span>${r.label}</span><strong>${r.shown} / ${r.max}</strong></p><div class="pips" role="progressbar" aria-label="${r.label}" aria-valuemin="0" aria-valuemax="${r.max}" aria-valuenow="${r.shown}">${Array.from({length:r.max},(_,i)=>`<span class="${i<r.shown?'on':''}"></span>`).join('')}</div><small class="${r.done?'done':''}">${r.done?'✓ Cumplido':(r.missing===1?'Falta ':'Faltan ')+r.missing}</small></div>`).join('')}</div><a href="./metodologia.html">Entender los requisitos ↗</a>${other.rank!=null?`<button class="outline hint" id="other-scope">En ${scope==='guatemala'?'+ Internacional':'Solo Guatemala'} sí tienes puesto: #${other.rank} →</button>`:''}`;
      $('other-scope')?.addEventListener('click',()=>changeScope(scope==='guatemala'?'combined':'guatemala'));
    }
    const activity=AccountModel.activity(v);
    $('account-stats').innerHTML=[[activity.wins,'Sets ganados','green'],[activity.losses,'Sets perdidos','red'],[activity.countedEvents,'Torneos que cuentan',''],[v.events.length,'Torneos asistidos','']].map(([n,label,color])=>`<div><strong class="${color}">${n}</strong><small>${label}</small></div>`).join('');
    $('stats-note').textContent=v.recordedActivity&&v.rank==null?
      `Actividad registrada en torneos admitidos de ${name}, temporada ${data.profile.seasonYear}. Tu puesto corresponde al corte publicado.`:
      `Ganados y perdidos: sets de torneos que cuentan en ${name}. Asistidos: tu actividad disponible en el corte ${data.profile.seasonYear}.`;
    $('history-legend').innerHTML=`<strong>Cuenta en ranking</strong>: suma en ${name}. <strong>Solo actividad</strong>: jugaste, pero no entra al cálculo de esta vista; te decimos por qué.`;
    $('history-coverage').textContent=data.profile.historyCoverage;renderHistory();
  }
  function renderLocalProgress(panel,v) {
    const combined=data.profile.views.combined;
    const {hasActivity,requirements,exclusions}=AccountModel.localProgress(v,data.profile.eligibilityRules,combined);
    const [events,sets]=requirements;
    const missing=[];
    if(events.missing) missing.push(`${events.missing} ${events.missing===1?'torneo que cuente':'torneos que cuenten'}`);
    if(sets.missing) missing.push(`${sets.missing} ${sets.missing===1?'set válido':'sets válidos'}`);
    const met=hasActivity&&!missing.length;
    const eventCount=events.now>events.max?`${events.now} torneos que cuentan (mínimo ${events.max})`:`${events.now} de ${events.max} torneos que cuentan`;
    const setCount=sets.now>sets.max?`${sets.now} sets válidos (mínimo ${sets.max})`:`${sets.now} de ${sets.max} sets válidos`;
    const summary=hasActivity
      ? `Llevás ${eventCount} y ${setCount}.${missing.length?` Te falta completar ${missing.join(' y ')}.`:''}`
      : 'No encontramos participaciones tuyas en los datos de este corte.';
    const help=['Uno por torneo admitido en el que jugaste al menos un set válido.',
      'Ganar o perder cuenta igual. Los DQ, W.O. y pases automáticos no suman.'];
    const bars=requirements.map((r,i)=>{
      const count=!hasActivity?`— / ${r.max}`:r.now>r.max?`${r.now} (mín. ${r.max})`:`${r.now} / ${r.max}`;
      const status=!hasActivity?'— Sin datos en este corte':r.done?'✓ Cumplido':r.missing===1?'○ Te falta 1':`○ Te faltan ${r.missing}`;
      return `<div class="sp-bar"><div class="sp-bar-head"><span id="sp-bar-${i}">${r.label}</span><strong>${count}</strong></div>
        <div class="sp-segments" role="progressbar" aria-labelledby="sp-bar-${i}" aria-valuemin="0" aria-valuemax="${r.max}"${hasActivity?` aria-valuenow="${r.shown}"`:''} aria-valuetext="${count}. ${status}">
          ${Array.from({length:r.max},(_,j)=>{const filled=hasActivity&&j<r.shown;return `<span aria-hidden="true"${filled?' class="on"':''}>${filled?'✓ ':''}${hasActivity?j+1:'—'}</span>`;}).join('')}
        </div><strong class="sp-status ${!hasActivity?'unknown':r.done?'done':'pending'}">${status}</strong><small>${help[i]}</small></div>`;
    }).join('');
    const labels={
      under_minimum_active_players:['minimum','↓','No alcanzó el mínimo'],
      no_valid_set_in_counted_event:['invalid','×','El torneo contó · tu participación no sumó'],
      no_valid_set:['invalid','×','Sin set válido registrado'],
      international_excluded_in_local_view:['intl','◎','Torneo internacional']
    };
    const rows=exclusions.map(event=>{
      const [kind,mark,label]=Object.hasOwn(labels,event.reasonCode)?labels[event.reasonCode]:['minimum','—','Fuera del corte'];
      const url=safeLink(event.url);
      const title=escape(event.name);
      const reason=event.countsIntl?'No suma en Solo Guatemala. Sí cuenta en «+ Internacional».':event.reason||'Esta participación no figura entre las que cuentan en este corte.';
      return `<li class="sp-event ${kind}"><div class="sp-event-head">${url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${title} ↗</a>`:`<strong>${title}</strong>`}<span>${date(event.date)}</span></div>
        <span class="sp-badge"><span aria-hidden="true">${mark}</span> ${label}</span><p>${escape(reason)}</p>
        ${event.countsIntl?`<button type="button" class="text-button" data-sp-intl="${escape(event.id)}">Ver en «+ Internacional» →</button>`:''}</li>`;
    }).join('');
    const report='mailto:contacto@rankingsmashbros.com?subject=Torneo%20faltante%20en%20el%20ranking';
    panel.removeAttribute('aria-label');
    panel.setAttribute('aria-labelledby','sp-title');
    panel.innerHTML=`<div class="sp-content"><div class="sp-head"><p class="kicker yellow">Sin puesto · Solo Guatemala</p>
      <h2 id="sp-title">¿Por qué no apareces en el ranking nacional?</h2>
      <p class="sp-cut"><span>Temporada <strong>${escape(data.profile.seasonYear)}</strong></span><span>Corte del <strong>${date(data.profile.generatedAt)}</strong></span></p>
      <p class="sp-summary">${summary}</p></div><div class="sp-bars">${bars}</div>
      ${met?`<div class="sp-met"><span aria-hidden="true">✓</span><div><strong>Cumplís la actividad mínima registrada</strong><p>Además de la actividad, también se revisan la pertenencia al ranking y la participación local.</p><p class="note">Con los datos de este corte no podemos confirmar un motivo específico. Si creés que es un error, reportalo y lo revisamos.</p></div></div>`:''}
      ${!hasActivity?`<div class="sp-no-data"><p>Puede que el torneo todavía no esté en el corte, que te hayas inscrito con otra cuenta o que los resultados sigan pendientes.</p><a class="primary" href="${report}"><span>Reportar un torneo faltante</span></a></div>`:''}
      ${rows?`<div class="sp-exclusions"><h3><button type="button" id="sp-toggle" aria-expanded="false" aria-controls="sp-events"><span>Torneos que no te sumaron en este corte <b>${exclusions.length}</b></span><span class="sp-chevron" aria-hidden="true">▾</span></button></h3><div id="sp-events" role="region" aria-labelledby="sp-toggle" hidden><ul>${rows}</ul></div></div>`:''}
      <div class="sp-links"><a href="./metodologia.html">Cómo se calcula: metodología ↗</a>${hasActivity?`<a href="${report}">Reportar un torneo faltante</a>`:''}
      ${combined.rank!=null?`<button type="button" class="text-button" data-sp-intl="">Tu puesto en «+ Internacional»: #${combined.rank} →</button>`:''}</div></div>`;
    const toggle=$('sp-toggle');
    toggle?.addEventListener('click',()=>{
      const open=toggle.getAttribute('aria-expanded')==='true';
      toggle.setAttribute('aria-expanded',String(!open));
      $('sp-events').hidden=open;
      toggle.querySelector('.sp-chevron').textContent=open?'▾':'▴';
    });
    panel.querySelectorAll('[data-sp-intl]').forEach(button=>button.addEventListener('click',()=>{
      const eventId=button.dataset.spIntl;
      changeScope('combined');
      const event=eventId&&$('account-history').querySelector(`[data-history-id="${CSS.escape(eventId)}"]`);
      if(event){
        event.tabIndex=-1;
        event.focus();
      }else document.querySelector('[data-scope="combined"]').focus();
    }));
  }
  function changeScope(next){scope=next;historyFilter='all';renderProfile();}
  // Sets of one tournament as this player lived them. Events outside the view keep their sets from the combined cut.
  function eventSets(event){return Array.isArray(event.sets)?event.sets:(event.counts?view():data.profile.views.combined).results.filter(set=>String(set.eventId)===event.id);}
  function rivalOf(id){return id==null?null:data.profile.rivals[id]??null;}
  function renderHistory() {
    const v=view(), me=data.user.playerId;
    $('history-filters').innerHTML=[['all','Toda la actividad',v.events.length],['counted','Cuentan',v.events.filter(e=>e.counts).length],['excluded','Solo actividad',v.events.filter(e=>!e.counts).length]].map(([filter,label,n])=>`<button data-filter="${filter}" aria-pressed="${filter===historyFilter}">${label} · ${n}</button>`).join('');
    all('[data-filter]').forEach(button=>button.addEventListener('click',()=>{historyFilter=button.dataset.filter;renderHistory();}));
    const events=AccountModel.history(v,historyFilter);
    $('account-history').innerHTML=events.length?events.map(e=>{
      const url=safeLink(e.url), sets=eventSets(e), open=openEvents.has(e.id);
      const rows=open?sets.filter(set=>AccountModel.opponent(set,me)).map(set=>{const rival=AccountModel.opponent(set,me), valid=!set.outcome||set.outcome==='competitive', score=valid?AccountModel.setScore(set,me):{won:rival.won,text:'DQ / W.O.'}, known=rivalOf(rival.id), place=known?.[scope]?.rank;
        return `<li${valid?'':' class="not-valid"'}><span class="result ${valid?(score.won?'won':'lost'):'void'}" aria-label="${valid?(score.won?'Ganado':'Perdido'):'No válido: DQ, W.O. o bye'}">${valid?(score.won?'G':'P'):'—'}</span><span class="versus">vs</span>${known?`<button class="rival-open" data-rival="${escape(rival.id)}" aria-label="Ver detalle de ${escape(known.tag||rival.tag)}">${known.main&&char(known.main)?art(known.main):''}<span>${escape(known.tag||rival.tag)}</span><small>${place!=null?'#'+place:'sin puesto'}</small></button>`:`<span class="rival-name">${escape(rival.tag)}</span>`}<b>${escape(score.text)}</b></li>`;}).join(''):'';
      return `<article data-history-id="${escape(e.id)}" class="history-row ${e.counts?'':'excluded'}"><div class="history-top"><div><p class="note">${date(e.date)}${e.country?' · '+escape(e.country):''}</p>${url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(e.name)} ↗</a>`:`<strong>${escape(e.name)}</strong>`}<p class="place">${escape(e.eventName)}</p></div><div class="history-record"><b>${e.wins}–${e.losses}</b><small>sets G–P${e.other?` · ${e.other} DQ/W.O.`:''}</small></div><span class="event-badge">${e.counts?'Cuenta en ranking':'Solo actividad'}</span></div>${e.reason?`<p class="why">No cuenta: ${escape(e.reason)}</p>`:''}${e.source==='recorded_activity'?'<p class="note">Participación registrada para tu historial y progreso. El puesto corresponde al corte publicado.</p>':''}${sets.length?`<button class="sets-toggle" data-event="${escape(e.id)}" aria-expanded="${open}">${open?'Ocultar sets ▴':`Ver ${sets.length} ${sets.length===1?'set':'sets'} ▾`}</button>`:''}${open?`<ul class="set-list">${rows}</ul>`:''}</article>`;}).join('')
      :`<p class="empty">${v.events.length?'No hay torneos en este filtro.':`No encontramos torneos tuyos de la temporada ${escape(data.profile.seasonYear)} en los datos que capturamos. Si jugaste uno y no aparece, puede faltar en nuestra cobertura de start.gg.`}</p>`;
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
  $('tab-tournament').addEventListener('click',()=>setScreen('tournament'));$('tab-profile').addEventListener('click',()=>setScreen('profile'));$('tab-characters').addEventListener('click',()=>setScreen('characters'));$('tab-premium').addEventListener('click',()=>setScreen('premium'));$('tab-organizer').addEventListener('click',()=>setScreen('organizer'));
  // Badge beside the alias and ring on the avatar while a paid period is running.
  function markPremium(active){document.body.classList.toggle('is-premium',active===true);document.querySelector('.premium-badge').hidden=active!==true;}
  all('#account-tabs [role=tab]').forEach(tab=>tab.addEventListener('keydown',event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const order=['profile','characters','premium','organizer','tournament'].filter(name=>!$(`tab-${name}`).hidden),at=order.indexOf(tab.id.slice(4));const next=event.key==='Home'?order[0]:event.key==='End'?order[order.length-1]:order[(at+(event.key==='ArrowRight'?1:order.length-1))%order.length];if(setScreen(next))$(`tab-${next}`).focus();}}));
  $('edit-characters').addEventListener('click',()=>setScreen('characters'));
  all('[data-scope]').forEach(button=>button.addEventListener('click',()=>changeScope(button.dataset.scope)));
  all('[data-role]').forEach(button=>button.addEventListener('click',()=>{const role=button.dataset.role;roles=roles.includes(role)?roles.filter(r=>r!==role):[...roles,role].sort((a,b)=>a==='player'?-1:b==='player'?1:0);message('role-error','');renderOnboarding();}));
  $('other-account').addEventListener('click',()=>closeAccount('logout'));$('no-player-other').addEventListener('click',()=>closeAccount('logout'));
  $('save-role').addEventListener('click',async()=>{const button=$('save-role');if(!roles.length){message('role-error','Elige al menos un interés para continuar.','error');return;}button.disabled=true;try{await request({action:'roles',roles});data.user.roles=[...roles];setScreen('profile',true);}catch{message('role-error','No se guardó tu elección. Intenta de nuevo.','error');}finally{button.disabled=false;}});
  $('change-role').addEventListener('click',()=>{renderOnboarding();setScreen('onboarding');});
  $('character-search').addEventListener('input',renderGrid);
  $('discard-characters').addEventListener('click',()=>{chosen=[...saved];message('character-message','');renderCharacters();});
  $('save-characters').addEventListener('click',async()=>{saving=true;renderCharacters();try{await request({action:'characters',characters:chosen});saved=[...chosen];data.user.chosen=[...chosen];window.SmashMyTournament?.refresh();message('character-message','Personajes guardados. Ya se ven en tu perfil. El ranking público conserva sus personajes detectados.','success');}catch{message('character-message','No se guardaron tus cambios. Siguen aquí; intenta de nuevo.','error');}finally{saving=false;renderCharacters();}});
  async function closeAccount(action) {
    if(action==='disconnect'&&!confirm('¿Desvincular tu cuenta de Ranking Smash Bros? Se cerrarán tus sesiones. Puedes volver a autorizarla después.'))return;
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
