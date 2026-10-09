/* Pure rules of the tournament agenda: no requests, no DOM. Data comes from data/agenda.json (start.gg).
   Null always means «start.gg did not say»: it is never shown as zero, open or closed. */
const TorneosModel = {
  DOW: ['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'],
  MONTHS: ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'],
  STALE_MS: 48*3600*1000,
  pad(n) { return String(n).padStart(2,'0'); },
  // Guatemala is UTC−6 all year. A shifted Date read with UTC getters gives the local calendar there.
  local(ms) { return new Date(ms-6*3600*1000); },
  dayNumber(ms) { return Math.floor((ms-6*3600*1000)/86400000); },
  date(ms) { const d=this.local(ms); return `${this.pad(d.getUTCDate())}/${this.pad(d.getUTCMonth()+1)}/${d.getUTCFullYear()}`; },
  time(ms) { const d=this.local(ms), h=d.getUTCHours(); return `${h%12||12}:${this.pad(d.getUTCMinutes())} ${h<12?'a. m.':'p. m.'}`; },
  box(ms) { const d=this.local(ms); return {dow:this.DOW[d.getUTCDay()].slice(0,3).toUpperCase(),day:d.getUTCDate(),month:this.MONTHS[d.getUTCMonth()].toUpperCase()}; },
  fullDate(ms) { return `${this.DOW[this.local(ms).getUTCDay()]} ${this.date(ms)} · ${this.time(ms)} (hora de Guatemala)`; },
  plural(n,one,many) { return `${n} ${n===1?one:many}`; },
  countdown(startMs,nowMs) {
    const days=this.dayNumber(startMs)-this.dayNumber(nowMs);
    return {days,soon:days<=3,urgent:days<=1,text:days<=0?'Hoy':days===1?'Mañana':days<14?`En ${days} días`:`En ${Math.floor(days/7)} semanas`};
  },
  // One tournament of agenda.json as the screen needs it. Returns null when it cannot be shown safely.
  normalize(t) {
    const start=Date.parse(t?.startAt), url=typeof t?.url==='string'&&/^https:\/\/www\.start\.gg\/tournament\/[a-z0-9-]+$/i.test(t.url)?t.url:null;
    if(!t||Number.isNaN(start)||!url||typeof t.name!=='string'||!t.name.trim())return null;
    const text=v=>typeof v==='string'&&v.trim()?v.trim():null, number=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
    const kinds=[]; for(const e of Array.isArray(t.events)?t.events:[]){const k=['singles','doubles','teams'].includes(e?.competitionType)?e.competitionType:'other';if(!kinds.includes(k))kinds.push(k);}
    const mode=['online','offline','mixed'].includes(t.attendanceType)?t.attendanceType:null, closes=Date.parse(t.registrationClosesAt);
    const lat=number(t.latitude), lng=number(t.longitude);
    return {id:String(t.id),slug:url.split('/tournament/')[1].toLowerCase(),name:t.name.trim(),url,start,mode,online:mode==='online',
      city:text(t.city),department:text(t.department),venue:text(t.venueName),address:text(t.venueAddress),
      lat:lat!==null&&lng!==null?lat:null,lng:lat!==null&&lng!==null?lng:null,kinds,
      registration:t.isRegistrationOpen===true?'open':t.isRegistrationOpen===false?'closed':null,closes:Number.isNaN(closes)?null:closes,
      entrants:number(t.numAttendees),candidate:t.isOfflineSingles===true,
      // Sign-ups of the in-person singles event: the closest thing to «players» before it is played.
      singles:(Array.isArray(t.events)?t.events:[]).reduce((best,e)=>e?.competitionType==='singles'&&e.isOnline!==true&&number(e.numEntrants)!==null?Math.max(best??0,e.numEntrants):best,null)};
  },
  // Only what has not started; a static daily file inevitably keeps an announcement past its start.
  upcoming(agenda,nowMs) {
    return (Array.isArray(agenda?.tournaments)?agenda.tournaments:[]).map(t=>this.normalize(t)).filter(t=>t&&t.start>nowMs).sort((a,b)=>a.start-b.start||a.name.localeCompare(b.name));
  },
  stale(agenda,nowMs) { const at=Date.parse(agenda?.generatedAt); return Number.isNaN(at)||nowMs-at>this.STALE_MS; },
  zones(list) {
    const departments=[], cities=[];
    for(const t of list){ if(t.online)continue; if(t.department&&!departments.includes(t.department))departments.push(t.department); if(t.city&&!cities.includes(t.city))cities.push(t.city); }
    return {departments:departments.sort((a,b)=>a.localeCompare(b)),cities:cities.sort((a,b)=>a.localeCompare(b))};
  },
  // zone: '' | 'd:Departamento' | 'c:Ciudad'. A zone only applies to in-person tournaments.
  filter(list,{zone='',mode='todos',ranking=false}={}) {
    return list.filter(t=>{
      if(zone&&(t.online||(zone[0]==='d'?t.department:t.city)!==zone.slice(2)))return false;
      if(mode==='presencial'&&t.online)return false;
      if(mode==='online'&&!t.online)return false;
      return !ranking||t.candidate;
    });
  },
  distance(aLat,aLng,bLat,bLng) {
    const rad=x=>x*Math.PI/180, dLat=rad(bLat-aLat), dLng=rad(bLng-aLng);
    const h=Math.sin(dLat/2)**2+Math.cos(rad(aLat))*Math.cos(rad(bLat))*Math.sin(dLng/2)**2;
    return 6371*2*Math.asin(Math.min(1,Math.sqrt(h)));
  },
  // «Esta semana» runs to Sunday and «Este mes» to its last day, both in Guatemala's calendar.
  // With a position, each group is ordered by distance: located in-person first, online next, unlocated last.
  groups(list,nowMs,position=null) {
    const today=this.dayNumber(nowMs), now=this.local(nowMs), sunday=today+((7-now.getUTCDay())%7);
    const month=now.getUTCFullYear()*12+now.getUTCMonth();
    const out=[{key:'week',title:'Esta semana',items:[]},{key:'month',title:'Este mes',items:[]},{key:'later',title:'Más adelante',items:[]}];
    for(const t of list){
      const d=this.local(t.start), km=position&&!t.online&&t.lat!==null?this.distance(position.lat,position.lng,t.lat,t.lng):null;
      const item={...t,km};
      out[this.dayNumber(t.start)<=sunday?0:d.getUTCFullYear()*12+d.getUTCMonth()===month?1:2].items.push(item);
    }
    if(position)for(const g of out)g.items.sort((a,b)=>{const rank=x=>x.km!==null?0:x.online?1:2;return rank(a)-rank(b)||(a.km??0)-(b.km??0)||a.start-b.start;});
    return out.filter(g=>g.items.length);
  },
  where(t) {
    if(t.online)return 'Online · desde cualquier lugar';
    const place=[t.city,t.department].filter(Boolean).join(', ');
    return [t.venue,place].filter(Boolean).join(' · ')||'Lugar por anunciar';
  },
  kindsLabel(t) { const names={singles:'Singles',doubles:'Dobles',teams:'Equipos',other:'Otro formato'}; return t.kinds.map(k=>names[k]).join(' · '); },
  modeLabel(t) { return t.mode==='online'?'Online':t.mode==='offline'?'Presencial':t.mode==='mixed'?'Presencial y online':'Modalidad no informada'; },
  registration(t,nowMs) {
    if(t.registration==='closed')return {kind:'closed',glyph:'×',text:'Inscripción cerrada'};
    if(t.registration!=='open')return {kind:'unknown',glyph:'?',text:'Inscripción no informada'};
    if(t.closes===null)return {kind:'open',glyph:'●',text:'Inscripción abierta'};
    const days=this.dayNumber(t.closes)-this.dayNumber(nowMs);
    if(days<=3)return {kind:'closing',glyph:'◐',text:`Abierta · cierra ${days<=0?'hoy':days===1?'mañana':`en ${days} días`}`};
    return {kind:'open',glyph:'●',text:`Inscripción abierta · cierra el ${this.date(t.closes)}`};
  },
  mapUrl(t) {
    const query=t.lat!==null?`${t.lat},${t.lng}`:t.address?[t.venue,t.address].filter(Boolean).join(', '):null;
    return query&&!t.online?`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`:null;
  },
  rankingNote(t) {
    if(t.online)return {ok:false,text:'No cuenta: el ranking solo usa torneos presenciales.'};
    if(t.candidate)return {ok:true,text:'Puede contar si llega a 20 jugadores activos en singles; eso se sabe hasta que termina.'};
    return t.kinds.length&&!t.kinds.includes('singles')?{ok:false,text:'No cuenta: el ranking solo usa singles.'}:null;
  },
  // Whether it can enter the ranking is only known when it ends (20 active players), so before that it is «possible».
  NEEDED: 20,
  rankingBadge(t) {
    if(t.candidate){const have=t.singles;return {kind:'possible',text:'Posible torneo rankeado',have,need:this.NEEDED,percent:have===null?null:Math.min(100,Math.round(have/this.NEEDED*100)),
      detail:have===null?'Necesita 20 jugadores activos en singles; start.gg no dice cuántos van inscritos':have>=this.NEEDED?`${have} inscritos en singles: ya pasa de los 20, falta que jueguen`:`${have} de 20 inscritos en singles · faltan ${this.NEEDED-have}`};}
    const note=this.rankingNote(t);
    return note&&!note.ok?{kind:'no',text:'No cuenta para el ranking',detail:note.text.replace('No cuenta: ','')}:null;
  },
  // Home block: the nearest in-person tournament with open registration; otherwise simply the nearest.
  next(list) { return list.find(t=>!t.online&&t.registration==='open')||list[0]||null; }
};
if (typeof module!=='undefined') module.exports=TorneosModel;
