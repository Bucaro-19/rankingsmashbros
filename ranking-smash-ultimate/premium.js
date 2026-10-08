/* Premium tab of the account: plans, return from payment and managing the subscription.
   State always comes from premium-api.php; nothing here decides who is premium. */
const SmashPremium = (() => {
  const PLANS={annual:{name:'Anual',amount:24,period:'año',each:'al año',note:'Equivale a 2 USD al mes, pagados una vez al año.'},monthly:{name:'Mensual',amount:3,period:'mes',each:'al mes',note:'Pagas mes a mes.'}};
  // What premium includes. «available» turns the «Próximamente» label off when a feature ships.
  const FEATURES=[{title:'Análisis del rival',text:'Probabilidad estimada, historial, forma reciente y matchup de personajes antes de un set.',available:true,href:'./analisis.html',action:'Analizar un rival →'},{title:'Top 15 por organizador',text:'El ranking de cada organizador con sus propios torneos.',available:false}];
  const FREE=['El ranking completo','Tu puesto, también fuera del top 100','Tu perfil y tus personajes','Tu historial de torneos','Tu récord contra cada rival'];
  const RECURRENTE='El pago se hace en la página segura de Recurrente, la pasarela de Guatemala. Saldrás de Smash GT y volverás al terminar. Smash GT nunca ve ni guarda tu tarjeta.';
  const PRINCIPLE='Pagar no da puntos ni cambia tu puesto.';
  const root=()=>document.getElementById('premium-screen');
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  // Dates are shown in Guatemala time (UTC−6, no daylight saving).
  const day=iso=>{const time=Date.parse(iso);if(Number.isNaN(time))return null;const d=new Date(time-21600000);return `${String(d.getUTCDate()).padStart(2,'0')}/${String(d.getUTCMonth()+1).padStart(2,'0')}/${d.getUTCFullYear()}`;};
  let context={csrf:'',authenticated:false,onStatus:null,admin:false}, info=null, plan='annual', arrival=null, confirming=false, askCancel=false, busy=false, timer=null;
  function setContext(next){context={...context,...next};}
  async function api(body=null) {
    const controller=new AbortController(), stop=setTimeout(()=>controller.abort(),20000);
    try {
      const response=await fetch('./premium-api.php',{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,
        headers:body?{'Content-Type':'application/json','X-CSRF-Token':info?.csrf||context.csrf}:{Accept:'application/json'},body:body?JSON.stringify(body):undefined});
      const json=await response.json();
      if(!response.ok||json.ok!==true){const error=new Error(json.reason||'premium_unavailable');error.status=response.status;throw error;}
      return json;
    } finally {clearTimeout(stop);}
  }
  const notice=(kind,glyph,title,text,extra='')=>`<div class="p-notice ${kind}" role="${kind==='error'?'alert':'status'}"><span aria-hidden="true">${glyph}</span><div><strong>${title}</strong><p>${text}</p>${extra}</div></div>`;
  const included=()=>`<section class="p-box p-includes" aria-labelledby="p-inc"><h3 id="p-inc">Qué incluye</h3><ul>${FEATURES.map(f=>`<li><span aria-hidden="true">${f.available?'✓':'…'}</span><div><strong>${f.title}${f.available?'':' <em>Próximamente</em>'}</strong><p>${f.text}</p>${f.available&&f.href&&context.authenticated?`<a class="p-go" href="${f.href}">${f.action}</a>`:''}</div></li>`).join('')}</ul></section>`;
  const free=()=>`<section class="p-box" aria-labelledby="p-free"><h3 id="p-free">Gratis para todos</h3><ul class="p-free">${FREE.map(item=>`<li><span aria-hidden="true">✓</span>${item}</li>`).join('')}</ul></section><p class="p-principle">${PRINCIPLE}</p>`;
  function renderPlans(top='') {
    const p=PLANS[plan], signed=context.authenticated, off=info&&info.available===false;
    // The site owner's account opens every premium feature without a subscription; say so instead of looking locked.
    const admin=context.admin?notice('ok','✓','Tu cuenta de administrador ya tiene todo lo de premium.','No necesitas suscripción para usar el análisis de rival ni las demás funciones. Si te suscribes, además apoyas el sitio y aparece la insignia Premium.','<a class="p-go" href="./analisis.html">Analizar un rival →</a>'):'';
    root().innerHTML=`${info?.test?notice('info','i','Modo de prueba.','Los pagos de esta pantalla usan el ambiente de pruebas de Recurrente: no se cobra dinero real.'):''}${admin}${top}
      <div class="p-hero"><p class="kicker yellow">Premium · Apoya el sitio</p><h1>Que la arena<br><span>se sostenga sola.</span></h1><p class="lead">Smash GT es un proyecto independiente de la comunidad. Con una suscripción pequeña ayudas a pagar el servidor y el trabajo de mantenerlo, y recibes funciones extra para preparar tus sets.</p></div>
      <div class="p-columns"><div class="p-main"><h2>Elige tu plan</h2>
        <div class="p-plans" role="radiogroup" aria-label="Plan">${Object.entries(PLANS).map(([key,item])=>`<button type="button" role="radio" aria-checked="${key===plan}" data-plan="${key}" tabindex="${key===plan?0:-1}"><span class="p-radio" aria-hidden="true"></span><span class="p-plan-name">${item.name}</span><span class="p-price"><b>${item.amount}</b> USD ${item.each}</span><span class="p-plan-note">${item.note}</span></button>`).join('')}</div>
        <div class="p-box p-before"><h3>Antes de pagar</h3><p>Se renueva automáticamente cada ${p.period} por ${p.amount} USD hasta que lo canceles.</p><p>Cancelas cuando quieras en esta pestaña, sin escribirle a nadie. Sigues siendo premium hasta el final del periodo que ya pagaste.</p>
          ${off?`<p class="p-warn">Los pagos todavía no están habilitados. Vuelve pronto.</p>`:signed?`<button type="button" id="p-pay" class="p-cta" ${busy?'disabled':''}><span>${busy?'Abriendo Recurrente…':`Apoyar con ${p.amount} USD ${p.each} ↗`}</span></button><p class="note">${RECURRENTE}</p>`
            :`<form action="./oauth.php" method="post" id="p-login"><input type="hidden" name="csrf" value="${escape(context.csrf)}"><button type="submit" class="p-cta blue"><span>Entrar con start.gg para apoyar ↗</span></button></form><p class="note">Primero vinculas tu cuenta: así la suscripción queda a tu nombre y puedes cancelarla desde aquí. Tu contraseña se escribe en start.gg.</p>`}
          <p id="p-error" class="p-warn" role="alert" hidden></p></div></div>
        <aside class="p-side">${included()}${free()}</aside></div>`;
    const radios=[...root().querySelectorAll('[data-plan]')];
    radios.forEach(button=>{button.addEventListener('click',()=>{plan=button.dataset.plan;render();root().querySelector(`[data-plan="${plan}"]`).focus();});
      button.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();plan=plan==='annual'?'monthly':'annual';render();root().querySelector(`[data-plan="${plan}"]`).focus();});});
    root().querySelector('#p-pay')?.addEventListener('click',pay);
    // After signing in, the visitor lands back on this tab.
    root().querySelector('#p-login')?.addEventListener('submit',()=>{try{sessionStorage.setItem('smashgt.volver','premium');}catch{}});
  }
  async function pay() {
    busy=true;render();
    try {
      const result=await api({action:'checkout',plan});
      const url=new URL(result.checkoutUrl);
      // The only place the browser is sent to pay is Recurrente's own page.
      if(url.protocol!=='https:'||url.hostname!=='app.recurrente.com')throw new Error('premium_unavailable');
      location.href=url.href;
    } catch(error) {
      busy=false;render();
      const box=root().querySelector('#p-error');
      if(box){box.textContent=error.message==='invalid_already_premium'?'Ya tienes una suscripción activa. Recarga la página para verla.':'No pudimos abrir el pago. No se hizo ningún cobro; intenta de nuevo en un momento.';box.hidden=false;}
    }
  }
  function renderManage() {
    const s=info.premium, p=PLANS[s.plan]||PLANS.monthly, end=day(s.currentPeriodEnd), since=day(s.startedAt), canceled=s.cancelRequested, due=s.status==='past_due';
    const chip=canceled?'<span class="p-chip off">○ Cancelada · sin renovación</span>':due?'<span class="p-chip warn">! Pago pendiente</span>':'<span class="p-chip on">● Activa</span>';
    const rows=[['Monto',`${p.amount} USD ${p.each}`],canceled?['Premium hasta',end]:due?['Acceso premium hasta',end]:['Próximo cobro',end],canceled?['Próximo cobro','Ninguno']:['Renovación',`Automática, cada ${p.period}`],['Premium desde',since]].filter(row=>row[1]);
    const top=canceled?notice('ok','✓',`Sigues siendo premium${end?` hasta el ${end}`:''}; no habrá más cobros.`,`Cancelaste la renovación. Gracias por el apoyo de este ${p.period}.`)
      :due?notice('warn','!','No pudimos renovar tu suscripción.',`Recurrente no pudo hacer el cobro de ${p.amount} USD. ${end?`Conservas premium hasta el ${end}.`:'Actualiza tu forma de pago para no perder el acceso.'} Si el cobro no se completa, tu premium termina ahí y puedes volver a suscribirte cuando quieras.`):'';
    root().innerHTML=`${info.test?notice('info','i','Modo de prueba.','Esta suscripción es del ambiente de pruebas de Recurrente: no se cobró dinero real.'):''}
      <div class="p-hero small"><p class="kicker yellow">Premium</p><h1>Tu suscripción</h1></div>${top}
      <div class="p-columns"><div class="p-main"><section class="p-box p-sub" aria-label="Tu suscripción"><div class="p-sub-head"><h2>Plan ${p.name.toLowerCase()}</h2>${chip}</div>
          <dl>${rows.map(([k,v])=>`<div><dt>${k}</dt><dd>${escape(v)}</dd></div>`).join('')}</dl>
          ${end?'':'<p class="note">Recurrente te avisará antes del próximo cobro.</p>'}
          ${canceled?'<p class="note">Puedes volver a suscribirte cuando termine este periodo.</p>':askCancel?`<div class="p-confirm" role="alertdialog" aria-labelledby="p-confirm-title" aria-describedby="p-confirm-text"><strong id="p-confirm-title">¿Cancelar tu suscripción?</strong><p id="p-confirm-text">Seguirás siendo premium${end?` hasta el ${end}`:' hasta el final del periodo pagado'}. Después no habrá más cobros. Puedes volver cuando quieras.</p><div><button type="button" id="p-keep" class="p-keep">No, mantener</button><button type="button" id="p-confirm-cancel" class="p-danger" ${busy?'disabled':''}>${busy?'Cancelando…':'Sí, cancelar'}</button></div></div>`
            :'<p class="note">Cancelas cuando quieras, sin escribirle a nadie. Sigues siendo premium hasta el final del periodo que ya pagaste.</p><button type="button" id="p-cancel" class="outline">Cancelar suscripción</button>'}
          <p id="p-error" class="p-warn" role="alert" hidden></p></section></div>
        <aside class="p-side"><section class="p-box p-includes" aria-labelledby="p-have"><h3 id="p-have">Lo que tienes</h3><ul>${FEATURES.map(f=>`<li><span aria-hidden="true">${f.available?'✓':'…'}</span><div><strong>${f.title}${f.available?'':' <em>Próximamente</em>'}</strong><p>${f.text}</p>${f.available&&f.href&&context.authenticated?`<a class="p-go" href="${f.href}">${f.action}</a>`:''}</div></li>`).join('')}</ul></section>${free()}</aside></div>`;
    root().querySelector('#p-cancel')?.addEventListener('click',()=>{askCancel=true;render();root().querySelector('#p-keep').focus();});
    const close=()=>{askCancel=false;render();root().querySelector('#p-cancel')?.focus();};
    root().querySelector('#p-keep')?.addEventListener('click',close);
    root().querySelector('.p-confirm')?.addEventListener('keydown',event=>{if(event.key==='Escape'&&!busy)close();});
    root().querySelector('#p-confirm-cancel')?.addEventListener('click',async()=>{
      busy=true;render();
      try{const result=await api({action:'cancel'});info.premium=result.premium;askCancel=false;busy=false;render();}
      catch{busy=false;render();const box=root().querySelector('#p-error');if(box){box.textContent='No pudimos cancelar ahora. Tu suscripción sigue igual; intenta de nuevo en un momento.';box.hidden=false;}}
    });
  }
  function renderConfirming(pendingTooLong) {
    root().innerHTML=pendingTooLong?`<div class="p-box p-pending"><h1>Todavía no lo vemos</h1><p class="lead">Recurrente aún no nos confirma el pago. No se te cobró dos veces: no vuelvas a pagar. Vuelve a revisar en un minuto.</p><div class="button-row"><button type="button" id="p-recheck" class="p-cta"><span>Revisar de nuevo</span></button><a class="outline" href="./cuenta.html">Ir a mi perfil</a></div></div>`
      :`<div class="p-box p-wait" role="status" aria-live="polite"><div class="p-bar"><span></span></div><h1>Confirmando tu pago…</h1><p class="lead">Puede tardar unos segundos mientras Recurrente nos avisa. Si cierras esta pestaña no pasa nada: lo verás aquí al volver.</p></div>`;
    root().querySelector('#p-recheck')?.addEventListener('click',()=>startConfirming());
  }
  function renderSuccess() {
    const s=info.premium, p=PLANS[s.plan]||PLANS.monthly, end=day(s.currentPeriodEnd);
    root().innerHTML=`<div class="p-success"><span aria-hidden="true">✓</span><h1>¡Ya eres premium!</h1><p>Gracias por apoyar Smash GT. Tu plan ${p.name.toLowerCase()} de ${p.amount} USD ${p.each} queda activo${end?`; el próximo cobro es el ${end}`:''}.</p><div class="button-row"><a class="outline dark" href="./analisis.html">Analizar un rival →</a><button type="button" id="p-see" class="outline dark">Ver mi suscripción</button></div></div>`;
    root().querySelector('#p-see').addEventListener('click',()=>{arrival=null;render();});
  }
  function render() {
    if(!info){root().innerHTML='<div class="p-box p-wait" role="status"><div class="p-bar"><span></span></div><p class="note">Consultando tu suscripción…</p></div>';return;}
    if(info==='error'){root().innerHTML=notice('error','×','No pudimos consultar tu suscripción.','No cambiamos nada ni hicimos ningún cobro. Vuelve a intentarlo en un momento.','<button type="button" id="p-retry" class="outline">Reintentar</button>');root().querySelector('#p-retry').addEventListener('click',show);return;}
    const s=info.premium;
    if(s?.premium&&arrival==='paid'){renderSuccess();return;}
    if(s?.premium){renderManage();return;}
    if(confirming||arrival==='slow'){renderConfirming(arrival==='slow');return;}
    const ended=s&&s.status==='ended';
    renderPlans(arrival==='canceled'?notice('muted','←','Cancelaste el pago en Recurrente.','No se hizo ningún cobro. Puedes intentarlo de nuevo cuando quieras.')
      :ended?notice('info','♥','Gracias por haber apoyado.',`Tu premium terminó${day(s.currentPeriodEnd)?` el ${day(s.currentPeriodEnd)}`:''}. Si quieres volver, aquí están los planes.`):'');
  }
  async function load() {
    try{info=await api();if(info.premium?.plan&&PLANS[info.premium.plan]&&!info.premium.premium)plan=info.premium.plan;context.onStatus?.(info.premium?.premium===true);}
    catch{info='error';}
  }
  // Back from Recurrente: the address only says «look again»; the answer is the server's.
  async function startConfirming() {
    confirming=true;arrival=null;render();
    for(let attempt=0;attempt<10;attempt++){
      await load();
      if(info==='error')break;
      if(info.premium?.premium){confirming=false;arrival='paid';render();return;}
      await new Promise(resolve=>{timer=setTimeout(resolve,3000);});
    }
    confirming=false;if(info!=='error')arrival='slow';render();
  }
  async function show() {
    clearTimeout(timer);
    const hash=location.hash;
    if(hash==='#premium-pago'||hash==='#premium-cancelado')history.replaceState(null,'','./cuenta.html#premium');
    info=null;render();
    if(!context.authenticated){await load();render();return;}
    if(hash==='#premium-pago'){startConfirming();return;}
    arrival=hash==='#premium-cancelado'?'canceled':null;
    await load();render();
  }
  // Quiet check from other tabs, only to show the badge.
  async function peek(){try{const result=await api();context.onStatus?.(result.premium?.premium===true);}catch{}}
  return {setContext,show,peek};
})();
