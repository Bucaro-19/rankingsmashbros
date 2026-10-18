/* Session-scoped view. Identity and own-pool projection are decided by the server. */
(() => {
  const $=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const catalog=typeof CHARACTER_CATALOG==='undefined'?[]:CHARACTER_CATALOG;
  let active=false,visible=false,controller=null,generation=0,data=null,poolIndex=0,view=null,loading=false,failed=false;
  const external=value=>{try{const u=new URL(value);return u.protocol==='https:'&&['start.gg','www.start.gg'].includes(u.hostname)&&!u.username&&!u.password?u.href:null;}catch{return null;}};
  const analysisLink=value=>/^\.\/(analisis|preparar)\.html\?rival=\d+$/.test(value||'')?value:null;
  const country=e=>e?.country==='SV'?'El Salvador':e?.country||'Zona local del torneo';
  const name=e=>e?.name==='LEGENDS7'?'Legends 7':e?.name||'Mi torneo';
  const clock=t=>t?.timestamp&&t.guatemala?t.guatemala.slice(-5):null;
  const date=t=>t?.guatemala?.slice(0,10)||null;
  const initials=m=>m?.tag?Array.from(m.tag.trim()).slice(0,2).join('').toUpperCase():'?';
  const rank=m=>Number.isInteger(m?.rank)?`#${m.rank} en nuestro ranking`:'Sin puesto en nuestro ranking';
  const seed=m=>Number.isInteger(m?.seed)?`<span>Seed ${m.seed}</span>`:'';
  const link=(href,text,cls='')=>href?`<a class="${cls}" href="${esc(href)}">${esc(text)}</a>`:'';
  const actions=(m,main=false)=>!m?'':`<div class="mt-actions">${link(analysisLink(m.analysisUrl),`Analizar a ${m.tag}`,main?'mt-button mt-primary':'mt-button')}${link(analysisLink(m.prepareUrl),`Prepara el set contra ${m.tag}`,'mt-button')}</div>`;
  const detail=m=>m?`<strong>${esc(m.tag)}</strong><small>${m.seed!=null?`Seed ${esc(m.seed)} · `:''}${esc(rank(m))}</small>`:'<strong>Por confirmar</strong>';
  function character(m){
    const known=m?.characters?.mains||[];
    // Keep an unknown main unknown; do not silently substitute a secondary.
    const main=catalog.find(c=>String(c.characterId)===String(known[0]?.characterId));
    if(!main||!/^\w{1,80}$/.test(main.slug)||main.slug==='random')return null;
    return {main,source:m.characters.source,secondary:known.slice(1,3).map(v=>catalog.find(c=>String(c.characterId)===String(v.characterId))).filter(c=>c&&/^\w{1,80}$/.test(c.slug)&&c.slug!=='random')};
  }
  function fighter(m,mine){
    const c=character(m),role=mine?'Tú':'Primer rival';
    const origin=!c?'? Sin personaje registrado':c.source==='profile'?`★ Elegido en ${mine?'tu':'su'} perfil`:'◉ Main detectado';
    return `<div class="mt-fighter ${mine?'mt-me':'mt-rival'}"><div class="mt-art ${c?'mt-has-portrait':''}"><div class="mt-stripe" aria-hidden="true"></div><div class="mt-initials" aria-hidden="true">${esc(initials(m))}</div>${c?`<img class="mt-portrait" src="./assets/characters/${esc(c.main.slug)}-portrait.png" alt="" loading="lazy" decoding="async">`:''}<span class="mt-origin">${esc(origin)}</span></div><div class="mt-fighter-info"><span class="mt-eyebrow">${role}</span><strong class="mt-tag">${esc(m?.tag||'Por confirmar')}</strong><div class="mt-player-facts">${seed(m)}<span>${esc(rank(m))}</span></div>${c?`<div class="mt-characters"><b>${esc(c.main.name)}</b>${c.secondary.map(c=>`<span><img src="./assets/characters/${esc(c.slug)}-icon.png" alt="" loading="lazy" width="26" height="26">${esc(c.name)}</span>`).join('')}</div>`:''}</div></div>`;
  }
  function hour(t){
    if(!clock(t))return '<span class="mt-muted">Horario aún no publicado</span>';
    return `<time datetime="${new Date(t.timestamp*1000).toISOString()}">${esc(clock(t))}</time><small>${esc(date(t))} · Guatemala</small>${t.local&&t.local!==t.guatemala?`<small>${esc(t.local)} · ${esc(t.timezone)}</small>`:''}`;
  }
  function header(){
    const e=data?.event;
    $('my-tournament-title').textContent=e?name(e):'Mi torneo';
    $('my-tournament-event').innerHTML=e?`${e.discipline?`<span>${esc(e.discipline)}</span>`:''}${date(e.start)?`<span>${esc(date(e.start))}</span>`:''}${e.country?`<span>${esc(country(e))}</span>`:''}${external(e.url)?`<a href="${esc(external(e.url))}" target="_blank" rel="noopener noreferrer">Ver en start.gg ↗</a>`:''}`:'';
    const at=data?.capturedAt?new Date(data.capturedAt):null;
    $('my-tournament-updated').textContent=at&&!Number.isNaN(at.getTime())?`Actualizado el ${new Intl.DateTimeFormat('es-GT',{timeZone:'America/Guatemala',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(at)} (Guatemala) · los horarios los define el organizador`:'';
  }
  function notice(status){
    const e=data?.event,states={
      snapshot_unavailable:['◷','Todavía no hay una captura disponible','Mi torneo se mostrará cuando tengamos los datos publicados por el organizador.'],
      registrations_unavailable:['◷','Los inscritos aún están ocultos','El organizador aún no publica la lista de inscritos. No podemos confirmar tu inscripción.'],
      not_registered:['?','No apareces inscrito',`No apareces inscrito en ${name(e)} con esta cuenta de start.gg. Buscamos la cuenta vinculada, no coincidencias por alias.`],
      pools_unpublished:['✓','Estás inscrito · pools sin publicar','El organizador aún no publica los pools. Vuelve a revisar más adelante.']
    };
    const s=states[status]||states.snapshot_unavailable;
    return `<section class="mt-notice"><span class="mt-notice-icon" aria-hidden="true">${s[0]}</span><h2>${esc(s[1])}</h2><p>${esc(s[2])}</p><div class="mt-actions">${external(e?.url)?`<a class="mt-button" href="${esc(external(e.url))}" target="_blank" rel="noopener noreferrer">Revisar en start.gg ↗</a>`:''}${status==='not_registered'?'<button class="mt-button" data-mt-profile type="button">Ver mi cuenta vinculada</button>':''}</div></section>`;
  }
  function schedule(pool){
    const first=pool.firstSet,t=first?.time,programmed=t?.source==='set_or_round'&&clock(t);
    const zone=[t,pool.start,data.event?.start].find(t=>t?.local&&t?.guatemala);
    const tz=zone?.local===zone?.guatemala&&zone?.local?`Hora de Guatemala · igual a la hora local de ${country(data.event)}`:zone?.timezone?`Guatemala y hora local · ${zone.timezone}`:'Hora de Guatemala · hora local aún no publicada';
    return `<aside class="mt-schedule"><h2>Horarios</h2><p class="mt-muted">◷ ${esc(tz)}</p><ul><li><div><b>Tu set${first?.round?` · ${esc(first.round)}`:''}</b><small>Horario de set/ronda de start.gg</small></div><div>${programmed?hour(t):'<span class="mt-muted">Sin programar</span>'}</div></li><li><div><b>Inicio del pool ${esc(pool.group||'')}</b><small>${pool.start?.source==='wave'?'Horario de wave':pool.start?.source==='round'?'Inicio de primera ronda':'Horario del pool'}</small></div><div>${hour(pool.start)}</div></li></ul><p class="mt-muted">Los horarios los define el organizador y pueden moverse. Vuelve a revisar antes de tu set.</p></aside>`;
  }
  function nextSet(pool){
    const first=pool.firstSet,op=first?.opponent,me=pool.members.find(m=>m.isMe),programmed=first?.time?.source==='set_or_round'&&clock(first.time);
    const shown=programmed?first.time:pool.start;
    const status=op?(first.opponentConfirmed?'✓ Confirmado':'◷ Posible rival · según seeds'):'◷ Rival pendiente';
    return `<section class="mt-next" aria-labelledby="mt-next-title"><div class="mt-next-heading"><div><h2 id="mt-next-title" class="mt-eyebrow">Mi próximo set</h2><p class="mt-phase">${esc(pool.phase)} · ${esc(pool.group||'Grupo sin nombre')}${first?.round?` · ${esc(first.round)}`:''}</p></div><span class="mt-chip ${op&&first.opponentConfirmed?'mt-confirmed':'mt-pending'}">${status}</span></div><div class="mt-big-time ${clock(shown)?'':'mt-unknown-time'}"><strong>${clock(shown)?esc(clock(shown)):'Horario aún no publicado'}</strong><div><b>${programmed?'Tu set · horario de set/ronda de start.gg':`Inicio del pool ${esc(pool.group||'')} · no es la hora de tu set`}</b><small>${programmed?`Inicio del pool: ${clock(pool.start)||'aún no publicado'}`:'Tu set puede empezar más tarde; aún no está programado.'}</small>${date(shown)?`<small>${esc(date(shown))} · Guatemala</small>`:''}</div></div><div class="mt-versus">${fighter(me,true)}${fighter(op,false)}<span class="mt-vs" aria-hidden="true">VS</span></div><div class="mt-next-footer">${op?`${first.opponentConfirmed?'':'<p class="mt-warning">Rival probable por seed; espera el resultado de la ronda anterior. No es un cruce confirmado.</p>'}${actions(op,true)}`:'<p class="mt-dashed">start.gg todavía no asigna tu primer rival. No mostramos uno hasta que se confirme; el análisis se activa entonces.</p>'}<p class="mt-muted">Personajes históricos o elegidos en el perfil: no sabemos con cuál jugará cada uno este set. El análisis completo y Prepara el set mantienen su acceso premium.</p></div></section>`;
  }
  function path(pool){
    const first=pool.firstSet;
    const rows=first?[{...first,current:true},...(pool.probablePath||[])]:[];
    return rows.length?`<ol class="mt-path">${rows.map((s,i)=>`<li class="${s.current?'mt-path-current':'mt-path-possible'}"><div class="mt-eyebrow">${i?'Si ganas':'Ahora'} <span>${s.current&&s.opponentConfirmed?'✓ Confirmado':'Probable · seeds'}</span></div><h3>${esc(s.round||'Ronda aún no publicada')}</h3><small>${s.current&&s.opponentConfirmed?'Tu rival':'Posible rival'}</small><div class="mt-person">${detail(s.opponent)}</div><p class="mt-muted">${i?'Según seeds y conexiones publicadas; los resultados pueden cambiarlo.':s.opponentConfirmed?'Cruce publicado por el organizador.':'Rival pendiente de confirmación.'}</p>${hour(s.time)}</li>`).join('')}</ol>`:'<p class="mt-dashed">start.gg todavía no asigna los enfrentamientos de tu próximo set. No dibujamos un camino inventado.</p>';
  }
  function graphModel(pool){
    const sets=pool.bracket?.sets||[],labels=new Map(),byId=new Map(sets.map(s=>[s.id,s]));
    let w=0,l=0,u=0;
    [...sets].sort((a,b)=>(a.side||'Z').localeCompare(b.side||'Z')||(Math.abs(a.round??9999)-Math.abs(b.round??9999))||String(a.id).localeCompare(String(b.id))).forEach(s=>labels.set(s.id,s.side==='W'?`W${++w}`:s.side==='L'?`L${++l}`:`S${++u}`));
    return {sets,labels,byId};
  }
  function slotText(slot,model){
    if(slot.member)return slot.member.tag;
    if(slot.isBye)return 'Pase automático (bye)';
    if(slot.from&&model.labels.has(slot.from.setId))return `${slot.from.outcome==='winner'?'Ganador':'Perdedor'} de ${model.labels.get(slot.from.setId)}`;
    return 'Por confirmar';
  }
  function setRows(s,model){
    return [0,1].map(index=>{
      const slot=s.slots.find(v=>v.index===index)||{},m=slot.member;
      return `<div class="mt-match-row ${m?.isMe?'mt-own-row':''} ${slot.isWinner?'mt-winner':''}"><small>${m?.seed??'—'}</small><span title="${esc(slotText(slot,model))}">${esc(slotText(slot,model))}${m?.isMe?' <b>TÚ</b>':''}</span><span>${slot.isWinner?'✓':''}</span></div>`;
    }).join('');
  }
  function graph(pool,asList=false){
    const model=graphModel(pool);
    return ['W','L',null].map(side=>{
      const matches=model.sets.filter(s=>s.side===side);if(!matches.length)return '';
      const rounds=[...new Set(matches.map(s=>s.round))].sort((a,b)=>Math.abs(a??9999)-Math.abs(b??9999));
      const title=side==='W'?'Winners':side==='L'?'Losers':'Rondas publicadas';
      if(asList)return `<section class="mt-list-side"><h3>${title}</h3>${rounds.map(r=>`<section><h4>${esc(matches.find(s=>s.round===r)?.label||'Ronda sin nombre')}</h4><ul>${matches.filter(s=>s.round===r).map(s=>`<li class="${s.isMine?'mt-my-set':''}"><b>${model.labels.get(s.id)} · ${s.isMine?'Tu set':s.finished?'Terminado':'Pendiente'}</b>${[0,1].map(i=>{const slot=s.slots.find(v=>v.index===i)||{};return `<p>${esc(slotText(slot,model))}${slot.member?.seed!=null?` (seed ${slot.member.seed})`:''}${slot.member?.isMe?' · TÚ':''}${slot.isWinner?' · Ganador':''}</p>`;}).join('')}${hour(s.time)}</li>`).join('')}</ul></section>`).join('')}</section>`;
      const positions=new Map(),width=rounds.length*280-48;
      const height=40+Math.max(...rounds.map(r=>matches.filter(s=>s.round===r).length))*132;
      const cards=rounds.map((r,col)=>{
        const group=matches.filter(s=>s.round===r);
        return `<div class="mt-round" style="left:${col*280}px"><h4>${esc(group[0]?.label||'Ronda sin nombre')}</h4>${group.map((s,row)=>{
          const y=40+row*132;positions.set(s.id,{x:col*280,y});
          return `<article class="mt-match ${s.isMine?'mt-my-set':''}" style="top:${y}px" aria-label="${esc(model.labels.get(s.id))}"><div class="mt-match-heading"><b>${model.labels.get(s.id)}</b><small>${s.isMine?'◷ Tu set':s.finished?'✓ Terminado':s.onProbablePath?'Posible cruce':'· Pendiente'}</small></div>${setRows(s,model)}${clock(s.time)?`<small class="mt-match-time">${esc(clock(s.time))} · ${esc(date(s.time))} GT</small>`:''}</article>`;
        }).join('')}</div>`;
      }).join('');
      const lines=matches.flatMap(s=>s.slots.map(v=>{
        const from=positions.get(v.from?.setId),to=positions.get(s.id);
        if(!from||!to||from.x>=to.x)return '';
        const x1=from.x+232,y1=from.y+58,x2=to.x,y2=to.y+45+v.index*26,mid=x1+24;
        const prior=model.byId.get(v.from.setId),confirmed=prior?.finished,probable=prior?.onProbablePath&&s.onProbablePath&&v.from.outcome==='winner';
        return `<path class="${confirmed?'mt-edge-confirmed':probable?'mt-edge-mine':'mt-edge-pending'}" d="M${x1},${y1} H${mid} V${y2} H${x2}"/>`;
      })).join('');
      return `<section class="mt-bracket-side"><h3>${title}</h3><p class="mt-muted">Desliza para explorar → · usa Lista para leer los nombres completos.</p><div class="mt-bracket-scroll" role="region" tabindex="0" aria-label="Bracket ${title} de tu pool"><div class="mt-canvas" style="width:${width}px;height:${height}px"><svg aria-hidden="true" width="${width}" height="${height}">${lines}</svg>${cards}</div></div></section>`;
    }).join('');
  }
  function bracket(pool){
    const hasGraph=!!pool.bracket?.sets?.length;
    if(!view||(!hasGraph&&view!=='path'))view=hasGraph&&window.matchMedia?.('(min-width:760px)').matches?'graph':'path';
    const views=hasGraph?[['path','Mi camino'],['graph','Bracket'],['list','Lista']]:[['path','Mi camino']];
    return `<section class="mt-bracket"><div class="mt-section-heading"><div><p class="mt-eyebrow">${esc(pool.phase)} · ${esc(pool.group||'')}</p><h2>Mi bracket</h2></div><div role="tablist" aria-label="Vista del bracket">${views.map(([key,label])=>`<button id="mt-view-${key}" role="tab" type="button" aria-selected="${key===view}" aria-controls="mt-bracket-panel" tabindex="${key===view?0:-1}" data-mt-view="${key}">${label}</button>`).join('')}</div></div><ul class="mt-legend" aria-label="Leyenda"><li><i class="mt-solid"></i>Confirmado: resultado o cruce ya publicado</li><li><i class="mt-square"></i>Tu set</li><li><i class="mt-dash"></i>Probable según seeds o posible rival: aún no confirmado</li></ul><div id="mt-bracket-panel" role="tabpanel" aria-labelledby="mt-view-${view}">${!hasGraph?'<p class="mt-dashed">El bracket completo de este pool todavía no está disponible. Mostramos tu primer rival y el camino probable cuando estén publicados.</p>':''}${view==='path'?path(pool):graph(pool,view==='list')}</div><p class="mt-muted">Marcadores aún no disponibles en esta vista. Las conexiones entre Winners y Losers se identifican en cada casilla.</p></section>`;
  }
  function poolList(pool){
    return `<section class="mt-pool-list"><div class="mt-section-heading"><h2>Mi pool</h2><span class="mt-chip">${esc(pool.group||'Grupo sin nombre')} · ${pool.members.length} jugadores</span></div><ul class="mt-roster">${pool.members.map(m=>`<li><span class="mt-roster-seed"><small>SEED</small><b>${m.seed??'—'}</b></span><div><strong>${esc(m.tag)}</strong><small>${esc(rank(m))}</small></div><div class="mt-roster-chips">${m.isMe?'<span class="mt-chip mt-you">Tú</span>':''}${pool.firstSet?.opponent?.playerId&&m.playerId===pool.firstSet.opponent.playerId?`<span class="mt-chip mt-opponent">${pool.firstSet.opponentConfirmed?'Primer rival':'Posible rival'}</span>`:''}${pool.strongest?.playerId&&m.playerId===pool.strongest.playerId?'<span class="mt-chip">◆ Referencia</span>':''}</div></li>`).join('')}</ul><p class="mt-muted">El seed lo asigna el organizador para este torneo. El puesto es de nuestro ranking nacional (+ Internacional): son datos distintos.</p></section>`;
  }
  function reference(pool){
    const m=pool.strongest;
    return `<section class="mt-reference"><p class="mt-eyebrow">◆ Rival de referencia del pool · puede ser distinto del que te toca ahora</p>${m?`<h2>${esc(m.tag)}</h2><p>${pool.strongestBasis==='rank'?'Mejor puesto en nuestro ranking dentro de este pool. Los jugadores sin puesto no se consideran más débiles.':'No hay rivales con puesto conocido: usamos el seed más alto (el número menor) como referencia.'}</p><p>${esc(rank(m))}${m.seed!=null?` · Seed ${m.seed}`:''}</p>${actions(m)}`:'<p>Sin puesto ni seeds suficientes para elegir un rival de referencia.</p>'}</section>`;
  }
  function render(){
    if(!active||!visible)return;
    header();$('my-tournament-retry').hidden=!failed;
    if(loading){$('my-tournament-body').innerHTML='<div class="mt-loading" role="status"><p>Cargando tu torneo…</p><div></div><div></div></div>';return;}
    if(failed){$('my-tournament-body').innerHTML='<div class="mt-notice mt-error" role="alert"><h2>No pudimos cargar tu torneo.</h2><p>No pudimos leer la última captura. Intenta de nuevo; tus datos no cambiaron.</p></div>';return;}
    if(!data)return;
    if(data.status!=='ready'||!data.pools?.length){$('my-tournament-body').innerHTML=notice(data.status);return;}
    const pool=data.pools[poolIndex]||data.pools[0];
    const phases=data.pools.length>1?`<div class="mt-phases" role="group" aria-label="Tus fases y grupos publicados">${data.pools.map((p,i)=>`<button type="button" data-mt-pool="${i}" aria-pressed="${i===poolIndex}"><b>${esc(p.phase)} · ${esc(p.group||'')}</b><small>${i===poolIndex?'Estás viendo':'Ver grupo publicado'}</small></button>`).join('')}</div>`:`<p class="mt-phase-chip">${esc(pool.phase)} · ${esc(pool.group||'Grupo sin nombre')}</p>`;
    $('my-tournament-body').innerHTML=`${phases}<div class="mt-hero">${nextSet(pool)}${schedule(pool)}</div>${bracket(pool)}${poolList(pool)}${reference(pool)}<p class="mt-foot">Pool y horarios son gratis. Datos tomados de start.gg; Ranking Smash Bros no organiza este torneo.</p>`;
  }
  async function load(restoreFocus=false){
    if(!active)return;controller?.abort();const id=++generation;controller=new AbortController();loading=true;failed=false;render();
    const pending=controller,timer=setTimeout(()=>pending.abort(),20000);
    try{
      const r=await fetch('./mi-torneo-api.php',{credentials:'same-origin',cache:'no-store',signal:pending.signal,headers:{Accept:'application/json'}}),value=await r.json();
      if(id!==generation||!active)return;if(!r.ok||value.ok!==true)throw new Error();
      data=value;poolIndex=0;view=null;
      $('my-tournament-banner').hidden=!value.upcoming||visible;
      $('my-tournament-banner-text').textContent=value.upcoming?`Tienes ${name(value.event)} en los próximos 7 días. Consulta tu pool y horarios.`:'';
    }catch{if(id!==generation||!active)return;failed=true;}
    finally{clearTimeout(timer);if(id===generation&&active){loading=false;render();if(restoreFocus&&visible)$('my-tournament').focus();}}
  }
  const showView=next=>{view=next;render();$(`mt-view-${next}`)?.focus();};
  window.SmashMyTournament={
    setContext({authenticated}){active=authenticated===true;generation++;controller?.abort();data=null;loading=false;failed=false;poolIndex=0;view=null;$('my-tournament-banner').hidden=true;$('my-tournament-body').textContent='';$('my-tournament-updated').textContent='';$('my-tournament-event').textContent='';$('my-tournament-retry').hidden=true;if(!active){visible=false;$('my-tournament').hidden=true;}if(active)load();},
    show(value=true){visible=value;$('my-tournament').hidden=!visible||!active;$('my-tournament-banner').hidden=!data?.upcoming||visible;render();},
    refresh(){if(active)load();}
  };
  $('my-tournament-retry').addEventListener('click',()=>load(true));
  $('my-tournament-banner-link').addEventListener('click',()=>{$('tab-tournament').click();$('my-tournament').focus();});
  $('my-tournament-body').addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button)return;
    if(button.dataset.mtView)showView(button.dataset.mtView);
    if(button.dataset.mtPool!==undefined){poolIndex=Number(button.dataset.mtPool);view=null;render();$('my-tournament-body').querySelector(`[data-mt-pool="${poolIndex}"]`)?.focus();}
    if(button.hasAttribute('data-mt-profile'))$('tab-profile').click();
  });
  $('my-tournament-body').addEventListener('keydown',event=>{
    const button=event.target.closest('[data-mt-view]');if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();event.stopPropagation();const keys=['path',...(data?.pools?.[poolIndex]?.bracket?.sets?.length?['graph','list']:[])],at=keys.indexOf(view);
    showView(event.key==='Home'?keys[0]:event.key==='End'?keys[keys.length-1]:keys[(at+(event.key==='ArrowRight'?1:keys.length-1))%keys.length]);
  });
  $('my-tournament-body').addEventListener('error',event=>{
    const image=event.target;if(image.tagName!=='IMG')return;
    if(image.classList.contains('mt-portrait')){image.parentElement.classList.remove('mt-has-portrait');const origin=image.parentElement.querySelector('.mt-origin');if(origin)origin.textContent+=' · retrato no disponible';}
    image.remove();
  },true);
})();
