/* Home block «Próximo torneo»: the nearest announced tournament from data/agenda.json.
   Stays hidden when the agenda cannot be read: the ranking page never depends on it. */
(() => {
  const box=document.getElementById('proximo-torneo'), M=typeof TorneosModel==='undefined'?null:TorneosModel;
  if(!box||!M)return;
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  fetch('./data/agenda.json',{cache:'no-cache'}).then(r=>r.ok?r.json():null).then(agenda=>{
    if(!agenda||agenda.schemaVersion!==1||M.stale(agenda,Date.now()))return;
    const now=Date.now(), list=M.upcoming(agenda,now), t=M.next(list);
    const head='<div class="nt-head"><h2 id="next-title">Próximo torneo</h2><a href="./torneos.html">Ver todos →</a></div>';
    if(!t){box.innerHTML=`${head}<p class="nt-none">— No hay torneos anunciados por ahora. Cuando se publique uno en start.gg, aparecerá aquí.</p>`;box.hidden=false;return;}
    const b=M.box(t.start), c=M.countdown(t.start,now), r=M.registration(t,now), more=list.length-1;
    box.innerHTML=`${head}<div class="nt-body"><div class="nt-date" aria-hidden="true"><span>${b.dow}</span><b>${b.day}</b><span>${b.month}</span></div>
      <div class="nt-copy"><p class="nt-count">${c.text} · ${M.time(t.start)}</p><h3>${escape(t.name)}</h3><p>${escape([t.online?null:t.city,M.modeLabel(t)].filter(Boolean).join(' · '))}</p><p class="nt-reg ${r.kind}"><span aria-hidden="true">${r.glyph}</span> ${r.text}</p></div></div>
      <a class="nt-cta" href="./torneos.html#${escape(t.slug)}"><span>Ver el torneo →</span></a>
      <p class="nt-note">${more>0?`Y ${M.plural(more,'torneo más','torneos más')} en la agenda. `:''}Smash GT no organiza estos torneos.</p>`;
    box.hidden=false;
  }).catch(()=>{});
})();
