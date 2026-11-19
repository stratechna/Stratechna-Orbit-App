/* Chamadas no CRM do Orbit — fase C1 (docs/PLANO-CHAMADAS-CRM.md, 19-11-2026).
 *
 * Carregado pela página /crm (orbit/www/crm.html). Os botões «Ligar» das fichas (CRM Form Scripts de
 * chamadas_crm.py e actividade_crm.py) chamam window.orbitChamadas.ligar(): o registo nasce no servidor
 * (orbit.chamadas_crm.iniciar), o telefone abre a chamada e, quando a pessoa volta ao CRM, aparece
 * «Como correu a chamada?». O que ficar por comentar volta a ser perguntado da próxima vez (por_comentar).
 *
 * O registo tem o nome «orbit-<chave>», com a chave gerada aqui — por isso a janela sabe que chamada é
 * mesmo que o iPhone suspenda a página antes de o servidor responder.
 */
(function () {
  'use strict'
  if (window.orbitChamadas) return

  const PENDENTE = 'orbit-chamada-pendente'
  const t = (s) => (typeof window.__ === 'function' ? window.__(s) : s)
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

  const ler = () => { try { return JSON.parse(localStorage.getItem(PENDENTE) || 'null') } catch (e) { return null } }
  const guardar = (v) => { try { v ? localStorage.setItem(PENDENTE, JSON.stringify(v)) : localStorage.removeItem(PENDENTE) } catch (e) {} }

  function chave() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID()
    return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12)
  }

  function pedir(metodo, dados, opcoes) {
    const corpo = new URLSearchParams()
    for (const [k, v] of Object.entries(dados || {})) corpo.append(k, v == null ? '' : v)
    return fetch('/api/method/' + metodo, Object.assign({
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json', 'X-Frappe-CSRF-Token': window.csrf_token || '' },
      body: corpo,
    }, opcoes || {})).then((r) => r.json().then((j) => {
      if (!r.ok) throw new Error((j && (j.exception || j._error_message)) || r.statusText)
      return j.message
    }))
  }

  // ---------------------------------------------------------------- ligar

  let saiuDaPagina = false

  function ligar({ numero, doctype, name, nome }) {
    numero = String(numero || '').replace(/[^\d+]/g, '')
    if (!numero) return
    const k = chave()
    guardar({ nome: 'orbit-' + k, ficha: nome || '', numero, inicio: Date.now() })
    saiuDaPagina = false
    pedir('orbit.chamadas_crm.iniciar', { chave: k, numero, doctype, name }, { keepalive: true })
      .catch((e) => { console.warn('[orbit-chamadas] iniciar', e); guardar(null); aviso(t('Não foi possível registar a chamada.'), true) })
    window.location.href = 'tel:' + numero
  }

  function voltou() {
    const p = ler()
    if (!p || document.getElementById('oc-janela')) return
    const passou = (Date.now() - p.inicio) / 1000
    if (passou > 7 * 86400) { guardar(null); return }   // já não se pergunta (por_comentar faz o mesmo)
    if (passou < 4) return                       // ainda a abrir o marcador
    if (!saiuDaPagina && passou < 20) return     // o tel: não chegou a sair do CRM (computador sem telefone)
    janela(p, Math.max(0, Math.round(passou - 6)))
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') saiuDaPagina = true
    else setTimeout(voltou, 400)
  })
  window.addEventListener('blur', () => { if (ler()) saiuDaPagina = true })
  window.addEventListener('focus', () => setTimeout(voltou, 400))
  window.addEventListener('pageshow', () => setTimeout(voltou, 600))

  // ---------------------------------------------------------------- janela

  const ESTADOS = [['atendida', 'Atendida'], ['nao_atendeu', 'Não atendeu'], ['ocupado', 'Ocupado'], ['numero_errado', 'Número errado']]

  function mmss(seg) { seg = Math.max(0, seg | 0); return Math.floor(seg / 60) + ':' + String(seg % 60).padStart(2, '0') }
  function segundos(txt) {
    const m = String(txt || '').trim().match(/^(\d+)(?::(\d{1,2}))?$/)
    return m ? (+m[1]) * 60 + (+(m[2] || 0)) : 0
  }
  function hora(ms) {
    try { return new Date(ms).toLocaleString('pt-PT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) } catch (e) { return '' }
  }

  function janela(p, duracao, depois) {
    estilo()
    fecharAviso()
    const fundo = document.createElement('div')
    fundo.id = 'oc-janela'
    fundo.className = 'oc-fundo'
    fundo.innerHTML = `
      <div class="oc-caixa" role="dialog" aria-modal="true" aria-labelledby="oc-titulo">
        <h2 id="oc-titulo">${esc(t('Como correu a chamada?'))}</h2>
        <p class="oc-sub">${esc([p.ficha, p.numero, hora(p.inicio)].filter(Boolean).join(' · '))}</p>
        <div class="oc-estados" role="radiogroup">
          ${ESTADOS.map(([v, r], i) => `<label><input type="radio" name="oc-estado" value="${v}" ${i ? '' : 'checked'}><span>${esc(t(r))}</span></label>`).join('')}
        </div>
        <label class="oc-campo oc-duracao">${esc(t('Duração (min:seg)'))}
          <input type="text" inputmode="numeric" id="oc-duracao" value="${mmss(duracao)}" autocomplete="off"></label>
        <label class="oc-campo">${esc(t('Nota'))}
          <textarea id="oc-nota" rows="3" placeholder="${esc(t('O que ficou combinado?'))}"></textarea></label>
        <details class="oc-tarefa"><summary>${esc(t('Próxima tarefa'))}</summary>
          <label class="oc-campo">${esc(t('O quê'))}<input type="text" id="oc-tarefa" autocomplete="off"></label>
          <label class="oc-campo">${esc(t('Até'))}<input type="date" id="oc-tarefa-data"></label>
        </details>
        <p class="oc-erro" id="oc-erro" hidden></p>
        <div class="oc-botoes">
          <button type="button" class="oc-anular" id="oc-anular">${esc(t('Não cheguei a ligar'))}</button>
          <span></span>
          <button type="button" class="oc-depois" id="oc-depois">${esc(t('Agora não'))}</button>
          <button type="button" class="oc-gravar" id="oc-gravar">${esc(t('Gravar'))}</button>
        </div>
      </div>`
    document.body.appendChild(fundo)
    const $ = (id) => fundo.querySelector('#' + id)
    const estado = () => (fundo.querySelector('input[name="oc-estado"]:checked') || {}).value
    const acertar = () => { fundo.querySelector('.oc-duracao').style.display = estado() === 'atendida' ? '' : 'none' }
    fundo.querySelectorAll('input[name="oc-estado"]').forEach((r) => r.addEventListener('change', acertar))
    acertar()

    const fechar = (limpar) => { if (limpar) guardar(null); fundo.remove(); document.removeEventListener('keydown', tecla); if (depois) depois() }
    const tecla = (e) => { if (e.key === 'Escape') fechar(true) }
    document.addEventListener('keydown', tecla)
    const erro = (m) => { const x = $('oc-erro'); x.textContent = m; x.hidden = false }
    const ocupado = (b) => fundo.querySelectorAll('button').forEach((x) => { x.disabled = b })

    $('oc-depois').onclick = () => fechar(true)
    $('oc-anular').onclick = () => {
      ocupado(true)
      pedir('orbit.chamadas_crm.anular', { nome: p.nome }).then(() => fechar(true))
        .catch(() => { ocupado(false); erro(t('Não foi possível apagar. Tente outra vez.')) })
    }
    $('oc-gravar').onclick = () => {
      ocupado(true)
      pedir('orbit.chamadas_crm.comentar', {
        nome: p.nome, estado: estado(), duracao: segundos($('oc-duracao').value),
        nota: $('oc-nota').value, tarefa: $('oc-tarefa').value, tarefa_data: $('oc-tarefa-data').value,
      }).then(() => { fechar(true); aviso(t('Chamada registada.')) })
        .catch(() => { ocupado(false); erro(t('Não foi possível gravar. Verifique a ligação e tente outra vez.')) })
    }
    setTimeout(() => { const n = $('oc-nota'); if (n && window.matchMedia('(pointer: fine)').matches) n.focus() }, 50)
  }

  // ---------------------------------------------------------------- por comentar

  function porComentar() {
    if (ler() || document.getElementById('oc-janela')) return
    pedir('orbit.chamadas_crm.por_comentar', {}).then((lista) => {
      lista = lista || []
      if (!lista.length) return
      const um = lista.length === 1
      aviso(um ? t('Tem 1 chamada por comentar.') : t('Tem {0} chamadas por comentar.').replace('{0}', lista.length), false, () => seguinte(lista))
    }).catch(() => {})
  }

  function seguinte(lista) {
    const c = lista.shift()
    if (!c) return
    const inicio = new Date(String(c.start_time).replace(' ', 'T')).getTime()
    janela({ nome: c.name, ficha: c.nome, numero: c.to, inicio }, 0, () => { if (lista.length) setTimeout(() => seguinte(lista), 300) })
  }

  // ---------------------------------------------------------------- aviso

  function fecharAviso() { const a = document.getElementById('oc-aviso'); if (a) a.remove() }

  function aviso(texto, erro, acao) {
    estilo()
    fecharAviso()
    const a = document.createElement('div')
    a.id = 'oc-aviso'
    a.className = 'oc-aviso' + (erro ? ' oc-aviso-erro' : '')
    a.setAttribute('role', 'status')
    a.innerHTML = `<span>${esc(texto)}</span>` +
      (acao ? `<button type="button" class="oc-aviso-acao">${esc(t('Comentar'))}</button>` : '') +
      `<button type="button" class="oc-aviso-x" aria-label="${esc(t('Fechar'))}">×</button>`
    document.body.appendChild(a)
    if (acao) a.querySelector('.oc-aviso-acao').onclick = () => { a.remove(); acao() }
    a.querySelector('.oc-aviso-x').onclick = () => a.remove()
    if (!acao) setTimeout(() => a.remove(), 4000)
  }

  // ---------------------------------------------------------------- aspecto

  function estilo() {
    if (document.getElementById('oc-estilo')) return
    const s = document.createElement('style')
    s.id = 'oc-estilo'
    s.textContent = `
      .oc-fundo{position:fixed;inset:0;z-index:10000;background:rgba(15,23,32,.45);display:flex;align-items:flex-end;justify-content:center}
      @media (min-width:640px){.oc-fundo{align-items:center}}
      .oc-caixa{--oc-fundo:#fff;--oc-texto:#1f2a33;--oc-suave:#5f6b75;--oc-linha:#dde2e6;--oc-campo:#f6f7f8;
        background:var(--oc-fundo);color:var(--oc-texto);width:100%;max-width:480px;max-height:92vh;overflow:auto;
        border-radius:16px 16px 0 0;padding:20px 20px calc(20px + env(safe-area-inset-bottom));box-shadow:0 10px 40px rgba(0,0,0,.25);
        font:15px/1.4 'DM Sans',system-ui,sans-serif}
      @media (min-width:640px){.oc-caixa{border-radius:14px}}
      [data-theme="dark"] .oc-caixa{--oc-fundo:#1c252e;--oc-texto:#eef1f3;--oc-suave:#a3adb5;--oc-linha:#34404b;--oc-campo:#26313b}
      .oc-caixa h2{margin:0 0 2px;font-size:18px;font-weight:600}
      .oc-sub{margin:0 0 14px;color:var(--oc-suave);font-size:13px}
      .oc-estados{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}
      .oc-estados label{position:relative}
      .oc-estados input{position:absolute;opacity:0;inset:0}
      .oc-estados span{display:block;text-align:center;padding:10px 6px;border:1px solid var(--oc-linha);border-radius:10px;cursor:pointer;font-size:14px}
      .oc-estados input:checked + span{background:#22303d;border-color:#22303d;color:#fff}
      .oc-estados input:focus-visible + span{outline:2px solid #b20009;outline-offset:2px}
      .oc-campo{display:block;font-size:13px;color:var(--oc-suave);margin-bottom:12px}
      .oc-campo input,.oc-campo textarea{display:block;width:100%;margin-top:4px;box-sizing:border-box;padding:9px 11px;font:inherit;font-size:16px;
        color:var(--oc-texto);background:var(--oc-campo);border:1px solid var(--oc-linha);border-radius:8px}
      .oc-duracao input{max-width:120px}
      .oc-tarefa{margin-bottom:12px}
      .oc-tarefa summary{cursor:pointer;font-size:14px;margin-bottom:8px;color:var(--oc-suave)}
      .oc-erro{color:#b20009;font-size:13px;margin:0 0 10px}
      .oc-botoes{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
      .oc-botoes span{flex:1}
      .oc-botoes button{font:inherit;font-size:14px;border-radius:8px;padding:9px 14px;cursor:pointer;border:1px solid transparent}
      .oc-botoes button:disabled{opacity:.6;cursor:default}
      .oc-gravar{background:#b20009;color:#fff}
      .oc-depois{background:transparent;border-color:var(--oc-linha)!important;color:var(--oc-texto)}
      .oc-anular{background:transparent;color:var(--oc-suave);padding-left:0!important;text-decoration:underline}
      .oc-aviso{position:fixed;z-index:9999;left:50%;transform:translateX(-50%);bottom:calc(16px + env(safe-area-inset-bottom));
        display:flex;align-items:center;gap:10px;max-width:calc(100% - 32px);background:#22303d;color:#fff;border-radius:10px;
        padding:10px 12px 10px 16px;font:14px/1.3 'DM Sans',system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.25)}
      .oc-aviso-erro{background:#b20009}
      .oc-aviso button{font:inherit;border:0;cursor:pointer;color:#fff;background:transparent}
      .oc-aviso-acao{background:#b20009!important;border-radius:6px;padding:5px 10px}
      .oc-aviso-x{font-size:18px;line-height:1;padding:0 4px;opacity:.8}`
    document.head.appendChild(s)
  }

  window.orbitChamadas = { ligar, porComentar }

  // Ao abrir o CRM (e não logo: deixa a app arrancar) — pendentes de outra vez.
  const arrancar = () => setTimeout(() => { if (ler()) voltou(); else porComentar() }, 2500)
  if (document.readyState === 'complete') arrancar()
  else window.addEventListener('load', arrancar)
})()
