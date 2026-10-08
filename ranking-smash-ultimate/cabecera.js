/* Shared header: show who is signed in. The stored tag is only a display hint written by the
   account page; the server confirms it, and visitors who never signed in make no account request. */
(() => {
  const link=document.getElementById('account-link');
  if(!link)return;
  const show=tag=>{
    if(typeof tag!=='string'||!tag.trim()){link.textContent='Iniciar sesión';link.removeAttribute('aria-label');return;}
    const name=tag.trim();
    link.textContent=name.length>18?`${name.slice(0,17)}…`:name;link.setAttribute('aria-label',`Tu cuenta: ${name}`);
  };
  let hint=null;
  try{hint=localStorage.getItem('smashgt.cuenta');}catch{}
  if(!hint)return;
  show(hint);
  fetch('./account-api.php',{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}})
    .then(response=>response.ok?response.json():null)
    .then(data=>{
      if(!data||data.ok!==true)return;
      const tag=data.authenticated?data.user.tag:null;
      try{if(tag)localStorage.setItem('smashgt.cuenta',tag);else localStorage.removeItem('smashgt.cuenta');}catch{}
      show(tag);
      // The server says so only to the owner's signed-in account.
      const panel=document.getElementById('panel-link');if(panel)panel.hidden=!(data.authenticated&&data.panel===true);
    }).catch(()=>{});
})();
