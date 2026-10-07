/* Pure account behavior; no ranking recalculation or preference persistence here. */
const AccountModel = {
  normalize(value) { return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); },
  movement(view) {
    if (view.rank == null) return {text:'Sin puesto en este corte', kind:'none'};
    if (!view.previousCutAt) return {text:'Sin comparación previa', kind:'none'};
    if (view.previousRank == null) return {text:'Nuevo en esta vista', kind:'new'};
    const delta=view.previousRank-view.rank, places=Math.abs(delta)===1?'puesto':'puestos';
    if (delta===0) return {text:'= Mismo puesto', kind:'same'};
    return {text:`${delta>0?'▲ Subiste':'▼ Bajaste'} ${Math.abs(delta)} ${places} · antes #${view.previousRank}`, kind:delta>0?'up':'down'};
  },
  // Activity still missing for a place in this view. The minimums come from the published rules.
  requirements(view, rules) {
    return [['Torneos que cuentan',view.countedEvents,rules.playerMinimumEvents],['Sets válidos',view.wins+view.losses,rules.playerMinimumSets]]
      .map(([label,now,max])=>({label,now,max,shown:Math.min(now,max),done:now>=max,missing:Math.max(0,max-now)}));
  },
  // A published set lists the winner first. Games come from start.gg's display text when it has
  // them; a walkover or an unreadable text gives no numbers, never an invented score.
  opponent(set, playerId) {
    const mine=set.playerIds.indexOf(playerId);
    if (mine===-1) return null;
    return {id:set.playerIds[1-mine]??null, tag:set.playerTags?.[1-mine]||'Rival sin alias', won:mine===0};
  },
  setScore(set, playerId) {
    const rival=this.opponent(set,playerId);
    if (!rival) return null;
    const match=/(?:^|\s)(\d{1,2}) - .*\s(\d{1,2})$/.exec(String(set.score||''));
    if (!match) return {won:rival.won, text:'—'};
    const a=Number(match[1]), b=Number(match[2]);
    if (a===b) return {won:rival.won, text:'—'};
    const high=Math.max(a,b), low=Math.min(a,b);
    return {won:rival.won, text:rival.won?`${high}–${low}`:`${low}–${high}`};
  },
  headToHead(results, playerId, rivalId) {
    const sets=results.filter(set=>set.playerIds.includes(playerId)&&set.playerIds.includes(rivalId)&&playerId!==rivalId);
    const wins=sets.filter(set=>set.playerIds[0]===playerId).length;
    return {wins, losses:sets.length-wins, sets:[...sets].sort((x,y)=>String(y.date).localeCompare(String(x.date)))};
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
