/* Counts one page view for the owner's private statistics. No third parties, no page content. */
(() => {
  const page=document.currentScript&&document.currentScript.dataset.page;
  if(!page||navigator.webdriver)return;
  const send=()=>fetch('./visita.php',{method:'POST',credentials:'same-origin',cache:'no-store',keepalive:true,
    headers:{'Content-Type':'application/json'},body:JSON.stringify({page,cookies:navigator.cookieEnabled!==false})}).catch(()=>{});
  if(document.visibilityState==='prerender')document.addEventListener('visibilitychange',send,{once:true});else send();
})();
