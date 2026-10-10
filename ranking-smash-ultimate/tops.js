/* Public directory. Only public names/positions; no session, payment or provider requests. */
const SmashTops = (() => {
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const slug = value => typeof value === 'string' && /^[a-z0-9-]{1,60}$/.test(value);
  const keys = (value, expected) => value && !Array.isArray(value) && typeof value === 'object' && Object.keys(value).sort().join('|') === [...expected].sort().join('|');
  function validate(data) {
    if (!keys(data,['ok','schemaVersion','items','nextCursor']) || data.ok !== true || data.schemaVersion !== 1 || !Array.isArray(data.items) || data.items.length > 12
        || (data.nextCursor !== null && !slug(data.nextCursor))) throw new Error('Invalid public directory');
    const seen = new Set();
    for (const item of data.items) {
      if (!keys(item,['name','coorganizers','topSize','tournaments','cutDate','top','url']) || typeof item.name !== 'string' || !item.name
          || !Array.isArray(item.coorganizers) || item.coorganizers.length > 10 || item.coorganizers.some(name=>typeof name !== 'string')
          || ![5,10,15].includes(item.topSize) || !Number.isSafeInteger(item.tournaments) || item.tournaments < 1
          || (item.cutDate !== null && !/^\d{4}-\d{2}-\d{2}$/.test(item.cutDate))
          || !Array.isArray(item.top) || item.top.length > 3 || typeof item.url !== 'string' || !item.url.startsWith('/top/') || !slug(item.url.slice(5)) || seen.has(item.url)) throw new Error('Invalid public top');
      item.top.forEach((player,index)=>{
        if (!keys(player,['rank','alias']) || player.rank !== index+1 || typeof player.alias !== 'string') throw new Error('Invalid podium');
      });
      seen.add(item.url);
    }
    if (data.nextCursor !== null && data.items.at(-1)?.url !== '/top/'+data.nextCursor) throw new Error('Invalid public cursor');
    return data;
  }
  const date = day => day === null ? 'Fecha no disponible' : day.split('-').reverse().join('/');
  function coorganizers(names) {
    if (!names.length) return '';
    const joined = names.length <= 3 ? names.map(escape).join(', ').replace(/, ([^,]*)$/, ' y $1') : `${names.slice(0,2).map(escape).join(', ')} y ${names.length-2} más`;
    return `<p class="tops-co"><span>Con </span>${joined}</p>${names.length>3 ? `<details class="tops-co-details"><summary>Ver los ${names.length} coorganizadores</summary><ul aria-label="Coorganizadores">${names.map(name=>`<li>${escape(name)}</li>`).join('')}</ul></details>` : ''}`;
  }
  function card(item) {
    return `<li><article class="tops-card" id="top-${item.url.slice(5)}" tabindex="-1"><div class="tops-size top-${item.topSize}"><span>TOP</span><strong>${item.topSize}</strong></div><div class="tops-body">
      <h2><span class="tops-sr">Top ${item.topSize} de </span>${escape(item.name)}</h2>${coorganizers(item.coorganizers)}
      <div class="tops-chips"><span>${item.tournaments} ${item.tournaments===1?'torneo':'torneos'}</span><span>Corte ${date(item.cutDate)}</span></div>
      ${item.top.length ? `<ol class="tops-preview" aria-label="Primeros puestos del top de ${escape(item.name)}">${item.top.map(player=>`<li><span class="tops-position"><span class="tops-sr">Puesto </span>${player.rank}</span><strong>${escape(player.alias)}</strong></li>`).join('')}</ol>` : '<p class="tops-no-players">Este top todavía no tiene jugadores con sets válidos.</p>'}
      ${item.top.length>0 && item.top.length<3 ? `<p class="tops-few"><span class="tops-glyph" aria-hidden="true">i</span>Este top tiene ${item.top.length} ${item.top.length===1?'jugador':'jugadores'} por ahora.</p>` : ''}
      <a class="tops-cta" href="${item.url}" aria-label="Ver top completo de ${escape(item.name)}"><span>Ver top completo →</span></a></div></article></li>`;
  }
  function skeletons(count) {
    return Array.from({length:count},()=>'<li class="tops-skeleton" aria-hidden="true"><span></span><div><b></b><b></b><b></b><b></b><b></b></div></li>').join('');
  }
  function failure(more) {
    return `<div class="tops-error" role="alert"><span class="tops-glyph" aria-hidden="true">×</span><div><strong>${more?'No pudimos cargar más tops.':'No pudimos cargar los tops.'}</strong><p>${more?'Los que ya ves siguen aquí. Intenta de nuevo.':'Revisa tu conexión e intenta de nuevo.'}</p></div><button class="tops-retry" id="tops-more">Reintentar</button></div>`;
  }
  function render(items, nextCursor, loading=false, error=false) {
    const status = `<p class="tops-status" role="status" aria-live="polite">${loading ? items.length?'Cargando más tops…':'Cargando tops…' : `${items.length} ${items.length===1?'top compartido':'tops compartidos'}`}</p>`;
    if (!items.length && error) return failure(false);
    if (!items.length && loading) return status+'<div class="tops-loading-bar" aria-hidden="true"><span></span></div><ul class="tops-list" aria-label="Cargando tops">'+skeletons(6)+'</ul>';
    if (!items.length) return status+'<div class="tops-empty"><div class="tops-empty-podium" aria-hidden="true"><span></span><span></span><span></span></div><h2>Todavía no hay tops compartidos.</h2><p>Si organizas torneos, crea el tuyo desde <a href="./cuenta.html#premium">tu cuenta</a>.</p></div>';
    return status+`<ul class="tops-list" aria-label="Tops compartidos">${items.map(card).join('')}${loading?skeletons(3):''}</ul>`+
      (error?failure(true):nextCursor?`<div class="tops-pagination"><button class="tops-more" id="tops-more" aria-busy="${loading}" ${loading?'disabled':''}><span>${loading?'Cargando…':'Ver más tops'}</span></button><p>Mostrando ${items.length} tops · Hay más disponibles</p></div>`:`<p class="tops-complete">Mostrando ${items.length} tops · Todos los disponibles</p>`);
  }
  function init(doc=document, request=fetch) {
    const root = doc.getElementById('tops-root'); if (!root) return;
    let items=[], next=null, busy=false;
    async function load(manual=false) {
      if (busy) return; busy=true;
      root.setAttribute('aria-busy','true'); root.innerHTML=render(items,next,true);
      const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),20000);
      try {
        const response=await request('./tops-api.php'+(next?'?after='+encodeURIComponent(next):''),{credentials:'omit',signal:controller.signal,headers:{Accept:'application/json'}});
        if (!response.ok) throw new Error('Directory unavailable');
        const data=validate(await response.json());
        const known=new Set(items.map(item=>item.url)), added=data.items.filter(item=>!known.has(item.url));
        items=items.concat(added); next=data.nextCursor; root.innerHTML=render(items,next);
        if (manual && added.length) root.querySelector('#top-'+added[0].url.slice(5))?.focus();
      } catch { root.innerHTML=render(items,next,false,true); }
      finally {
        clearTimeout(timer);busy=false;root.setAttribute('aria-busy','false');
        root.querySelector('#tops-more')?.addEventListener('click',()=>load(true));
      }
    }
    const ready=load(); return {ready,load:()=>load(true)};
  }
  return {validate,render,init};
})();
if (typeof module !== 'undefined') module.exports=SmashTops;
if (typeof document !== 'undefined') SmashTops.init();
