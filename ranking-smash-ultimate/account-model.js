/* Pure account behavior; no ranking recalculation or preference persistence here. */
const AccountModel = {
  normalize(value) { return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); },
  movement(view) {
    if (view.rank == null) return {text:'Sin puesto en este corte', kind:''};
    if (!view.previousCutAt) return {text:'Sin comparación previa', kind:''};
    if (view.previousRank == null) return {text:'Nuevo en esta vista', kind:'new'};
    const delta=view.previousRank-view.rank;
    return {text:delta===0?'= Sin cambio':`${delta>0?'▲':'▼'} ${Math.abs(delta)} · antes #${view.previousRank}`, kind:delta>0?'up':delta<0?'down':''};
  },
  assign(current, slot, id) {
    const next=[current[0] || null,current[1] || null,current[2] || null];
    const existing=next.indexOf(id), previous=next[slot];
    if (slot>0 && !next[0]) return next.filter(Boolean);
    if (existing!==-1) next[existing]=previous;
    next[slot]=id;
    return next.filter(Boolean);
  },
  remove(current, slot) { return slot===0 ? [...current] : current.filter((_,i)=>i!==slot); },
  dirty(current, saved) { return JSON.stringify(current)!==JSON.stringify(saved); },
  history(view, filter) { return view.events.filter(e=>filter==='all'||(filter==='counted'?e.counts:!e.counts)); }
};
if (typeof module!=='undefined') module.exports=AccountModel;
