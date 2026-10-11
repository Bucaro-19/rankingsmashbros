/* Owner's private panel. Figures come from panel-api.php; this file only presents them. */
(() => {
  const $=id=>document.getElementById(id), M=PanelModel, N=n=>M.number(n);
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const PERIODS=[['7','7 días'],['30','30 días'],['90','90 días'],['season','Temporada']];
  let report=null, csrf='', registrationSnapshot='', period='30', metric='visitors', selected=-1, items=[], listOpen=false;
  try{const saved=localStorage.getItem('smashgt.panel.periodo');if(PERIODS.some(p=>p[0]===saved))period=saved;}catch{}
  function show(state){$('panel-loading').hidden=state!=='loading';$('panel-error').hidden=state!=='error';$('panel-ready').hidden=state!=='ready';}
  async function load() {
    closeRegistrations(false);
    show('loading');
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),20000);
    try {
      const response=await fetch('./panel-api.php',{credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{Accept:'application/json'}});
      // The session ended or the account changed: the server page decides what to show.
      if(response.status===401||response.status===403){location.reload();return;}
      const json=await response.json();
      if(!response.ok||json.ok!==true)throw new Error(String(response.status));
      report=json.report;csrf=json.csrf;registrationSnapshot=json.registrationSnapshot;render();show('ready');
    } catch(error) {
      // Old figures are never left on screen as if they were current.
      report=null;$('error-code').textContent=`STATS-${/^\d{3}$/.test(error.message)?error.message:'RED'}`;show('error');
    } finally {clearTimeout(timer);}
  }
  function render() {
    closeRegistrations(false);
    $('updated').textContent=`Datos actualizados: ${M.dmy(report.updatedAt.slice(0,10))} · ${report.updatedAt.slice(11,16)} (hora de Guatemala, UTC−6)`;
    renderGlance();
    $('periods').innerHTML=PERIODS.map(([key,label])=>`<button type="button" data-period="${key}" aria-pressed="${key===period}">${label}</button>`).join('');
    document.querySelectorAll('[data-period]').forEach(button=>button.addEventListener('click',()=>{period=button.dataset.period;try{localStorage.setItem('smashgt.panel.periodo',period);}catch{}selected=-1;render();}));
    renderPeriod();
  }
  function glanceCard(name,label) {
    const p=report.periods[name];
    if(!p.daysWithData)return `<div class="card"><p class="label">${label}</p><p class="figure">—</p><p class="sub">Sin días completos todavía</p></div>`;
    return `<div class="card"><p class="label">${label}</p><p class="figure">${N(p.visitors)}</p><p class="sub">${p.daysWithData<p.days?`Solo ${M.plural(p.daysWithData,'día','días')} con datos`:'visitantes distintos'}</p></div>`;
  }
  function renderGlance() {
    const t=report.today, a=report.accounts, gone=a.total-a.linked;
    const yesterday=report.yesterday?`Ayer completo: ${M.plural(report.yesterday.visitors,'visitante','visitantes')}`:report.counterStartedAt?'Ayer: sin datos (el contador empezó hoy)':'El contador todavía no registra visitas';
    $('glance').innerHTML=`<div class="card today wide"><p class="label">Hoy · en curso</p><p class="figure">${N(t.visitors)}</p><p class="strong">${t.visitors===1?'visitante':'visitantes'} hasta las ${report.updatedAt.slice(11,16)}</p><p>${yesterday}</p>${registrationButton('today',M.plural(t.registrations,'registro nuevo hoy','registros nuevos hoy'))}${report.yesterday?registrationButton('yesterday',M.plural(report.yesterday.registrations,'registro nuevo ayer','registros nuevos ayer')):''}</div>`
      +glanceCard('7','Últimos 7 días')+glanceCard('30','Últimos 30 días')
      +`<div class="card accounts wide"><p class="label">Cuentas registradas</p>${registrationButton('all',`${N(a.total)}`, 'figure', 'Cuentas registradas')}<p class="sub">${a.total?`${N(a.linked)} ${a.linked===1?'sigue vinculada':'siguen vinculadas'} a start.gg · ${M.plural(gone,'desvinculada','desvinculadas')}`:'Aún no hay cuentas registradas'}</p>${a.premium!=null?`<p class="sub"><strong class="yellow">${N(a.premium)}</strong> ${a.premium===1?'cuenta premium':'cuentas premium'}</p>${(a.premiumList||[]).length?`<ul class="premium-list">${a.premiumList.map(x=>`<li><strong>${escape(x.tag)}</strong><span>${x.plan==='annual'?'Anual':'Mensual'} · ${x.renews?'se renueva':'termina'} el ${escape(String(x.until).split('-').reverse().join('/'))}</span></li>`).join('')}</ul>`:''}`:''}</div>`;
  }
  function renderPeriod() {
    const p=report.periods[period], title=period==='season'?`Temporada ${report.seasonYear}`:M.LABELS[period];
    const head=`<div class="period-head"><h2 id="period-title">${title}</h2><span class="note">${p.days>0?`${M.dmy(p.from)} – ${M.dmy(p.to)} · días completos`:'Aún sin días completos'}</span></div>`;
    if(!p.daysWithData) {
      const started=report.counterStartedAt;
      $('period').innerHTML=head+`<div class="empty"><strong>Sin datos todavía</strong><p>${started?`El contador empezó el ${M.dmy(started)}. `:'El contador todavía no registra visitas. '}Los totales usan días completos: el primero aparecerá mañana a primera hora. Mientras tanto, lo de hoy se ve arriba.</p></div>`;
      $('chart').hidden=true;$('pages').hidden=true;return;
    }
    const change=M.change(period,p), short=M.shortNotice(report,p), v=p.visitors, regs=p.registrations, per=regs?Math.round(v/regs):0;
    $('period').innerHTML=head+(short?`<div class="info" role="status"><span aria-hidden="true">i</span><p>${escape(short)}</p></div>`:'')
      +`<div class="cards"><div class="card wide"><p class="label">Visitantes distintos</p><p class="figure big blue">${N(v)}</p><span class="chip ${change.kind}">${escape(change.text)}</span><p class="fine">Se cuentan por navegador: una persona con teléfono y computadora cuenta como dos.</p>
          <div class="secondary"><p><span>Redes distintas</span><strong>${N(p.networks)}</strong></p><p class="fine">Más bajo: varias personas pueden compartir una red (casa, local, torneo).</p></div></div>
        <div class="card"><p class="label">Con sesión iniciada</p><p class="figure mid">${N(p.loggedVisitors)}</p><p class="sub">${v?Math.round(p.loggedVisitors/v*100):0}% de los visitantes</p></div>
        <div class="card"><p class="label">Vistas de página</p><p class="figure mid">${N(p.pageviews)}</p><p class="sub">${v?(p.pageviews/v).toFixed(1):'0'} por visitante</p></div>
        <div class="card accounts wide"><p class="label">Registros nuevos</p>${registrationButton(period,N(regs),'figure big yellow','Registros nuevos')}<p class="strong">${regs?(v?`1 registro por cada ${M.plural(per,'visitante','visitantes')}`:'Registros sin visitas medidas en el periodo'):'Sin registros nuevos en el periodo'}</p>
          ${regs&&v?`<div class="ratio" aria-hidden="true"><span style="width:${Math.min(100,regs/v*1000).toFixed(1)}%"></span></div><p class="fine">${(regs/v*100).toFixed(1)}% de los visitantes se registró. Barra a escala ×10 para que se lea.</p>`:`<p class="fine">${regs?'':'Los registros aparecerán aquí junto a los visitantes.'}</p>`}</div></div>`;
    items=M.items(report,period);if(selected<0||selected>=items.length||items[selected].none)selected=M.defaultIndex(items);
    renderChart();renderPages(p);
  }
  function renderChart() {
    closeRegistrations(false);
    const weekly=period==='90'||period==='season', word=metric==='visitors'?'visitantes':'vistas', key=metric;
    const usable=items.filter(i=>!i.none), max=M.axisMax(usable.map(i=>i[key])), rmax=Math.max(1,...usable.map(i=>i.registrations));
    const it=items[selected], firstUsable=items.findIndex(i=>!i.none), labels=[items[0],items[Math.floor((items.length-1)/2)],items[items.length-1]].map(i=>i.short);
    const bars=items.map((x,i)=>x.none?`<button type="button" class="bar none" disabled aria-hidden="true" tabindex="-1"><span></span></button>`
      :`<button type="button" class="bar${x.partial?' partial':''}" data-bar="${i}" tabindex="${i===selected?0:-1}" aria-pressed="${i===selected}" aria-label="${escape(`${x.label}: ${M.reading(x)}`)}"><span style="height:${x[key]?Math.max(2,x[key]/max*100):0}%"></span></button>`).join('');
    const strip=items.map(x=>`<span class="${x.partial?'partial':''}" style="height:${x.none||!x.registrations?0:Math.max(8,x.registrations/rmax*100)}%"></span>`).join('');
    const rows=[...items].reverse().filter(x=>!x.none).map(x=>`<li><span>${escape(x.label.replace(/^./,c=>c.toUpperCase()))}</span><span><span><strong class="blue">${N(x.visitors)}</strong> ${x.visitors===1?'visitante':'visitantes'}</span><span><strong>${N(x.pageviews)}</strong> ${x.pageviews===1?'vista':'vistas'}</span>${registrationButton(x.scope,M.plural(x.registrations,'registro','registros'))}</span></li>`).join('');
    $('chart').hidden=false;
    $('chart').innerHTML=`<div class="chart-head"><h2 id="chart-title">${weekly?'Evolución por semana':'Evolución diaria'}</h2><div class="segmented small" role="group" aria-label="Dato de la gráfica"><button type="button" data-metric="visitors" aria-pressed="${metric==='visitors'}">Visitantes</button><button type="button" data-metric="pageviews" aria-pressed="${metric==='pageviews'}">Vistas</button></div></div>
      <div class="reading${it?.partial?' partial':''}" role="status" aria-live="polite"><strong>${it?escape(it.label.replace(/^./,c=>c.toUpperCase())):''}</strong><span>${it?`${M.plural(it.visitors,'visitante','visitantes')} · ${M.plural(it.pageviews,'vista','vistas')}${it.partial?' · parcial':''}`:''}</span>${it?registrationButton(it.scope,M.plural(it.registrations,'registro nuevo','registros nuevos')):''}</div>
      <div class="plot"><div class="axis" aria-hidden="true"><span>${N(max)}</span><span>${N(max/2)}</span><span>0</span></div><div class="plot-body">
        <div id="bars" class="bars${items.length>40?' dense':''}" role="group" aria-label="Gráfica de ${word}${weekly?' por semana':' por día'}. Usa las flechas para recorrer.">${bars}</div>
        <div class="x-labels" aria-hidden="true"><span>${labels[0]}</span><span>${labels[1]}</span><span>${labels[2]}</span></div>
        <p class="strip-title">Registros nuevos · máx. ${N(rmax)}</p><div class="strip${items.length>40?' dense':''}" aria-hidden="true">${strip}</div></div></div>
      <div class="legend"><span><i class="k-blue"></i>${metric==='visitors'?'Visitantes distintos':'Vistas de página'} ${weekly?'por semana':'por día'}</span><span><i class="k-yellow"></i>Registros nuevos</span>${items.some(i=>i.partial)?`<span><i class="k-partial"></i>${weekly?'Semana incompleta':'Hoy, en curso (no suma al total)'}</span>`:''}${items.some(i=>i.none)?'<span><i class="k-none"></i>Sin datos (antes del contador)</span>':''}</div>
      <p class="fine">${weekly?'Cada barra es una semana de siete días contada hacia atrás desde ayer.':'Cada barra es un día completo de Guatemala.'} Toca una barra o usa las flechas ← → para ver su valor.</p>
      <button type="button" id="list-toggle" class="outline" aria-expanded="${listOpen}" aria-controls="value-list">${listOpen?'Ocultar la lista':'Ver valores como lista'}</button>
      ${listOpen?`<ol id="value-list" class="value-list" aria-label="Valores ${weekly?'por semana':'por día'}, del más reciente al más antiguo">${rows}</ol>`:''}`;
    document.querySelectorAll('[data-bar]').forEach(button=>button.addEventListener('click',()=>pick(Number(button.dataset.bar),false)));
    document.querySelectorAll('[data-metric]').forEach(button=>button.addEventListener('click',()=>{metric=button.dataset.metric;renderChart();document.querySelector(`[data-metric="${metric}"]`).focus();}));
    $('bars').addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();pick(M.step(items,selected,event.key),true);});
    $('list-toggle').addEventListener('click',()=>{listOpen=!listOpen;renderChart();$('list-toggle').focus();});
    if(firstUsable===-1)$('chart').hidden=true;
  }
  function pick(index,focus){selected=index;renderChart();if(focus)document.querySelector(`[data-bar="${index}"]`)?.focus();}
  function renderPages(p) {
    const rows=M.pages(p);
    $('pages').hidden=false;
    $('pages').innerHTML=`<div class="period-head"><h2 id="pages-title">Páginas más visitadas</h2><span class="note">Vistas en ${period==='season'?'la temporada':`los últimos ${period} días`} · la encuesta no se cuenta</span></div><ol>${rows.map(r=>`<li><div><span class="pos">${r.position}</span><span class="name">${escape(r.name)}</span><strong>${N(r.views)}</strong><span class="pct">${r.percent}%</span></div><div class="track" aria-hidden="true"><span style="width:${r.width}%"></span></div></li>`).join('')}</ol>`;
  }
  let registrationTrigger=null, registrationRequest=null, registrationVersion=0, registrationData=[], registrationNext=null, registrationTotal=null, registrationScope='';
  function registrationButton(scope,label,classes='',context='') {
    return `<button type="button" class="registration-toggle ${classes}" data-registration="${escape(scope)}" aria-expanded="false" aria-controls="registration-list" aria-label="${escape(`Ver cuentas: ${context?`${context} · `:''}${label}`)}">${escape(label)}<span class="fine"> · Ver cuentas</span></button>`;
  }
  function closeRegistrations(focus=true) {
    registrationVersion++; registrationRequest?.abort(); registrationRequest=null;
    const trigger=registrationTrigger; registrationTrigger=null;
    document.querySelectorAll('[data-registration]').forEach(b=>b.setAttribute('aria-expanded','false'));
    const panel=$('registration-list'); panel.hidden=true; panel.setAttribute('aria-busy','false'); panel.replaceChildren();
    // Keep the shared region outside DOM subtrees replaced by chart/period rendering.
    $('panel-ready').append(panel);
    if(focus&&trigger?.isConnected)trigger.focus();
    registrationData=[]; registrationNext=null; registrationTotal=null;
  }
  async function fetchRegistrations(more=false) {
    const panel=$('registration-list'), version=++registrationVersion;
    registrationRequest?.abort(); const controller=new AbortController(); registrationRequest=controller;
    const timer=setTimeout(()=>controller.abort(),20000);
    panel.setAttribute('aria-busy','true');
    renderRegistrations('loading');
    try {
      const query=new URLSearchParams({registrations:registrationScope,day:report.today.date,snapshot:registrationSnapshot,offset:String(more?registrationNext:0)});
      const response=await fetch(`./panel-api.php?${query}`,{credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{Accept:'application/json'}});
      if(version!==registrationVersion)return;
      if(response.status===401||response.status===403){closeRegistrations(false);report=null;location.reload();return;}
      const json=await response.json();
      if(version!==registrationVersion)return;
      if(!response.ok||json.ok!==true)throw new Error(json.reason==='registration_snapshot_expired'?'expired':'unavailable');
      registrationData=more?registrationData.concat(json.registrations.items):json.registrations.items;
      registrationNext=json.registrations.nextOffset; registrationTotal=json.registrations.total;
      renderRegistrations('ready',json.registrations.total);
      // No raw IDs/identity fields are ever used; only the server's closed projection.
      panel.querySelector('h3')?.focus();
    } catch(error) {
      if(version===registrationVersion)renderRegistrations(error.message==='expired'?'expired':'error',null,more);
    } finally {
      clearTimeout(timer);
      if(version===registrationVersion){registrationRequest=null;panel.setAttribute('aria-busy','false');}
    }
  }
  function renderRegistrations(state,total=null,more=false) {
    const panel=$('registration-list'); total=total??registrationTotal;
    panel.innerHTML=`<div class="period-head"><h3 tabindex="-1">${total!==null?M.plural(total,'cuenta','cuentas'):'Cuentas registradas'}</h3><button type="button" class="outline" data-registration-close>Cerrar lista</button></div>
      <p class="fine">${escape(registrationTrigger?.getAttribute('aria-label')?.replace('Ver cuentas: ','')||'')} · De la más nueva a la más antigua · hora de Guatemala</p>
      <ul class="premium-list">${registrationData.map(x=>`<li><strong>${escape(x.tag)}</strong><span><time datetime="${escape(x.registeredAt)}">${escape(M.registrationTime(x.registeredAt))}</time><br>${x.linked?'Vinculada a start.gg':'Desvinculada de start.gg'}</span></li>`).join('')}</ul>
      <p role="status" aria-live="polite">${state==='loading'?'Consultando las cuentas…':state==='expired'?'Este reporte venció. Actualiza los datos para consultar las cuentas.':state==='error'?'No pudimos consultar las cuentas. Puedes reintentar.':!total?'Nadie se registró en este periodo':''}</p>
      ${state==='expired'?'<button type="button" class="outline" data-registration-refresh>Actualizar datos</button>':state==='error'?`<button type="button" class="outline" data-registration-retry="${more}">Reintentar</button>`:state==='ready'&&registrationNext!==null?'<button type="button" class="outline" data-registration-more>Ver más</button>':''}`;
  }
  document.addEventListener('click',event=>{
    const trigger=event.target.closest('[data-registration]');
    if(trigger) {
      if(registrationTrigger===trigger){closeRegistrations();return;}
      closeRegistrations(false); registrationTrigger=trigger; registrationScope=trigger.dataset.registration;
      trigger.setAttribute('aria-expanded','true');
      const panel=$('registration-list');
      const host=trigger.closest('.card, .reading, li');
      if(host?.classList.contains('card'))host.parentElement.insertAdjacentElement('afterend',panel);
      else if(host?.classList.contains('reading'))host.insertAdjacentElement('afterend',panel);
      else (host||trigger.parentElement).append(panel);
      panel.hidden=false;
      fetchRegistrations(); panel.querySelector('h3')?.focus();
    } else if(event.target.closest('[data-registration-close]'))closeRegistrations();
    else if(event.target.closest('[data-registration-refresh]')){closeRegistrations(false);load();}
    else if(event.target.closest('[data-registration-more]'))fetchRegistrations(true);
    else if(event.target.closest('[data-registration-retry]'))fetchRegistrations(event.target.closest('[data-registration-retry]').dataset.registrationRetry==='true');
  });
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&registrationTrigger){event.preventDefault();closeRegistrations();}});
  $('panel-retry').addEventListener('click',load);
  $('panel-logout').addEventListener('click',async()=>{
    const button=$('panel-logout');button.disabled=true;
    try{await fetch('./account-api.php',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({action:'logout'})});try{localStorage.removeItem('smashgt.cuenta');}catch{}location.href='./';}
    catch{button.disabled=false;}
  });
  load();
})();
