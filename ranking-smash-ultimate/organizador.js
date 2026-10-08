/* «Mis torneos» tab of the account: the organizer's own top, its tournaments and its public link.
   Everything shown comes from organizador-api.php; nothing here decides whose tournament it is,
   who is premium or how many points anyone has. */
const SmashOrganizador = (() => {
  const MONTHS=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
  const WHY={doubles:['Dobles','es de dobles u otro formato. El top solo usa singles de Smash Ultimate.'],
    format:['Otro formato','es online. El top solo usa torneos presenciales de singles.'],
    no_sets:['Sin sets','no tiene sets válidos (DQ, byes o resultados sin marcador).'],
    out_of_season:['Fuera de temporada',year=>`se jugó fuera de la temporada ${year} (1 de enero al 31 de diciembre).`],
    small:['Menos de 20 activos','tuvo menos de 20 jugadores activos. El top usa los mismos torneos que entran al ranking nacional.'],
    unfinished:['Sin terminar','start.gg todavía no lo marca como terminado. Entrará con el corte siguiente a su cierre.'],
    excluded:['Fuera del ranking','quedó fuera del ranking nacional tras una revisión manual.']};
  const REVIEW={sent:['info','⏳','Revisión enviada.','La revisamos a mano. Verás el resultado aquí; no tienes que hacer nada más.'],
    approved:['ok','✓','Revisión aprobada.','Comprobamos que eres administrador del torneo en start.gg. Ya cuenta para tu top.'],
    rejected:['error','×','Revisión rechazada.','']};
  const ERRORS={invalid_tournament_url:'Pega un enlace de start.gg (https://www.start.gg/tournament/...).',invalid_already_yours:'Ese torneo ya aparece a tu nombre en la lista.',
    invalid_already_sent:'Ya pediste revisión de ese torneo. Verás el resultado en la lista.',invalid_claim_limit:'Tienes varias revisiones en espera. Cuando se resuelvan podrás pedir otra.',
    invalid_member_limit:'Ya llegaste al máximo de coorganizadores.',invalid_invite:'Esta invitación ya se usó o venció. Pide una nueva al organizador.',invalid_invite_own:'Esta invitación es tuya: compártela con tu coorganizador.',
    invalid_review_unknown_tournament:'Ese torneo no está en el catálogo de la captura: todavía no se puede aprobar.',invalid_review_message:'Escribe el motivo del rechazo (máximo 255 caracteres).',premium_required:'Esta acción necesita premium vigente.'};
  const root=()=>document.getElementById('organizer-screen');
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl=url=>{try{const u=new URL(url);return u.protocol==='https:'&&/(^|\.)start\.gg$/.test(u.hostname)?u.href:null;}catch{return null;}};
  const parts=iso=>/^\d{4}-\d{2}-\d{2}/.test(iso||'')?iso.slice(0,10).split('-').map(Number):null;
  const longDay=iso=>{const p=parts(iso);return p?`${p[2]} ${MONTHS[p[1]-1]} ${p[0]}`:'';};
  const shortDay=iso=>{const p=parts(iso);return p?`${String(p[2]).padStart(2,'0')}/${String(p[1]).padStart(2,'0')}/${p[0]}`:'';};
  // Stored instants are shown as Guatemala days (UTC−6, no daylight saving).
  const instantDay=iso=>{const t=Date.parse(iso);return Number.isNaN(t)?'':shortDay(new Date(t-21600000).toISOString());};
  const plural=(n,one,many)=>`${n} ${n===1?one:many}`;
  const number=n=>Number(n).toLocaleString('en-US');
  let context={csrf:'',authenticated:false,goTo:null}, info=null, organizer=null, open=-1, busy=false, flash={}, inviteUrl=null, invitation=null;
  function setContext(next){context={...context,...next};}
  async function api(body=null) {
    const controller=new AbortController(), stop=setTimeout(()=>controller.abort(),20000);
    const query=new URLSearchParams();
    if(!body&&organizer)query.set('organizador',organizer);
    if(!body&&invitation)query.set('invita',invitation);
    try {
      const response=await fetch(`./organizador-api.php${query.size?`?${query}`:''}`,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,
        headers:body?{'Content-Type':'application/json','X-CSRF-Token':info?.csrf||context.csrf}:{Accept:'application/json'},body:body?JSON.stringify({...body,organizer:body.organizer??organizer??undefined}):undefined});
      const json=await response.json();
      if(!response.ok||json.ok!==true){const error=new Error(json.reason||'organizer_unavailable');error.status=response.status;throw error;}
      return json;
    } finally {clearTimeout(stop);}
  }
  const notice=(kind,glyph,title,text,extra='')=>`<div class="p-notice ${kind}" role="${kind==='error'?'alert':'status'}"><span aria-hidden="true">${glyph}</span><div><strong>${title}</strong><p>${text}</p>${extra}</div></div>`;
  const said=key=>flash[key]?`<p class="o-said ${flash[key][0]}" role="${flash[key][0]==='bad'?'alert':'status'}">${escape(flash[key][1])}</p>`:`<p class="o-said" role="status" aria-live="polite"></p>`;
  const icon=id=>{const c=id&&typeof CHARACTER_CATALOG!=='undefined'?CHARACTER_CATALOG.find(x=>x.characterId===String(id)):null;
    return c?`<img src="${escape(c.icon)}" alt="${escape(c.name)}" width="30" height="30" loading="lazy">`:'<span title="Sin personaje registrado">—</span>';};
  const charName=id=>{const c=id&&typeof CHARACTER_CATALOG!=='undefined'?CHARACTER_CATALOG.find(x=>x.characterId===String(id)):null;return c?c.name:'Sin personaje registrado';};

  function gate(kind) {
    const expired=kind==='expired'?instantDay(info.expiredAt):'';
    const G={login:['→','blue','Entra con start.gg','Primero vincula tu cuenta. Así sabemos qué torneos registra start.gg a tu nombre. Tu contraseña se escribe en start.gg, no aquí.','Continuar con start.gg ↗','Ver el ranking nacional no requiere cuenta.'],
      interest:['+','blue','Marca «Organizador» en tu perfil','Esta pestaña es para quienes organizan torneos. Márcalo en Mi perfil, en «¿Qué te interesa?», y vuelve aquí.','Ir a Mi perfil','Marcarlo es solo un interés: lo que decide qué torneos son tuyos es start.gg, no lo que marques aquí.'],
      premium:['★','yellow','Disponible con premium','El top de tus torneos es parte de premium, junto al análisis de rival. Es un apoyo para que el sitio se sostenga.','Apoyar con 3 USD al mes o 24 USD al año','El cobro ocurre en Recurrente. Puedes cancelar cuando quieras desde la pestaña Premium.'],
      expired:['!','yellow','Renueva para volver a verlo','Tu top se sigue calculando con cada corte. Al renovar lo ves de nuevo y tu enlace público vuelve a funcionar.','Renovar premium','El cobro ocurre en Recurrente. Puedes cancelar cuando quieras desde la pestaña Premium.']}[kind];
    const member=info.role==='member';
    const button=kind==='login'?`<form action="./oauth.php" method="post" id="o-login"><input type="hidden" name="csrf" value="${escape(info.csrf||context.csrf)}"><button type="submit" class="p-cta blue"><span>${G[4]}</span></button></form>`
      :member?'':`<button type="button" class="p-cta ${G[1]==='blue'?'blue':''}" data-act="${kind==='interest'?'profile':'premium'}"><span>${G[4]}</span></button>`;
    return `${kind==='expired'?notice('warn','!',`${member?'El premium del organizador':'Tu premium'} venció${expired?` el ${expired}`:''}.`,`${member?'Su top y su':'Tu top y tu'} enlace público quedan en pausa. No se borra nada: al renovar vuelven igual, con el mismo enlace.`):''}
      <div class="p-hero"><p class="kicker yellow">Mis torneos · Premium</p><h1>El top<br><span>de tus torneos.</span></h1><p class="lead">Un ranking aparte, solo con los torneos que organizas en start.gg. Lo ves aquí y lo compartes con un enlace en tus redes. No reemplaza ni cambia el ranking nacional.</p></div>
      <div class="p-columns"><section class="p-box o-gate ${G[1]}" aria-labelledby="o-gate-title"><span class="o-glyph" aria-hidden="true">${G[0]}</span><h2 id="o-gate-title">${member&&kind!=='login'?'El organizador necesita premium':G[2]}</h2>
          <p>${member&&kind!=='login'?'El premium del organizador cubre a su equipo. Cuando lo active o lo renueve, verás aquí su top.':G[3]}</p>${button}<p class="note">${member&&kind!=='login'?'No necesitas pagar tú.':G[5]}</p></section>
        <aside class="p-side"><section class="p-box"><h3>Qué verás</h3><ol class="o-steps"><li>Tus torneos del año y por qué cada uno cuenta o no.</li><li>El top 5, 10 o 15 con puntos, sets y torneos jugados contigo.</li><li>El detalle de cada jugador en tus torneos.</li><li>Un enlace público para compartir, que activas o desactivas.</li></ol>
          <p class="o-principle"><strong>Pagar no da puntos ni cambia puestos</strong>, ni en este top ni en el nacional. El ranking nacional, tu perfil y tu historial siguen gratis.</p></section></aside></div>`;
  }

  function invitationBox() {
    const i=info?.invite; if(!invitation||!i)return '';
    if(!i.valid)return notice('muted','○','Esta invitación ya no sirve.','Ya se usó o venció. Pide una nueva al organizador.','<button type="button" class="outline" data-act="invite-dismiss">Entendido</button>');
    if(!info.authenticated)return notice('info','+',`${escape(i.organizer)} te invitó como coorganizador.`,'Entra con start.gg para unirte a su equipo y ver su top.');
    if(i.own)return notice('info','i','Esta invitación es tuya.','Compártela con la persona que quieres sumar como coorganizador.','<button type="button" class="outline" data-act="invite-dismiss">Entendido</button>');
    if(i.member)return notice('ok','✓',`Ya eres coorganizador de ${escape(i.organizer)}.`,'No hace falta usar la invitación.','<button type="button" class="outline" data-act="invite-dismiss">Entendido</button>');
    return notice('info','+',`${escape(i.organizer)} te invitó como coorganizador.`,'Verás su top y sus torneos en esta pestaña. No recibes permisos en start.gg y puedes salir cuando quieras.',
      `<div class="button-row"><button type="button" class="p-cta blue o-inline" data-act="join" ${busy?'disabled':''}><span>Unirme al equipo</span></button><button type="button" class="outline" data-act="invite-dismiss">Ahora no</button></div>${said('join')}`);
  }

  function switcher() {
    const list=info.contexts||[]; if(list.length<2)return '';
    return `<div class="o-switch" role="group" aria-label="Organizador">${list.map(c=>`<button type="button" data-act="context" data-id="${escape(c.id)}" aria-pressed="${c.id===(organizer||list[0].id)}">${c.role==='owner'?'Mis torneos':escape(c.name)}</button>`).join('')}</div>`;
  }

  function reviewsBox() {
    const list=info.pendingReviews; if(!Array.isArray(list))return '';
    return `<section class="p-box o-admin" aria-labelledby="o-admin-title"><h3 id="o-admin-title">Revisiones por resolver · ${list.length}</h3><p class="note">Solo tú ves esto. Aprueba únicamente si comprobaste en start.gg que la cuenta administra el torneo.</p>
      ${list.length?`<ul>${list.map(r=>`<li><div><strong>${escape(r.organizer)}</strong> pide <a href="${escape(safeUrl(r.url)||'#')}" target="_blank" rel="noopener noreferrer">${escape(r.tournament||r.url.replace('https://www.start.gg/tournament/',''))} ↗</a><span class="note">${shortDay(r.sentAt)}${r.inCatalog?'':' · no está en el catálogo de la captura'}</span></div>
        <label class="sr-only" for="o-why-${escape(r.id)}">Motivo si rechazas</label><input id="o-why-${escape(r.id)}" type="text" maxlength="255" placeholder="Motivo si rechazas">
        <div class="button-row"><button type="button" class="outline" data-act="resolve" data-id="${escape(r.id)}" data-approve="1" ${r.inCatalog?'':'disabled'}>Aprobar</button><button type="button" class="outline" data-act="resolve" data-id="${escape(r.id)}">Rechazar</button></div></li>`).join('')}</ul>`:'<p>No hay revisiones en espera.</p>'}${said('resolve')}</section>`;
  }

  function topRow(r,i,name) {
    const isOpen=open===i, d=r.detail||{events:[],opponents:[]};
    return `<li><button type="button" class="o-row ${i===0?'first':i<3?'podium':''}" data-act="row" data-index="${i}" aria-expanded="${isOpen}" aria-controls="o-det-${i}">
        <span class="o-rank"><span class="sr-only">Puesto </span>${r.rank}</span><span class="o-icon">${icon(r.mainCharId)}</span>
        <span class="o-who"><b>${escape(r.alias)}</b><small>${r.setsWon}–${r.setsLost} en sets · ${plural(r.events,'torneo','torneos')}</small></span>
        <span class="o-pts"><b>${number(r.points)}</b><small>pts</small></span><span class="o-arrow" aria-hidden="true">${isOpen?'▴':'▾'}</span></button>
      ${isOpen?`<div id="o-det-${i}" class="o-detail"><div class="o-figures"><span><b>${r.setsWon}–${r.setsLost}</b>sets con ${escape(name)}</span><span><b>${r.events}</b>${r.events===1?'torneo jugado':'torneos jugados'}</span><span><b class="small">${escape(charName(r.mainCharId))}</b>personaje más usado</span></div>
        <h4>Sus torneos contigo</h4>${d.events.map(e=>{const url=safeUrl(e.url);return `<${url?`a href="${escape(url)}" target="_blank" rel="noopener noreferrer"`:'div'} class="o-played"><span><b>${escape(e.name)}${url?' ↗':''}</b><small>${longDay(e.date)}</small></span><strong>${e.won}–${e.lost}</strong></${url?'a':'div'}>`;}).join('')}
        ${d.opponents.length?`<h4>Contra quién jugó</h4><div class="o-rivals">${d.opponents.map(v=>`<span><b>${escape(v.alias)}</b><strong class="${v.won>v.lost?'up':v.won<v.lost?'down':''}">${v.won}–${v.lost}</strong><small>${v.won>v.lost?'a favor':v.won<v.lost?'en contra':'parejo'}</small></span>`).join('')}</div>`:''}</div>`:''}</li>`;
  }

  function tournament(t,season,canAsk) {
    const counts=t.status==='counts', pending=t.status==='unconfirmed', why=WHY[t.reason]||WHY.excluded, url=safeUrl(t.url);
    const text=pending?'Por confirmar: start.gg no te muestra como dueño de este torneo; puede que seas coorganizador. Si lo organizaste, pide revisión y lo comprobamos.':`No cuenta: ${typeof why[1]==='function'?why[1](season):why[1]}`;
    const meta=[longDay(t.date),t.place].filter(Boolean).join(' · ');
    const nums=t.activePlayers===null?'':t.validSets===null?`${t.activePlayers} activos`:`${t.activePlayers} activos · ${plural(t.validSets,'set válido','sets válidos')}`;
    const rev=t.review&&REVIEW[t.review.status];
    return `<li class="o-tour ${counts?'counts':pending?'pending':'out'}"><div class="o-tour-name">${url?`<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(t.name)} ↗</a>`:`<b>${escape(t.name)}</b>`}${meta?`<small>${escape(meta)}</small>`:''}</div>
      ${nums?`<span class="o-tour-nums">${nums}</span>`:''}<span class="o-state"><span aria-hidden="true">${counts?'✓':pending?'?':'×'}</span>${counts?'Cuenta':pending?'Por confirmar':`No cuenta · ${why[0]}`}</span>
      ${counts?'':`<p>${text}</p>`}
      ${pending&&canAsk&&t.review?.status==='rejected'&&url?`<button type="button" class="o-ask" data-act="review" data-url="${escape(url)}" ${busy?'disabled':''}>Pedir revisión</button>`:''}
      ${rev?`<p class="o-review ${rev[0]}" role="status"><span aria-hidden="true">${rev[1]}</span><span><strong>${rev[2]}</strong> ${escape(t.review.status==='rejected'?(t.review.message||''):rev[3])}</span></p>`:''}</li>`;
  }

  function dataView() {
    const d=info.data, o=d.organizer, s=d.summary, owner=info.role==='owner', name=o.name, n=s.eventsCounted, size=o.topSize;
    const period=s.periodFrom?`${shortDay(s.periodFrom)} – ${shortDay(s.periodTo)}`:'', cut=s.cutDate?`Corte del ${shortDay(s.cutDate)}`:'';
    const shownUrl=(info.publicUrl||'').replace('https://','');
    const head=`<div class="p-hero small o-head"><p class="kicker yellow">Top del organizador · Temporada ${d.seasonYear}</p><h1>Top ${size}<br><span>${escape(name)}</span></h1>
      ${n?`<div class="o-chips"><span>${period}</span><span>${n===1?'1 torneo que cuenta':`${n} torneos que cuentan`}</span><span class="dim">${cut}</span></div>`:''}
      <p class="o-info"><span aria-hidden="true">i</span><span><strong>No es el ranking nacional de Smash GT.</strong> Usa solo los torneos de ${escape(name)}, así que un jugador puede ser #3 aquí y #40 en el nacional.</span></p>
      ${owner?'':`<p class="note">Eres coorganizador de ${escape(name)}. <button type="button" class="o-link" data-act="leave">Salir del equipo</button></p>`}</div>`;
    const stale=s.isStale?notice('muted','↻',`Actualizado con el corte del ${shortDay(s.cutDate)}.`,'El corte de esta semana aún no se procesa. Los torneos posteriores aparecerán cuando termine.'):'';
    const empty=!d.events.length?`<section class="p-box o-empty" role="status"><span class="o-glyph" aria-hidden="true">?</span><h2>No encontramos torneos a tu nombre</h2><p>Buscamos torneos de Smash Ultimate de ${d.seasonYear} donde tu cuenta de start.gg aparece como dueña. No encontramos ninguno, así que todavía no hay top.</p>
        <ol class="o-steps"><li>Si eres coorganizador o el torneo está en la cuenta de otra persona, pide revisión con el enlace del torneo.</li><li>Si acabas de terminar un torneo, aparecerá con el siguiente corte del domingo.</li><li>Revisa que hayas entrado con la misma cuenta de start.gg con la que creas los torneos.</li></ol></section>`
      :`<section class="p-box o-empty" role="status"><span class="o-glyph" aria-hidden="true">×</span><h2>Ninguno de tus torneos cuenta todavía</h2><p>Encontramos ${plural(d.events.length,'torneo','torneos')} a tu nombre, pero ninguno cumple las reglas, así que todavía no hay top. Abajo verás el motivo de cada uno.</p>
        <ul class="o-steps plain"><li>Cuentan torneos presenciales de singles de Smash Ultimate de ${d.seasonYear} que también entran al ranking nacional.</li><li>Cuando un torneo tuyo cuente, el top aparece con el siguiente corte del domingo.</li></ul></section>`;
    const small=n>0&&n<3?`<div class="p-notice warn o-small" role="note"><span aria-hidden="true">≈</span><div><strong>Muestra pequeña: este top sale de solo ${n===1?'1 torneo':'2 torneos'}.</strong><p>Con pocos torneos, un par de sets cambian mucho los puestos. Tómalo como una foto del momento; se vuelve más confiable con cada torneo que organices.</p></div></div>`:'';
    const sizes=owner?`<div class="o-sizes" role="group" aria-label="Tamaño del top">${d.sizes.map(v=>`<button type="button" data-act="size" data-size="${v}" aria-pressed="${v===size}" ${busy?'disabled':''}>Top ${v}</button>`).join('')}</div>`:'';
    const few=d.top.length<size&&d.top.length>0?`<p class="note">Hay ${plural(d.top.length,'jugador','jugadores')} con sets suficientes: el top muestra los que hay.</p>`:'';
    const top=n?`${small}<div class="p-columns o-columns"><section class="o-top" aria-labelledby="o-top-title"><div class="o-top-head"><h2 id="o-top-title">Top ${size}</h2>${sizes}</div>${said('size')}
        <p class="o-min"><strong>Para aparecer:</strong> ${escape(d.minRule)}</p>
        ${d.top.length?`<p class="note">Toca un jugador para ver su detalle.</p><ol class="o-list">${d.top.map((r,i)=>topRow(r,i,name)).join('')}</ol>${few}`:'<p>Todavía ningún jugador tiene sets suficientes.</p>'}
        ${d.rest.length?`<details class="o-rest"><summary>Ver la lista completa · ${plural(d.rest.length,'jugador más','jugadores más')}<span aria-hidden="true">▾</span></summary><ol start="${size+1}">${d.rest.map(x=>`<li><span>${x.rank}</span><span><b>${escape(x.alias)}</b><small>${x.setsWon}–${x.setsLost} en sets · ${plural(x.events,'torneo','torneos')}</small></span><strong>${number(x.points)}</strong></li>`).join('')}</ol></details>`:''}</section>
      <div class="p-side"><section class="p-box" aria-labelledby="o-sum"><h3 id="o-sum">Resumen</h3><dl class="o-sum"><div><dd>${n}</dd><dt>${n===1?'torneo cuenta':'torneos cuentan'}</dt></div><div><dd>${s.distinctPlayers}</dd><dt>jugadores distintos</dt></div><div><dd>${s.validSets}</dd><dt>sets válidos</dt></div></dl>
          <p class="note">Periodo cubierto: ${period}. ${cut}. Solo torneos de ${escape(name)}.</p></section>
        ${info.publicUrl?`<section class="p-box o-public ${o.publicEnabled?'on':''}" aria-labelledby="o-pub"><div class="o-pub-head"><h3 id="o-pub">Enlace público</h3>${owner?`<button type="button" role="switch" aria-checked="${o.publicEnabled}" aria-labelledby="o-pub" data-act="public" ${busy?'disabled':''}><span aria-hidden="true"></span></button>`:''}</div>
          <p class="o-pub-state" role="status"><span aria-hidden="true">${o.publicEnabled?'●':'○'}</span>${o.publicEnabled?'Activado: cualquiera con el enlace puede verlo':'Desactivado: nadie puede abrirlo'}</p>
          <p>${o.publicEnabled?`Muestra el top ${size}, el resumen y los torneos usados. No muestra datos de contacto ni tu cuenta.`:'Al activarlo vuelve a funcionar la misma dirección; no hace falta compartir uno nuevo.'}</p>
          <div class="o-url">${escape(shownUrl)}</div><div class="button-row"><button type="button" class="p-cta blue o-inline" data-act="copy" data-copy="${escape(info.publicUrl)}" ${o.publicEnabled?'':'disabled'}><span>${flash.copy?'✓ Copiado':'Copiar enlace'}</span></button>${o.publicEnabled?`<a class="outline" href="${escape(info.publicUrl)}" target="_blank" rel="noopener">Ver página pública ↗</a>`:''}</div>${said('public')}</section>`:''}
        ${owner?teamBox():''}</div></div>`:empty;
    const counted=d.events.length?`${plural(d.events.length,'encontrado','encontrados')} · ${n===1?'1 cuenta':`${n} cuentan`}`:'0 encontrados';
    const list=`<section class="o-tours" aria-labelledby="o-tor"><div class="o-top-head"><h2 id="o-tor">Mis torneos ${d.seasonYear}</h2><span class="note">${counted}</span></div>
      <p class="lead">Mostramos los torneos de Smash Ultimate que start.gg registra a nombre de ${owner?'tu cuenta':escape(name)}. Marcar «Organizador» en tu perfil es solo un interés: lo que decide qué torneos son tuyos es start.gg.</p>
      <ul>${d.events.map(t=>tournament(t,d.seasonYear,true)).join('')}</ul>
      <details class="o-rest o-missing" ${d.events.length?'':'open'}><summary>¿Falta un torneo tuyo? Pide revisión<span aria-hidden="true">＋</span></summary><form id="o-missing"><label for="o-miss-url">Pega el enlace del torneo en start.gg. Revisamos que tu cuenta sea dueña o administradora del torneo; no basta con decir que lo organizaste.</label>
        <div><input id="o-miss-url" type="url" required maxlength="300" placeholder="https://www.start.gg/tournament/..."><button type="submit" ${busy?'disabled':''}>Enviar</button></div>${said('review')}</form></details></section>`;
    return `${head}${stale}${top}${n?'':(owner?teamBox(true):'')}${list}`;
  }

  function teamBox(wide=false) {
    const members=info.members||[];
    return `<section class="p-box o-team ${wide?'wide':''}" aria-labelledby="o-team"><h3 id="o-team">Coorganizadores</h3><p>Suma a quienes organizan contigo. Ven este top y tus torneos; tu premium los cubre. No reciben permisos en start.gg ni pueden cambiar tu enlace.</p>
      ${members.length?`<ul>${members.map(m=>`<li><span><b>${escape(m.name)}</b><small>desde el ${shortDay(m.since)}</small></span><button type="button" class="o-link" data-act="remove" data-id="${escape(m.id)}" data-name="${escape(m.name)}">Quitar</button></li>`).join('')}</ul>`:'<p class="note">Todavía no agregas a nadie.</p>'}
      ${inviteUrl?`<div class="o-url">${escape(inviteUrl.replace('https://',''))}</div><div class="button-row"><button type="button" class="p-cta blue o-inline" data-act="copy" data-copy="${escape(inviteUrl)}" data-key="copyInvite"><span>${flash.copyInvite?'✓ Copiado':'Copiar invitación'}</span></button></div><p class="note">Envíasela a una sola persona: sirve una vez y vence en 7 días. Crear otra anula esta.</p>`
        :`<button type="button" class="outline" data-act="invite" ${busy?'disabled':''}>Crear invitación</button>`}${said('team')}</section>`;
  }

  function render() {
    const node=root(); if(!node)return;
    if(!info){node.innerHTML='<div class="p-box p-wait" role="status" aria-live="polite"><div class="p-bar"><span></span></div><p class="note">Buscando tus torneos…</p></div>';return;}
    if(info==='error'){node.innerHTML=notice('error','×','No pudimos cargar tus torneos.','No cambiamos nada. Tu enlace público sigue como estaba. Vuelve a intentarlo en un momento.','<button type="button" class="outline" data-act="retry">Reintentar</button>');return;}
    const body=!info.authenticated?gate('login'):info.state==='data'?dataView():gate(info.state);
    node.innerHTML=`${invitationBox()}${info.authenticated?switcher():''}${body}${info.authenticated?reviewsBox():''}`;
  }

  async function load(){try{info=await api();}catch{info='error';}}
  async function act(key,body,after) {
    if(busy)return; busy=true; flash={}; render();
    try{const result=await api(body); await after?.(result); await load();}
    catch(error){flash[key]=['bad',ERRORS[error.message]||'No pudimos guardar el cambio. Intenta de nuevo en un momento.'];}
    busy=false; render();
  }
  function clearInvitation(){invitation=null;const url=new URL(location.href);url.searchParams.delete('invita');history.replaceState(null,'',url.pathname+url.search+url.hash);}

  function onClick(event) {
    const button=event.target.closest('[data-act]'); if(!button||button.disabled)return;
    const a=button.dataset.act, d=info?.data;
    if(a==='retry')show();
    else if(a==='profile'||a==='premium')context.goTo?.(a);
    else if(a==='row'){const i=Number(button.dataset.index);open=open===i?-1:i;render();root().querySelector(`[data-act=row][data-index="${i}"]`)?.focus();}
    else if(a==='context'){organizer=button.dataset.id;open=-1;inviteUrl=null;flash={};show();}
    else if(a==='size')act('size',{action:'settings',topSize:Number(button.dataset.size)},()=>{open=-1;});
    else if(a==='public')act('public',{action:'settings',publicEnabled:!d.organizer.publicEnabled});
    else if(a==='copy'){const key=button.dataset.key||'copy';navigator.clipboard?.writeText(button.dataset.copy).then(()=>{flash={[key]:true,[key==='copy'?'public':'team']:['ok','Enlace copiado al portapapeles.']};render();setTimeout(()=>{if(flash[key]){flash={};render();}},2400);}).catch(()=>{flash={[key==='copy'?'public':'team']:['bad','No pudimos copiarlo. Selecciona la dirección y cópiala a mano.']};render();});}
    else if(a==='invite')act('team',{action:'invite'},result=>{inviteUrl=result.inviteUrl;});
    else if(a==='remove'){if(confirm(`¿Quitar a ${button.dataset.name} de tus coorganizadores? Dejará de ver tu top.`))act('team',{action:'removeMember',member:button.dataset.id});}
    else if(a==='leave'){if(confirm('¿Salir del equipo de este organizador? Dejarás de ver su top.'))act('team',{action:'leave'},()=>{organizer=null;});}
    else if(a==='review')act('review',{action:'review',url:button.dataset.url},()=>{flash.review=['ok','✓ Revisión enviada. Verás el resultado en esta lista.'];});
    else if(a==='join')act('join',{action:'join',token:invitation,organizer:null},result=>{organizer=result.organizer;clearInvitation();});
    else if(a==='invite-dismiss'){clearInvitation();render();}
    else if(a==='resolve'){const approve=button.dataset.approve==='1', message=root().querySelector(`#o-why-${CSS.escape(button.dataset.id)}`)?.value||'';
      if(!approve||confirm('¿Aprobar? El torneo contará para el top de esta cuenta.'))act('resolve',{action:'resolve',claim:button.dataset.id,approve,message});}
  }
  function onSubmit(event) {
    if(event.target.id==='o-login'){try{sessionStorage.setItem('smashgt.volver','torneos');if(invitation)sessionStorage.setItem('smashgt.invita',invitation);}catch{}return;}
    if(event.target.id!=='o-missing')return;
    event.preventDefault();
    const url=root().querySelector('#o-miss-url').value.trim();
    if(!/^https:\/\/(www\.)?start\.gg\/tournament\//i.test(url)){flash={review:['bad',ERRORS.invalid_tournament_url]};render();root().querySelector('.o-missing').open=true;root().querySelector('#o-miss-url').value=url;root().querySelector('#o-miss-url').focus();return;}
    act('review',{action:'review',url}).then(()=>{if(!flash.review)flash.review=['ok','✓ Revisión enviada. Verás el resultado en esta lista.'];render();const box=root().querySelector('.o-missing');if(box)box.open=true;});
  }
  let wired=false;
  async function show() {
    if(!wired&&root()){root().addEventListener('click',onClick);root().addEventListener('submit',onSubmit);wired=true;}
    const fromUrl=new URLSearchParams(location.search).get('invita');
    let kept=null; try{kept=sessionStorage.getItem('smashgt.invita');sessionStorage.removeItem('smashgt.invita');}catch{}
    const token=fromUrl||kept; if(/^[a-f0-9]{48}$/.test(token||''))invitation=token;
    info=null;render();await load();render();
  }
  return {setContext,show};
})();
