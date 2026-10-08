/* «Próximos torneos»: the agenda of data/agenda.json. Registration happens on start.gg; this page only links.
   «Cerca de mí» works on the device: coordinates are never sent or stored anywhere. */
(() => {
  const M=TorneosModel, root=document.getElementById('t-root');
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let agenda=null, list=[], filters={zone:'',mode:'todos',ranking:false}, geo={state:'off',position:null}, open=null, failed=false;
  const wide=()=>matchMedia('(min-width:900px)').matches;
  const fromHash=()=>{const slug=decodeURIComponent(location.hash.slice(1));return /^[a-z0-9-]+$/.test(slug)?slug:null;};

  const dateBox=(t,now,big='')=>{const b=M.box(t.start), c=M.countdown(t.start,now);return `<div class="t-date ${c.soon?'soon':''} ${big}" aria-hidden="true"><span>${b.dow}</span><b>${b.day}</b><span>${b.month}</span></div>`;};
  const count=(t,now)=>{const c=M.countdown(t.start,now);return `<p class="t-count ${c.urgent?'urgent':''}">${c.text} · ${M.time(t.start)}</p>`;};
  const reg=(t,now)=>{const r=M.registration(t,now);return `<p class="t-reg ${r.kind}"><span aria-hidden="true">${r.glyph}</span> ${r.text}</p>`;};
  const cta=(t,big='')=>t.registration==='open'?`<a class="t-cta ${big}" href="${escape(t.url)}" target="_blank" rel="noopener noreferrer"><span>Inscribirme en start.gg ↗</span></a>`
    :`<a class="t-outline ${big}" href="${escape(t.url)}" target="_blank" rel="noopener noreferrer">Ver en start.gg ↗</a>`;
  const distance=t=>geo.state!=='ok'?'':t.km!==null?` · a ${t.km<10?t.km.toFixed(1):Math.round(t.km)} km`:t.online?'':' · sin ubicación exacta';

  function card(t,now) {
    return `<li><article class="t-card ${open===t.slug&&wide()?'selected':''}">${dateBox(t,now)}<div class="t-body">${count(t,now)}
      <h3><button type="button" data-open="${escape(t.slug)}">${escape(t.name)}</button></h3><p class="t-where">${escape(M.where(t))}${distance(t)}</p>
      <p class="t-chips"><span>${M.modeLabel(t)}</span>${t.kinds.length?`<span>${M.kindsLabel(t)}</span>`:''}${t.entrants!==null?`<span>${M.plural(t.entrants,'inscrito','inscritos')}</span>`:''}</p>
      ${reg(t,now)}<div class="t-actions">${cta(t)}<button type="button" class="t-link" data-open="${escape(t.slug)}">Ver detalle</button></div></div></article></li>`;
  }
  function detail(t,now) {
    const r=M.registration(t,now), note=M.rankingNote(t), map=M.mapUrl(t), place=[t.city,t.department].filter(Boolean).join(', ');
    const kinds={singles:['Singles (1 contra 1)',t.online?null:true],doubles:['Dobles (2 contra 2)',false],teams:['Equipos',false],other:['Otro formato',null]};
    const events=t.kinds.length?t.kinds.map(k=>`<p><b>${kinds[k][0]}</b>${kinds[k][1]===true?'<small class="ok">◆ Puede contar para el ranking</small>':kinds[k][1]===false?'<small>— No cuenta para el ranking</small>':''}</p>`).join(''):'<p>start.gg no indica los eventos.</p>';
    const closes=t.registration==='closed'?'start.gg ya no acepta inscripciones.':t.closes!==null?`Cierra el ${M.date(t.closes)} a las ${M.time(t.closes)}`:'start.gg no indica cuándo cierra.';
    const venue=t.online?`<p>Online: se juega desde casa. Las indicaciones de conexión están en start.gg.</p>`
      :t.venue||t.address||place?`${t.venue?`<p><b>${escape(t.venue)}</b></p>`:''}${t.address?`<p>${escape(t.address)}</p>`:''}${place?`<p>${escape(place)}</p>`:''}${!t.venue&&!t.address?'<p class="t-muted">El organizador aún no publicó el lugar exacto. Revisa start.gg más cerca de la fecha.</p>':''}${map?`<a class="t-map" href="${escape(map)}" target="_blank" rel="noopener noreferrer">Abrir en mapas ↗</a>`:''}`
      :'<p class="t-muted">El organizador aún no publicó el lugar exacto. Revisa start.gg más cerca de la fecha.</p>';
    return `<article class="t-detail" aria-labelledby="t-detail-title">${wide()?'':'<button type="button" class="t-back" data-close>← Todos los torneos</button>'}
      <div class="t-detail-head">${dateBox(t,now,'big')}<div>${count(t,now)}<h2 id="t-detail-title" tabindex="-1">${escape(t.name)}</h2><p class="t-where">${M.fullDate(t.start)}</p></div></div>
      <dl><div><dt>Eventos</dt><dd>${events}</dd></div>
        <div><dt>Inscripción</dt><dd><p class="t-reg ${r.kind}"><span aria-hidden="true">${r.glyph}</span> ${r.text}</p><p>${closes}</p><p>${t.entrants!==null?`${M.plural(t.entrants,'inscrito','inscritos')} hasta ahora.`:'start.gg no muestra cuántos van inscritos.'}</p></dd></div>
        <div><dt>${t.online?'Modalidad':'Lugar'}</dt><dd>${venue}</dd></div>
        ${note?`<div><dt>Ranking</dt><dd><p class="${note.ok?'ok':''}">${note.ok?'◆':'—'} ${note.text}</p></dd></div>`:''}</dl>
      ${cta(t,'big')}<p class="t-note">Datos de start.gg, actualizados el ${updated()}.</p></article>`;
  }
  const updated=()=>{const at=Date.parse(agenda?.generatedAt);return Number.isNaN(at)?'fecha desconocida':`${M.date(at)} ${M.time(at)}`;};
  const zoneLabel=()=>filters.zone?filters.zone.slice(2):'todo el país';

  function filtersPanel() {
    const z=M.zones(list), option=(value,label)=>`<option value="${escape(value)}" ${filters.zone===value?'selected':''}>${escape(label)}</option>`;
    const G={pidiendo:['◎','Pidiendo permiso de ubicación a tu navegador…',false],ok:['◎','Ordenado por distancia desde tu ubicación, dentro de cada grupo. Los torneos sin ubicación exacta van al final.',false],
      negado:['×','No diste permiso de ubicación. Puedes activarlo en los ajustes del navegador o elegir un departamento arriba.',true],
      noDisponible:['!','No pudimos obtener tu ubicación. Revisa que el GPS esté activo o elige un departamento arriba.',true]}[geo.state];
    return `<section class="t-filters" aria-label="Filtros"><div class="t-row"><label class="sr-only" for="t-zone">Departamento o ciudad</label>
        <select id="t-zone">${option('','Todo el país')}${z.departments.length?`<optgroup label="Departamentos">${z.departments.map(d=>option('d:'+d,d)).join('')}</optgroup>`:''}${z.cities.length?`<optgroup label="Ciudades">${z.cities.map(c=>option('c:'+c,c)).join('')}</optgroup>`:''}</select>
        <button type="button" id="t-near" class="${geo.state==='ok'?'on':''}" aria-pressed="${geo.state==='ok'}" ${geo.state==='pidiendo'?'disabled':''}>◎ ${geo.state==='pidiendo'?'Pidiendo permiso…':geo.state==='ok'?'Cerca de mí · activo':'Cerca de mí'}</button></div>
      <p class="t-note">Tu ubicación se usa solo en tu teléfono para ordenar la lista; no se envía ni se guarda.</p>
      ${G?`<p class="t-geo" role="status"><span aria-hidden="true">${G[0]}</span><span>${G[1]}${G[2]?' <button type="button" class="t-link" id="t-retry-geo">Intentar de nuevo</button>':''}</span></p>`:''}
      <div class="t-row"><div class="t-modes" role="radiogroup" aria-label="Modalidad">${[['todos','Todos'],['presencial','Presencial'],['online','Online']].map(([k,l])=>`<button type="button" role="radio" aria-checked="${filters.mode===k}" data-mode="${k}" tabindex="${filters.mode===k?0:-1}">${l}</button>`).join('')}</div>
        <label class="t-check"><input type="checkbox" id="t-ranking" ${filters.ranking?'checked':''}> Solo los que pueden contar para el ranking</label></div>
      ${filters.ranking?'<p class="t-note">Muestra torneos presenciales con singles. Para contar, el torneo debe llegar a 20 jugadores activos, y eso se sabe hasta que termina.</p>':''}</section>`;
  }
  function body(now) {
    const shown=M.filter(list,filters), groups=M.groups(shown,now,geo.state==='ok'?geo.position:null);
    if(!list.length)return `<section class="t-empty"><h2>Todavía no hay torneos anunciados</h2><p>Cuando un organizador publique un torneo de Smash Ultimate en Guatemala en start.gg, aparecerá aquí. Revisamos la agenda todos los días.</p></section>`;
    if(!shown.length){const narrowed=filters.mode!=='todos'||filters.ranking;
      return `<section class="t-empty"><h2>${filters.zone?`No hay torneos anunciados en ${escape(zoneLabel())}`:'Ningún torneo coincide con los filtros'}</h2><p>${filters.zone?`Por ahora no hay torneos presenciales anunciados en ${escape(zoneLabel())}. ${narrowed?'Prueba quitando los filtros de modalidad o de ranking. ':''}Los torneos online no tienen zona: aparecen en «Todo el país».`:'Prueba quitando los filtros de modalidad o de ranking.'}</p><button type="button" class="t-outline" id="t-clear">Ver todo el país</button></section>`;}
    const flat=groups.flatMap(g=>g.items), current=flat.find(t=>t.slug===open)||(wide()?flat[0]:null);
    if(wide()&&current)open=current.slug;
    const lists=`<p class="t-total" role="status">${M.plural(shown.length,'torneo','torneos')} en ${escape(zoneLabel())} · ${geo.state==='ok'?'por distancia':'por fecha'}</p>${groups.map(g=>`<section class="t-group"><div class="t-group-head"><h2>${g.title}</h2><span>${M.plural(g.items.length,'torneo','torneos')}</span></div><ul>${g.items.map(t=>card(t,now)).join('')}</ul></section>`).join('')}`;
    if(!wide())return current?detail(current,now):lists;
    return `<div class="t-columns"><div class="t-list">${lists}</div><aside class="t-side">${current?detail(current,now):''}</aside></div>`;
  }
  function render(focusDetail=false) {
    const now=Date.now();
    if(failed){root.innerHTML=`<section class="t-empty error" role="alert"><h2>No pudimos cargar la agenda.</h2><p>Vuelve a intentarlo en un momento. Mientras tanto, los torneos siguen publicados en start.gg.</p><div class="t-actions"><button type="button" class="t-cta" id="t-reload"><span>Reintentar</span></button><a class="t-outline" href="https://www.start.gg/search/tournaments?countryCode=GT" target="_blank" rel="noopener noreferrer">Buscar en start.gg ↗</a></div></section>`;return;}
    if(!agenda){root.innerHTML='<div class="t-loading" role="status"><div class="t-bar"><span></span></div><p>Cargando la agenda de start.gg…</p><div></div><div></div><div></div></div>';return;}
    list=M.upcoming(agenda,now);
    const mobileDetail=!wide()&&open&&M.filter(list,filters).some(t=>t.slug===open);
    const stale=M.stale(agenda,now)?`<div class="t-stale" role="status"><span aria-hidden="true">↻</span><div><strong>Estos datos tienen más de 48 horas.</strong><p>Última actualización: ${updated()}. Confirma fecha, hora y lugar en start.gg antes de ir.</p></div></div>`:'';
    root.innerHTML=`${mobileDetail?'':filtersPanel()}${stale}${body(now)}`;
    if(focusDetail)document.getElementById('t-detail-title')?.focus();
  }
  function setOpen(slug,focus=true){open=slug;history.replaceState(null,'',slug?`#${slug}`:location.pathname+location.search);render(focus&&!!slug);if(!slug||!wide())scrollTo({top:0});}
  function locate() {
    if(!navigator.geolocation){geo={state:'noDisponible',position:null};render();return;}
    geo={state:'pidiendo',position:null};render();
    navigator.geolocation.getCurrentPosition(p=>{geo={state:'ok',position:{lat:p.coords.latitude,lng:p.coords.longitude}};render();},
      error=>{geo={state:error.code===1?'negado':'noDisponible',position:null};render();},{enableHighAccuracy:false,timeout:15000,maximumAge:600000});
  }
  root.addEventListener('click',event=>{
    const target=event.target.closest('button'); if(!target)return;
    if(target.dataset.open)setOpen(target.dataset.open);
    else if('close' in target.dataset)setOpen(null);
    else if(target.id==='t-near'){if(geo.state==='ok'){geo={state:'off',position:null};render();}else locate();}
    else if(target.id==='t-retry-geo')locate();
    else if(target.dataset.mode){filters.mode=target.dataset.mode;if(!wide())open=null;render();root.querySelector(`[data-mode="${filters.mode}"]`)?.focus();}
    else if(target.id==='t-clear'){filters={zone:'',mode:'todos',ranking:false};render();}
    else if(target.id==='t-reload')load();
  });
  root.addEventListener('change',event=>{
    if(event.target.id==='t-zone')filters.zone=event.target.value; else if(event.target.id==='t-ranking')filters.ranking=event.target.checked; else return;
    if(!wide())open=null; render(); document.getElementById(event.target.id)?.focus();
  });
  root.addEventListener('keydown',event=>{
    const radio=event.target.closest('[data-mode]'); if(!radio||!['ArrowLeft','ArrowRight'].includes(event.key))return;
    event.preventDefault(); const order=['todos','presencial','online']; filters.mode=order[(order.indexOf(filters.mode)+(event.key==='ArrowRight'?1:2))%3]; render(); root.querySelector(`[data-mode="${filters.mode}"]`)?.focus();
  });
  let lastWide=wide(); addEventListener('resize',()=>{if(wide()!==lastWide){lastWide=wide();render();}});
  async function load() {
    failed=false;agenda=null;render();
    const controller=new AbortController(), stop=setTimeout(()=>controller.abort(),15000);
    try {
      const response=await fetch('./data/agenda.json',{cache:'no-cache',signal:controller.signal});
      if(!response.ok)throw new Error('Sin agenda');
      const data=await response.json();
      if(data?.schemaVersion!==1||!Array.isArray(data.tournaments))throw new Error('Agenda inválida');
      agenda=data;open=fromHash();
    } catch { failed=true; } finally { clearTimeout(stop); }
    render();
  }
  load();
})();
