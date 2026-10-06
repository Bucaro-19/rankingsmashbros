const byId = (id) => document.getElementById(id);
const updatedFormat = new Intl.DateTimeFormat('es-GT', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Guatemala' });
const eventFormat = new Intl.DateTimeFormat('es-GT', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

function startLink(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && ['start.gg', 'www.start.gg'].includes(url.hostname) ? url.href : null;
  } catch { return null; }
}

function node(tag, value) {
  const item = document.createElement(tag);
  item.textContent = value;
  return item;
}

function linkedName(name, url) {
  const safe = startLink(url);
  if (!safe) return node('strong', name);
  const link = node('a', name);
  link.href = safe;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}

function renderEvent(event) {
  const row = document.createElement('tr');
  const date = node('td', eventFormat.format(new Date(`${event.date}T12:00:00Z`)));
  const name = document.createElement('td');
  name.append(linkedName(event.name, event.url));
  const context = event.country === 'GT'
    ? `${event.eventName} · ${event.entrants} inscritos · TTS estimado: ${event.ttsPointsEstimate ?? 'sin dato'}`
    : `${event.eventName} · ${event.entrants} inscritos · peso basado en jugadores activos`;
  name.append(node('small', context));
  row.append(date, name, node('td', event.country || '—'), node('td', String(event.activePlayers)), node('td', String(event.validSets)));
  return row;
}

function render(data) {
  if (![2, 3].includes(data.schemaVersion) || !data.rankingComputed || !Array.isArray(data.events) || !Array.isArray(data.excludedEvents)) {
    throw new Error('La captura no tiene el catálogo de torneos');
  }
  if (data.events.length !== data.counts?.events || data.events.some((event) =>
    !event || typeof event.name !== 'string' || typeof event.eventName !== 'string' ||
    !Number.isInteger(event.activePlayers) || !Number.isInteger(event.validSets) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(event.date))) {
    throw new Error('Catálogo de torneos inválido');
  }
  byId('method-season').textContent = data.seasonLabel;
  byId('method-updated').textContent = `Datos: ${updatedFormat.format(new Date(data.generatedAt))}`;
  byId('method-version').textContent = data.methodVersion || 'Método piloto';
  byId('method-exact').textContent = data.method || 'La fórmula de este corte no está disponible.';
  byId('event-status').textContent = `${data.events.length} torneos considerados · ${data.counts.sets.toLocaleString('es-GT')} sets competitivos.`;
  byId('event-rows').replaceChildren(...data.events.map(renderEvent));
  const excluded = data.excludedEvents.map((event) => {
    const item = document.createElement('li');
    item.append(linkedName(event.name, event.url), document.createTextNode(`: ${event.reason}`));
    return item;
  });
  byId('excluded-events').replaceChildren(...excluded);
  byId('excluded-count').textContent = `(${excluded.length})`;
}

async function refresh() {
  try {
    const response = await fetch('./data/public.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Datos no disponibles');
    const bundle = await response.json();
    const local = new URLSearchParams(window.location.search).get('scope') === 'guatemala';
    if (local && !bundle.localRanking) throw new Error('La vista local no está disponible');
    render(local ? bundle.localRanking : bundle);
    byId('method-view').textContent = local ? 'Vista: solo Guatemala. La tabla y los conteos corresponden al cálculo local independiente.' : 'Vista: Guatemala + internacionales. La tabla y los conteos corresponden al cálculo combinado.';
  } catch {
    byId('event-status').textContent = 'No pudimos cargar el catálogo. Vuelve a intentarlo más tarde.';
  }
}

refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 60000);
