const $ = (selector) => document.querySelector(selector);
let snapshot = null;
let loading = false;
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
function openPlayer(player) {
  const pilot = ['local_pilot', 'international_pilot'].includes(snapshot.status);
  $('#player-title').textContent = player.knownAs ? `${player.tag} (antes ${player.knownAs})` : player.tag;
  $('#player-summary').textContent = pilot
    ? `#${player.rank} provisional · ${player.rating} puntos Smash GT. ${player.wins} victorias y ${player.losses} derrotas en ${player.events} torneos considerados. Elegibilidad: ${player.countryBasis}. ${snapshot.scope}`
    : `País del perfil: Guatemala. ${player.sets} sets completados observados. ${player.historyComplete ? 'Historial consultado sin recortes de páginas.' : 'La cobertura del historial todavía es parcial.'} Posición nacional pendiente de cálculo.`;
  const recent = snapshot.results.filter((match) => match.playerIds.includes(player.id));
  $('#player-matches').replaceChildren(...recent.slice(0, 8).map(resultNode));
  if (!recent.length) empty($('#player-matches'), 'Todavía sin resultados', 'No encontramos sets presenciales completados en los datos consultados para esta ventana.');
  const link = safeLink(player.url);
  $('#player-link').hidden = !link;
  if (link) $('#player-link').href = link;
  $('#player-dialog').showModal();
}
function renderPlayers() {
  const target = $('#players-list');
  if (!snapshot) return empty(target, 'Estamos preparando la primera lista', 'Conectaremos los perfiles y resultados antes de publicar jugadores y posiciones.');
  const query = $('#search').value.trim().toLocaleLowerCase('es');
  const players = snapshot.players.filter((player) => `${player.tag} ${player.knownAs || ''}`.toLocaleLowerCase('es').includes(query));
  if (!players.length) return empty(target, query ? 'No encontramos ese nombre' : 'La primera lista está en camino', query ? 'Prueba otro nombre o borra la búsqueda. La cobertura de jugadores aún está en construcción.' : 'Los jugadores aparecerán después de consultar sus perfiles y detectar Guatemala como país.');
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
    if (coverage && typeof player.historyComplete !== 'boolean') throw new Error('Cobertura inválida');
  }
  for (const match of data.results) {
    if (!Array.isArray(match.playerIds) || typeof match.tournament !== 'string' || typeof match.date !== 'string' || (match.score !== null && typeof match.score !== 'string') || (match.country !== null && typeof match.country !== 'string')) throw new Error('Resultado inválido');
  }
  for (const name of ['players', 'events', 'sets', 'countries']) {
    if ((data.status === 'coverage_only' || pilot) && (!Number.isInteger(data.counts?.[name]) || data.counts[name] < 0)) throw new Error('Conteo inválido');
  }
  if ((data.status === 'coverage_only' || pilot) && !Number.isFinite(Date.parse(data.generatedAt))) throw new Error('Fecha inválida');
  if (pilot && (data.players.length > 100 || data.players.some((player, index) => player.rank !== index + 1) || typeof data.scope !== 'string')) throw new Error('Ranking inválido');
  return data;
}
function render() {
  const pilot = ['local_pilot', 'international_pilot'].includes(snapshot.status);
  const international = snapshot.status === 'international_pilot';
  const ready = snapshot.status === 'coverage_only' || pilot;
  $('#data-status').textContent = international ? 'Top 100 piloto · Guatemala y el extranjero' : pilot ? 'Top 100 piloto · solo torneos en Guatemala' : ready ? 'Datos preliminares · ranking pendiente' : 'Preparando la primera temporada';
  $('#updated').textContent = ready ? `Última consulta: ${dateFormat.format(new Date(snapshot.generatedAt))}` : 'Sin sincronización todavía';
  $('#season-label').textContent = ready ? snapshot.seasonLabel : 'Temporada por confirmar';
  for (const name of ['players', 'events', 'sets', 'countries']) $(`#${name}-count`).textContent = ready ? snapshot.counts[name].toLocaleString('es-GT') : '—';
  $('#tab-count').textContent = ready ? snapshot.players.length : '—';
  $('#list-note').textContent = international ? 'Clasificación experimental con torneos presenciales de Guatemala y del extranjero de jugadores descubiertos localmente. La elegibilidad de jugadores y eventos sigue en revisión; no es UltRank ni el ranking oficial.' : pilot ? 'Clasificación experimental con torneos presenciales de Guatemala. Los resultados del extranjero y la elegibilidad de jugadores siguen pendientes; no es UltRank ni el ranking oficial.' : ready ? 'Lista alfabética de perfiles detectados. Cobertura experimental; todavía no representa el ranking nacional completo.' : 'Las posiciones se publicarán cuando validemos el cálculo.';
  $('#hero-note').textContent = international ? 'Torneos en Guatemala y en el extranjero. Piloto en revisión.' : 'Primer corte local. Resultados internacionales en revisión.';
  $('#aside-scope').textContent = international ? 'Este top es una prueba abierta: incluye torneos internacionales de jugadores encontrados en la escena local. El orden cambiará al revisar la elegibilidad y los eventos.' : 'Este top es una prueba abierta: el orden cambiará cuando completemos los torneos internacionales y revisemos quiénes representan a Guatemala.';
  $('#aside-phase1').replaceChildren(element('span', '01'), document.createTextNode(international ? ' Identificar jugadores que compiten solo fuera' : ' Agregar resultados del extranjero'));
  $('#method-scope').textContent = international ? 'Esta versión toma eventos presenciales individuales de Guatemala y de otros países donde participaron jugadores descubiertos localmente. Exige dos eventos y cuatro sets por clasificado; faltan los jugadores que compiten solo fuera del país.' : 'Esta versión toma eventos presenciales individuales de Guatemala con al menos 32 jugadores activos y exige dos eventos y cuatro sets por clasificado. Los torneos del extranjero aún no cuentan.';
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
$('#region').addEventListener('change', renderResults);
$('#refresh').addEventListener('click', refresh);
$('#player-dialog .close').addEventListener('click', () => $('#player-dialog').close());
renderPlayers(); renderResults(); refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 60000);
