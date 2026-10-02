const $ = id => document.getElementById(id);
const node = (tag, content, className) => {
  const element = document.createElement(tag);
  if (content !== undefined) element.textContent = String(content);
  if (className) element.className = className;
  return element;
};
const dateTime = value => new Intl.DateTimeFormat('es-GT', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Guatemala' }).format(new Date(value));

function renderScenarios(data) {
  const items = [
    ['baseline', 'Base histórica: 32 activos', data.baseline],
    ['pointsException', 'Excepción 200 puntos', data.scenarios.pointsException],
    ['min24', 'Mínimo de 24 activos', data.scenarios.min24],
    ['min16', 'Mínimo de 16 activos', data.scenarios.min16]
  ];
  const cards = $('scenario-cards');
  const tops = $('scenario-tops');
  for (const [key, label, result] of items) {
    const card = node('article', undefined, 'analysis-scenario');
    card.dataset.kind = key;
    card.append(node('h3', label), node('strong', result.events), node('span', 'torneos admitidos'));
    const detail = node('p');
    const extra = key === 'baseline' ? 'Punto de comparación histórico. El ranking público ahora usa 20 activos en Guatemala.'
      : `${result.addedEvents} eventos más · ${result.commonPlayersMoved} jugadores que siguen en el top 100 cambian de puesto · mayor cambio: ${result.largestMove} puestos.`;
    detail.textContent = `${result.sets} sets válidos. ${extra}`;
    card.append(detail);
    cards.append(card);

    const block = node('div');
    block.append(node('h3', label));
    const list = node('ol');
    for (const player of result.top10) {
      const row = node('li');
      row.append(node('strong', player.tag), node('small', `${player.rating} puntos${player.oldRank && player.oldRank !== player.rank ? ` · antes #${player.oldRank}` : ''}`));
      list.append(row);
    }
    block.append(list);
    tops.append(block);
  }
}

function eventTable(rows) {
  if (!rows.length) return node('p', 'No se encontraron eventos de esta serie en la captura.', 'analysis-empty');
  const table = node('table', undefined, 'analysis-table');
  const head = node('thead');
  const headerRow = node('tr');
  for (const title of ['Fecha', 'Torneo', 'Inscritos', 'Activos', 'Puntos estimados', 'Valorados', 'Excepción numérica']) headerRow.append(node('th', title));
  head.append(headerRow);
  const body = node('tbody');
  for (const event of rows) {
    const row = node('tr');
    row.append(node('td', event.date));
    const name = node('td');
    if (typeof event.url === 'string' && /^https:\/\/www\.start\.gg\/tournament\/[\w-]+\/event\/[\w-]+$/.test(event.url)) {
      const link = node('a', event.name);
      link.href = event.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      name.append(link);
    } else name.append(node('span', event.name));
    name.append(node('small', event.eventName));
    if (event.exclusionReason) name.append(node('small', event.exclusionReason));
    row.append(name, node('td', event.entrants), node('td', event.activePlayers),
      node('td', event.estimatedPoints ?? '—'), node('td', event.valuedPlayers),
      node('td', event.exclusionReason ? 'Fuera por formato' : event.qualifiesByException ? 'Sí; pendiente de revisión' : 'No', event.qualifiesByException ? 'passes' : 'fails'));
    body.append(row);
  }
  table.append(head, body);
  return table;
}

async function loadStudy() {
  try {
    const response = await fetch('./data/analisis-torneos.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('No se pudo descargar el estudio.');
    const data = await response.json();
    if (data.schemaVersion !== 1 || data.status !== 'simulacion_sin_cambio_de_regla' || !Array.isArray(data.smallEvents)) throw new Error('Los datos del estudio no son válidos.');
    $('analysis-cut').textContent = `Captura local: ${dateTime(data.snapshotAt)}`;
    $('analysis-foreign').textContent = `Resultados extranjeros fijos: ${dateTime(data.foreignResultsAsOf)}`;
    $('analysis-base').textContent = data.baselineVerifiedAsOf ? `Base verificada con el top: ${dateTime(data.baselineVerifiedAsOf)}` : 'Base de comparación sin verificar';
    $('small-count').textContent = `(${data.smallEvents.length})`;
    renderScenarios(data);
    const oven = data.smallEvents.filter(event => /the oven|mazza/i.test(event.name));
    const ovenPassing = oven.filter(event => event.qualifiesByException).length;
    $('oven-status').textContent = `${oven.length} eventos de la serie en el corte; ${ovenPassing} cumplen la excepción estimada. Los formatos especiales se muestran para transparencia, pero no se simulan como singles estándar.`;
    $('oven-events').append(eventTable(oven));
    $('all-small-events').append(eventTable(data.smallEvents));
    const passing = data.smallEvents.filter(event => event.qualifiesByException).length;
    $('analysis-status').textContent = `${data.smallEvents.length} eventos pequeños evaluados; ${passing} cumplen la excepción estimada de 200 puntos y dos jugadores valorados.`;
  } catch (error) {
    $('analysis-status').textContent = 'No se pudo cargar el estudio. Intenta actualizar la página más tarde.';
  }
}

loadStudy();
