/* Native Canvas/PNG and a bounded, store-only ZIP. No service, telemetry or example data. */
const SmashLaminas = (() => {
  const FORMATS={h:[1920,1080],v:[1080,1350],s:[1080,1920]}, BG='#0B0F1A', PANEL='#121829', TRACK='#1A2236', WHITE='#F4F1EA', MUTED='#C9CED8', BLUE='#49A6E9';
  const accent=rank=>({1:'#FFD23F',2:'#C9CED8',3:'#E39B5B'}[rank]||BLUE);
  const chars=value=>Array.from(String(value??''));
  const short=(value,max)=>chars(value).length>max?chars(value).slice(0,max-1).join('')+'…':String(value??'');
  const initials=tag=>chars(String(tag).trim()).slice(0,2).join('').toUpperCase()||'?';
  const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const filename=(data,player,format)=>`${player?String(player.rank).padStart(2,'0')+'-'+safeName(player.tag):'top-'+data.organizer.topSize+'-'+safeName(data.organizer.name)}-${{h:'horizontal',v:'vertical',s:'historia'}[format]}.png`;
  const safeName=value=>String(value).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]+/gi,'-').replace(/^-|-$/g,'').slice(0,48).toLowerCase()||'sin-tag';
  function validate(data) {
    if(data?.schemaVersion!==1||typeof data.organizer?.name!=='string'||![5,10,15].includes(data.organizer.topSize)||!Array.isArray(data.organizer.coorganizers)||data.organizer.coorganizers.length>10||!Array.isArray(data.players)||data.players.length>data.organizer.topSize)throw Error('Datos de láminas no disponibles.');
    data.players.forEach((p,i)=>{if(p.rank!==i+1||typeof p.tag!=='string'||!Array.isArray(p.mains)||p.mains.length>3||!Array.isArray(p.results))throw Error('Datos de jugador incompletos.');});
    return data;
  }
  // All text is fitted inside a finite box, including the fixed footer (never truncated).
  function painter(ctx, bounds=[]) {
    const box=(x,y,w,h,color)=>{ctx.fillStyle=color;ctx.fillRect(x,y,w,h);};
    const outline=(x,y,w,h,color,dashed=false)=>{ctx.save();ctx.strokeStyle=color;ctx.lineWidth=2;ctx.setLineDash(dashed?[8,6]:[]);ctx.strokeRect(x,y,w,h);ctx.restore();};
    const diagonal=(x,y,w,h,color)=>{ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+w,y);ctx.lineTo(x+w-h*.176,y+h);ctx.lineTo(x-h*.176,y+h);ctx.closePath();ctx.fill();};
    const diagonalY=(x,y,w,h,color)=>{ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+w,y-w*.07);ctx.lineTo(x+w,y+h-w*.07);ctx.lineTo(x,y+h);ctx.closePath();ctx.fill();};
    const slantOutline=(x,y,w,h,color)=>{ctx.save();ctx.translate(x,y);ctx.transform(1,0,-.176,1,0,0);outline(0,0,w,h,color);ctx.restore();};
    function text(value,x,y,w,h,size=22,color=WHITE,font='Archivo',lines=1,ellipsis=false) {
      value=String(value??''); if(!value)return;
      let rows=[];
      for(;size>=8;size--) {
        ctx.font=`${font==='Archivo'?700:900} ${size}px "${font}"`;rows=[''];
        for(const c of chars(value)) {
          const last=rows.length-1;
          if(c==='\n'||ctx.measureText(rows[last]+c).width>w)rows.push(c==='\n'?'':c);
          else rows[last]+=c;
        }
        if(ellipsis&&rows.length>lines) {rows=rows.slice(0,lines);while(ctx.measureText(rows[lines-1]+'…').width>w)rows[lines-1]=chars(rows[lines-1]).slice(0,-1).join('');rows[lines-1]+='…';}
        if(rows.length<=lines&&rows.length*size*1.1<=h&&rows.every(row=>ctx.measureText(row).width<=w))break;
      }
      ctx.fillStyle=color;ctx.textBaseline='top';rows.forEach((row,i)=>ctx.fillText(row,x,y+i*size*1.1));
      bounds.push({value,x,y,width:w,height:h,size,lines:rows.length});
    }
    function image(img,x,y,w,h,contain=true) {
      if(!img)return false;
      const ratio=contain?Math.min(w/img.width,h/img.height):Math.max(w/img.width,h/img.height);
      ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();ctx.drawImage(img,x+(w-img.width*ratio)/2,y+(h-img.height*ratio)/2,img.width*ratio,img.height*ratio);ctx.restore();return true;
    }
    return {box,outline,diagonal,diagonalY,slantOutline,text,image};
  }
  function draw(data,format,player=null,canvas=null,images=new Map()) {
    validate(data); if(!FORMATS[format])throw Error('Formato no válido.');
    canvas=canvas||document.createElement('canvas');[canvas.width,canvas.height]=FORMATS[format];
    const ctx=canvas.getContext('2d'); if(!ctx)throw Error('Este navegador no permite crear PNG.');
    const bounds=[],g=painter(ctx,bounds),h=format==='h',y0=format==='s'?250:0;
    g.box(0,0,canvas.width,canvas.height,BG);
    if(format==='s'){g.diagonalY(-80,40,1240,70,PANEL);g.diagonalY(-80,124,1240,22,BLUE);g.diagonalY(-80,160,1240,8,'#FFD23F');g.diagonalY(-80,1740,1240,8,'#FFD23F');g.diagonalY(-80,1762,1240,22,BLUE);g.diagonalY(-80,1798,1240,70,PANEL);}
    ctx.save();ctx.translate(0,y0);
    const logo=images.get('logo'),org=data.organizer,season=org.seasonYear?`Temporada ${org.seasonYear}`:'';
    const main=p=>p.mains[0]||null;
    const icon=(p,x,y,size)=>{const m=main(p);if(!g.image(m&&images.get(m.slug+'-icon'),x,y,size,size)){g.box(x,y,size,size,BG);g.text(initials(p.tag),x+4,y+4,size-8,size-8,Math.round(size*.55),accent(p.rank),'Big Shoulders Display');}};
    if(player) {
      if(!data.players.includes(player))throw Error('Jugador ajeno a este top.');
      const a=accent(player.rank),m=main(player),portrait=m&&images.get(m.slug+'-portrait');
      g.diagonal(h?1180:560,-40,h?900:700,h?1160:860,PANEL);g.diagonal(h?1132:520,-40,h?22:18,h?1160:860,a);
      if(portrait){const height=h?1100:820,width=portrait.width*height/portrait.height;g.image(portrait,(h?2040:1230)-width,h?20:40,width,height);const fade=ctx.createLinearGradient(0,h?560:540,0,h?1050:840);fade.addColorStop(0,'#0B0F1A00');fade.addColorStop(1,BG);ctx.fillStyle=fade;ctx.fillRect(h?1130:520,h?560:540,h?790:560,h?520:310);}
      else {g.slantOutline(h?1340:660,h?150:180,h?440:320,h?400:300,a);g.text(initials(player.tag),h?1380:700,h?230:235,h?360:240,h?260:190,h?240:170,a,'Big Shoulders Display');}
      g.image(logo,h?96:64,h?64:60,h?388:320,h?36:30);
      g.box(h?508:64,h?64:108,h?626:620,44,PANEL);g.text(short(`Top ${org.topSize} · ${org.name}`,60),h?524:78,h?74:118,h?590:590,26,h?22:19,WHITE,'Archivo',1,true);
      g.text(season,h?1240:720,h?74:116,h?584:296,30,h?22:19,BLUE);
      const rank=String(player.rank).padStart(2,'0');g.text(rank,h?96:64,h?160:186,h?310:500,h?360:270,h?360:300,a,'Big Shoulders Display');
      g.text(`Puesto ${player.rank} de ${org.topSize}`,h?430:64,h?178:454,h?700:952,34,h?22:20,MUTED);
      const length=chars(player.tag).length,step=length<=8?0:length<=12?1:length<=16?2:3;
      g.text(short(player.tag,20).toUpperCase(),h?430:64,h?228:520,h?700:952,h?152:160,(h?[168,132,100,76]:[150,118,92,72])[step],WHITE,'Big Shoulders Display',2);
      const label=m?m.name:'Sin personaje registrado',labelW=h?430:420;
      if(m)g.diagonal(h?430:64,h?408:706,labelW,h?56:50,a);else g.outline(h?430:64,h?408:706,labelW,h?56:50,MUTED,true);
      g.text(label,h?448:80,h?424:720,labelW-40,30,h?22:20,m?BG:MUTED);
      player.mains.slice(1,3).forEach((c,i)=>{const x=(h?882:510)+i*76,y=h?400:700;ctx.save();ctx.beginPath();ctx.arc(x+32,y+32,32,0,Math.PI*2);ctx.fillStyle=TRACK;ctx.fill();ctx.clip();g.image(images.get(c.slug+'-icon'),x+5,y+5,54,54);ctx.restore();});
      const gp=Number.isInteger(player.setsWon)&&Number.isInteger(player.setsLost)?`${player.setsWon}–${player.setsLost}`:'—';
      const total=player.setsWon+player.setsLost,pct=total>0?`${Math.round(100*player.setsWon/total)}%`:'—';
      const five=player.vsTop5?`${player.vsTop5.won}–${player.vsTop5.lost}`:'—';
      [gp,pct,five].forEach((v,i)=>{const x=(h?1240:64)+i*(h?198:320),y=h?600:810,w=h?188:312;g.box(x,y,w,h?108:78,PANEL);if(!i)g.box(x,y,5,h?108:78,a);g.text(v,x+16,y+10,w-32,h?60:46,h?56:50,WHITE,'Big Shoulders Display');g.text((h?['sets en el top','de victorias','vs. top 5']:['sets','victorias','vs. top 5'])[i],x+16,y+(h?74:54),w-32,24,h?16:15,MUTED);});
      const results=player.results.filter(r=>Number.isSafeInteger(r.placement)&&r.placement>0),featured=results.slice(0,3),other=results.slice(3,h?9:7);
      if(featured.length) {
        if(h)g.text('TORNEOS DESTACADOS',96,520,1040,32,20,MUTED);
        const area=h?1040:952,colW=(area-(featured.length-1)*(h?14:8))/(h?featured.length:Math.max(2,featured.length));
        featured.forEach((r,i)=>{const x=(h?96:64)+i*(colW+(h?14:8)),y=h?560:910,ac=accent(r.placement),winRows=r.wins.slice(0,h?4:3);
          g.box(x,y,colW,h?350:220,PANEL);g.box(x,y,colW,h?5:4,ac);g.diagonal(x+14,y+16,h?96:70,h?62:48,ac);
          g.text(String(r.placement)+'º',x+22,y+22,h?72:52,h?52:40,h?46:34,BG,'Big Shoulders Display');
          g.text(r.name.toUpperCase(),x+(h?126:98),y+18,colW-(h?144:112),h?64:50,h?28:22,WHITE,'Big Shoulders Display',2,true);
          if(winRows.length)winRows.forEach((w,j)=>{const yy=y+(h?104:84)+j*(h?46:38);g.box(x+14,yy,colW-28,h?40:34,BG);if(!g.image(w.mainSlug&&images.get(w.mainSlug+'-icon'),x+18,yy+3,h?32:28,h?32:28))g.text(initials(w.tag),x+18,yy+6,30,24,14,MUTED);g.text(short(w.tag,20),x+58,yy+8,colW-76,h?28:24,h?20:17,WHITE,'Archivo',1,true);});
          else {g.outline(x+14,y+(h?104:84),colW-28,h?76:90,MUTED,true);g.text('Sin victorias destacadas',x+26,y+(h?120:100),colW-52,h?52:62,h?17:15,MUTED,'Archivo',2);}
        });
      }
      if(other.length){g.text('OTROS RESULTADOS',h?1240:64,h?740:1158,h?584:952,28,h?15:16,MUTED);other.forEach((r,i)=>g.text(`${r.placement}º · ${short(r.name,h?40:22)}`,h?1240:64+(i%2)*476,(h?778:1190)+Math.floor(i/(h?1:2))*(h?32:28),h?584:458,h?30:26,h?18:16,MUTED,'Archivo',1,true));}
    } else {
      if(h){g.diagonal(4,-40,840,1160,PANEL);g.diagonal(872,-40,18,1160,'#FFD23F');}
      else {g.diagonalY(-60,-60,1200,380,PANEL);g.diagonalY(-60,410,1200,12,'#FFD23F');}
      g.image(logo,h?96:64,h?72:60,h?388:320,h?36:30);
      const orgLength=chars(org.name).length,orgSize=(h?[96,68,52]:[72,54,44])[orgLength<=20?0:orgLength<=40?1:2];
      if(h){g.text(season,96,146,520,40,22,BLUE);g.text('TOP',96,200,520,192,220,WHITE,'Big Shoulders Display');g.text(String(org.topSize),96,394,520,190,220,'#FFD23F','Big Shoulders Display');g.text(org.name.toUpperCase(),96,628,520,174,orgSize,WHITE,'Big Shoulders Display',3);}
      else {g.text(org.name.toUpperCase(),64,120,690,136,orgSize,WHITE,'Big Shoulders Display',2,true);g.text('TOP',850,60,166,132,150,WHITE,'Big Shoulders Display');g.text(String(org.topSize),850,196,166,132,150,'#FFD23F','Big Shoulders Display');g.text(season,64,332,500,28,17,BLUE);}
      if(org.coorganizers.length)g.text('Con '+org.coorganizers.join(', '),h?96:64,h?834:276,h?520:690,h?96:54,h?20:17,MUTED,'Archivo',h?3:2,true);
      const podium=data.players.slice(0,3),rest=data.players.slice(3),podY=h?72:org.coorganizers.length?420:390,podH=h?(org.topSize===15?370:org.topSize===10?440:560):(org.topSize===15?340:org.topSize===10?400:500),start=h?720:64,area=h?1104:952;
      const weights=h?[1,1,1]:[1.25,1,1],unit=(area-(podium.length-1)*10)/weights.slice(0,podium.length).reduce((a,b)=>a+b,0);let xx=start;
      podium.forEach((p,i)=>{const w=unit*weights[i],a=accent(p.rank);g.box(xx,podY,w,podH,PANEL);g.box(xx,podY,w,6,a);ctx.save();ctx.globalAlpha=.14;g.text(String(p.rank).padStart(2,'0'),xx+10,podY+14,w-20,180,220,a,'Big Shoulders Display');ctx.restore();icon(p,xx+w-112,podY+24,88);g.diagonal(xx+16,podY+podH-194,92,50,a);g.text(String(p.rank).padStart(2,'0'),xx+26,podY+podH-190,64,44,44,BG,'Big Shoulders Display');g.text(short(p.tag,20).toUpperCase(),xx+16,podY+podH-128,w-32,80,h?60:i?40:50,WHITE,'Big Shoulders Display',2);g.text(main(p)?.name||'Sin personaje registrado',xx+16,podY+podH-40,w-32,32,h?18:15,MUTED,'Archivo',2);xx+=w+10;});
      if(rest.length){const cols=org.topSize===5?1:2,rows=org.topSize===15?6:org.topSize===10?4:2,y=h?podY+podH+28:org.topSize===15?790:org.topSize===10?850:950,available=(h?952:1230)-y,rh=Math.min(org.topSize===5?110:999,(available-(rows-1)*8)/rows),cw=(area-(cols-1)*12)/cols;
        rest.forEach((p,i)=>{const column=Math.floor(i/rows),row=i%rows,x=start+column*(cw+12),yy=y+row*(rh+8);g.box(x,yy,cw,rh,PANEL);g.diagonal(x,yy,64,rh,TRACK);g.text(String(p.rank).padStart(2,'0'),x+12,yy+(rh-38)/2,38,38,34,WHITE,'Big Shoulders Display');icon(p,x+78,yy+(rh-44)/2,44);g.text(short(p.tag,20).toUpperCase(),x+134,yy+(rh-40)/2,cw-150,40,h?34:30,WHITE,'Big Shoulders Display',1,true);});}
    }
    const footer=`Top de ${org.name} · solo sus torneos · no es el ranking nacional · rankingsmashbros.com`;
    g.box(h?96:64,h?982:1256,h?10:9,h?10:9,'#FFD23F');g.text(footer,h?120:85,h?980:1254,h?1704:931,h?60:52,h?19:16,MUTED,'Archivo',3);
    ctx.restore();return {canvas,bounds:bounds.map(b=>({...b,y:b.y+y0})),format};
  }
  const imageCache=new Map();
  async function prepare(data,doc=document,ImageClass=Image) {
    validate(data);
    const sample=[data.organizer.name,...data.organizer.coorganizers,...data.players.flatMap(p=>[p.tag,...p.mains.map(m=>m.name),...p.results.map(r=>r.name)])].join(' ');
    const loaded=await Promise.all([doc.fonts.load('900 72px "Big Shoulders Display"',sample),doc.fonts.load('700 22px "Archivo"',sample)]);await doc.fonts.ready;
    if(loaded.some(faces=>!faces.length||faces.some(face=>face.status!=='loaded'))||!doc.fonts.check('900 72px "Big Shoulders Display"')||!doc.fonts.check('700 22px "Archivo"'))throw Error('No se cargaron las fuentes. Intenta de nuevo.');
    const slugs=new Set();for(const p of data.players){p.mains.forEach(c=>slugs.add(c.slug));p.results.forEach(r=>r.wins.forEach(w=>{if(w.mainSlug)slugs.add(w.mainSlug);}));}
    const jobs=[['logo','./assets/rsb-logo-gt-oscuro.svg']];
    for(const slug of slugs)if(/^[a-z0-9_]{1,80}$/.test(slug))for(const kind of ['icon','portrait'])jobs.push([slug+'-'+kind,`./assets/characters/${slug}-${kind}.png`]);
    const images=new Map();await Promise.all(jobs.map(([key,url])=>new Promise(resolve=>{if(ImageClass===globalThis.Image&&imageCache.has(url)){images.set(key,imageCache.get(url));resolve();return;}const img=new ImageClass(),timer=setTimeout(()=>resolve(),10000);img.onload=()=>{clearTimeout(timer);images.set(key,img);if(ImageClass===globalThis.Image)imageCache.set(url,img);resolve();};img.onerror=()=>{clearTimeout(timer);resolve();};img.src=url;})));
    if(!images.has('logo'))throw Error('No se cargó el logo. Intenta de nuevo.');return images;
  }
  const png=canvas=>new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(Error('No se pudo crear el PNG.')),'image/png'));
  const crcTable=Uint32Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
  const crc32=bytes=>{let n=0xffffffff;for(const b of bytes)n=crcTable[(n^b)&255]^(n>>>8);return(n^0xffffffff)>>>0;};
  // ZIP32, UTF-8 filenames, no compression. Hard cap protects browser memory; no dependency.
  function zip(files) {
    if(files.length>16||files.some(f=>!f.bytes||!(/^[\w-]+\.png$/).test(f.name))||new Set(files.map(f=>f.name)).size!==files.length)throw Error('Archivos ZIP no válidos.');
    if(files.reduce((n,f)=>n+f.bytes.length,0)>64*1024*1024)throw Error('El ZIP supera 64 MiB. Descarga las láminas por separado.');
    const parts=[],central=[];let offset=0,centralSize=0;
    for(const f of files){const name=new TextEncoder().encode(f.name),crc=crc32(f.bytes),local=new Uint8Array(30+name.length),v=new DataView(local.buffer);v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint16(12,33,true);v.setUint32(14,crc,true);v.setUint32(18,f.bytes.length,true);v.setUint32(22,f.bytes.length,true);v.setUint16(26,name.length,true);local.set(name,30);parts.push(local,f.bytes);
      const c=new Uint8Array(46+name.length),q=new DataView(c.buffer);q.setUint32(0,0x02014b50,true);q.setUint16(4,20,true);q.setUint16(6,20,true);q.setUint16(8,0x800,true);q.setUint16(14,33,true);q.setUint32(16,crc,true);q.setUint32(20,f.bytes.length,true);q.setUint32(24,f.bytes.length,true);q.setUint16(28,name.length,true);q.setUint32(42,offset,true);c.set(name,46);central.push(c);centralSize+=c.length;offset+=local.length+f.bytes.length;
    }
    const end=new Uint8Array(22),e=new DataView(end.buffer);e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,centralSize,true);e.setUint32(16,offset,true);return new Blob([...parts,...central,end],{type:'application/zip'});
  }
  function controls(data) {
    if(!data||!data.players?.length)return '';
    return `<details class="o-laminas"><summary>Descargar láminas <span aria-hidden="true">↓</span></summary><p class="note">PNG para tus redes, generados en este navegador. Solo tus torneos que cuentan. El ZIP incluye el top completo y una lámina por jugador en el formato elegido.</p><div class="o-lamina-controls"><div><label for="o-slide-format">Formato</label><select id="o-slide-format" data-slide-format><option value="h">Horizontal · 1920 × 1080</option><option value="v">Publicación · 1080 × 1350</option><option value="s">Historia · 1080 × 1920</option></select></div><div><label for="o-slide-player">Lámina</label><select id="o-slide-player" data-slide-player><option value="top">Top completo</option>${data.players.map(p=>`<option value="${p.rank}">${p.rank} · ${esc(short(p.tag,20))}</option>`).join('')}</select></div></div><div class="button-row"><button type="button" class="outline" data-slide-download="one">Descargar PNG</button><button type="button" class="p-cta blue o-inline" data-slide-download="all"><span>Descargar todas · ZIP</span></button></div><p class="note" data-slide-status role="status" aria-live="polite"></p><div data-slide-preview></div></details>`;
  }
  function save(blob,name) {
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  }
  async function download(button,data) {
    const root=button.closest('.o-laminas');if(!root||root.dataset.busy==='true')return;
    root.dataset.busy='true';const controls=[...root.querySelectorAll('button,select')],status=root.querySelector('[data-slide-status]');controls.forEach(c=>c.disabled=true);
    try {
      validate(data);const format=root.querySelector('[data-slide-format]').value,choice=root.querySelector('[data-slide-player]').value;
      const selected=button.dataset.slideDownload==='all'?[null,...data.players]:[choice==='top'?null:data.players.find(p=>p.rank===Number(choice))];
      if(selected.some(p=>p===undefined))throw Error('Lámina no disponible.');
      status.textContent='Cargando fuentes e imágenes…';const images=await prepare(data),files=[];let archiveBytes=0;
      for(let i=0;i<selected.length;i++){
        if(!root.isConnected)return;status.textContent=`Preparando ${i+1} de ${selected.length}…`;
        const {canvas}=draw(data,format,selected[i],null,images),blob=await png(canvas);
        if(selected.length===1){root.querySelector('[data-slide-preview]').replaceChildren(canvas);canvas.setAttribute('aria-label',selected[i]?`Lámina de ${selected[i].tag}`:'Lámina del top completo');canvas.setAttribute('role','img');files.push({name:filename(data,selected[i],format),blob});}
        else {archiveBytes+=blob.size;if(archiveBytes>64*1024*1024)throw Error('El ZIP supera 64 MiB. Descarga las láminas por separado.');files.push({name:filename(data,selected[i],format),bytes:new Uint8Array(await blob.arrayBuffer())});canvas.width=canvas.height=1;}
      }
      if(!root.isConnected)return;
      const all=button.dataset.slideDownload==='all';save(all?zip(files):files[0].blob,all?`top-${data.organizer.topSize}-${safeName(data.organizer.name)}-${{h:'horizontal',v:'vertical',s:'historia'}[format]}.zip`:files[0].name);status.textContent=all?`${files.length} láminas listas en el ZIP.`:'PNG listo. La vista previa está debajo.';
    } catch(error){status.textContent=error.message||'No se pudieron crear las láminas. Intenta de nuevo.';}
    finally {root.dataset.busy='false';controls.forEach(c=>c.disabled=false);}
  }
  return {FORMATS,validate,draw,prepare,png,zip,crc32,filename,controls,download};
})();
if(typeof module!=='undefined')module.exports=SmashLaminas;
