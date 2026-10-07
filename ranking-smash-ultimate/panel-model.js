/* Pure presentation rules of the owner's panel: no requests, no DOM, no figures of its own. */
const PanelModel = {
  LABELS: {'7':'Últimos 7 días','30':'Últimos 30 días','90':'Últimos 90 días',season:'Temporada'},
  DOW: ['domingo','lunes','martes','miércoles','jueves','viernes','sábado'],
  pad(n) { return String(n).padStart(2,'0'); },
  // Dates arrive as YYYY-MM-DD of Guatemala; they are never re-interpreted in the browser's zone.
  parts(day) { const [y,m,d]=String(day).split('-').map(Number); return {y,m,d,dow:new Date(Date.UTC(y,m-1,d)).getUTCDay()}; },
  dm(day) { const p=this.parts(day); return `${this.pad(p.d)}/${this.pad(p.m)}`; },
  dmy(day) { return `${this.dm(day)}/${this.parts(day).y}`; },
  shift(day,n) { const p=this.parts(day); return new Date(Date.UTC(p.y,p.m-1,p.d+n)).toISOString().slice(0,10); },
  number(n) { return Number(n).toLocaleString('en'); },
  plural(n,one,many) { return `${this.number(n)} ${n===1?one:many}`; },
  // Top of the vertical axis: a round number at or above the largest value, never below 4.
  axisMax(values) {
    const max=Math.max(0,...values); if (max<=4) return 4;
    const step=Math.pow(10,Math.floor(Math.log10(max))), unit=[1,2,2.5,5,10].find(u=>u*step>=max);
    return unit*step;
  },
  // Comparison with the previous window, always in words. No previous window means no percentage.
  change(name, period) {
    if (name==='season') return {kind:'none', text:'Primera temporada medida: sin comparación'};
    if (!period.previous) return {kind:'none', text:'Sin periodo anterior completo para comparar'};
    const before=period.previous.visitors, now=period.visitors, span=`los ${name} días anteriores (${this.number(before)})`;
    if (before===0) return {kind:now>0?'up':'none', text:now>0?`▲ Más que ${span}`:`= Igual que ${span}`};
    const pct=Math.round(Math.abs(now-before)/before*100);
    if (now===before||pct===0) return {kind:'none', text:`= Igual que ${span}`};
    return now>before?{kind:'up', text:`▲ ${pct}% más que ${span}`}:{kind:'down', text:`▼ ${pct}% menos que ${span}`};
  },
  // Notice when the period is longer than the measured history.
  shortNotice(report, period) {
    if (!period.daysWithData||period.daysWithData>=period.days) return '';
    const n=period.daysWithData;
    return `El contador empezó el ${this.dmy(report.counterStartedAt)}: este periodo solo tiene ${n} ${n===1?'día completo':'días completos'}. Los totales crecerán solos; no faltan datos.`;
  },
  // Bars of the chart. 7 and 30 days: one per day, days before the counter as «none», today last
  // and partial. 90 days and season: one per week as computed by the server.
  items(report, name) {
    const period=report.periods[name];
    if (name==='90'||name==='season') {
      return (report.weekly[name]||[]).map(w=>({label:`Semana ${this.dm(w.from)} – ${this.dm(w.to)}${w.partial?` · ${this.span(w.from,w.to)} días (empieza el contador)`:''}`,short:this.dm(w.from),
        visitors:w.visitors,pageviews:w.pageviews,registrations:w.registrations,partial:w.partial,weekly:true}));
    }
    const byDate=new Map(report.daily.map(d=>[d.date,d])), items=[];
    for (let day=period.from; day<=period.to; day=this.shift(day,1)) {
      const row=byDate.get(day);
      items.push(row?{label:`${this.DOW[this.parts(day).dow]} ${this.dm(day)}`,short:this.dm(day),visitors:row.visitors,pageviews:row.pageviews,registrations:row.registrations}
        :{none:true,short:this.dm(day)});
    }
    const t=report.today;
    items.push({label:`Hoy ${this.dm(t.date)} · en curso hasta ${report.updatedAt.slice(11,16)}`,short:'Hoy',visitors:t.visitors,pageviews:t.pageviews,registrations:t.registrations,partial:true,today:true});
    return items;
  },
  span(from,to) { let n=1; for (let day=from; day<to; day=this.shift(day,1)) n++; return n; },
  // The reading starts on the last complete day or week, never on the partial one.
  defaultIndex(items) {
    for (let i=items.length-1;i>=0;i--) if (!items[i].none&&!items[i].partial) return i;
    for (let i=items.length-1;i>=0;i--) if (!items[i].none) return i;
    return -1;
  },
  step(items,index,key) {
    const usable=items.map((x,i)=>x.none?-1:i).filter(i=>i>=0), at=usable.indexOf(index);
    if (!usable.length) return index;
    if (key==='Home') return usable[0];
    if (key==='End') return usable[usable.length-1];
    if (key==='ArrowLeft') return usable[Math.max(0,at-1)];
    if (key==='ArrowRight') return usable[Math.min(usable.length-1,at+1)];
    return index;
  },
  reading(item) {
    return `${this.plural(item.visitors,'visitante','visitantes')}${item.weekly?' (semana)':''} · ${this.plural(item.pageviews,'vista','vistas')} · ${this.plural(item.registrations,'registro nuevo','registros nuevos')}${item.partial?' · parcial':''}`;
  },
  pages(period) {
    const names={home:'Inicio / ranking',top20:'Análisis del top 20',torneos:'Análisis de torneos',metodologia:'Metodología',cuenta:'Cuenta'};
    const rows=Object.entries(period.pages||{}).map(([key,views])=>({key,name:names[key]||key,views})).sort((a,b)=>b.views-a.views||a.name.localeCompare(b.name));
    const total=rows.reduce((n,r)=>n+r.views,0), top=rows[0]?.views||0;
    return rows.map((r,i)=>({...r,position:i+1,percent:total?Math.round(r.views/total*100):0,width:top?Math.round(r.views/top*100):0}));
  }
};
if (typeof module!=='undefined') module.exports=PanelModel;
