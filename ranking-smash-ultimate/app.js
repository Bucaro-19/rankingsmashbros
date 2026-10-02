const $ = (selector) => document.querySelector(selector);
let snapshot = null;
let loading = false;
let rankingView = 'top';
let playerMatches = [];
let visibleMatches = 20;
const dateFormat = new Intl.DateTimeFormat('es-GT', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Guatemala' });

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
function openPlayer(player) {
  const pilot = ['local_pilot', 'international_pilot'].includes(snapshot.status);
  $('#player-title').textContent = player.knownAs ? `${player.tag} (antes ${player.knownAs})` : player.tag;
  const movement = snapshot.previousCutAt && Number.isInteger(player.previousRank)
    ? ` En el corte anterior: #${player.previousRank}.`
    : '';
  const stats = pilot ? [[`#${player.rank}`, 'Puesto provisional'], [String(player.rating), 'Puntos Smash GT'], [String(player.events), 'Torneos válidos']] : [];
  $('#player-stats').replaceChildren(...stats.map(([value, label]) => {
    const item = element('div'); item.append(element('strong', value), element('span', label)); return item;
  }));
  $('#player-stats').hidden = !pilot;
  $('#player-summary').textContent = pilot
    ? `${player.wins} victorias y ${player.losses} derrotas.${movement} Corte: ${snapshot.seasonLabel}. Elegibilidad: ${player.countryBasis}. Este historial corresponde a los eventos incluidos en el ranking; puede no abarcar toda tu actividad en start.gg.`
    : `País del perfil: Guatemala. ${player.sets} sets completados observados. ${player.historyComplete ? 'Historial consultado sin recortes de páginas.' : 'La cobertura del historial todavía es parcial.'} Posición nacional pendiente de cálculo.`;
  playerMatches = snapshot.results.filter((match) => match.playerIds.includes(player.id));
  visibleMatches = 20;
  renderPlayerMatches();
  const link = safeLink(player.url);
  $('#player-link').hidden = !link;
  if (link) $('#player-link').href = link;
  $('#player-dialog').showModal();
}
function renderPlayers() {
  const target = $('#players-list');
  if (!snapshot) return empty(target, 'Estamos preparando la primera lista', 'Conectaremos los perfiles y resultados antes de publicar jugadores y posiciones.');
  const normalize = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');
  const query = normalize($('#search').value.trim());
  const pilot = ['local_pilot', 'international_pilot'].includes(snapshot.status);
  const players = snapshot.players.filter((player) => query
    ? normalize(`${player.tag} ${player.knownAs || ''}`).includes(query)
    : rankingView === 'all' || !pilot || player.rank <= 100);
  $('#scene-title').textContent = query ? 'Encuentra tu puesto.' : rankingView === 'all' ? 'Ranking completo.' : 'Top 100 piloto.';
  $('#ranking-summary').textContent = query ? `${players.length} ${players.length === 1 ? 'coincidencia' : 'coincidencias'} entre ${snapshot.players.length} jugadores disponibles.` : `${players.length} de ${snapshot.players.length} clasificados · ${rankingView === 'top' ? 'vista Top 100' : 'todos los puestos'}.`;
  if (!players.length) return empty(target, query ? 'No encontramos ese alias en este corte' : 'La primera lista está en camino', query ? 'Prueba tu alias de start.gg. Si aún no apareces, puedes no cumplir los 2 torneos y 4 sets válidos, o pueden faltar datos por verificar. Esto no significa que no juegues en Guatemala.' : 'Los jugadores aparecerán después de consultar sus perfiles y validar su actividad.');
  target.replaceChildren(...players.map((player) => {
    const row = element('button', undefined, 'player-row');
    const pilot = ['local_pilot', 'international_pilot'].includes(snapshot.status);
    if (pilot && player.rank <= 3) row.classList.add('podium-row', `podium-${player.rank}`);
    row.type = 'button';
    row.setAttribute('aria-label', `Ver detalle de ${player.tag}${player.knownAs ? `, antes ${player.knownAs}` : ''}`);
    const avatar = element('span', pilot ? String(player.rank).padStart(2, '0') : player.tag.slice(0, 2).toUpperCase(), 'avatar');
    avatar.setAttribute('aria-hidden', 'true');
    const label = element('span');
    label.append(element('strong', player.tag));
    if (player.knownAs) label.append(element('small', `Antes: ${player.knownAs}`));
    label.append(element('small', pilot ? `${player.events} torneos · ${player.wins} V / ${player.losses} D` : 'Guatemala · país del perfil'));
    if (pilot && snapshot.previousCutAt) {
      const delta = Number.isInteger(player.previousRank) ? player.previousRank - player.rank : null;
      const movement = delta === null ? 'Sin puesto previo publicado' : delta > 0 ? `↑ ${delta} puestos` : delta < 0 ? `↓ ${Math.abs(delta)} puestos` : 'Sin cambio de puesto';
      label.append(element('small', movement, `movement ${delta > 0 ? 'up' : delta < 0 ? 'down' : 'same'}`));
    }
    const end = element('span', pilot ? `${player.rating} pts` : `${player.sets} sets observados`, 'row-end');
    end.append(element('small', pilot ? 'Clasificación provisional ↗' : 'Sin posición asignada ↗'));
    row.append(avatar, label, end);
    row.addEventListener('click', () => {
      try { openPlayer(player); }
      catch (error) {
        $('#load-error').textContent = 'No pudimos abrir el detalle del jugador. Vuelve a intentarlo.';
        $('#load-error').hidden = false;
      }
    });
    return row;
  }));
}
function renderResults() {
  const target = $('#results-list');
  const region = $('#region').value;
  const results = (snapshot?.results || []).filter((match) => region === 'all' || (region === 'GT' ? match.country === 'GT' : match.country && match.country !== 'GT'));
  if (!results.length) return empty(target, region === 'international' && snapshot?.status === 'local_pilot' ? 'El extranjero sigue en revisión' : 'Todavía no hay resultados para mostrar', region === 'international' && snapshot?.status === 'local_pilot' ? 'La primera clasificación usa torneos presenciales de Guatemala. Agregaremos partidas fuera del país al completar su verificación.' : 'Aquí podrás seguir las partidas de la comunidad, dentro y fuera de Guatemala.');
  target.replaceChildren(...results.slice(0, 100).map(resultNode));
  if (results.length > 100) target.append(element('p', 'Se muestran los 100 resultados más recientes de este filtro.', 'list-note'));
}
function validate(data) {
  const pilot = data.schemaVersion === 2 && ['local_pilot', 'international_pilot'].includes(data.status) && data.rankingComputed === true;
  const coverage = data.schemaVersion === 1 && ['awaiting_data', 'coverage_only'].includes(data.status) && data.rankingComputed === false;
  if ((!pilot && !coverage) || !Array.isArray(data.players) || !Array.isArray(data.results)) throw new Error('Formato inválido');
  for (const player of data.players) {
    if (typeof player.id !== 'string' || typeof player.tag !== 'string' || !Number.isInteger(player.sets) || player.sets < 0) throw new Error('Jugador inválido');
    if (player.knownAs != null && typeof player.knownAs !== 'string') throw new Error('Alias inválido');
    if (pilot && (!Number.isInteger(player.rank) || player.rank < 1 || !Number.isInteger(player.rating) || !Number.isInteger(player.wins) || !Number.isInteger(player.losses) || !Number.isInteger(player.events) || typeof player.countryBasis !== 'string')) throw new Error('Clasificación inválida');
    if (player.previousRank != null && (!Number.isInteger(player.previousRank) || player.previousRank < 1)) throw new Error('Posición anterior inválida');
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
  return data;
}
function render() {
  const pilot = ['local_pilot', 'international_pilot'].includes(snapshot.status);
  const international = snapshot.status === 'international_pilot';
  const ready = snapshot.status === 'coverage_only' || pilot;
  $('#data-status').textContent = international ? 'Ranking piloto · Guatemala y el extranjero' : pilot ? 'Ranking piloto · solo torneos en Guatemala' : ready ? 'Datos preliminares · ranking pendiente' : 'Preparando la primera temporada';
  $('#updated').textContent = ready ? `Última consulta: ${dateFormat.format(new Date(snapshot.generatedAt))}` : 'Sin sincronización todavía';
  $('#season-label').textContent = ready ? snapshot.seasonLabel : 'Temporada por confirmar';
  for (const name of ['players', 'events', 'sets', 'countries']) $(`#${name}-count`).textContent = ready ? snapshot.counts[name].toLocaleString('es-GT') : '—';
  $('#tab-count').textContent = ready ? snapshot.players.length : '—';
  $('#search-help').textContent = snapshot.rankingCoverage === 'all_eligible'
    ? 'La búsqueda incluye todos los clasificados, también fuera del top 100. Mínimo: 2 torneos y 4 sets válidos, además de los requisitos de pertenencia al ranking.'
    : 'La búsqueda incluye todos los puestos publicados en este corte. La ampliación del listado se mostrará al completar una nueva actualización.';
  $('#list-note').textContent = international ? 'Corte semanal experimental con torneos presenciales de Guatemala y del extranjero de jugadores descubiertos localmente. Las flechas comparan cortes con las mismas reglas; la elegibilidad sigue en revisión. No es UltRank ni el ranking oficial.' : pilot ? 'Clasificación experimental con torneos presenciales de Guatemala. Los resultados del extranjero y la elegibilidad de jugadores siguen pendientes; no es UltRank ni el ranking oficial.' : ready ? 'Lista alfabética de perfiles detectados. Cobertura experimental; todavía no representa el ranking nacional completo.' : 'Las posiciones se publicarán cuando validemos el cálculo.';
  $('#hero-note').textContent = international ? `Temporada ${snapshot.seasonYear || 2026} · actualización prevista los domingos a las 00:00, hora de Guatemala, para todos los clasificados.` : 'Primer corte local. Resultados internacionales en revisión.';
  $('#aside-scope').textContent = international ? 'Este top es una prueba abierta: incluye torneos internacionales de jugadores encontrados en la escena local. El orden cambiará al revisar la elegibilidad y los eventos.' : 'Este top es una prueba abierta: el orden cambiará cuando completemos los torneos internacionales y revisemos quiénes representan a Guatemala.';
  $('#aside-phase1').replaceChildren(element('span', '01'), document.createTextNode(international ? ' Identificar jugadores que compiten solo fuera' : ' Agregar resultados del extranjero'));
  const localMinimum = snapshot.eligibilityRules?.localMinimumActive ?? 32;
  $('#method-scope').textContent = `En Guatemala cuentan los torneos individuales presenciales con al menos ${localMinimum} participantes activos: cada uno debe haber jugado un set válido. Para clasificar se mantienen 2 torneos y 4 sets.` + (international ? ' En el extranjero se mantienen 64 activos; faltan jugadores que compiten solo fuera del país.' : ' Los torneos del extranjero aún no cuentan.');
  if (snapshot.methodVersion === 'BT-PILOTO-3' && !snapshot.previousCutAt) {
    $('#list-note').textContent += ' Nuevo criterio: 20 activos por torneo de Guatemala. Este primer corte no muestra movimientos frente a la regla anterior de 32.';
  }
  $('#results-note').textContent = international ? 'Partidas consideradas en esta versión dentro y fuera de Guatemala; la selección de eventos sigue en revisión.' : 'Partidas consideradas en esta versión local; los resultados de fuera de Guatemala aún se están recopilando.';
  renderPlayers(); renderResults();
}
async function refresh() {
  if (loading) return;
  loading = true;
  $('#refresh').disabled = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch('./data/public.json', { cache: 'no-store', signal: controller.signal });
    if (!response.ok) throw new Error('No disponible');
    const next = validate(await response.json());
    snapshot = next;
    render();
    $('#load-error').hidden = true;
  } catch {
    $('#load-error').textContent = snapshot ? 'No pudimos actualizar los datos. Se mantiene la última consulta disponible. Puedes volver a intentarlo.' : 'No pudimos cargar los datos. Comprueba tu conexión y pulsa Actualizar.';
    $('#load-error').hidden = false;
  } finally { clearTimeout(timeout); loading = false; $('#refresh').disabled = false; }
}
const tabs = [$('#tab-players'), $('#tab-results')];
function selectTab(selected) {
  for (const tab of tabs) {
    const active = selected === tab;
    tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
    document.getElementById(tab.getAttribute('aria-controls')).hidden = !active;
  }
}
for (const tab of tabs) {
  tab.addEventListener('click', () => selectTab(tab));
  tab.addEventListener('keydown', (event) => {
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[1] : tabs[1 - tabs.indexOf(tab)];
      selectTab(next); next.focus();
    }
  });
}
$('#search').addEventListener('input', renderPlayers);
for (const [id, view] of [['view-top', 'top'], ['view-all', 'all']]) {
  $(`#${id}`).addEventListener('click', () => {
    rankingView = view;
    $('#search').value = '';
    $('#view-top').setAttribute('aria-pressed', String(view === 'top'));
    $('#view-all').setAttribute('aria-pressed', String(view === 'all'));
    renderPlayers();
  });
}
$('.find-rank-link').addEventListener('click', () => { selectTab($('#tab-players')); $('#search').focus(); });
$('#player-more').addEventListener('click', () => { visibleMatches += 20; renderPlayerMatches(); });
$('#region').addEventListener('change', renderResults);
$('#refresh').addEventListener('click', refresh);
$('#player-dialog .close').addEventListener('click', () => $('#player-dialog').close());
renderPlayers(); renderResults(); refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 60000);
