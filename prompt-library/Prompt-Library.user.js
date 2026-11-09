// ==UserScript==
// @name         Prompt Library for AI Chats
// @namespace    https://github.com/browser-tweaks
// @version      1.2.1
// @description  Manage reusable prompts locally and insert them into AI chat composers.
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @match        https://claude.ai/*
// @match        https://gemini.google.com/*
// @match        https://copilot.microsoft.com/*
// @match        https://chat.deepseek.com/*
// @match        https://www.perplexity.ai/*
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_setClipboard
// @run-at       document-idle
// ==/UserScript==

(() => {
  'use strict';
  const KEY = 'prompt-library-v1';
  const LIMIT = 250;
  const safeString = s => typeof s === 'string' ? s : '';
  const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2,10)}`;
  function sanitize(items) {
    if (!Array.isArray(items)) throw new Error('Expected an array of prompts.');
    if (items.length > LIMIT) throw new Error(`Maximum ${LIMIT} prompts.`);
    return items.map(p => {
      if (!p || typeof p !== 'object' || typeof p.title !== 'string' || typeof p.body !== 'string') throw new Error('Each prompt needs title and body strings.');
      const title = p.title.trim().slice(0,100), body = p.body.slice(0,20000);
      if (!title || !body.trim()) throw new Error('Title and body cannot be blank.');
      return { id:uid(), title, body };
    });
  }
  let prompts;
  try { prompts = sanitize(JSON.parse(GM_getValue(KEY,'[]'))); }
  catch (err) { console.warn('Prompt Library: storage could not be parsed',err); prompts = []; }
  const save = () => GM_setValue(KEY, JSON.stringify(prompts));
  const host = document.createElement('div'); host.id = 'vm-prompt-library';
  host.style.setProperty('position', 'fixed', 'important');
  host.style.setProperty('inset', '0', 'important');
  host.style.setProperty('z-index', '2147483646', 'important');
  host.style.setProperty('pointer-events', 'none', 'important');
  const shadow = host.attachShadow({mode:'open'});
  shadow.innerHTML = `
    <style>
      :host{font:12px system-ui,sans-serif;color:#222;pointer-events:none}
      *{box-sizing:border-box}button,input,textarea{font:inherit}
      #launcher{position:absolute;left:8px;bottom:112px;pointer-events:auto;z-index:2;
        width:34px;height:34px;display:flex;align-items:center;justify-content:center;
        background:#243b53;color:white;border:0;border-radius:999px;padding:0;
        font-weight:700;font-size:16px;line-height:1;cursor:pointer;
        box-shadow:0 2px 8px #0004}
      #launcher:hover{transform:translateY(-1px)}
      #panel{position:absolute;left:48px;bottom:98px;width:min(375px,calc(100vw - 58px));
        max-height:min(70vh,650px);pointer-events:auto;display:none;flex-direction:column;
        z-index:2147482002;background:#fff;color:#222;border:1px solid #aab;
        border-radius:8px;box-shadow:0 6px 22px #0005;overflow:hidden}
      #panel.open{display:flex}
      header{background:#243b53;color:#fff;padding:5px 8px;min-height:29px;
        display:flex;justify-content:space-between;align-items:center}
      header strong{font-size:12px}
      #main{padding:7px;overflow:auto;display:grid;gap:5px}
      input,textarea{width:100%;padding:5px 7px;border:1px solid #aab;
        border-radius:4px;background:#fff;color:#222}
      #search{height:27px}
      textarea{min-height:90px;resize:vertical}
      button{cursor:pointer;border:1px solid #bdc5ce;background:#f4f6f8;color:#222;
        border-radius:4px;padding:3px 6px;min-height:23px;line-height:1.15;white-space:nowrap}
      button:hover{background:#e5edf4}
      header button{background:#fff;color:#222;min-height:20px;padding:1px 6px}
      .row{display:flex;gap:4px;align-items:center;flex-wrap:nowrap}
      #entries{display:grid;gap:2px}
      .entry{border:1px solid #e1e4e8;border-radius:4px;padding:3px 4px;
        display:flex;gap:5px;align-items:center;min-height:29px}
      .entry:hover{background:#f7f9fb}
      .entry strong{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;
        white-space:nowrap;font-size:12px;cursor:help}
      .entry .row{flex-shrink:0;gap:3px}
      .entry button{padding:2px 5px;min-height:21px;font-size:11px}
      .entry button.delete{width:21px;padding:2px 0}
      #editor{display:none;gap:5px;border-top:1px solid #ddd;padding-top:6px}
      #editor.open{display:grid}
      #notice{font-size:11px;color:#576575}
      #notice:empty{display:none}
      #file{display:none}
      @media(max-width:420px){#launcher{left:6px;bottom:104px;width:32px;height:32px;font-size:15px}
        #panel{left:42px;bottom:92px;width:calc(100vw - 50px)}
        .entry button{padding:2px 4px}}
    </style>
    <button id="launcher" type="button" title="Prompt Library (Alt+Shift+P)" aria-label="Prompt Library">P</button>
    <section id="panel" role="dialog" aria-label="Prompt Library" aria-modal="false">
      <header><strong>Prompt Library</strong><button id="close" type="button" aria-label="Close">✕</button></header>
      <div id="main">
        <input id="search" type="search" placeholder="Search saved prompts" aria-label="Search prompts">
        <div class="row"><button id="new" type="button">+ New</button><button id="export" type="button">Export</button><button id="import" type="button">Import</button><input id="file" type="file" accept="application/json,.json"></div>
        <div id="entries"></div>
        <div id="editor"><input id="title" maxlength="100" placeholder="Prompt title" aria-label="Prompt title"><textarea id="body" maxlength="20000" placeholder="Prompt text" aria-label="Prompt text"></textarea><div class="row"><button id="save" type="button">Save</button><button id="cancel" type="button">Cancel</button></div></div>
        <div id="notice" role="status"></div>
      </div>
    </section>`;
  const $ = id => shadow.getElementById(id);
  let editing = null, previousFocus = null;
  const notify = msg => { $('notice').textContent = msg; };
  function openPanel() {
    previousFocus = document.activeElement;
    $('panel').classList.add('open'); render(); $('search').focus();
  }
  function closePanel() { $('panel').classList.remove('open'); if(previousFocus?.isConnected) previousFocus.focus(); }
  $('launcher').addEventListener('click',() => $('panel').classList.contains('open') ? closePanel() : openPanel());
  $('close').addEventListener('click',closePanel);
  window.addEventListener('keydown',e => {
    if (e.altKey && e.shiftKey && !e.ctrlKey && !e.metaKey && e.code === 'KeyP') {
      e.preventDefault(); $('panel').classList.contains('open') ? closePanel() : openPanel();
    }
    if (e.key === 'Escape' && $('panel').classList.contains('open')) closePanel();
  });
  function edit(prompt=null) {
    editing=prompt?.id || null; $('title').value=prompt?.title || ''; $('body').value=prompt?.body || '';
    $('editor').classList.add('open'); $('title').focus();
  }
  $('new').addEventListener('click',()=>edit());
  $('cancel').addEventListener('click',()=>$('editor').classList.remove('open'));
  $('save').addEventListener('click',() => {
    const title=$('title').value.trim(), body=$('body').value;
    if (!title || !body.trim()) return notify('Title and prompt text are required.');
    if (!editing && prompts.length>=LIMIT) return notify('Prompt limit reached.');
    if (editing) { const item=prompts.find(p=>p.id===editing); if(item) Object.assign(item,{title,body}); }
    else prompts.unshift({id:uid(),title,body});
    save(); $('editor').classList.remove('open'); render(); notify('Saved locally.');
  });
  function composer() {
    const selectors = [
      '#prompt-textarea[contenteditable="true"]',
      '[data-testid="chat-input"] [contenteditable="true"]',
      'main [role="textbox"][contenteditable="true"]',
      'main [contenteditable="true"]',
      'main textarea',
      'textarea[placeholder]',
      '[contenteditable="true"][role="textbox"]',
    ];
    for (const selector of selectors) {
      const els = [...document.querySelectorAll(selector)];
      const match = els.reverse().find(el => el.getClientRects().length && !el.closest('#vm-prompt-library'));
      if (match) return match;
    }
    return null;
  }
  function insert(text) {
    const el = composer();
    if (!el) { GM_setClipboard(text); return notify('Composer not found; prompt copied to clipboard.'); }
    el.focus();
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
      const setter = Object.getOwnPropertyDescriptor(el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,'value').set;
      const start=el.selectionStart ?? el.value.length, end=el.selectionEnd ?? el.value.length;
      setter.call(el, el.value.slice(0,start) + text + el.value.slice(end));
      el.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:text}));
      el.setSelectionRange(start+text.length,start+text.length);
    } else {
      // execCommand is deprecated but still the most compatible way to trigger
      // editors' input handling. If it fails, copy instead of silently losing text.
      const ok = document.execCommand('insertText',false,text);
      if (!ok) { GM_setClipboard(text); return notify('Editor rejected insertion; prompt copied to clipboard.'); }
    }
    notify('Inserted into the composer (not sent).');
  }
  function render() {
    $('entries').replaceChildren();
    const query=$('search').value.trim().toLowerCase();
    const list=prompts.filter(p=>(p.title+' '+p.body).toLowerCase().includes(query));
    if (!list.length) { const empty=document.createElement('p'); empty.textContent='No matching prompts.'; $('entries').append(empty); }
    for (const p of list) {
      const item=document.createElement('div'); item.className='entry';
      const title=document.createElement('strong'); title.textContent=p.title;
      title.title=p.body; // Native hover tooltip shows the complete prompt.
      const actions=document.createElement('div'); actions.className='row';
      for (const [label,cb] of [
        ['Insert',()=>{const body=p.body;closePanel();insert(body);}],
        ['Copy',()=>{GM_setClipboard(p.body);notify('Copied to clipboard.');}],
        ['Edit',()=>edit(p)],
        ['×',()=>{if(confirm(`Delete prompt "${p.title}"?`)){prompts=prompts.filter(x=>x.id!==p.id);save();render();}}],
      ]) { const btn=document.createElement('button');btn.type='button';btn.textContent=label;if(label==='×'){btn.className='delete';btn.title='Delete prompt';btn.setAttribute('aria-label','Delete '+p.title);}btn.addEventListener('click',cb);actions.append(btn); }
      item.append(title,actions);$('entries').append(item);
    }
  }
  $('search').addEventListener('input',render);
  $('export').addEventListener('click',() => {
    const content=JSON.stringify(prompts.map(({title,body})=>({title,body})),null,2);
    const url=URL.createObjectURL(new Blob([content],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='prompt-library.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $('import').addEventListener('click',()=>$('file').click());
  $('file').addEventListener('change',async () => {
    const file=$('file').files?.[0];$('file').value='';if(!file)return;
    if(file.size>5_000_000)return notify('Import file exceeds 5 MB.');
    try {
      const imported=sanitize(JSON.parse(await file.text()));
      if(!confirm(`Replace all ${prompts.length} saved prompts with ${imported.length} imported prompts?`))return;
      prompts=imported;save();render();notify('Imported prompts; previous library replaced.');
    } catch(err) { notify(`Import failed: ${safeString(err.message)}`); }
  });
  // ChatGPT may replace the body contents after the userscript mounts.
  // Observe actual body children, not only changes to <html>.
  let watchedBody = null;
  const observer = new MutationObserver(() => {
    if (!document.body) return;
    if (host.parentElement !== document.body) mount();
    if (watchedBody !== document.body) watchBody();
  });

  function mount() {
    if (!document.body) return;
    if (host.parentElement !== document.body) document.body.append(host);
  }

  function watchBody() {
    if (!document.documentElement) return;
    observer.disconnect();
    observer.observe(document.documentElement, { childList: true });
    watchedBody = document.body;
    if (watchedBody) observer.observe(watchedBody, { childList: true });
  }

  function start() {
    mount();
    watchBody();
  }

  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start, { once: true });

  console.info('[Prompt Library] v1.2.1 initialized on', location.hostname);
})();
