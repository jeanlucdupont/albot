// ==UserScript==
// @name         Prompt Library for AI Chats
// @namespace    https://github.com/browser-tweaks
// @version      1.0.0
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
  const shadow = host.attachShadow({mode:'open'});
  shadow.innerHTML = `
    <style>
      :host{all:initial;font:14px system-ui,sans-serif;color:#222}
      *{box-sizing:border-box} button,input,textarea{font:inherit}
      #launcher{position:fixed;right:18px;bottom:62px;z-index:2147482001;background:#243b53;color:#fff;border:0;border-radius:18px;padding:9px 13px;cursor:pointer;box-shadow:0 2px 9px #0004}
      #panel{position:fixed;right:18px;bottom:108px;width:min(430px,calc(100vw - 36px));max-height:min(75vh,700px);display:none;flex-direction:column;z-index:2147482002;background:#fff;color:#222;border:1px solid #aab;border-radius:12px;box-shadow:0 8px 32px #0005;overflow:hidden}
      #panel.open{display:flex}header{background:#243b53;color:#fff;padding:12px;display:flex;justify-content:space-between;align-items:center}
      #main{padding:12px;overflow:auto;display:grid;gap:9px}input,textarea{width:100%;padding:9px;border:1px solid #aab;border-radius:5px;background:#fff;color:#222}textarea{min-height:95px;resize:vertical}
      button{cursor:pointer;border:1px solid #bdc5ce;background:#f4f6f8;color:#222;border-radius:5px;padding:6px 9px}button:hover{background:#e5edf4}
      header button{background:#fff;color:#222}.row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.entry{border:1px solid #ddd;border-radius:7px;padding:9px;display:grid;gap:6px}.entry strong{overflow-wrap:anywhere}.preview{white-space:pre-wrap;max-height:54px;overflow:hidden;color:#555;font-size:12px}
      #editor{display:none;gap:7px;border-top:1px solid #ddd;padding-top:10px}#editor.open{display:grid}#notice{font-size:12px;color:#576575}#file{display:none}
    </style>
    <button id="launcher" type="button" title="Prompt Library (Alt+Shift+P)">Prompts</button>
    <section id="panel" role="dialog" aria-label="Prompt Library" aria-modal="false">
      <header><strong>Prompt Library</strong><button id="close" type="button" aria-label="Close">✕</button></header>
      <div id="main">
        <input id="search" type="search" placeholder="Search saved prompts" aria-label="Search prompts">
        <div class="row"><button id="new" type="button">New prompt</button><button id="export" type="button">Export JSON</button><button id="import" type="button">Import JSON</button><input id="file" type="file" accept="application/json,.json"></div>
        <div id="entries"></div>
        <div id="editor"><input id="title" maxlength="100" placeholder="Prompt title" aria-label="Prompt title"><textarea id="body" maxlength="20000" placeholder="Prompt text" aria-label="Prompt text"></textarea><div class="row"><button id="save" type="button">Save</button><button id="cancel" type="button">Cancel</button></div></div>
        <div id="notice" role="status">Local storage only. Inserting never submits a prompt.</div>
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
      const preview=document.createElement('div'); preview.className='preview'; preview.textContent=p.body;
      const actions=document.createElement('div'); actions.className='row';
      for (const [label,cb] of [
        ['Insert',()=>{const body=p.body;closePanel();insert(body);}],
        ['Copy',()=>{GM_setClipboard(p.body);notify('Copied to clipboard.');}],
        ['Edit',()=>edit(p)],
        ['Delete',()=>{if(confirm(`Delete prompt "${p.title}"?`)){prompts=prompts.filter(x=>x.id!==p.id);save();render();}}],
      ]) { const btn=document.createElement('button');btn.type='button';btn.textContent=label;btn.addEventListener('click',cb);actions.append(btn); }
      item.append(title,preview,actions);$('entries').append(item);
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
  const mount=()=>{ if(document.body)document.body.append(host); };
  if(document.body) mount(); else document.addEventListener('DOMContentLoaded',mount,{once:true});
})();
