const el = id => document.getElementById(id);
const node = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = String(text); return n; };
let study;
function stat(value, label) { const n = node('article'); n.append(node('b', value), node('span', label)); return n; }
function row(values) { const n = node('tr'); for (const v of values) { const cell = node('td'); cell.append(typeof v === 'object' ? v : document.createTextNode(String(v))); n.append(cell); } return n; }
function link(name, url) { const safe = /^https:\/\/www\.start\.gg\/tournament\/[\w-]+\/event\/[\w-]+$/.test(url || ''); const n = node(safe ? 'a' : 'span', name); if (safe) { n.href = url; n.target = '_blank'; n.rel = 'noopener noreferrer'; } return n; }
function table(headers, rows) { const wrap = node('div'); wrap.className = 'study-table-wrap'; const t = node('table'); t.className = 'study-table'; const h = node('thead'); const hr = node('tr'); headers.forEach(text => { const th = node('th', text); th.scope = 'col'; hr.append(th); }); h.append(hr); const b = node('tbody'); rows.forEach(r => b.append(row(r))); t.append(h,b); wrap.append(t); return wrap; }
function details(title, content) { const d = node('details'); d.append(node('summary', title), content); return d; }
function renderPlayer() {
  const p = study.profiles.find(p => p.id === el('study-player').value);
  const area = node('article'); area.className = 'study-profile'; area.append(node('h3', `#${p.rank} · ${p.tag}`));
  const stats = node('div'); stats.className = 'study-stats'; stats.append(stat(p.rating,'Puntos actuales'),stat(p.events,'Torneos válidos'),stat(p.months.length,'Meses activos'),stat(`${p.wins}–${p.losses}`,'Victorias–derrotas')); area.append(stats);
  area.append(node('p', `${p.uniqueOpponents} rivales distintos. Contra el top 20 de este corte: ${p.top20Wins} victorias y ${p.top20Losses} derrotas. En el extranjero: ${p.foreignEvents} torneos, ${p.foreignWins} victorias y ${p.foreignLosses} derrotas.`));
  area.append(node('p', `Meses con actividad: ${p.months.join(', ')}. El evento con más sets concentra ${Math.round(p.largestEventShare * 100)}% de su historial válido. Tener más sets o meses no garantiza un puesto superior.`));
  const s = p.sensitivity;
  area.append(node('p', `Al quitar uno de los ${study.sensitivityEventCount} torneos del corte y recalcular todo, sus posiciones van de ${s.bestRank === null ? 'sin puesto' : '#'+s.bestRank} a ${s.worstRank === null ? 'sin puesto' : '#'+s.worstRank}. Deja de cumplir el mínimo de actividad en ${s.unrankedScenarios} escenarios. Este rango es sensibilidad, no incertidumbre estadística.`));
  const extreme = [...s.scenarios].sort((a,b)=>(b.rank === null ? 10000 : Math.abs(b.rank-p.rank))-(a.rank === null ? 10000 : Math.abs(a.rank-p.rank))).slice(0,5);
  area.append(details('Escenarios con mayor cambio de puesto',table(['Torneo retirado','Puesto recalculado'],extreme.map(x=>[x.event,x.rank === null ? 'Sin actividad suficiente' : '#'+x.rank]))));
  area.append(details('Torneos y resultados usados',table(['Fecha / país','Torneo','V–D'],p.eventLedger.map(e=>[`${e.date} · ${e.country}`,link(e.name,e.url),`${e.wins}–${e.losses}`]))));
  const explanation = node('div'); explanation.append(node('p','Los rivales sin puesto pueden ser extranjeros o no cumplir la elegibilidad; no significa que sean débiles. Los puestos mostrados son del corte completo.'));
  explanation.append(table(['Rival','Puesto en Guatemala','V–D del jugador elegido'],p.opponents.map(o=>[o.tag,o.rank === null ? 'Sin puesto en este corte' : '#'+o.rank,`${o.wins}–${o.losses}`]))); area.append(details('Rivales, incluidos los enfrentamientos directos',explanation));
  el('player-detail').replaceChildren(area);
}
function renderScenario() {
  const key = el('study-scenario').value, s = study.scenarios[key];
  const text = {none:'Referencia: puntos actuales, sin premio extra por asistencia.',events:'Prueba: 0 puntos con 2 torneos; 5 con 3; 10 con 4; hasta 30 con 8 o más. El bono también se obtiene aunque esos torneos adicionales solo aporten derrotas.',months:'Prueba: 0 puntos con 1 o 2 meses activos; 10 con 3; 20 con 4; 30 con 5 o más. Se cuentan meses calendario de Guatemala con al menos un set válido.'};
  el('scenario-explanation').textContent=text[key]; el('scenario-summary').replaceChildren(stat(s.movedPlayers,'Jugadores que cambian de puesto'),stat(s.maxMove,'Mayor movimiento en puestos'),stat(s.newTop100.length,'Entradas nuevas al top 100'),stat(s.newTop20.length,'Entradas nuevas al top 20'));
  el('scenario-entry').textContent = `Nuevos en el top 100: ${s.newTop100.join(', ') || 'ninguno'}. Nuevos en el top 20: ${s.newTop20.join(', ') || 'ninguno'}.`;
  el('scenario-rows').replaceChildren(...s.players.filter(p=>p.rank<=20||p.baseRank<=20).map(p=>row([p.tag,'#'+p.baseRank,'#'+p.rank,p.basePoints,'+'+p.bonus,p.points])));
}
async function load() {
  try {
    const response = await fetch('./data/analisis-top20.json',{cache:'no-store'}); if (!response.ok) throw new Error('No disponible'); study=await response.json();
    if (study.schemaVersion!==1||study.status!=='study_not_adopted'||study.profiles.length!==20) throw new Error('Estudio inválido');
    el('study-cut').textContent = 'Corte: '+new Intl.DateTimeFormat('es-GT',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Guatemala'}).format(new Date(study.cut)); el('study-method').textContent=study.methodVersion;
    el('study-status').textContent=`Base verificada: ${study.counts.players} clasificados, ${study.counts.events} eventos y ${study.counts.sets.toLocaleString('es-GT')} sets. ${study.sensitivityEventCount} recálculos retirando un torneo a la vez.`;
    el('study-player').replaceChildren(...study.profiles.map(p=>{const o=node('option',`#${p.rank} ${p.tag}`);o.value=p.id;return o;}));
    el('top20-rows').replaceChildren(...study.profiles.map(p=>row([`#${p.rank} ${p.tag}`,p.rating,`${p.events} / ${p.months.length}`,`${p.wins}–${p.losses}`,`${p.top20Wins}–${p.top20Losses}`,`#${p.sensitivity.bestRank} a #${p.sensitivity.worstRank}${p.sensitivity.unrankedScenarios ? `; sin puesto en ${p.sensitivity.unrankedScenarios}`:''}`])));
    const lead = study.profiles[0], second = study.profiles[1];
    const direct = second.opponents.find(o=>o.id===lead.id);
    const local = study.coverageSensitivity.localOnlyTop20;
    const cards = [];
    function finding(title,text) { const a=node('article');a.append(node('h3',title),node('p',text));cards.push(a); }
    finding('El #1 y el #2', `${second.tag} tiene ${direct?.wins ?? 0}–${direct?.losses ?? 0} contra ${lead.tag} en este corte, pero figura segundo. Al retirar juntos los ${study.coverageSensitivity.removedEvents} torneos extranjeros, ${second.tag} pasa al #${local.find(p=>p.id===second.id)?.localOnlyRank} y ${lead.tag} al #${local.find(p=>p.id===lead.id)?.localOnlyRank}. Ninguno de los recálculos que quita solo un evento invierte el primer y segundo puesto.`);
    const vulnerable=[...study.profiles].sort((a,b)=>(b.sensitivity.worstRank-b.sensitivity.bestRank)-(a.sensitivity.worstRank-a.sensitivity.bestRank))[0];
    finding('Sensibilidad con pocos eventos', `${vulnerable.tag} es #${vulnerable.rank} con ${vulnerable.events} torneos. Al retirar un evento a la vez queda entre #${vulnerable.sensitivity.bestRank} y #${vulnerable.sensitivity.worstRank}. El historial aún puede sostener órdenes bastante distintos.`);
    const minimum=study.profiles.filter(p=>p.sensitivity.unrankedScenarios>0);
    finding('Clasificar con el mínimo', minimum.length ? minimum.map(p=>`${p.tag}: ${p.events} torneos; pierde elegibilidad en ${p.sensitivity.unrankedScenarios} escenarios`).join('. ')+'. Es una señal de muestra limitada, no una sanción al jugador.' : 'Ningún jugador del top 20 pierde elegibilidad en estos escenarios.');
    finding('Cobertura y cálculo', `${study.coverageSensitivity.qualifiedPlayersWithForeignSets} de ${study.counts.players} clasificados tienen sets en los torneos extranjeros incluidos. El cálculo base ${study.solverCheck.converged ? 'alcanzó su tolerancia numérica' : 'no alcanzó su tolerancia numérica'} en ${study.solverCheck.iterations} iteraciones. Esto no certifica la calidad del orden.`);
    el('study-findings').replaceChildren(...cards);
    el('study-player').disabled=false;el('study-scenario').disabled=false;
    renderPlayer();renderScenario();
    try { const currentResponse = await fetch('./data/public.json',{cache:'no-store'}); if (!currentResponse.ok) throw new Error(); const current = await currentResponse.json(); if (current.generatedAt!==study.cut) { el('study-status').textContent+=' El ranking ya tiene otro corte: esta página conserva el estudio fechado y no representa sus puestos actuales.'; el('study-status').classList.add('study-warning'); } } catch { el('study-status').textContent+=' No pudimos comprobar si existe un corte más reciente.'; }
  } catch { el('study-status').textContent='No pudimos cargar el estudio. Actualiza la página para intentarlo de nuevo.'; }
}
el('study-player').addEventListener('change',renderPlayer);el('study-scenario').addEventListener('change',renderScenario);load();
