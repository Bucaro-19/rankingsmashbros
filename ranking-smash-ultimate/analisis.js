/* Rival analysis screen. Data comes from analisis-api.php, which decides what a free account
   may receive; this file never fills gaps with examples or derives premium data on its own. */
(() => {
  const M=AnalisisModel, root=document.getElementById('a-root'), scopeBar=document.getElementById('a-scope');
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const bySlug=slug=>CHARACTER_CATALOG.find(c=>c.slug===slug);
  const charName=slug=>bySlug(slug)?.name||'Personaje no registrado';
  const icon=slug=>{const c=bySlug(slug);return c?`<img src="${escape(c.icon)}" alt="" loading="lazy">`:'<span class="a-noicon" aria-hidden="true">?</span>';};
  const safeLink=value=>{try{const u=new URL(value);return u.protocol==='https:'&&['www.start.gg','start.gg'].includes(u.hostname)?u.href:null;}catch{return null;}};
  const params=new URLSearchParams(location.search);
  let scope=params.get('scope')==='gt'?'gt':'intl', rivalId=/^[1-9][0-9]{0,19}$/.test(params.get('rival')||'')?params.get('rival'):null;
  let data=null, searching=!rivalId, pair=null, query='', searchTimer=null, searchRun=0;

  async function api(search) {
    const controller=new AbortController(), stop=setTimeout(()=>controller.abort(),20000);
    try {
      const response=await fetch(`./analisis-api.php?${new URLSearchParams(search)}`,{credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{Accept:'application/json'}});
      const json=await response.json();
      if(!response.ok||json.ok!==true){const error=new Error(json.reason||'analysis_unavailable');error.status=response.status;throw error;}
      return json;
    } finally {clearTimeout(stop);}
  }
  function address() {
    const next=new URLSearchParams();if(rivalId)next.set('rival',rivalId);if(scope==='gt')next.set('scope','gt');
    history.replaceState(null,'',`./analisis.html${next.toString()?`?${next}`:''}`);
  }
  const notice=(kind,glyph,title,text,extra='')=>`<div class="a-notice ${kind}" role="${kind==='error'?'alert':'status'}"><span aria-hidden="true">${glyph}</span><div><strong>${title}</strong>${text?`<p>${text}</p>`:''}${extra}</div></div>`;
  function renderLoading(){root.innerHTML='<div class="a-loading" role="status"><div class="a-bar"><span></span></div><p>Preparando el análisis…</p><div class="a-skeleton tall"></div><div class="a-skeleton"></div><div class="a-skeleton"></div></div>';}
  function renderError(error) {
    scopeBar.hidden=true;
    if(error.status===401){root.innerHTML=`<section class="a-sober"><h1>Primero, <span>tu cuenta.</span></h1><p>El análisis de rival usa tu jugador vinculado. Entra con start.gg y vuelve aquí.</p><a class="cta blue" href="./cuenta.html"><span>Entrar con start.gg ↗</span></a></section>`;return;}
    const text=error.status===429?'Hiciste muchas consultas seguidas. Espera un minuto y vuelve a intentar.':error.status===404?'No encontramos a ese jugador en el corte actual.':'No pudimos preparar el análisis. Tus datos no cambiaron; vuelve a intentarlo en un momento.';
    root.innerHTML=notice('error','×',error.status===404?'Rival no encontrado.':'No pudimos cargar el análisis.',text,`<small>Código de referencia: ANA-${error.status||'RED'}</small>`)+`<div class="a-actions"><button type="button" id="a-retry" class="cta blue"><span>Reintentar</span></button><button type="button" id="a-other" class="outline">Elegir otro rival</button></div>`;
    document.getElementById('a-retry').addEventListener('click',load);document.getElementById('a-other').addEventListener('click',openSearch);
  }
  function half(person,mine) {
    const main=mine?(person.chosen?.[0]||person.detected?.find(d=>d.slug)?.slug):person.detected?.find(d=>d.slug)?.slug, c=bySlug(main);
    const rank=person.rank?.[scope], points=person.points?.[scope];
    return `<div class="a-half ${mine?'me':'him'}">${c?`<img src="${escape(c.portrait)}" alt="">`:`<span class="a-initials" aria-hidden="true">${escape(M.initials(person.tag))}</span>`}<div><strong>${escape(person.tag)}</strong><span>${rank!=null?`#${rank} · ${M.number(points)} pts`:'Sin puesto en esta vista'}</span></div></div>`;
  }
  function vsCard() {
    return `<section class="a-vs" aria-label="Tú contra ${escape(data.rival.tag)}"><div class="a-vs-head"><h1>Análisis de rival</h1><button type="button" id="a-change" class="outline">Cambiar rival</button></div><div class="a-vs-body">${half(data.me,true)}${half(data.rival,false)}<span class="a-vs-badge" aria-hidden="true">VS</span></div></section>`;
  }
  function recordBox() {
    const r=data.records?.[scope]||data.record, total=r.sets;
    return `<section class="a-box"><h2>Récord entre ustedes</h2><p class="a-figure">${r.wins}–${r.losses}</p><p class="a-note">${total?M.plural(total,'set','sets')+` en ${M.SCOPES[scope]}`:`Aún no se han enfrentado en ${escape(data.seasonYear)} en esta vista.`}</p></section>`;
  }
  function renderLocked() {
    const expired=data.state==='vencido'&&data.premium?.expiredAt;
    root.innerHTML=vsCard()+(data.rival.rank?.[scope]==null?`<p class="a-warn">Sin puesto en esta vista no significa rival débil: puede jugar fuera del país o tener poca actividad en este corte.</p>`:'')+recordBox()
      +`<section class="a-premium"><p class="kicker yellow">${expired?`Tu premium venció el ${M.date(data.premium.expiredAt)}`:'Premium · Apoya el sitio'}</p><h2>El análisis completo es premium</h2>
        <ul><li>Probabilidad estimada del set con los puntos de ambos.</li><li>Con qué personaje te conviene jugar, con su muestra y confianza.</li><li>Cómo te va contra sus personajes y a él contra los tuyos.</li><li>Su forma reciente y contra qué nivel de rivales gana y pierde.</li></ul>
        <p class="a-plans">3 USD al mes · 24 USD al año <span>(ahorras 12 USD)</span></p>
        <a class="cta" href="./cuenta.html#premium"><span>${expired?'Renovar premium':'Hacerme premium'}</span></a>
        <p class="a-note">Premium es un apoyo para sostener el sitio. Pagar no da puntos ni cambia tu puesto. El ranking, tu perfil y tu historial siguen siendo gratis.</p></section>`;
    wireCommon();
  }
  function probabilityBox() {
    const p=M.probability(data.probability);
    if(!p)return `<section class="a-box"><h2>Probabilidad estimada</h2><p class="a-empty">Sin estimación: ${escape(data.rival.points?.[scope]==null?data.rival.tag:data.me.tag)} no tiene puntos en ${M.SCOPES[scope]}.</p>${data.rival.rank?.[scope]==null?'<p class="a-note">Sin puesto en esta vista no significa rival débil: puede jugar fuera del país o tener poca actividad en este corte.</p>':''}</section>`;
    return `<section class="a-box a-prob"><h2>Probabilidad estimada</h2><div class="a-prob-main"><span class="a-prob-figure">${p.text}</span><span class="a-prob-word ${p.kind}"><b>${p.word}</b></span></div>
      <div class="a-duel" role="img" aria-label="Tú ${p.mine} por ciento, ${escape(data.rival.tag)} ${100-p.mine} por ciento"><span style="width:${p.mine}%"></span></div><div class="a-duel-labels"><span>Tú</span><span>${escape(data.rival.tag)}</span></div>
      <p class="a-note">Estimación del modelo con los puntos del ranking de ambos. No es una promesa: el set se decide jugando.</p></section>`;
  }
  function recommendationBox() {
    const first=data.rival.detected?.find(d=>d.usableForMatchups)?.slug, items=data.recommendations||[];
    if(!(data.me.chosen||[]).length)return `<section class="a-box a-advice"><h2>Con qué personaje jugar</h2><p>Elige tus personajes para que podamos sugerirte con cuál jugar. Mientras tanto, abajo usamos los que detectamos en tus torneos.</p><a class="outline" href="./cuenta.html">Elegir mis personajes →</a></section>`;
    if(!items.length)return `<section class="a-box a-advice"><h2>Con qué personaje jugar</h2><p class="a-empty-title">Sin datos suficientes</p><p>${escape(M.noRecommendation(data,data.rival.tag))}</p></section>`;
    return `<section class="a-box a-advice"><h2>Con qué personaje jugar</h2>${items.map(item=>{const r=M.recommendation(item,charName(item.slug),charName(item.reasonData?.opponentSlug||first));
      return `<article class="a-rec ${r.good?'good':'avoid'}"><div class="a-rec-icon">${icon(item.slug)}<span aria-hidden="true">${r.mark}</span></div><div><h3>${escape(r.title)}</h3><p>${escape(r.reason)}</p><p class="a-rec-meta"><span class="a-chip">${escape(r.confidence)}</span><span>${escape(r.sample)}</span></p></div></article>`;}).join('')}</section>`;
  }
  function recordRow(label,slug,pair,unit) {
    const r=M.record(pair,unit);
    return `<li class="a-row"><div class="a-row-head">${slug?icon(slug):''}<span>${escape(label)}</span><b>${r.empty?'—':r.count}</b></div>${r.percent!=null?`<div class="a-meter" aria-hidden="true"><span style="width:${r.percent}%"></span></div><p class="a-row-note">${r.percent}% · ${r.note}</p>`:`<p class="a-row-note ${r.small?'small':''}">${r.note}</p>`}</li>`;
  }
  function matchupBox() {
    const usage=M.usage(data.rival.detected), usable=usage.filter(d=>d.usableForMatchups&&d.slug), keys=M.myMatrixCharacters(data);
    const his=`<h3>Con qué juega ${escape(data.rival.tag)}</h3>${usage.length?`<div class="a-chips">${usage.map(d=>`<span class="a-chip-char">${d.slug?icon(d.slug):''}<b>${escape(d.name)}</b><small>${M.plural(d.games,'game','games')} · ${d.percent}%</small></span>`).join('')}</div>`:''}<p class="a-note">${escape(M.coverage(data.rival))}</p>`;
    if(!usable.length)return `<section class="a-box"><h2>Matchup de personajes</h2>${his}</section>`;
    const meRows=usable.map(d=>recordRow(`Tú contra ${d.name}`,d.slug,data.meVsChar?.[d.slug],'sets')).join('');
    const mine=(data.me.chosen?.length?data.me.chosen:keys.mine);
    const himRows=mine.map(slug=>recordRow(`${data.rival.tag} contra ${charName(slug)}`,slug,data.himVsChar?.[slug],'sets')).join('');
    if(!pair||!data.gameMatrix?.[pair])pair=Object.keys(data.gameMatrix||{})[0]||null;
    let cross='';
    if(pair){const [a,b]=pair.split('|'), cell=data.gameMatrix[pair];
      cross=`<h3>Personaje contra personaje, por game</h3><div class="a-pickers"><div role="group" aria-label="Tu personaje">${keys.mine.map(slug=>`<button type="button" data-mine="${escape(slug)}" aria-pressed="${slug===a}">${icon(slug)}<span>${escape(charName(slug))}</span></button>`).join('')}</div><span aria-hidden="true">vs</span><div role="group" aria-label="Su personaje">${keys.his.map(slug=>`<button type="button" data-his="${escape(slug)}" aria-pressed="${slug===b}">${icon(slug)}<span>${escape(charName(slug))}</span></button>`).join('')}</div></div>
        <ul class="a-rows" aria-live="polite">${recordRow(`Tú con ${charName(a)}`,null,cell.me,'games')}${recordRow(`${data.rival.tag} con ${charName(b)}`,null,cell.him,'games')}${recordRow(`La escena: ${charName(a)} contra ${charName(b)}`,null,cell.scene,'games')}</ul>${M.gamesNote(data.gameDataStatus)?`<p class="a-note">${escape(M.gamesNote(data.gameDataStatus))}</p>`:'<p class="a-note">La escena son los games con personaje registrado en los torneos de este corte, no todos los que se jugaron.</p>'}`;}
    return `<section class="a-box"><h2>Matchup de personajes</h2>${his}<h3>Cómo te va contra sus personajes</h3><ul class="a-rows">${meRows}</ul><h3>Cómo le va a él contra ${data.me.chosen?.length?'los tuyos':'tus personajes detectados'}</h3><ul class="a-rows">${himRows||'<li class="a-row"><p class="a-row-note">Sin personajes tuyos para cruzar.</p></li>'}</ul>${cross}</section>`;
  }
  function historyBox() {
    const r=data.records?.[scope]||data.record, sets=data.h2h||[], other=scope==='gt'?data.records?.intl:null, streak=M.streak(data.streak);
    if(!sets.length)return `<section class="a-box"><h2>Historial entre ustedes</h2><p class="a-empty">${other&&other.sets?`En Solo Guatemala no tienen sets: los ${other.sets} fueron en torneos internacionales.`:`Aún no se han enfrentado en ${escape(data.seasonYear)}. Abajo tienes cómo le va contra tus personajes.`}</p></section>`;
    return `<section class="a-box"><h2>Historial entre ustedes</h2><div class="a-history-head"><p class="a-figure">${r.wins}–${r.losses}</p>${streak?`<span class="a-chip">${escape(streak)}</span>`:''}</div>${r.sets<10?`<p class="a-warn">Muestra pequeña: ${M.plural(r.sets,'set','sets')}. Tómalo como pista, no como tendencia.</p>`:''}
      <ul class="a-sets">${sets.map(set=>{const link=safeLink(set.url);return `<li><span class="a-result ${set.won?'won':'lost'}" aria-label="${set.won?'Ganaste':'Perdiste'}">${set.won?'G':'P'}</span><div><strong>${link?`<a href="${escape(link)}" target="_blank" rel="noopener noreferrer">${escape(set.event)} ↗</a>`:escape(set.event)}</strong><small>${M.date(set.date)}${set.countryCode?` · ${escape(set.countryCode)}`:''} · ${set.myChar||set.theirChar?`${escape(set.myChar?charName(set.myChar):'Personaje no registrado')} vs ${escape(set.theirChar?charName(set.theirChar):'Personaje no registrado')}`:'Personaje no registrado'}</small></div><b>${M.setScore(set)}</b></li>`;}).join('')}</ul>${data.h2hTruncated?'<p class="a-note">Se muestran los 200 sets más recientes.</p>':''}</section>`;
  }
  function formBox() {
    const form=data.rivalForm||[], tiers=data.rivalTiers?.[scope];
    if(!form.length)return `<section class="a-box"><h2>Forma reciente de ${escape(data.rival.tag)}</h2><p class="a-empty">Sin torneos de ${escape(data.rival.tag)} en ${M.SCOPES[scope]} dentro de este corte. Prueba con ${scope==='gt'?'+ Internacional':'Solo Guatemala'}.</p></section>`;
    return `<section class="a-box"><h2>Forma reciente de ${escape(data.rival.tag)}</h2><ul class="a-sets">${form.map(e=>{const link=safeLink(e.url);return `<li><div><strong>${link?`<a href="${escape(link)}" target="_blank" rel="noopener noreferrer">${escape(e.event)} ↗</a>`:escape(e.event)}</strong><small>${M.date(e.date)}${e.countryCode?` · ${escape(e.countryCode)}`:''}</small></div><b>${e.setsWon}–${e.setsLost}</b></li>`;}).join('')}</ul>
      ${data.rivalFormTotal>form.length?`<p class="a-note">Últimos ${form.length} de ${data.rivalFormTotal} torneos conocidos en este corte.</p>`:''}
      ${tiers?`<h3>Contra qué nivel gana y pierde</h3><div class="a-tiers">${M.TIERS.map(([key,label])=>{const t=tiers[key]||[0,0];return `<div><span>${label}</span><b>${t[0]+t[1]?`${t[0]}–${t[1]}`:'—'}</b></div>`;}).join('')}</div><p class="a-note">Según el puesto de cada rival en este corte y vista. «Sin puesto» no significa rival débil: puede jugar fuera del país o tener poca actividad.</p>`:''}
      <p class="a-note">Sets conocidos en este corte; no es el historial completo de start.gg.</p></section>`;
  }
  function renderFull() {
    root.innerHTML=`<div class="a-columns"><div class="a-left">${vsCard()}${probabilityBox()}${recommendationBox()}</div><div class="a-right">${matchupBox()}${historyBox()}${formBox()}</div></div>`;
    root.querySelectorAll('[data-mine]').forEach(button=>button.addEventListener('click',()=>{pair=`${button.dataset.mine}|${pair.split('|')[1]}`;renderFull();root.querySelector(`[data-mine="${CSS.escape(button.dataset.mine)}"]`)?.focus();}));
    root.querySelectorAll('[data-his]').forEach(button=>button.addEventListener('click',()=>{pair=`${pair.split('|')[0]}|${button.dataset.his}`;renderFull();root.querySelector(`[data-his="${CSS.escape(button.dataset.his)}"]`)?.focus();}));
    wireCommon();
  }
  function wireCommon(){document.getElementById('a-change')?.addEventListener('click',openSearch);}
  function renderResults(list,truncated) {
    const box=document.getElementById('a-results');if(!box)return;
    box.innerHTML=list.length?list.map(p=>`<li><button type="button" data-pick="${escape(p.playerId)}"><span class="a-initials small" aria-hidden="true">${escape(M.initials(p.tag))}</span><span class="a-pick-main"><strong>${escape(p.tag)}</strong><small>${p.rank?.[scope]!=null?`#${p.rank[scope]} · ${M.number(p.points[scope])} pts`:'Sin puesto en esta vista'}${p.country?` · ${escape(p.country)}`:''}</small></span><span class="a-pick-record">${p.record?.sets?`${p.record.wins}–${p.record.losses} contigo`:'Sin sets contigo'}</span></button></li>`).join('')+(truncated?'<li class="a-note">Hay más resultados: escribe más letras.</li>':'')
      :`<li class="a-empty">${query?'Nadie con ese alias en el corte.':'Aún no tienes rivales con sets en este corte. Busca por alias.'}</li>`;
    box.querySelectorAll('[data-pick]').forEach(button=>button.addEventListener('click',()=>{rivalId=button.dataset.pick;searching=false;pair=null;address();load();}));
  }
  async function runSearch() {
    const run=++searchRun, status=document.getElementById('a-search-status');
    if(query.length===1){if(status)status.textContent='Escribe al menos 2 letras.';return;}
    if(status)status.textContent='Buscando…';
    try{const result=await api({buscar:query,scope});if(run!==searchRun)return;if(status)status.textContent=query?`${result.results.length} ${result.results.length===1?'jugador':'jugadores'}`:'Rivales con los que has jugado';renderResults(result.results,result.truncated);}
    catch(error){if(run!==searchRun)return;if(error.status===401){renderError(error);return;}if(status)status.textContent=error.status===429?'Demasiadas búsquedas seguidas. Espera un momento.':'No pudimos buscar. Intenta de nuevo.';}
  }
  function openSearch() {
    searching=true;scopeBar.hidden=false;
    root.innerHTML=`<section class="a-search"><p class="kicker">Análisis de rival</p><h1>¿Contra quién <span>juegas?</span></h1><label><span class="sr-only">Buscar jugador por alias</span><input id="a-query" type="search" placeholder="Busca por alias…" autocomplete="off" maxlength="80" value="${escape(query)}"></label><p id="a-search-status" class="a-note" role="status"></p><ul id="a-results" class="a-results"></ul>${rivalId&&data?'<button type="button" id="a-cancel" class="outline">Volver al análisis</button>':''}</section>`;
    const input=document.getElementById('a-query');input.focus();
    input.addEventListener('input',()=>{query=input.value.trim();clearTimeout(searchTimer);searchTimer=setTimeout(runSearch,300);});
    document.getElementById('a-cancel')?.addEventListener('click',()=>{searching=false;render();});
    runSearch();
  }
  function render() {
    scopeBar.hidden=false;scopeBar.querySelectorAll('[data-scope]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.scope===scope)));
    if(searching){openSearch();return;}
    if(data.state==='sinJugador'){scopeBar.hidden=true;root.innerHTML=`<section class="a-sober"><h1>Primero, <span>tu jugador.</span></h1><p>Tu cuenta todavía no tiene un jugador de start.gg vinculado, así que no hay con qué comparar. En tu perfil te explicamos cómo resolverlo.</p><a class="cta blue" href="./cuenta.html"><span>Ir a mi perfil →</span></a></section>`;return;}
    if(data.access?.full)renderFull();else renderLocked();
  }
  async function load() {
    if(!rivalId){openSearch();return;}
    renderLoading();
    try{data=await api({rival:rivalId,scope});render();document.title=`${data.rival?.tag?`Tú vs ${data.rival.tag}`:'Análisis de rival'} — Smash GT`;}
    catch(error){renderError(error);}
  }
  scopeBar.querySelectorAll('[data-scope]').forEach(button=>button.addEventListener('click',()=>{if(scope===button.dataset.scope)return;scope=button.dataset.scope;pair=null;address();if(searching){render();}else load();}));
  load();
})();
