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
  function card(item) {
    return `<article class="t-card tops-card"><div class="t-date"><span>TOP</span><b>${item.topSize}</b></div><div class="t-body">
      <h2>${escape(item.name)}</h2>${item.coorganizers.length ? `<p class="t-where">Coorganizan: ${item.coorganizers.map(escape).join(', ')}</p>` : ''}
      <p class="t-where">${item.tournaments} ${item.tournaments===1?'torneo':'torneos'} · Corte: ${date(item.cutDate)}</p>
      ${item.top.length ? `<ol class="tops-preview" aria-label="Primeros puestos">${item.top.map(player=>`<li><span aria-hidden="true">#${player.rank}</span><strong>${escape(player.alias)}</strong></li>`).join('')}</ol>` : '<p class="t-note">Todavía no hay jugadores con los sets suficientes para aparecer.</p>'}
      <a class="t-cta" href="${item.url}"><span>Ver top completo ↗</span></a></div></article>`;
  }
  function render(items, nextCursor, loading=false, error=false) {
    if (!items.length && error) return '<div class="t-empty error" role="alert"><h2>No pudimos cargar los tops.</h2><p>Vuelve a intentarlo en un momento.</p><button class="t-outline" id="tops-more">Reintentar</button></div>';
    if (!items.length) return '<div class="t-empty" role="status"><h2>Todavía no hay tops compartidos.</h2><p>Si organizas torneos, crea el tuyo desde tu cuenta.</p><a class="t-cta" href="./cuenta.html#premium"><span>Ir a Premium ↗</span></a></div>';
    return `<p class="t-total" role="status">${items.length} ${items.length===1?'top compartido':'tops compartidos'}${nextCursor?' · Hay más disponibles':''}</p><div class="tops-list">${items.map(card).join('')}</div>
      ${error?'<p class="t-note" role="alert">No pudimos cargar más tops. Los anteriores siguen visibles; puedes reintentar.</p>':''}
      ${nextCursor?`<button class="t-outline" id="tops-more" ${loading?'disabled':''}>${loading?'Cargando…':error?'Reintentar':'Ver más tops'}</button>`:''}`;
  }
  function init() {
    const root = document.getElementById('tops-root'); if (!root) return;
    let items=[], next=null, busy=false;
    async function load() {
      if (busy) return; busy=true;
      root.setAttribute('aria-busy','true');
      if (items.length) root.innerHTML=render(items,next,true);
      const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),20000);
      try {
        const response=await fetch('./tops-api.php'+(next?'?after='+encodeURIComponent(next):''),{credentials:'omit',signal:controller.signal,headers:{Accept:'application/json'}});
        if (!response.ok) throw new Error('Directory unavailable');
        const data=validate(await response.json());
        const known=new Set(items.map(item=>item.url)); items=items.concat(data.items.filter(item=>!known.has(item.url))); next=data.nextCursor;
        root.innerHTML=render(items,next);
      } catch { root.innerHTML=render(items,next,false,true); }
      finally {
        clearTimeout(timer);busy=false;root.setAttribute('aria-busy','false');
        root.querySelector('#tops-more')?.addEventListener('click',load);
      }
    }
    load();
  }
  return {validate,render,init};
})();
if (typeof module !== 'undefined') module.exports=SmashTops;
if (typeof document !== 'undefined') SmashTops.init();
