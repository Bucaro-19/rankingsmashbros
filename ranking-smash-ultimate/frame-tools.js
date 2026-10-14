/* Numeric frame facts from the private premium response; never fetches the source. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SmashFrameTools=api;})(globalThis,()=>{
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function fits(options,onShield){return Number.isInteger(onShield)&&onShield<0?(options||[]).filter(o=>Number.isInteger(o.frame)&&o.frame>0&&o.frame<=-onShield):[];}
  function sheet({title,main,mainName,facts,moves}){
    if(!facts)return `<p class="pr-empty">— Aún no hay ficha técnica de ${esc(title)}. Sus resultados en las otras secciones siguen valiendo.</p>`;
    const f=facts.fastest,options=facts.oos||[];
    const rows=options.map(o=>`<li><span>${esc(o.name)}</span><b>frame ${esc(o.frame)}</b></li>`).join('');
    const punish=!main?'<p class="pr-empty">— Sin main detectado del rival: no podemos listar sus castigables.</p>':!(moves||[]).length?`<p class="pr-empty">— No tenemos golpes con ventaja inequívoca en escudo de su ${esc(mainName)} en esta ficha.</p>`:
      `<ul class="pr-punishes">${moves.map(m=>{const available=fits(options,m.onShield);return `<li><div><strong>${esc(m.name)}</strong><span>−${esc(-m.onShield)} en escudo · te deja ${esc(-m.onShield)} frames</span></div><p class="${available.length?'pr-fits':'pr-note'}">${available.length?'✓ Te entran: '+available.map(o=>`${esc(o.name)} (frame ${esc(o.frame)})`).join(', '):'× Ninguna de tus opciones fuera del escudo registradas entra a tiempo'}</p></li>`;}).join('')}</ul>`;
    return `<p class="pr-kicker">Tu movimiento más rápido · normales en tierra con dato inequívoco</p><p class="pr-fast"><strong>${esc(f.name)}</strong><b>frame ${esc(f.frame)}</b><span>${esc(f.damage)}% de daño base</span></p><p class="pr-kicker">Tus opciones fuera del escudo${options.length?' · '+options.length:''}</p>${rows?`<ul class="pr-frame-rows">${rows}</ul>`:'<p class="pr-empty">— Sin opciones fuera del escudo con dato inequívoco en esta ficha.</p>'}<p class="pr-kicker">Castigables de su ${esc(mainName)}</p>${punish}`;
  }
  function credit(source){return source?`<p class="pr-note">Frames y daño: <a href="https://ultimateframedata.com/smash" target="_blank" rel="noopener noreferrer">Ultimate Frame Data ↗</a>, versión ${source.gameVersion?esc(source.gameVersion)+' del juego':'no declarada por la fuente'}. Son datos del juego, no del ranking.</p>`:'';}
  return {fits,sheet,credit};
});
