/* Own static snapshots only. No Instagram SDK, embeds, remote images or browser credentials. */
(function (global) {
  'use strict';
  const PATH=/^assets\/instagram\/[a-f0-9]{64}-(?:full|thumb)\.(?:webp|jpg)$/;
  const LINK=/^https:\/\/www\.instagram\.com\/(?:p|reel|tv)\/[A-Za-z0-9_-]+\/?$/;
  const TYPES={IMAGE:'Foto',VIDEO:'Video · portada',CAROUSEL_ALBUM:'Carrusel · primera imagen'};
  const stamp=value=>typeof value==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(value)&&Number.isFinite(Date.parse(value));
  function normalize(feed) {
    if(!feed||feed.schemaVersion!==1||!stamp(feed.generatedAt)||!Array.isArray(feed.posts)||feed.posts.length>12)return null;
    const seen=new Set(),posts=[];
    for(const p of feed.posts){
      if(!p||typeof p.id!=='string'||!(/^[1-9][0-9]{0,39}$/).test(p.id)||seen.has(p.id)||!Object.hasOwn(TYPES,p.type)||typeof p.caption!=='string'||Array.from(p.caption).length>2200||!LINK.test(p.permalink)||!stamp(p.timestamp))return null;
      seen.add(p.id);let image=null;
      if(p.image!==null){
        const i=p.image;if(!i||!PATH.test(i.src)||!PATH.test(i.thumbnail))return null;
        if(!['width','height','thumbnailWidth','thumbnailHeight'].every(k=>Number.isInteger(i[k])&&i[k]>0&&i[k]<=(k.startsWith('thumbnail')?360:1080)))return null;
        image={src:i.src,thumbnail:i.thumbnail,width:i.width,height:i.height,thumbnailWidth:i.thumbnailWidth,thumbnailHeight:i.thumbnailHeight};
      }
      posts.push({id:p.id,type:p.type,caption:p.caption,permalink:p.permalink,timestamp:p.timestamp,image});
    }
    return {generatedAt:feed.generatedAt,posts:posts.sort((a,b)=>Date.parse(b.timestamp)-Date.parse(a.timestamp)||b.id.localeCompare(a.id))};
  }
  const alt=caption=>Array.from(caption.replace(/\s+/gu,' ').trim()).slice(0,180).join('')||'Publicación de Ranking Smash Bros';
  const date=value=>new Intl.DateTimeFormat('es-GT',{day:'numeric',month:'long',year:'numeric',timeZone:'America/Guatemala'}).format(new Date(value));
  async function load(fetcher=global.fetch){
    const r=await fetcher('./data/instagram.json',{credentials:'omit',cache:'no-cache',headers:{Accept:'application/json'}});
    if(!r.ok||Number(r.headers?.get('content-length')||0)>131072)return null;
    let raw;
    if(r.body?.getReader){
      const reader=r.body.getReader(),chunks=[];let size=0;
      try{while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;if(size>131072){await reader.cancel();return null;}chunks.push(value);}}finally{reader.releaseLock();}
      const bytes=new Uint8Array(size);let at=0;for(const part of chunks){bytes.set(part,at);at+=part.length;}raw=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
    }else{raw=await r.text();if(new TextEncoder().encode(raw).length>131072)return null;}
    try{return normalize(JSON.parse(raw));}catch{return null;}
  }
  function init(doc,host=global){
  const section=doc.querySelector('[data-instagram]');if(!section)return {ready:Promise.resolve()};
  const grid=section.querySelector('.ig-grid'),empty=section.querySelector('.ig-empty'),dialog=doc.getElementById('ig-dialog');
  let opener=null;
  const el=(tag,cls,text)=>{const n=doc.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  function picture(image,caption,large=false){
    const box=el('div','ig-picture'),fallback=el('div','ig-picture-fallback');
    const mark=el('img');mark.src='./assets/rsb-mark.svg';mark.alt='';mark.width=64;mark.height=64;fallback.append(mark);box.append(fallback);
    if(image){const img=el('img','ig-photo');img.src='./'+(large?image.src:image.thumbnail);img.alt=alt(caption);img.width=large?image.width:image.thumbnailWidth;img.height=large?image.height:image.thumbnailHeight;img.loading=large?'eager':'lazy';img.decoding='async';img.addEventListener('error',()=>img.remove(),{once:true});box.append(img);}return box;
  }
  function open(post,button){
    if(!dialog||typeof dialog.showModal!=='function'){host.open(post.permalink,'_blank','noopener,noreferrer');return;}
    opener=button;const media=dialog.querySelector('.ig-dialog-media');media.replaceChildren(picture(post.image,post.caption,true));
    dialog.querySelector('.ig-dialog-type').textContent=TYPES[post.type];
    const time=dialog.querySelector('time');time.dateTime=post.timestamp;time.textContent=date(post.timestamp);
    dialog.querySelector('.ig-dialog-caption').textContent=post.caption;
    dialog.querySelector('.ig-original').href=post.permalink;dialog.showModal();doc.body.classList.add('ig-modal-open');dialog.querySelector('.ig-close').focus();
  }
  if(dialog){
    dialog.querySelector('.ig-close').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
    dialog.addEventListener('close',()=>{doc.body.classList.remove('ig-modal-open');dialog.querySelector('.ig-dialog-media').replaceChildren();if(opener?.isConnected)opener.focus({preventScroll:true});opener=null;});
  }
  async function start(){
    let feed=null;try{feed=await load(host.fetch.bind(host));}catch{}
    if(!feed?.posts.length){if(section.dataset.instagram==='preview')section.hidden=true;if(empty)empty.hidden=false;return;}
    const posts=section.dataset.instagram==='preview'?feed.posts.slice(0,6):feed.posts;
    for(const post of posts){
      const card=el('button','ig-card');card.type='button';card.setAttribute('aria-haspopup','dialog');card.setAttribute('aria-label',`Abrir publicación del ${date(post.timestamp)}: ${alt(post.caption)}`);
      card.append(picture(post.image,post.caption));const info=el('span','ig-card-info');info.append(el('span','ig-type',TYPES[post.type]));
      const time=el('time','ig-date',date(post.timestamp));time.dateTime=post.timestamp;info.append(time);info.append(el('span','ig-card-caption',post.caption||'Ranking Smash Bros'));card.append(info);card.addEventListener('click',()=>open(post,card));grid.append(card);
    }
    if(empty)empty.hidden=true;section.hidden=false;
  }
  const trigger=doc.querySelector('[data-instagram-trigger]');
  let ready;
  if(trigger&&'IntersectionObserver' in host){ready=new Promise(resolve=>{const observer=new host.IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();start().then(resolve);}},{rootMargin:'300px'});observer.observe(trigger);});}else ready=start();
  return {ready};
  }
  const model={normalize,alt,date,load,TYPES,init};
  if(typeof module!=='undefined'&&module.exports)module.exports=model;
  if(global.document)init(global.document,global);
})(typeof window!=='undefined'?window:globalThis);
