/* Pure presentation rules of the rival analysis: no requests, no DOM, no figures of its own.
   Everything shown comes from analisis-api.php; this file only decides how to word it. */
const AnalisisModel = {
  SCOPES: {intl:'+ Internacional', gt:'Solo Guatemala'},
  TIERS: [['top10','Top 10'],['t11_50','11–50'],['t51_100','51–100'],['outsideTop100','101 o más'],['unranked','Sin puesto']],
  number(n) { return Number(n).toLocaleString('en'); },
  initials(tag) { return String(tag||'?').trim().slice(0,2).toUpperCase(); },
  date(value) { const day=String(value||'').slice(0,10).split('-'); return day.length===3?`${day[2]}/${day[1]}/${day[0]}`:'Sin fecha'; },
  plural(n,one,many) { return `${this.number(n)} ${n===1?one:many}`; },
  // Model estimate from the points of both in the active view. Shown between 10% and 90%.
  probability(probability) {
    const p=probability?.p;
    if (typeof p!=='number'||!Number.isFinite(p)) return null;
    const percent=Math.round(p*100);
    const text=percent>90?'>90%':percent<10?'<10%':`${percent}%`;
    const word=percent>65?'Llegas favorito':percent<35?'Él llega favorito':'Set parejo';
    return {text, word, kind:percent>65?'light':percent<35?'blue':'yellow', mine:Math.min(90,Math.max(10,percent))};
  },
  // Records are always a count. Percentage and bar only from ten sets or games on.
  record(pair, unit='sets') {
    const [w,l]=Array.isArray(pair)?pair:[0,0], total=w+l, one=unit==='games'?'game':'set';
    if (total===0) return {count:'0–0', total, percent:null, note:`Sin ${unit} registrados`, small:false, empty:true};
    if (total<10) return {count:`${w}–${l}`, total, percent:null, note:`Muestra pequeña · ${this.plural(total,one,unit)}`, small:true, empty:false};
    return {count:`${w}–${l}`, total, percent:Math.round(w/total*100), note:this.plural(total,one,unit), small:false, empty:false};
  },
  usage(detected) {
    return (detected||[]).map(d=>({...d, percent:d.totalGames>0?Math.round(d.games/d.totalGames*100):0}));
  },
  coverage(person) {
    const c=person?.coverage; if (!c) return '';
    if (c.source!=='published'||c.registered==null) return `Sin dato de personajes para ${person.tag} en este corte: no está entre los clasificados.`;
    if (c.registered===0) return `start.gg no registró personaje en ninguno de sus ${this.plural(c.total,'set','sets')} de esta temporada.`;
    return `Personaje registrado en ${this.number(c.registered)} de ${this.plural(c.total,'set','sets')} de ${person.tag}.`;
  },
  // Advice in the tone of a teammate. Numbers always shown; never a verdict.
  recommendation(item, name, opponentName) {
    const own=item.reasonData?.own||[0,0], scene=item.reasonData?.scene||[0,0], good=item.type==='good';
    const basis=item.reasonData?.basis==='own_sets'
      ? `Con ${name} llevas ${own[0]}–${own[1]} en sets contra él.`
      : `En la escena, ${name} lleva ${scene[0]}–${scene[1]} en games contra ${opponentName}.`;
    return {good, mark:good?'✓':'!', title:good?`${name} te ha funcionado`:`${name} te ha costado`, reason:basis,
      confidence:`Confianza ${item.confidence}`, sample:`${this.plural(item.ownSets,'set tuyo','sets tuyos')} · ${this.plural(item.sceneGames,'game de escena','games de escena')}`};
  },
  // Why there is no advice, with the real numbers.
  noRecommendation(data, opponentTag) {
    if (!(data.rival?.detected||[]).some(d=>d.usableForMatchups)) return `Sin personajes detectados de ${opponentTag}: no podemos cruzar personajes todavía.`;
    const sets=data.record?.sets||0, known=(data.h2h||[]).filter(s=>s.myChar||s.theirChar).length;
    return `Hay ${this.plural(sets,'set','sets')} entre ustedes (${known} con personaje registrado). Para recomendar necesitamos al menos 2 sets tuyos con personaje o 150 games de la escena en el cruce.`;
  },
  streak(streak) {
    if (!streak||streak.sets<2) return '';
    return streak.won?`Llevas ${streak.sets} seguidos ganados`:`Llevas ${streak.sets} seguidos perdidos`;
  },
  setScore(set) {
    return Number.isInteger(set.myGames)&&Number.isInteger(set.theirGames)?`${set.myGames}–${set.theirGames}`:'—';
  },
  // Which of my characters feed the matrix: chosen first; without them, the detected ones the server used.
  myMatrixCharacters(data) {
    const keys=Object.keys(data.gameMatrix||{}), mine=[...new Set(keys.map(k=>k.split('|')[0]))], his=[...new Set(keys.map(k=>k.split('|')[1]))];
    return {mine, his};
  },
  gamesNote(status) {
    if (status==='cut_not_synced') return 'Los games de este corte todavía se están sincronizando. Vuelve a revisar más tarde.';
    if (status==='empty') return 'Todavía no hay games con personaje registrados para este corte.';
    return '';
  }
};
if (typeof module!=='undefined') module.exports=AnalisisModel;
