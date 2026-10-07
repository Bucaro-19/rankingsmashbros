const $ = selector => document.querySelector(selector);
let snapshot=null, published=null, includeInternational=true, loading=false;
let rankingView='top', selectedMain=null, selectedPlayerId=null;
let playerMatches=[], allPlayerMatches=[], visibleMatches=20;
const dateFormat=new Intl.DateTimeFormat('es-GT',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Guatemala'});
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function safeLink(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && ['start.gg', 'www.start.gg'].includes(url.hostname) ? url.href : null;
  } catch { return null; }
}
function empty(target, title, description) {
  const box = element('div', undefined, 'empty');
  const icon = element('span', '↗', 'empty-icon');
  icon.setAttribute('aria-hidden', 'true');
  box.append(icon, element('h3', title), element('p', description));
  target.replaceChildren(box);
}
function resultNode(match) {
  const row = element('article', undefined, 'result-row');
  const url = safeLink(match.url);
  const title = element(url ? 'a' : 'strong', match.score || 'Marcador no disponible');
  if (url) { title.href = url; title.target = '_blank'; title.rel = 'noopener noreferrer'; }
  row.append(title, element('p', `${match.tournament} · ${match.country || 'País no indicado'} · ${match.date}`));
  return row;
}
function renderPlayerMatches() {
  $('#player-matches').replaceChildren(...playerMatches.slice(0, visibleMatches).map(resultNode));
  $('#player-history-count').textContent = `${Math.min(visibleMatches, playerMatches.length)} de ${playerMatches.length} sets válidos · del más reciente al más antiguo.`;
  $('#player-more').hidden = visibleMatches >= playerMatches.length;
  if (!playerMatches.length) empty($('#player-matches'), 'Todavía sin resultados', 'No encontramos sets presenciales completados en los datos consultados para esta ventana.');
}
function activityView(player, data) {
  if (!player.activity) return null;
  const catalog = new Map((data.events || []).map(event => [event.id, event]));
  const {events, months} = player.activity;
  if (!Array.isArray(events) || !Array.isArray(months) || events.length !== player.events
      || new Set(events.map(event => event.id)).size !== events.length) throw new Error('Actividad inválida');
  const ledger = events.map(record => {
    const event = catalog.get(record.id);
    if (!event || !/^\d{4}-\d{2}-\d{2}$/.test(event.date)
        || !Number.isInteger(record.wins) || record.wins < 0
        || !Number.isInteger(record.losses) || record.losses < 0
        || record.wins + record.losses < 1) throw new Error('Torneo de actividad inválido');
    return {...event, wins: record.wins, losses: record.losses};
  }).sort((a,b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
  if (ledger.reduce((n,e) => n+e.wins,0) !== player.wins
      || ledger.reduce((n,e) => n+e.losses,0) !== player.losses
      || player.sets !== player.wins + player.losses
      || JSON.stringify([...new Set(ledger.map(e => e.date.slice(0,7)))].sort()) !== JSON.stringify(months)) throw new Error('Totales de actividad inválidos');
  return {ledger, months};
}
function showPlayerMatches(event = null) {
  playerMatches = event ? allPlayerMatches.filter(match => match.eventId === event.id) : allPlayerMatches;
  visibleMatches = 20;
  $('#player-history-title').textContent = event ? `Sets en ${event.name}` : 'Sets considerados en este corte';
  $('#player-all-results').hidden = !event;
  renderPlayerMatches();
}
function renderActivity(player) {
  const view = activityView(player, snapshot);
  $('#player-activity').hidden = !view;
  if (!view) return;
  $('#activity-summary').textContent = `${view.months.length} ${view.months.length === 1 ? 'mes con actividad' : 'meses con actividad'} · ${player.events} torneos · ${player.sets} sets válidos.`;
  const monthNames = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  const monthLong = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
  const cutMonth = Number(snapshot.seasonLabel.split(' – ')[1]?.split('/')[1]);
  $('#activity-months').replaceChildren(...monthNames.map((name, index) => {
    const key = `${snapshot.seasonYear}-${String(index+1).padStart(2,'0')}`;
    const count = view.ledger.filter(event => event.date.startsWith(key)).length;
    const future = index+1 > cutMonth;
    const item = element('li', undefined, `activity-month${count ? ' is-active' : ''}${future ? ' is-future' : ''}`);
    const label = count ? `${count} ${count === 1 ? 'torneo' : 'torneos'}` : future ? 'Tras el corte' : 'Sin registro';
    item.setAttribute('aria-label', `${monthLong[index]} ${snapshot.seasonYear}: ${label}`);
    item.append(element('strong', name), element('span', label));
    return item;
  }));
  $('#activity-events-title').textContent = `Ver los ${player.events} torneos que cuentan`;
  $('#activity-events').open = false;
  $('#activity-ledger').replaceChildren(...view.ledger.map(event => {
    const item = element('li');
    const url = safeLink(event.url);
    const title = element(url ? 'a' : 'strong', event.name);
    if (url) { title.href=url; title.target='_blank'; title.rel='noopener noreferrer'; }
    const button = element('button', 'Ver sets', 'activity-sets');
    button.type='button'; button.setAttribute('aria-label', `Ver sets en ${event.name}, ${event.date}`);
    button.addEventListener('click', () => { showPlayerMatches(event); $('#player-history-title').scrollIntoView({block:'start'}); });
    item.append(title, element('p', `${event.eventName} · ${event.country} · ${event.date}`),
      element('p', `${event.wins} ${event.wins === 1 ? 'victoria' : 'victorias'} · ${event.losses} ${event.losses === 1 ? 'derrota' : 'derrotas'} · ${event.wins+event.losses} sets válidos`), button);
    return item;
  }));
}
function validateMains(player) {
  const mains = player.mains, c = player.mainCoverage;
  if (!Array.isArray(mains) || !c || mains.some(m => typeof m.characterId !== 'string' || typeof m.name !== 'string' || !m.name.trim() || !Number.isInteger(m.games) || m.games < 1)
      || new Set(mains.map(m=>m.characterId)).size !== mains.length
      || ['setsQueried','setsWithSelections','gamesWithSelections','ambiguousGames'].some(k=>!Number.isInteger(c[k]) || c[k]<0)
      || c.setsQueried !== player.sets || c.setsWithSelections > c.setsQueried
      || mains.reduce((n,m)=>n+m.games,0) !== c.gamesWithSelections
      || mains.some((m,i)=>i>0 && (m.games>mains[i-1].games || (m.games===mains[i-1].games && m.characterId<mains[i-1].characterId)))) throw new Error('Personajes inválidos');
}
function validate(data, nested = false) {
  if (!data || typeof data !== 'object') throw new Error('Datos inválidos');
  const pilot = [2, 3].includes(data.schemaVersion) && ['local_pilot', 'international_pilot'].includes(data.status) && data.rankingComputed === true;
  const coverage = data.schemaVersion === 1 && ['awaiting_data', 'coverage_only'].includes(data.status) && data.rankingComputed === false;
  if ((!pilot && !coverage) || !Array.isArray(data.players) || !Array.isArray(data.results)) throw new Error('Formato inválido');
  for (const player of data.players) {
    if (typeof player.id !== 'string' || typeof player.tag !== 'string' || !Number.isInteger(player.sets) || player.sets < 0) throw new Error('Jugador inválido');
    if (player.knownAs != null && typeof player.knownAs !== 'string') throw new Error('Alias inválido');
    if (pilot && (!Number.isInteger(player.rank) || player.rank < 1 || !Number.isInteger(player.rating) || !Number.isInteger(player.wins) || !Number.isInteger(player.losses) || !Number.isInteger(player.events) || typeof player.countryBasis !== 'string')) throw new Error('Clasificación inválida');
    if (player.previousRank != null && (!Number.isInteger(player.previousRank) || player.previousRank < 1)) throw new Error('Posición anterior inválida');
    if (data.schemaVersion === 3) validateMains(player);
    if (player.activity) activityView(player, data);
    if (coverage && typeof player.historyComplete !== 'boolean') throw new Error('Cobertura inválida');
  }
  for (const match of data.results) {
    if (!Array.isArray(match.playerIds) || typeof match.tournament !== 'string' || typeof match.date !== 'string' || (match.score !== null && typeof match.score !== 'string') || (match.country !== null && typeof match.country !== 'string')) throw new Error('Resultado inválido');
  }
  for (const name of ['players', 'events', 'sets', 'countries']) {
    if ((data.status === 'coverage_only' || pilot) && (!Number.isInteger(data.counts?.[name]) || data.counts[name] < 0)) throw new Error('Conteo inválido');
  }
  if ((data.status === 'coverage_only' || pilot) && !Number.isFinite(Date.parse(data.generatedAt))) throw new Error('Fecha inválida');
  if (pilot && (data.players.some((player, index) => player.rank !== index + 1) || typeof data.scope !== 'string'
      || data.counts.players !== data.players.length || new Set(data.players.map((player) => player.id)).size !== data.players.length)) throw new Error('Ranking inválido');
  if (pilot && data.rankingCoverage === 'all_eligible' && (data.counts.eligiblePlayers !== data.players.length || data.counts.top100 !== Math.min(100, data.players.length))) throw new Error('Clasificación incompleta');
  if (data.seasonYear != null && (!Number.isInteger(data.seasonYear) || data.seasonYear < 2026)) throw new Error('Temporada inválida');
  if (data.rankingScope === 'guatemala' && (data.status !== 'local_pilot'
      || !Array.isArray(data.events) || data.events.some(e => e.country !== 'GT')
      || data.results.some(m => m.country !== 'GT'))) throw new Error('Vista local inválida');
  if ('localRanking' in data) {
    if (nested || data.rankingScope !== 'combined') throw new Error('Vistas inválidas');
    const local = validate(data.localRanking, true);
    if (local.rankingScope !== 'guatemala' || local.generatedAt !== data.generatedAt
        || local.seasonYear !== data.seasonYear || local.seasonLabel !== data.seasonLabel
        || local.methodVersion !== data.methodVersion
        || !Array.isArray(data.events)
        || JSON.stringify(local.eligibilityRules) !== JSON.stringify(data.eligibilityRules)
        || JSON.stringify(local.events.map(e=>e.id).sort()) !== JSON.stringify(data.events.filter(e=>e.country==='GT').map(e=>e.id).sort())) throw new Error('Las vistas no corresponden al mismo corte');
  }
  return data;
}
function chooseSnapshot(data, international) {
  if (!international && !data.localRanking) throw new Error('Vista local no disponible');
  return international ? data : data.localRanking;
}
function damageColor(rank) {
  const stops=[[244,241,234],[255,210,63],[255,140,40],[255,77,46],[200,30,40]];
  const x=Math.min(.999999,Math.max(0,1-(rank-1)/14))*4, i=Math.floor(x), f=x-i;
  return `rgb(${stops[i].map((v,k)=>Math.round(v+(stops[i+1][k]-v)*f)).join(',')})`;
}
function movement(player, data=snapshot) {
  if (!data.previousCutAt || !Number.isInteger(player.previousRank)) return {text:'—',label:data.previousCutAt?'Sin puesto previo publicado':'Sin corte anterior comparable',kind:'same'};
  const delta=player.previousRank-player.rank;
  return {text:delta>0?`▲ ${delta}`:delta<0?`▼ ${-delta}`:'—',label:delta>0?`Subió ${delta} puestos`:delta<0?`Bajó ${-delta} puestos`:'Sin cambio de puesto',kind:delta>0?'up':delta<0?'down':'same'};
}
function mainList(player) { return (player.mains || []).slice(0,3); }
function imageNode(name, kind='icon', fallback='?') {
  const asset=characterAsset(name);
  const missing=()=>element('span',fallback,kind==='portrait'&&fallback!=='?'?'unknown-hero':'unknown-art');
  if (!asset) return missing();
  const img=element('img'); img.src=asset[kind]; img.alt=kind==='portrait'?'':name; img.loading=kind==='icon'?'lazy':'eager'; img.decoding='async';
  if (kind==='portrait' && asset[kind].startsWith('./')) img.className='is-tight';
  img.addEventListener('error',()=>img.replaceWith(missing()),{once:true});
  return img;
}
function playerSub(player) { return [mainList(player)[0]?.name || 'Main sin registro',player.knownAs?`antes ${player.knownAs}`:null,`${player.events} torneos`].filter(Boolean).join(' · '); }
function openFrom(player) { return ()=>openPlayer(player); }
function renderHero() {
  const player=snapshot.players[0];
  $('#hero-season').textContent=`Temporada ${snapshot.seasonYear || 2026} · Corte ${snapshot.seasonLabel.split(' – ')[1]} · Piloto`;
  for (const [id,key] of [['players-count','players'],['events-count','events'],['sets-count','sets']]) $('#'+id).textContent=snapshot.counts[key].toLocaleString('es-GT');
  $('#hero-player').disabled=!player;
  if (!player) { $('#hero-tag').textContent='Sin clasificados';$('#hero-points').textContent='—';$('#hero-art').replaceChildren();return; }
  $('#hero-tag').textContent=player.tag;$('#hero-points').textContent=String(player.rating);
  $('#hero-art').replaceChildren(imageNode(mainList(player)[0]?.name,'portrait',player.tag));
  $('#hero-player').setAttribute('aria-label',`Ver detalle de ${player.tag}, puesto 1`);
  $('#hero-player').onclick=openFrom(player);
  const text=snapshot.players.slice(0,10).map(p=>`#${String(p.rank).padStart(2,'0')} ${p.tag} · ${p.rating} pts ${movement(p).text}`).join('  ✦  ')+'  ✦  ';
  const copy=element('span',text);copy.setAttribute('aria-hidden','true');
  $('#ticker-track').replaceChildren(element('span',text),copy);
}
function renderChips() {
  const mains=new Map();
  snapshot.players.forEach(p=>mainList(p).forEach(m=>mains.set(m.characterId,m)));
  if (selectedMain && !mains.has(selectedMain)) selectedMain=null;
  $('#main-filter').hidden=!mains.size;
  const chip=(name,id)=>{const b=element('button',undefined,'main-chip');b.type='button';b.title=name;b.setAttribute('aria-label',id?`Filtrar por ${name}`:'Todos los personajes');b.setAttribute('aria-pressed',String(selectedMain===id));b.append(id?imageNode(name):document.createTextNode('Todos'));b.onclick=()=>{selectedMain=id;renderChips();renderPlayers();};return b;};
  $('#main-chips').replaceChildren(chip('Todos',null),...[...mains.values()].sort((a,b)=>a.name.localeCompare(b.name)).map(m=>chip(m.name,m.characterId)));
  const known=snapshot.players.filter(p=>p.mains?.length).length;
  $('#main-coverage-note').textContent=known?`Personajes registrados para ${known} de ${snapshot.players.length} clasificados. Los chips incluyen el main y hasta dos secundarios por jugador; son selecciones reportadas en este corte.`:'Todavía no hay selecciones de personajes disponibles en esta vista. “?” significa sin datos registrados, no que el jugador no tenga un main.';
}
function podiumCard(player) {
  const card=element('button',undefined,`podium-card${player.rank===1?' is-first':''}`);card.type='button';card.setAttribute('aria-label',`Ver detalle de ${player.tag}, puesto ${player.rank}`);
  card.append(element('span',String(player.rank),'podium-number'),imageNode(mainList(player)[0]?.name,'portrait'));
  const caption=element('span',undefined,'podium-caption'),name=element('span'),score=element('b',String(player.rating));score.style.color=damageColor(player.rank);
  name.append(element('strong',player.tag),element('small',`${player.events} torneos · ${movement(player).text} ${movement(player).label}`));caption.append(name,score);card.append(caption);card.onclick=openFrom(player);return card;
}
function rankRow(player,max) {
  const row=element('button',undefined,'rank-row');row.type='button';row.setAttribute('aria-label',`Ver detalle de ${player.tag}, puesto ${player.rank}`);
  const move=movement(player),arrow=element('span',move.text,`rank-move ${move.kind}`);arrow.setAttribute('aria-label',move.label);
  const identity=element('span',undefined,'rank-identity'),icon=element('span',undefined,'stock-icon'),name=element('span',undefined,'rank-name');
  icon.append(imageNode(mainList(player)[0]?.name));name.append(element('strong',player.tag),element('small',playerSub(player)));identity.append(icon,name);
  const secondaries=element('span',undefined,'rank-secondaries');mainList(player).slice(1).forEach(m=>secondaries.append(imageNode(m.name)));
  const score=element('span',undefined,'rank-score'),track=element('span',undefined,'points-track'),fill=element('span',undefined,'points-fill');score.style.color=damageColor(player.rank);fill.style.width=`${Math.max(0,Math.min(100,player.rating/Math.max(1,max)*100))}%`;track.setAttribute('aria-hidden','true');track.append(fill);score.append(track,element('b',String(player.rating)));
  row.append(element('span',String(player.rank).padStart(2,'0'),'rank-number'),arrow,identity,secondaries,element('span',`${player.wins}–${player.losses}`,'rank-record'),score);row.onclick=openFrom(player);return row;
}
function filteredPlayers(data, query, main, view) {
  const norm=v=>v.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('es');
  const q=norm(query.trim()),filtered=Boolean(q||main);
  return data.players.filter(p=>(!q||norm(`${p.tag} ${p.knownAs||''}`).includes(q))&&(!main||mainList(p).some(m=>m.characterId===main))&&(filtered||view==='all'||p.rank<=100));
}
function renderPlayers() {
  if (!snapshot) return;
  const query=$('#search').value,filtered=Boolean(query.trim()||selectedMain);
  const rows=filteredPlayers(snapshot,query,selectedMain,rankingView);
  $('#podium').hidden=filtered||!rows.length;
  $('#podium').replaceChildren(...[2,1,3].map(rank=>rows.find(p=>p.rank===rank)).filter(Boolean).map(podiumCard));
  const visible=filtered?rows:rows.filter(p=>p.rank>3);
  $('#players-list').replaceChildren(...visible.map(p=>rankRow(p,snapshot.players[0]?.rating||1)));
  if (!rows.length) $('#players-list').append(element('p','Nadie con ese tag o main en este corte. Prueba otro filtro o cambia el alcance.','gt-empty'));
  $('#ranking-summary').textContent=filtered?`${rows.length} ${rows.length===1?'coincidencia':'coincidencias'} entre ${snapshot.players.length} clasificados.`:`${rows.length} de ${snapshot.players.length} clasificados · ${rankingView==='all'?'todos los puestos':'Top 100'}.`;
  $('#view-all').hidden=filtered||snapshot.players.length<=100;
  $('#view-all').textContent=rankingView==='all'?'Ver solo top 100':`Ver los ${snapshot.players.length} clasificados`;
  $('#view-all').setAttribute('aria-pressed',String(rankingView==='all'));
}
function playerRivals(player, data) {
  const rivals=new Map(),names=new Map(data.players.map(p=>[p.id,p.tag]));
  for(const match of data.results) {
    const index=match.playerIds.indexOf(player.id);if(index<0)continue;
    const other=match.playerIds[1-index];if(!other)continue;
    const row=rivals.get(other)||{id:other,tag:names.get(other)||match.playerTags?.[1-index]||`Rival #${other}`,wins:0,losses:0};
    row[index===0?'wins':'losses']++;rivals.set(other,row);
  }
  return [...rivals.values()].sort((a,b)=>(b.wins+b.losses)-(a.wins+a.losses)||a.tag.localeCompare(b.tag)).slice(0,5);
}
function openPlayer(player) {
  selectedPlayerId=player.id;
  $('#drawer-rank').textContent=String(player.rank);$('#drawer-art').replaceChildren(imageNode(mainList(player)[0]?.name,'portrait'));
  $('#player-title').textContent=player.tag;$('#player-subtitle').textContent=playerSub(player);
  $('#player-movement').textContent=`${movement(player).text} ${movement(player).label}`;
  const stats=[[String(player.rating),'Puntos'],[`${player.wins}–${player.losses}`,'Sets G–P'],[String(player.events),'Torneos']];
  $('#player-stats').replaceChildren(...stats.map(([value,label],index)=>{const d=element('div'),v=element('strong',value);if(!index)v.style.color=damageColor(player.rank);d.append(v,element('span',label));return d;}));
  $('#player-summary').textContent=`#${player.rank} provisional · ${snapshot.rankingScope==='guatemala'?'Solo Guatemala':'Guatemala + internacionales'} · ${snapshot.seasonLabel}. Elegibilidad: ${player.countryBasis}. Historial de eventos admitidos; puede faltar actividad de start.gg.`;
  const mains=mainList(player),coverage=player.mainCoverage;
  $('#player-mains').replaceChildren(...mains.map((m,i)=>{const d=element('div',undefined,'main-usage'),label=element('span',m.name);label.append(element('small',`${i===0?'Principal detectado':'Secundario'} · ${m.games} partidas`));d.append(imageNode(m.name),label);return d;}));
  const near=mains.length>1 && mains[1].games>=mains[0].games*.8;
  $('#player-main-note').textContent=coverage?`${coverage.gamesWithSelections} partidas con personaje registrado en ${coverage.setsWithSelections} de ${coverage.setsQueried} sets consultados. ${mains.length?'El main se estima por uso registrado; la cobertura puede ser parcial.':'Sin datos para detectar un main.'}${near?' Uso repartido: los dos más usados tienen cantidades cercanas (el segundo alcanza al menos el 80% del primero). Podrá revisarse cuando existan cuentas.':''}${coverage.ambiguousGames?` ${coverage.ambiguousGames} partidas con selecciones ambiguas se omitieron.`:''}`:'Todavía no hay datos de personajes para este jugador.';
  if(!mains.length)$('#player-mains').append(element('span','?','unknown-art'));
  const view=activityView(player,snapshot);
  $('#player-recent').replaceChildren(...(view?.ledger||[]).slice(0,5).map(e=>{const url=safeLink(e.url),r=element(url?'a':'div',undefined,'drawer-event'),label=element('span',e.name),record=element('b',`${e.wins}–${e.losses}`);label.append(element('small',`${e.date} · ${e.country}`));record.style.color=e.wins>e.losses?'#5BE38A':e.wins<e.losses?'#FF4D2E':'#F4F1EA';if(url){r.href=url;r.target='_blank';r.rel='noopener noreferrer';}r.append(label,record);return r;}));
  if(!view)$('#player-recent').append(element('p','El detalle por torneo no está disponible en este corte anterior.','drawer-note'));
  $('#player-rivals').replaceChildren(...playerRivals(player,snapshot).map(r=>{const d=element('div',undefined,'drawer-rival'),record=element('b',`${r.wins}–${r.losses}`);record.style.color=r.wins>r.losses?'#5BE38A':r.wins<r.losses?'#FF4D2E':'#F4F1EA';d.append(element('span',r.tag),record);return d;}));
  allPlayerMatches=snapshot.results.filter(m=>m.playerIds.includes(player.id));showPlayerMatches();renderActivity(player);
  const url=safeLink(player.url);$('#player-link').hidden=!url;if(url)$('#player-link').href=url;
  if(!$('#player-dialog').open)$('#player-dialog').showModal();$('#player-dialog').scrollTop=0;
}
function render() {
  const local=snapshot.rankingScope==='guatemala';
  $('#scope-local').disabled=!published.localRanking;$('#scope-combined').disabled=false;
  $('#scope-local').setAttribute('aria-pressed',String(!includeInternational));$('#scope-combined').setAttribute('aria-pressed',String(includeInternational));
  $('#data-status').textContent=`Ranking piloto · ${local?'Solo Guatemala':'Guatemala + internacionales'}`;
  $('#updated').textContent=`Datos: ${dateFormat.format(new Date(snapshot.generatedAt))}`;
  $('#scope-help').textContent=local?'Cálculo independiente con eventos de Guatemala. Cambian puntos, actividad y elegibilidad; las flechas comparan únicamente cortes de esta vista.':'Incluye los eventos admitidos de Guatemala y del extranjero. “Solo Guatemala” recalcula toda la clasificación con eventos locales.';
  $('#list-note').textContent=`${snapshot.scope} Corte ${snapshot.seasonLabel} · ${snapshot.methodVersion}. ${snapshot.previousCutAt?'Movimiento frente al corte del '+dateFormat.format(new Date(snapshot.previousCutAt)):'Sin corte anterior comparable para mostrar movimientos.'}`;
  $('#footer-method').textContent=snapshot.methodVersion;
  document.querySelectorAll('a[href^="./metodologia.html"]').forEach(link=>{const hash=link.hash;link.href='./metodologia.html'+(local?'?scope=guatemala':'')+hash;});
  renderHero();renderChips();renderPlayers();
}
function setScope(international) {
  if(!published || (!international&&!published.localRanking))return;
  includeInternational=international;snapshot=chooseSnapshot(published,international);
  if($('#player-dialog').open)$('#player-dialog').close();render();
}
async function refresh() {
  if(loading)return;loading=true;$('#refresh').disabled=true;
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try {
    const response=await fetch('./data/public.json',{cache:'no-store',signal:controller.signal});
    if(!response.ok)throw new Error('Sin datos');
    const next=validate(await response.json()),chosen=chooseSnapshot(next,includeInternational);
    const changed=snapshot&&(snapshot.generatedAt!==chosen.generatedAt||snapshot.rankingScope!==chosen.rankingScope);
    published=next;snapshot=chosen;if(changed&&$('#player-dialog').open)$('#player-dialog').close();
    render();$('#load-error').hidden=true;
  } catch {
    $('#load-error').textContent=snapshot?'No pudimos actualizar. Conservamos el último corte completo que cargaste.':'No pudimos cargar un corte válido. Intenta actualizar en un momento.';$('#load-error').hidden=false;
  } finally { clearTimeout(timer);loading=false;$('#refresh').disabled=false; }
}
function renderDemo(slug='pikachu',animate=false) {
  const selected=CHARACTER_CATALOG.find(c=>c.slug===slug)||CHARACTER_CATALOG[0];if(!selected)return;
  $('#demo-art').replaceChildren(imageNode(selected.name,'portrait'));$('#demo-icon').replaceChildren(imageNode(selected.name));$('#demo-main-name').textContent=`Main · ${selected.name}`;
  document.querySelectorAll('#demo-roster button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.slug===selected.slug)));
  if(animate){$('#demo-card').classList.remove('is-pop');requestAnimationFrame(()=>requestAnimationFrame(()=>$('#demo-card').classList.add('is-pop')));$('#demo-status').textContent=`Carta de demostración: ${selected.name}. No se guardó tu selección.`;}
}
// Keep browser-only bindings after this boundary so contract tests load pure helpers.
const tabs = [];
$('#search').addEventListener('input',renderPlayers);
$('#view-all').onclick=()=>{rankingView=rankingView==='all'?'top':'all';renderPlayers();};
$('#scope-local').onclick=()=>setScope(false);$('#scope-combined').onclick=()=>setScope(true);
$('#refresh').onclick=refresh;$('#player-close').onclick=()=>$('#player-dialog').close();
$('#player-dialog').addEventListener('click',event=>{const rect=$('#player-dialog').getBoundingClientRect();if(event.target===$('#player-dialog')&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom))$('#player-dialog').close();});
$('#player-all-results').onclick=()=>showPlayerMatches();$('#player-more').onclick=()=>{visibleMatches+=20;renderPlayerMatches();};
$('#ticker-pause').onclick=()=>{const paused=$('#ticker-track').classList.toggle('is-paused');$('#ticker-pause').setAttribute('aria-pressed',String(paused));$('#ticker-pause').setAttribute('aria-label',paused?'Reanudar barra de resultados':'Pausar barra de resultados');$('#ticker-pause').textContent=paused?'▶':'Ⅱ';};
$('#demo-roster').replaceChildren(...CHARACTER_CATALOG.map(c=>{const b=element('button');b.type='button';b.dataset.slug=c.slug;b.title=c.name;b.setAttribute('aria-label',`Probar ${c.name}`);b.setAttribute('aria-pressed','false');b.append(imageNode(c.name));b.onclick=()=>renderDemo(c.slug,true);return b;}));
renderDemo();refresh();setInterval(()=>{if(!document.hidden)refresh();},60000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});

// Header: show who is signed in. The stored tag is only a display hint written by the account
// page; the server confirms it, and visitors who never signed in make no account request.
(() => {
  const link=document.getElementById('account-link');
  if(!link)return;
  const show=tag=>{
    if(typeof tag!=='string'||!tag.trim()){link.textContent='Tu cuenta · Beta';link.removeAttribute('aria-label');return;}
    const name=tag.trim();
    link.textContent=name.length>18?`${name.slice(0,17)}…`:name;link.setAttribute('aria-label',`Tu cuenta: ${name}`);
  };
  let hint=null;
  try{hint=localStorage.getItem('smashgt.cuenta');}catch{}
  if(!hint)return;
  show(hint);
  fetch('./account-api.php',{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}})
    .then(response=>response.ok?response.json():null)
    .then(data=>{
      if(!data||data.ok!==true)return;
      const tag=data.authenticated?data.user.tag:null;
      try{if(tag)localStorage.setItem('smashgt.cuenta',tag);else localStorage.removeItem('smashgt.cuenta');}catch{}
      show(tag);
    }).catch(()=>{});
})();
