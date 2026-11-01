// ==UserScript==
// @name         ChatGPT Conversation Map
// @namespace    https://github.com/browser-tweaks
// @version      1.0.0
// @description  Searchable outline and jump navigation for currently loaded ChatGPT conversation turns.
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(() => {
  'use strict';
  const TURN_SELECTOR='[data-testid^="conversation-turn-"]';
  const host=document.createElement('div');host.id='vm-conversation-map';
  const shadow=host.attachShadow({mode:'open'});
  shadow.innerHTML=`
    <style>
      :host{all:initial;font:13px/1.4 system-ui,sans-serif;color:#222}*{box-sizing:border-box}
      button,input{font:inherit}button{cursor:pointer}
      #toggle{position:fixed;left:12px;bottom:14px;z-index:2147482001;border:0;border-radius:18px;background:#265c52;color:white;padding:9px 13px;box-shadow:0 2px 8px #0005}
      #panel{position:fixed;left:12px;bottom:58px;width:min(370px,calc(100vw - 24px));max-height:min(76vh,760px);background:#fff;color:#222;z-index:2147482002;border:1px solid #bac7c2;border-radius:10px;box-shadow:0 8px 30px #0005;display:none;flex-direction:column;overflow:hidden}
      #panel.open{display:flex}header{padding:10px 12px;background:#265c52;color:#fff;display:flex;align-items:center;justify-content:space-between}
      #close{color:#222;background:white;border:0;border-radius:4px;padding:3px 8px}#filters{display:grid;gap:7px;padding:10px;border-bottom:1px solid #ddd}
      input[type="search"]{padding:8px;border:1px solid #aab;border-radius:5px;width:100%;color:#222;background:#fff}
      #items{overflow:auto;padding:8px;min-height:50px}.turn{width:100%;text-align:left;border:0;background:#fff;color:#222;padding:9px;border-bottom:1px solid #ddd;border-radius:5px;display:grid;gap:3px}
      .turn:hover,.turn:focus-visible{background:#e4f3ed}.role{font-weight:700;color:#23695b;font-size:11px}.turn.assistant .role{color:#6c5b88}.snippet{overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
      #status{padding:8px 12px;font-size:11px;color:#5b6266;border-top:1px solid #ddd}label{display:flex;align-items:center;gap:5px}
    </style>
    <button id="toggle" type="button" title="Conversation Map (Alt+Shift+M)">Map</button>
    <section id="panel" role="dialog" aria-label="Conversation Map" aria-modal="false">
      <header><strong>Conversation Map</strong><button id="close" type="button">✕</button></header>
      <div id="filters"><input id="search" type="search" placeholder="Find a question or response" aria-label="Search conversation turns"><label><input id="only-user" type="checkbox" checked> User prompts only</label></div>
      <div id="items"></div><div id="status" role="status">Currently loaded turns only</div>
    </section>`;
  const $=id=>shadow.getElementById(id);
  let open=false,lastRoute=location.pathname,selected=null,refreshTimer=0,lastSummary='';
  const isUser=el=>el.getAttribute('data-message-author-role')==='user'||!!el.querySelector('[data-message-author-role="user"],[data-testid="user-message"],[data-testid="user-message-bubble"]');
  function getTurns() {
    const result=[...document.querySelectorAll(TURN_SELECTOR)];
    return result.length ? result : [...document.querySelectorAll('main article')].filter(el=>!el.parentElement?.closest('article'));
  }
  function readTurn(el) {
    // Prefer the actual message payload; exclude toolbar/button chrome where possible.
    const message=el.querySelector('[data-message-author-role],.markdown,[data-testid="user-message"]') || el;
    const clone=message.cloneNode(true);
    clone.querySelectorAll('button,nav,svg,textarea,script,style,[aria-hidden="true"]').forEach(x=>x.remove());
    return (clone.innerText || clone.textContent || '').replace(/\s+/g,' ').trim().slice(0,240);
  }
  function jump(el) {
    if(selected?.isConnected)selected.style.removeProperty('outline');
    selected=el;el.style.setProperty('outline','2px solid #10a37f','important');
    el.scrollIntoView({behavior:'smooth',block:'center'});
  }
  function render() {
    if(!open)return;
    if(location.pathname!==lastRoute) { lastRoute=location.pathname;selected=null;$('search').value=''; }
    const turns=getTurns();
    const q=$('search').value.trim().toLowerCase(), onlyUser=$('only-user').checked;
    const entries=turns.map((el,index)=>({el,index,user:isUser(el),text:readTurn(el)}))
      .filter(e=>(!onlyUser||e.user)&&(!q||e.text.toLowerCase().includes(q)));
    const signature=location.pathname+'|'+q+'|'+onlyUser+'|'+entries.map(e=>e.index+':'+e.text).join('|');
    if(signature===lastSummary)return;
    lastSummary=signature;$('items').replaceChildren();
    for(const e of entries) {
      const btn=document.createElement('button');btn.type='button';btn.className='turn'+(e.user?'':' assistant');
      const role=document.createElement('span');role.className='role';role.textContent=`#${e.index+1} · ${e.user?'You':'Assistant'}`;
      const summary=document.createElement('span');summary.className='snippet';summary.textContent=e.text || '(no readable text)';
      btn.append(role,summary);btn.addEventListener('click',()=>jump(e.el));$('items').append(btn);
    }
    $('status').textContent=`${entries.length} shown / ${turns.length} currently loaded turns. Older virtualized turns may be missing.`;
  }
  function setOpen(value) {
    open=value;$('panel').classList.toggle('open',value);
    if(value) {lastSummary='';render();$('search').focus();}
  }
  $('toggle').addEventListener('click',()=>setOpen(!open));$('close').addEventListener('click',()=>setOpen(false));
  $('search').addEventListener('input',()=>{lastSummary='';render();});
  $('only-user').addEventListener('change',()=>{lastSummary='';render();});
  window.addEventListener('keydown',e=>{
    if(e.altKey&&e.shiftKey&&!e.ctrlKey&&!e.metaKey&&e.code==='KeyM') {e.preventDefault();setOpen(!open);}
    if(e.key==='Escape'&&open)setOpen(false);
  });
  window.addEventListener('popstate',()=>{lastSummary='';render();});
  function schedule() {
    if(!open||refreshTimer)return;
    refreshTimer=setTimeout(()=>{refreshTimer=0;render();},700);
  }
  function mount() {
    if(!document.body)return;
    document.body.append(host);
    new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true,characterData:true});
  }
  if(document.body)mount();else document.addEventListener('DOMContentLoaded',mount,{once:true});
})();
