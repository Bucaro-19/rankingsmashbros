/* «Prepara el set»: the deep rival analysis. Every figure comes from analisis-api.php (field `deep`);
   this file only lays it out. Nothing is estimated or filled in here: no data is shown as «—» with its reason. */
(() => {
  const root=document.getElementById('pr-root');
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const bySlug=slug=>CHARACTER_CATALOG.find(c=>c.slug===slug);
  const name=slug=>bySlug(slug)?.name||'Personaje no registrado';
  const icon=(slug,size=36)=>{const c=bySlug(slug);return c?`<img src="${escape(c.icon)}" alt="" width="${size}" height="${size}" loading="lazy">`:'<span aria-hidden="true">?</span>';};
  const plural=(n,one,many)=>`${n} ${n===1?one:many}`;
  const sum=pair=>pair?pair[0]+pair[1]:0;
  const rec=pair=>`${pair[0]}–${pair[1]}`;
  const params=new URLSearchParams(location.search);
  const scope=params.get('scope')==='gt'?'gt':'intl', rivalId=/^[1-9][0-9]{0,19}$/.test(params.get('rival')||'')?params.get('rival'):null;
  const SCOPES={gt:'Solo Guatemala',intl:'+ Internacional'};
  const SECTIONS=[['counters','Counters para ti','Hasta 5 personajes que suelen irle bien contra su main, con la muestra de cada uno.'],
    ['evita','Mejor evita','Personajes que, según los datos, tienden a sufrir contra su main.'],
    ['herramientas','Tus herramientas contra él','Tu movimiento más rápido, tus opciones fuera del escudo y qué puedes castigar.'],
    ['le-cuesta','Le cuesta contra','Contra qué personajes tiene peor y mejor récord en games.'],
    ['el-set','Cómo juega el set','Primer game, game decisivo, sets cerrados y qué hace después de perder un game.'],
    ['en-comun','Rivales en común','Jugadores que ambos enfrentaron, con el récord de cada uno.'],
    ['nivel','Contra qué nivel rinde','Su récord contra el top 10, el top 11–30 y el resto del ranking.']];
  const back=document.getElementById('pr-back');
  if(rivalId)back.href=`./analisis.html?rival=${rivalId}${scope==='gt'?'&scope=gt':''}`;
  let data=null;

  const head=(n,kicker,title,lead)=>`<header class="pr-head"><p class="pr-kicker">${n} · ${kicker}</p><h2>${title}</h2>${lead?`<p>${lead}</p>`:''}</header>`;
  const empty=text=>`<p class="pr-empty"><span aria-hidden="true">—</span> ${text}</p>`;
  const small=(strong,text)=>`<p class="pr-small" role="note"><span aria-hidden="true">≈</span><span><strong>${strong}</strong> ${text}</span></p>`;
  const noChars=()=>{const r=data.deep.rival;return `start.gg no registró personajes en los sets de ${escape(data.rival.tag)} (${r.coveredSets} de ${r.totalSets}), así que no podemos saber contra qué personajes le va mejor o peor.`;};
  const CONF={alta:['●●●','hi'],media:['●●○','mid'],baja:['●○○','low']};

  function card(c,good,main) {
    const conf=CONF[c.confidence]||CONF.baja, P=name(c.slug), M=name(main);
    const row=(label,value,sample)=>`<div class="pr-src"><span>${label}</span><span><b>${value}</b>${sample?`<small>${sample}</small>`:''}</span></div>`;
    const mine=c.mySets?row(`Tus sets con ${escape(P)} contra él`,rec(c.mySets),plural(sum(c.mySets),'set','sets')):row(`Tus sets con ${escape(P)} contra él`,'—',c.mine?'Nunca lo usaste contra él':'Sin sets con él todavía');
    const his=sum(c.hisGames)?row(`Su ${escape(M)} contra ${escape(P)} (sus games)`,rec(c.hisGames),plural(sum(c.hisGames),'game','games')):row(`Su ${escape(M)} contra ${escape(P)} (sus games)`,'—','Sin games registrados');
    const scene=sum(c.sceneGames)?row(`${escape(P)} contra ${escape(M)} en Guatemala`,rec(c.sceneGames),plural(sum(c.sceneGames),'game','games')):row(`${escape(P)} contra ${escape(M)} en Guatemala`,'—','Sin games registrados');
    return `<article class="pr-card ${good?'good':'avoid'}"><div class="pr-card-head"><span class="pr-icon big">${icon(c.slug,46)}</span><div><p class="pr-tags"><span>${good?'✓ Conviene':'× Mejor evita'}</span>${c.mine?'<span class="mine">★ Tu elegido</span>':''}</p><h3>${escape(P)}</h3></div>
        <span class="pr-conf ${conf[1]}"><span aria-hidden="true">${conf[0]}</span> ${c.confidence}</span></div>
      ${mine}${his}${scene}
      <p class="pr-basis">Confianza ${c.confidence} · basado en ${plural(sum(c.mySets),'set tuyo','sets tuyos')}, ${plural(sum(c.hisGames),'game suyo','games suyos')} y ${plural(sum(c.sceneGames),'game','games')} de la escena</p>
      <details class="pr-why"><summary>${good?'Por qué funciona':'Por qué cuesta'}</summary><div><p class="pr-guide-tag">Guía general del juego · no son datos del ranking</p>
        ${c.guide?`<p class="pr-guide">${escape(c.guide)}</p>`:`<p class="pr-guide none">— Todavía no tenemos guía para ${escape(P)} contra ${escape(M)}. Los datos de arriba siguen valiendo.</p>`}</div></details></article>`;
  }
  function cards(n,id,list,good) {
    const d=data.deep, main=d.rival.main, M=main?name(main):'main';
    const intro=good?'Hasta 5 personajes que suelen irle bien contra su main. Cada uno muestra de dónde sale y cuánta muestra tiene.':'Personajes que, según los datos, tienden a sufrir contra su main. No es un veto: si es tu personaje fuerte, puede seguir siendo tu mejor opción.';
    const weak=list.length&&list.every(c=>c.confidence==='baja');
    const body=!main?empty(noChars()):!list.length?empty(good?`Todavía no hay datos suficientes para recomendar un personaje contra su ${escape(M)}.`:`Los datos de este corte no señalan ningún personaje que sufra contra su ${escape(M)}.`)
      :`${weak?small('Muestra pequeña.','Estas recomendaciones salen de pocos datos. Tómalas como pista para probar, no como regla.'):''}<div class="pr-cards">${list.map(c=>card(c,good,main)).join('')}</div>`;
    return `<section id="${id}" class="pr-section">${head(n,`Contra su ${escape(M)}`,good?'Counters para ti':'Mejor evita',intro)}${body}</section>`;
  }
  function toolkit() {
    const d=data.deep, chosen=data.me.chosen||[], M=d.rival.main?name(d.rival.main):'main';
    const glossary=`<details class="pr-fold"><summary>Glosario: frame, fuera del escudo, ventaja</summary><dl><dt>Frame:</dt><dd>la unidad de tiempo del juego; hay 60 por segundo, así que «frame 3» pega a los 3/60 de segundo.</dd><dt>Fuera del escudo:</dt><dd>lo que puedes sacar justo después de bloquear; el frame ya incluye saltar o soltar el escudo.</dd><dt>Ventaja en escudo:</dt><dd>«−12 en escudo» significa que, tras chocar con tu escudo, el rival queda 12 frames sin poder actuar.</dd></dl></details>`;
    const sheets=chosen.length?chosen.map(slug=>`<article class="pr-sheet"><div class="pr-sheet-head"><span class="pr-icon">${icon(slug)}</span><h3>${escape(name(slug))} <small>contra su ${escape(M)}</small></h3></div>${empty(`Aún no hay ficha técnica de ${escape(name(slug))}. Sus resultados en las otras secciones siguen valiendo.`)}</article>`).join('')
      :empty('Elige tus personajes en <a href="./cuenta.html">tu cuenta</a> para ver aquí su ficha técnica.');
    return `<section id="herramientas" class="pr-section">${head(3,'Ficha técnica','Tus herramientas contra él',`Por cada uno de tus personajes elegidos: lo más rápido que tienes, qué sacar desde el escudo y qué golpes de su ${escape(M)} puedes castigar.`)}${glossary}${sheets}</section>`;
  }
  function vsChars() {
    const d=data.deep, r=d.rival, rv=escape(data.rival.tag);
    const rows=list=>list.map(x=>{const n=x.won+x.lost, few=n<5;return `<li><span class="pr-icon">${icon(x.slug)}</span><span class="pr-row-main"><b>${escape(name(x.slug))}</b><span class="pr-meter" aria-hidden="true"><span style="width:${Math.round(100*x.won/n)}%"></span></span><small class="${few?'few':''}">${few?`≈ ${plural(n,'game','games')} · menos de 5`:`${n} games · gana el ${Math.round(100*x.won/n)}%`}</small></span><span class="pr-rec"><b>${x.won}–${x.lost}</b><small>games</small></span></li>`;}).join('');
    const any=d.vsChars.hard.length||d.vsChars.good.length, few=[...d.vsChars.hard,...d.vsChars.good].some(x=>x.won+x.lost<5);
    const foot=`<p class="pr-note">Solo cuenta games con personaje registrado: ${r.coveredSets} de ${plural(r.totalSets,'set','sets')}.</p>`;
    if(!any)return `<section id="le-cuesta" class="pr-section">${head(4,`Récord de ${rv} en games`,'Le cuesta contra',`Personajes contra los que ${rv} tiene peor récord. Las cifras son sus games ganados–perdidos.`)}${empty(noChars())}</section>`;
    return `<section id="le-cuesta" class="pr-section">${head(4,`Récord de ${rv} en games`,'Le cuesta contra',`Personajes contra los que ${rv} tiene peor récord. Las cifras son sus games ganados–perdidos.`)}
      ${few?small('Algunas filas tienen menos de 5 games.','Un par de games más pueden cambiarlas; van marcadas con ≈.'):''}
      ${d.vsChars.hard.length?`<ul class="pr-rows hard">${rows(d.vsChars.hard)}</ul>`:empty(`En este corte no tiene récord negativo contra ningún personaje registrado.`)}
      <h3 class="pr-sub">Le va bien contra</h3>${d.vsChars.good.length?`<ul class="pr-rows good">${rows(d.vsChars.good)}</ul>`:empty('En este corte no tiene récord positivo contra ningún personaje registrado.')}${foot}</section>`;
  }
  function setPattern() {
    const p=data.deep.setPattern, rv=escape(data.rival.tag);
    const top=(lead)=>head(5,'Su récord por momento del set','Cómo juega el set',lead);
    if(!p)return `<section id="el-set" class="pr-section">${top('')}${empty('Sus sets de este corte no tienen marcador por game en start.gg, así que no sabemos cómo se repartieron los games.')}</section>`;
    const block=(title,pair,text)=>`<div class="pr-block ${sum(pair)?'':'none'}"><p>${title}</p>${sum(pair)?`<b>${rec(pair)}</b><small>${text}</small>`:'<b>—</b><small>Sin sets así registrados</small>'}</div>`;
    const a=p.afterLoss, moved=a.total-a.kept;
    const after=a.total?`<div class="pr-bar2" role="img" aria-label="Mantiene personaje ${a.kept} de ${a.total} veces; cambia ${moved} de ${a.total}"><span class="keep" style="flex:${a.kept}"></span><span class="move" style="flex:${moved}"></span></div>
        <ul class="pr-legend"><li><span class="keep" aria-hidden="true"></span>Mantiene personaje ${a.kept} de ${plural(a.total,'vez','veces')}</li><li><span class="move" aria-hidden="true"></span>${moved?`Cambia ${moved} de ${plural(a.total,'vez','veces')} → ${a.switched.map(s=>`${escape(name(s.slug))} (${s.n})`).join(', ')}`:`Cambia 0 de ${plural(a.total,'vez','veces')}: no cambió nunca`}</li></ul>
        <p class="pr-note">Basado en ${plural(a.total,'game perdido','games perdidos')} con personaje registrado en el siguiente${a.total<5?' · ≈ muestra pequeña':''}</p>`
      :empty('No hay games perdidos con personaje registrado en el siguiente game, así que no sabemos si cambia.');
    return `<section id="el-set" class="pr-section">${top(`Basado en ${plural(p.setsScored,'set','sets')} de ${rv} con marcador${p.setsWithScores<p.setsScored?`; ${p.setsWithScores} con el detalle de cada game`:' por game'}. Las cifras son sus ganados–perdidos.`)}
      ${p.setsScored<5?small(`Muestra pequeña: ${plural(p.setsScored,'set','sets')}.`,'Sirve para saber qué ha pasado, no para anticipar qué hará.'):''}
      <div class="pr-grid2">${block('Primer game',p.game1,`Ganó el primer game en ${p.game1[0]} de ${plural(sum(p.game1),'set','sets')}`)}${block('Game decisivo',p.decider,`${plural(sum(p.decider),'set llegó','sets llegaron')} al último game`)}
        ${block('Sets cerrados 2–1',p.close21,`${plural(sum(p.close21),'set','sets')} al mejor de 3 que terminaron 2–1`)}${block('Sets cerrados 3–2',p.close32,`${plural(sum(p.close32),'set','sets')} al mejor de 5 que terminaron 3–2`)}</div>
      <h3 class="pr-sub">Después de perder un game</h3>${after}</section>`;
  }
  function common() {
    const list=data.deep.common, rv=escape(data.rival.tag);
    const rate=pair=>pair[0]/sum(pair);
    const rows=list.map(x=>{const diff=rate(x.me)-rate(x.him), verdict=Math.abs(diff)<.1?['= Parejo','even']:diff>0?['◀ Tú saliste mejor','me']:['Él salió mejor ▶','him'];
      const cell=(pair,who,win)=>`<span class="pr-cell ${win?'win':''}" aria-label="${who}: ${pair[0]} ganados, ${pair[1]} perdidos"><b>${rec(pair)}</b><small>${plural(sum(pair),'set','sets')}</small></span>`;
      return `<li><span class="pr-row-main"><b>${escape(x.alias)}</b><small class="v-${verdict[1]}">${verdict[0]}</small></span>${cell(x.me,'Tú',verdict[1]==='me')}${cell(x.him,data.rival.tag,verdict[1]==='him')}</li>`;}).join('');
    return `<section id="en-comun" class="pr-section">${head(6,'Sets en este corte','Rivales en común','Jugadores que ambos enfrentaron, con el récord en sets de cada uno.')}
      ${list.length?`<div class="pr-common-head" aria-hidden="true"><span>Rival</span><span>Tú</span><span>${rv}</span></div><ul class="pr-rows common">${rows}</ul>
        ${data.deep.commonTotal>list.length?`<p class="pr-note">Se muestran los ${list.length} con más sets de ${data.deep.commonTotal} rivales en común.</p>`:''}
        <p class="pr-note">◀ Tú saliste mejor · Él salió mejor ▶ · = Parejo (menos de 10 puntos de diferencia en % de sets). El recuadro marcado es el mejor récord.</p>`
        :empty('No tienen rivales en común en este corte. Cuando ambos jueguen contra la misma persona, aparecerá aquí.')}</section>`;
  }
  function tiers() {
    const t=data.deep.byTier;
    const block=(title,pair)=>`<div class="pr-block ${sum(pair)?'has':'none'}"><p>${title}</p>${sum(pair)?`<b>${rec(pair)}</b><small>Ganó ${pair[0]} de ${plural(sum(pair),'set','sets')}${sum(pair)<5?' · ≈ menos de 5 sets':''}</small>`:'<b>—</b><small>Sin sets en este tramo</small>'}</div>`;
    return `<section id="nivel" class="pr-section">${head(7,'Sus sets por puesto del rival','Contra qué nivel rinde','')}
      ${t?`<div class="pr-grid3">${block('Top 10',t.top10)}${block('Top 11–30',t.t11_30)}${block('Resto',t.rest)}</div>`:empty('Aún no tiene sets contra rivales clasificados en este corte.')}
      <p class="pr-note">«Resto del ranking» son los clasificados del puesto 31 en adelante. Los sets contra rivales sin puesto no entran aquí, y un rival sin puesto no es un rival débil: puede ser extranjero o tener poca actividad en el corte.</p></section>`;
  }
  function intro(locked) {
    const d=data.deep?.rival, rv=escape(data.rival.tag);
    const main=d?.main?`<p class="pr-main"><span class="pr-icon">${icon(d.main)}</span><span>Su main: <b>${escape(name(d.main))}</b>${d.mainShare!=null?` · ${Math.round(d.mainShare*100)}% de sus games registrados`:''} · personaje registrado en ${d.coveredSets} de ${plural(d.totalSets,'set','sets')}</span></p>`
      :d?`<p class="pr-main"><span>Sin main detectado: start.gg registró personaje en ${d.coveredSets} de ${plural(d.totalSets,'set','sets')}.</span></p>`:'';
    return `<div class="pr-intro"><p class="pr-kicker yellow">Análisis de rival · Premium</p><h1>Prepara el set<br><span>contra ${rv}</span></h1>${main}</div>
      <nav class="pr-index" aria-label="Secciones">${SECTIONS.map((s,i)=>`<a href="#${s[0]}">${i+1} · ${s[1]}${locked?' ★':''}</a>`).join('')}</nav>`;
  }
  // Free view: one real finding in full, how much more is calculated (counts only, sent as counts by the
  // server) and the way in. The striped bars are decoration: no paid figure reaches this page.
  function finding(rv) {
    const t=data.teaser, h=t?.headline;
    if(!h)return `<section class="pr-finding none"><p class="pr-kicker">Hallazgo principal · gratis</p><h2>Aún no hay un hallazgo con muestra suficiente</h2><p>Para adelantarte algo de ${rv} pedimos al menos 5 games o sets detrás del dato. En este corte todavía no los hay; no mostramos cifras de uno o dos games como si dijeran algo.</p></section>`;
    const n=h.won+h.lost, P=h.slug?escape(name(h.slug)):'';
    const F={hard:[`A ${rv} le cuesta contra ${P}`,`Ganó ${h.won} de ${n} games contra ${P} en este corte. Entre los personajes con muestra suficiente, es contra el que peor le va.`],
      game1:[h.won<h.lost?`${rv} suele empezar perdiendo`:h.won>h.lost?`${rv} suele ganar el primer game`:`${rv} reparte el primer game`,`Ganó el primer game en ${h.won} de ${plural(n,'set','sets')} con marcador por game.`],
      top10:[`Contra el top 10: ${h.won}–${h.lost}`,`Ganó ${h.won} de ${plural(n,'set','sets')} contra jugadores del top 10 de esta vista.`]}[h.kind];
    return `<section class="pr-finding"><p class="pr-kicker">Hallazgo principal · gratis</p><div class="pr-finding-head">${h.slug?`<span class="pr-icon big">${icon(h.slug,46)}</span>`:''}<h2>${F[0]}</h2></div><p>${F[1]}</p><p class="pr-note">Es un dato medido en los sets y games del corte, no una opinión.</p></section>`;
  }
  function also(rv) {
    const l=data.teaser?.locked; if(!l)return '';
    const M=data.teaser.main?escape(name(data.teaser.main)):'main';
    const cards=[l.counters>0&&[`${plural(l.counters,'personaje evaluado','personajes evaluados')} contra su ${M}`,'Cuáles te convienen y cuáles evitar, con tus sets contra él, sus games contra cada personaje y lo que pasa en la escena de Guatemala, cada uno con su muestra y su nivel de confianza.'],
      l.common>0&&[`${plural(l.common,'rival','rivales')} en común contigo`,`Tu récord y el de ${rv} contra cada jugador que ambos enfrentaron, lado a lado, y quién salió mejor.`],
      l.sets>0&&[`Cómo jugó ${plural(l.sets,'set','sets')}`,'Primer game, game decisivo, sets cerrados 2–1 y 3–2, y si mantiene o cambia de personaje después de perder un game.'],
      l.characters>0&&[`${plural(l.characters,'personaje más','personajes más')} en su récord`,'Contra cuáles le va peor y contra cuáles mejor, en games ganados y perdidos.']].filter(Boolean).slice(0,2);
    return cards.length?`<div class="pr-also">${cards.map(c=>`<article><p class="pr-kicker">También calculado</p><h3>${c[0]}</h3><p>${c[1]}</p></article>`).join('')}</div>`:'';
  }
  function renderLocked() {
    const expired=data.state==='vencido'&&data.premium?.expiredAt, rv=escape(data.rival.tag), l=data.teaser?.locked;
    const basis=l&&l.totalSets?`El análisis completo ya está calculado con ${plural(l.totalSets,'set','sets')} de ${rv} en este corte${l.coveredSets?` (${l.coveredSets} con personaje registrado)`:''}.`:`El análisis completo usa los resultados de ${rv} y los tuyos para preparar el set.`;
    root.innerHTML=`${intro(true)}${finding(rv)}${also(rv)}
      <section class="pr-lock"><div class="pr-lock-bars" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
        <div class="pr-lock-box"><span class="pr-lock-glyph" aria-hidden="true">★</span><h2>${expired?'Renueva para volver a verlo':'Disponible con premium'}</h2><p>${basis} Lo gratis sigue igual: su puesto, sus puntos y el récord entre ustedes.</p>
          <a class="pr-cta" href="./cuenta.html#premium"><span>Apoyar con 3 USD al mes o 24 USD al año</span></a><p class="pr-note">Se renueva solo hasta que lo canceles desde la pestaña Premium. El cobro ocurre en Recurrente; Ranking Smash Bros nunca ve tu tarjeta.</p></div></section>
      <h2 class="pr-locked-title">Lo que incluye</h2><ol class="pr-locked">${SECTIONS.map((s,i)=>`<li id="${s[0]}"><span class="pr-num" aria-hidden="true">${i+1}</span><div><h2>${s[1]}</h2><p>${s[2]}</p></div><span class="pr-star">★ Premium</span></li>`).join('')}</ol>${foot()}`;
  }
  const foot=()=>`<p class="pr-principle">Pagar no da puntos ni cambia tu puesto.</p><p class="pr-note center">Datos de resultados: start.gg · Ranking Smash Bros, ranking experimental.</p>`;
  function render() {
    const cut=Date.parse(data.generatedAt), day=Number.isNaN(cut)?'':new Date(cut-21600000).toISOString().slice(0,10).split('-').reverse().join('/');
    document.getElementById('pr-cut').textContent=`${SCOPES[scope]}${day?` · ${day}`:''}`;
    if(data.state==='sinJugador'){root.innerHTML=`<section class="pr-sober"><h1>Primero, <span>tu jugador.</span></h1><p>Tu cuenta todavía no tiene un jugador de start.gg vinculado, así que no hay sets tuyos para comparar.</p><a class="pr-cta blue" href="./cuenta.html"><span>Ir a tu cuenta</span></a></section>`;return;}
    document.title=`Prepara el set contra ${data.rival.tag} — Ranking Smash Bros`;
    if(!data.deep){renderLocked();return;}
    const d=data.deep;
    root.innerHTML=`${intro(false)}<div class="pr-columns"><div>${cards(1,'counters',d.counters,true)}${cards(2,'evita',d.avoid,false)}${toolkit()}</div><div>${vsChars()}${setPattern()}${common()}${tiers()}</div></div>${foot()}`;
  }
  async function load() {
    if(!rivalId){root.innerHTML=`<section class="pr-sober"><h1>Elige <span>un rival.</span></h1><p>Esta pantalla prepara el set contra un jugador concreto.</p><a class="pr-cta blue" href="./analisis.html"><span>Buscar rival</span></a></section>`;return;}
    const controller=new AbortController(), stop=setTimeout(()=>controller.abort(),20000);
    try {
      const response=await fetch(`./analisis-api.php?${new URLSearchParams({rival:rivalId,scope})}`,{credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{Accept:'application/json'}});
      const json=await response.json();
      if(!response.ok||json.ok!==true){const error=new Error(json.reason||'unavailable');error.status=response.status;throw error;}
      data=json;render();
    } catch(error) {
      root.innerHTML=error.status===401?`<section class="pr-sober"><h1>Primero, <span>tu cuenta.</span></h1><p>Preparar el set usa tu jugador vinculado. Entra con start.gg y vuelve aquí.</p><a class="pr-cta blue" href="./cuenta.html"><span>Entrar a tu cuenta</span></a></section>`
        :`<section class="pr-sober"><h1>No pudimos <span>cargarlo.</span></h1><p>${error.status===404?'No encontramos a ese jugador en este corte.':error.status===429?'Demasiadas consultas seguidas. Espera un momento.':'Vuelve a intentarlo en un momento.'}</p><button type="button" class="pr-cta blue" id="pr-retry"><span>Reintentar</span></button></section>`;
      document.getElementById('pr-retry')?.addEventListener('click',()=>{root.innerHTML='<div class="pr-loading" role="status"><div class="pr-bar"><span></span></div><p>Preparando el set…</p></div>';load();});
    } finally {clearTimeout(stop);}
  }
  load();
})();
