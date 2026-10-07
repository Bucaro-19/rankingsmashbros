/* Método: fills the page from the published cut. Content and rules stay in the HTML. */
(() => {
  const byId=id=>document.getElementById(id);
  const updatedFormat=new Intl.DateTimeFormat('es-GT',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Guatemala'});
  const dayFormat=new Intl.DateTimeFormat('es-GT',{day:'numeric',month:'short',timeZone:'UTC'});
  const monthFormat=new Intl.DateTimeFormat('es-GT',{month:'long',year:'numeric',timeZone:'UTC'});
  const normalize=value=>String(value||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
  const local=new URLSearchParams(location.search).get('scope')==='guatemala';
  const FIRST=12;
  let events=[], localIds=new Set(), showAll=false;
  document.documentElement.classList.remove('no-js');

  function startLink(value) {
    try { const url=new URL(value); return url.protocol==='https:'&&['start.gg','www.start.gg'].includes(url.hostname)?url.href:null; } catch { return null; }
  }
  function node(tag,value,className) { const item=document.createElement(tag); item.textContent=value; if(className)item.className=className; return item; }
  function linkedName(name,url) {
    const safe=startLink(url);
    if(!safe)return node('strong',name);
    const link=node('a',`${name} ↗`); link.href=safe; link.target='_blank'; link.rel='noopener noreferrer'; return link;
  }
  function validCatalog(data) {
    return [2,3].includes(data.schemaVersion)&&data.rankingComputed&&Array.isArray(data.events)&&Array.isArray(data.excludedEvents)
      &&data.events.length===data.counts?.events&&data.events.every(event=>event&&typeof event.name==='string'&&typeof event.eventName==='string'
        &&Number.isInteger(event.activePlayers)&&Number.isInteger(event.validSets)&&/^\d{4}-\d{2}-\d{2}$/.test(event.date));
  }
  function renderRow(event) {
    const counts=localIds.has(String(event.id)), outside=local&&!counts;
    const row=node('article','',`event-row${outside?' outside':''}`), main=document.createElement('div'), numbers=node('div','','event-numbers'), badges=node('div','','event-badges');
    const context=event.country==='GT'?`${event.eventName} · ${event.entrants} inscritos · TTS estimado: ${event.ttsPointsEstimate??'sin dato'}`:`${event.eventName} · ${event.entrants} inscritos · peso basado en jugadores activos`;
    main.append(linkedName(event.name,event.url),node('small',`${dayFormat.format(new Date(`${event.date}T12:00:00Z`))}${event.country?` · ${event.country}`:''}`),node('small',context));
    for(const [value,label] of [[event.activePlayers,'activos'],[event.validSets,'sets']]){const cell=document.createElement('span');cell.append(node('b',String(value)),document.createTextNode(label));numbers.append(cell);}
    badges.append(node('span',counts?'✓ Solo Guatemala':'— No cuenta en Solo Guatemala',counts?'':'off'),node('span','✓ + Internacional'));
    row.append(main,numbers,badges);return row;
  }
  function renderList() {
    const list=byId('event-list'), query=normalize(byId('event-search').value.trim());
    const matching=events.filter(event=>!query||normalize(`${event.name} ${event.eventName}`).includes(query));
    const shown=query||showAll?matching:matching.slice(0,FIRST), fragment=document.createDocumentFragment();
    let month='';
    for(const event of shown){
      const label=monthFormat.format(new Date(`${event.date}T12:00:00Z`));
      if(label!==month){month=label;fragment.append(node('h3',label,'event-month'));}
      fragment.append(renderRow(event));
    }
    if(!events.length)fragment.append(node('p','Este corte todavía no tiene torneos considerados. Aparecerán aquí cuando se publique el primero.','event-empty'));
    else if(!matching.length)fragment.append(node('p','Ningún torneo coincide con esa búsqueda.','event-empty'));
    list.replaceChildren(fragment);list.setAttribute('aria-busy','false');
    const more=byId('event-more');more.hidden=Boolean(query)||showAll||matching.length<=FIRST;more.textContent=`Ver los ${matching.length} torneos`;
  }
  function render(bundle) {
    const view=local?bundle.localRanking:bundle;
    if(!view||!validCatalog(view)||!validCatalog(bundle))throw new Error('Catálogo de torneos inválido');
    localIds=new Set((bundle.localRanking?.events||[]).map(event=>String(event.id)));
    // The list always shows every tournament of the cut; the local view marks which ones it leaves out
    // and takes its own figures for the ones it counts.
    const localById=new Map((bundle.localRanking?.events||[]).map(event=>[String(event.id),event]));
    events=bundle.events.map(event=>local&&localById.has(String(event.id))?localById.get(String(event.id)):event).sort((a,b)=>b.date.localeCompare(a.date)||a.name.localeCompare(b.name));
    byId('method-season').textContent=view.seasonLabel;
    byId('method-updated').textContent=`Datos: ${updatedFormat.format(new Date(view.generatedAt))}`;
    byId('method-version').textContent=view.methodVersion||'Método piloto';
    byId('method-exact').textContent=view.method||'La fórmula de este corte no está disponible.';
    byId('method-view').textContent=local?'Vista: solo Guatemala. La tabla y los conteos corresponden al cálculo local independiente.':'Vista: Guatemala + internacionales. La tabla y los conteos corresponden al cálculo combinado.';
    byId('event-status').textContent=`${view.events.length} torneos considerados · ${view.counts.sets.toLocaleString('es-GT')} sets competitivos.`;
    const excluded=view.excludedEvents.map(event=>{const item=document.createElement('li');item.append(linkedName(event.name,event.url),document.createTextNode(`: ${event.reason}`));return item;});
    byId('excluded-events').replaceChildren(...excluded);byId('excluded-count').textContent=`(${excluded.length})`;
    byId('event-retry').hidden=true;renderList();
  }
  async function refresh(quiet) {
    try {
      const response=await fetch('./data/public.json',{cache:'no-store'});
      if(!response.ok)throw new Error('Datos no disponibles');
      const bundle=await response.json();
      if(local&&!bundle.localRanking)throw new Error('La vista local no está disponible');
      render(bundle);
    } catch {
      if(quiet&&events.length)return;
      byId('event-status').textContent='No pudimos cargar el catálogo. Vuelve a intentarlo más tarde.';
      byId('event-list').replaceChildren();byId('event-list').setAttribute('aria-busy','false');byId('event-more').hidden=true;byId('event-retry').hidden=false;
    }
  }
  // Scope selector: plain links; here they only learn which one is current.
  byId('scope-local').toggleAttribute('aria-current',local);if(local)byId('scope-local').setAttribute('aria-current','true');
  if(local)byId('scope-combined').removeAttribute('aria-current');
  byId('event-search').addEventListener('input',renderList);
  byId('event-more').addEventListener('click',()=>{showAll=true;renderList();});
  byId('event-retry').addEventListener('click',()=>{byId('event-status').textContent='Cargando torneos del corte…';refresh(false);});

  // Index: a collapsible bar on small screens, a side list on wide ones; the current section is marked.
  const index=byId('method-index'), toggle=byId('index-toggle'), links=[...index.querySelectorAll('a')];
  toggle.addEventListener('click',()=>{const open=index.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));});
  links.forEach(link=>link.addEventListener('click',()=>{index.classList.remove('open');toggle.setAttribute('aria-expanded','false');}));
  const mark=id=>links.forEach((link,i)=>{const current=link.getAttribute('href')===`#${id}`;if(current){link.setAttribute('aria-current','true');byId('index-current').textContent=`${i+1} · ${link.textContent}`;}else link.removeAttribute('aria-current');});
  if('IntersectionObserver' in window){
    const observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting)mark(entry.target.id);},{rootMargin:'-20% 0px -70% 0px'});
    document.querySelectorAll('.method-section').forEach(section=>observer.observe(section));
  }
  mark('m1');
  refresh(false);
  setInterval(()=>{if(!document.hidden)refresh(true);},60000);
})();
