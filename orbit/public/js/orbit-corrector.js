/* Stratechna Orbit — «Rever texto» no CRM, no Desk e no ERP (20-11-2026, docs/PLANO-CORRECTOR-LANGUAGETOOL.md, F3).
 *
 * Quando a pessoa está a escrever num editor — TipTap/ProseMirror no CRM e no Desk, Quill no ERP, ou uma caixa de
 * texto grande —, aparece no canto do editor um botão «Rever texto». O texto vai a `orbit.corrector.verificar`
 * (o servidor fala com o LanguageTool próprio; o texto nunca sai dos nossos servidores) e abre-se um painel com cada
 * erro, a explicação e as sugestões, como no Orbit Mail (o mesmo desenho do `orbit-corrector.js` do Stratechna-Mail).
 *
 * - A troca faz-se pelo próprio editor (transacção do ProseMirror, Delta do Quill, setRangeText + «input» na caixa),
 *   por isso o anular (⌘Z / Ctrl+Z) desfaz e as marcas do texto (negrito…) ficam.
 * - Num email de resposta revê-se só o que se escreveu: pára na citação (blockquote) e na assinatura «-- ».
 * - «Juntar ao dicionário» guarda a palavra neste navegador (localStorage orbit-corrector:dicionario, o mesmo nome
 *   do Orbit Mail, mas cada endereço tem o seu).
 * Entra pela página www/crm.html, www/helpdesk/index.html e pelo app_include_js da secretária (hooks.py).
 */
(function () {
  'use strict'
  if (window.orbitCorrector) return

  const t = (s, n) => {
    const r = typeof window.__ === 'function' ? window.__(s) : s
    return n == null ? r : String(r).replace('{0}', n)
  }
  const DICIONARIO = 'orbit-corrector:dicionario'
  const LETRA = 'system-ui,-apple-system,Segoe UI,Roboto,sans-serif'

  function dicionario() {
    try { return JSON.parse(localStorage.getItem(DICIONARIO) || '[]') || [] } catch (e) { return [] }
  }
  function juntarAoDicionario(p) {
    const d = dicionario()
    if (!d.includes(p)) d.push(p)
    try { localStorage.setItem(DICIONARIO, JSON.stringify(d.slice(-2000))) } catch (e) {}
  }
  const ehAssinatura = (s) => s === '--' || /^--\s/.test(s)

  // ── Os três tipos de editor ────────────────────────────────────────────────
  /* Cada «alvo» sabe ler o texto (com o mapa de posições), trocar e seleccionar. */

  // Quill (secretária do Frappe): o Frappe não expõe o Quill; a instância fica presa ao elemento editável.
  function prenderQuill() {
    const C = window.frappe && frappe.ui && frappe.ui.form && frappe.ui.form.ControlTextEditor
    if (!C || C.prototype.__orbitCorrector) return !!C
    const orig = C.prototype.make_quill_editor
    C.prototype.make_quill_editor = function () {
      const r = orig.apply(this, arguments)
      try { if (this.quill && this.quill.root) this.quill.root.__orbitQuill = this.quill } catch (e) {}
      return r
    }
    C.prototype.__orbitCorrector = true
    return true
  }

  function alvoDe(el) {
    if (!el || el.nodeType !== 1) return null
    const pm = el.closest('.ProseMirror')
    if (pm && pm.editor && pm.editor.view) return alvoTiptap(pm, pm.editor)
    const ql = el.closest('.ql-editor')
    if (ql && ql.__orbitQuill) return alvoQuill(ql, ql.__orbitQuill)
    if (el.tagName === 'TEXTAREA' && !el.readOnly && !el.disabled && el.offsetHeight >= 60 && !el.closest('.CodeMirror, .ace_editor')) return alvoArea(el)
    return null
  }

  function alvoTiptap(dom, ed) {
    const view = ed.view
    function ler() {
      const doc = view.state.doc
      const blocos = []
      let parou = false
      doc.descendants((no, pos) => {
        if (parou) return false
        if (no.type.name === 'blockquote') {
          parou = true
          const ant = blocos[blocos.length - 1]
          if (ant && /:\s*$/.test(ant.texto.trim())) blocos.pop()
          return false
        }
        if (no.isTextblock) {
          const b = { texto: '', pedacos: [] }
          no.forEach((f, off) => {
            if (f.isText) { b.pedacos.push({ ini: b.texto.length, fim: b.texto.length + f.text.length, pos: pos + 1 + off }); b.texto += f.text }
            else { b.texto += f.type.name === 'hardBreak' ? '\n' : ' ' }
          })
          if (ehAssinatura(b.texto.replace(/ /g, ' ').trim())) { parou = true; return false }
          blocos.push(b)
          return false
        }
        return true
      })
      let texto = ''
      const pedacos = []
      blocos.forEach((b, i) => {
        if (i) texto += '\n\n'
        b.pedacos.forEach((p) => pedacos.push({ ini: texto.length + p.ini, fim: texto.length + p.fim, pos: p.pos }))
        texto += b.texto
      })
      return { texto, pedacos }
    }
    function posicao(d, o, fim) {
      for (const p of d.pedacos) if (o >= p.ini && (o < p.fim || (fim && o === p.fim))) return p.pos + (o - p.ini)
      return null
    }
    return {
      el: dom, ler,
      trocar(d, ini, comp, novo) {
        const a = posicao(d, ini, false), b = posicao(d, ini + comp, true)
        if (a == null || b == null) return false
        if (view.state.doc.textBetween(a, b) !== d.texto.substr(ini, comp)) return false
        view.dispatch(novo ? view.state.tr.insertText(novo, a, b) : view.state.tr.delete(a, b))
        return true
      },
      seleccionar(d, ini, comp) {
        const a = posicao(d, ini, false), b = posicao(d, ini + comp, true)
        if (a == null || b == null) return
        try { ed.chain().focus().setTextSelection({ from: a, to: b }).scrollIntoView().run() } catch (e) {}
      },
    }
  }

  function alvoQuill(root, q) {
    function ler() {
      const tudo = q.getText()
      // citação e assinatura: o Quill do Frappe guarda a citação como blockquote; corta-se na 1.ª linha citada
      const linhas = q.getLines()
      let fim = tudo.length
      for (let i = 0; i < linhas.length; i++) {
        const l = linhas[i]
        const txt = tudo.substr(q.getIndex(l), l.length()).trim()
        const citada = l.domNode && l.domNode.tagName === 'BLOCKQUOTE'
        if (citada || ehAssinatura(txt)) {
          fim = q.getIndex(l)
          const ant = linhas[i - 1]
          if (citada && ant && /:\s*$/.test(tudo.substr(q.getIndex(ant), ant.length()).trim())) fim = q.getIndex(ant)
          break
        }
      }
      return { texto: tudo.slice(0, fim).replace(/\n$/, ''), pedacos: null }
    }
    return {
      el: root, ler,
      trocar(d, ini, comp, novo) {
        if (q.getText(ini, comp) !== d.texto.substr(ini, comp)) return false
        const fmt = q.getFormat(ini, Math.max(comp, 1))
        q.deleteText(ini, comp, 'user')
        if (novo) q.insertText(ini, novo, fmt, 'user')
        return true
      },
      seleccionar(d, ini, comp) { try { q.setSelection(ini, comp, 'user') } catch (e) {} },
    }
  }

  function alvoArea(a) {
    function ler() {
      const linhas = a.value.split('\n')
      let fim = a.value.length, pos = 0
      for (let i = 0; i < linhas.length; i++) {
        const s = linhas[i].trim()
        if (ehAssinatura(s) || /^>/.test(s)) {
          fim = pos
          if (/^>/.test(s) && i > 0 && /:\s*$/.test(linhas[i - 1].trim())) fim = Math.max(0, pos - linhas[i - 1].length - 1)
          break
        }
        pos += linhas[i].length + 1
      }
      return { texto: a.value.slice(0, fim), pedacos: null }
    }
    return {
      el: a, ler,
      trocar(d, ini, comp, novo) {
        if (a.value.substr(ini, comp) !== d.texto.substr(ini, comp)) return false
        a.setRangeText(novo, ini, ini + comp, 'end')
        a.dispatchEvent(new Event('input', { bubbles: true }))
        a.dispatchEvent(new Event('change', { bubbles: true }))
        return true
      },
      seleccionar(d, ini, comp) { try { a.focus(); a.setSelectionRange(ini, ini + comp) } catch (e) {} },
    }
  }

  // ── O pedido ───────────────────────────────────────────────────────────────
  function csrf() {
    return (window.frappe && frappe.csrf_token) || window.csrf_token || ''
  }
  async function rever(texto) {
    const r = await fetch('/api/method/orbit.corrector.verificar', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Frappe-CSRF-Token': csrf() },
      body: JSON.stringify({ texto }),
    })
    let c = {}
    try { c = await r.json() } catch (e) {}
    if (r.status === 429) throw new Error(t('O corrector está ocupado. Tente daqui a um momento.'))
    if (!r.ok) {
      let msg = ''
      try { msg = JSON.parse(JSON.parse(c._server_messages || '[]')[0] || '{}').message } catch (e) {}
      throw new Error(msg || t('Não foi possível rever o texto.'))
    }
    return c.message
  }

  // ── O painel ───────────────────────────────────────────────────────────────
  const ESTILO = `
#orbit-corrector{position:fixed;z-index:10000;right:24px;bottom:24px;width:380px;max-width:calc(100vw - 32px);
max-height:min(70vh,560px);display:flex;flex-direction:column;background:#fff;color:#22303d;border-radius:12px;
box-shadow:0 10px 36px rgba(0,0,0,.28);font:14px/1.45 ${LETRA}}
#orbit-corrector .oc-cab{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid #e3e7eb}
#orbit-corrector .oc-tit{flex:1;font-weight:600}
#orbit-corrector .oc-lin{font-size:12px;color:#6b7a88}
#orbit-corrector .oc-x{border:0;background:transparent;font-size:20px;line-height:1;cursor:pointer;color:#6b7a88;padding:2px 6px}
#orbit-corrector .oc-lista{overflow:auto;padding:6px 0}
#orbit-corrector .oc-item{padding:10px 14px;border-bottom:1px solid #f0f2f4;cursor:pointer}
#orbit-corrector .oc-item:last-child{border-bottom:0}
#orbit-corrector .oc-item:hover{background:#f8fafb}
#orbit-corrector .oc-ctx{color:#3d5163;word-break:break-word}
#orbit-corrector .oc-err{text-decoration:underline wavy;text-underline-offset:3px;font-weight:600}
#orbit-corrector .oc-orto .oc-err{text-decoration-color:#b20009}
#orbit-corrector .oc-gram .oc-err{text-decoration-color:#1d6fd6}
#orbit-corrector .oc-msg{font-size:12.5px;color:#6b7a88;margin-top:3px}
#orbit-corrector .oc-sug{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
#orbit-corrector .oc-sug button{border:1px solid #c8d0d8;background:#fff;border-radius:7px;padding:4px 10px;cursor:pointer;font:500 13px ${LETRA};color:#22303d}
#orbit-corrector .oc-sug button.oc-pri{background:#22303d;border-color:#22303d;color:#fff}
#orbit-corrector .oc-sug button.oc-sec{border-color:transparent;color:#6b7a88}
#orbit-corrector .oc-vazio{padding:22px 16px;text-align:center;color:#3d5163}
#orbit-corrector .oc-vazio b{display:block;font-size:15px;color:#22303d;margin-bottom:4px}
#orbit-corrector-botao{position:fixed;z-index:9999;display:none;align-items:center;gap:5px;height:26px;padding:0 9px 0 7px;
border:1px solid #c8d0d8;border-radius:13px;background:#fff;color:#22303d;font:500 12px ${LETRA};cursor:pointer;
box-shadow:0 2px 8px rgba(0,0,0,.12);opacity:.92}
#orbit-corrector-botao:hover{opacity:1;border-color:#22303d}
#orbit-corrector-botao svg{width:15px;height:15px;fill:currentColor}
@media (max-width:600px){#orbit-corrector{left:8px;right:8px;bottom:8px;width:auto;max-width:none;max-height:60vh}
#orbit-corrector .oc-sug button{padding:8px 12px;font-size:14px}}`
  const ICONE = 'M12.45 16h2.09L9.43 3H7.57L2.46 16h2.09l1.12-3h5.64l1.14 3zm-6.02-5L8.5 5.48 10.57 11H6.43zm15.16.59l-8.09 8.09L9.83 16l-1.41 1.41 5.09 5.09L23 13l-1.41-1.41z'

  function estilo() {
    if (document.getElementById('orbit-corrector-estilo')) return
    const s = document.createElement('style')
    s.id = 'orbit-corrector-estilo'
    s.textContent = ESTILO
    document.head.appendChild(s)
  }
  function el(tag, cls, txt) {
    const e = document.createElement(tag)
    if (cls) e.className = cls
    if (txt != null) e.textContent = txt
    return e
  }
  function nomeLingua(c) {
    return { pt: t('Português'), es: t('Espanhol'), en: t('Inglês'), fr: t('Francês'), de: t('Alemão'), it: t('Italiano'), nl: t('Neerlandês') }[c] || c
  }

  let estado = null // { alvo, doc, erros, lingua, trocas }
  let aRever = false

  function fecharPainel() {
    const p = document.getElementById('orbit-corrector')
    if (p) p.remove()
    estado = null
  }

  function painel(mensagem) {
    estilo()
    let p = document.getElementById('orbit-corrector')
    if (!p) {
      p = el('div')
      p.id = 'orbit-corrector'
      p.setAttribute('role', 'dialog')
      p.setAttribute('aria-label', t('Rever texto'))
      // não roubar o foco ao editor (o botão do canto esconde-se quando o editor o perde)
      p.addEventListener('mousedown', (e) => { if (e.target.tagName === 'BUTTON') e.preventDefault() })
      document.body.appendChild(p)
    }
    p.innerHTML = ''
    const cab = el('div', 'oc-cab')
    const n = estado ? estado.erros.length : 0
    cab.appendChild(el('div', 'oc-tit', mensagem || !n ? t('Rever texto') : n === 1 ? t('1 sugestão') : t('{0} sugestões', n)))
    if (estado && estado.lingua) cab.appendChild(el('span', 'oc-lin', nomeLingua(estado.lingua.split('-')[0])))
    const x = el('button', 'oc-x', '×')
    x.type = 'button'
    x.title = t('Fechar')
    x.setAttribute('aria-label', t('Fechar'))
    x.addEventListener('click', fecharPainel)
    cab.appendChild(x)
    p.appendChild(cab)
    const lista = el('div', 'oc-lista')
    p.appendChild(lista)
    if (mensagem) { lista.appendChild(el('div', 'oc-vazio', mensagem)); return }
    if (!n) {
      const v = el('div', 'oc-vazio')
      v.appendChild(el('b', null, t('Nada a corrigir.')))
      v.appendChild(document.createTextNode(t('Não encontrei erros no que escreveu.')))
      lista.appendChild(v)
      return
    }
    estado.erros.forEach((m) => lista.appendChild(itemDe(m)))
  }

  function itemDe(m) {
    const d = estado.doc
    const it = el('div', 'oc-item ' + (m.ortografia ? 'oc-orto' : 'oc-gram'))
    const errado = d.texto.substr(m.offset, m.length)
    const a = Math.max(0, m.offset - 40), b = Math.min(d.texto.length, m.offset + m.length + 40)
    const ctx = el('div', 'oc-ctx')
    ctx.appendChild(document.createTextNode((a ? '…' : '') + d.texto.slice(a, m.offset).replace(/\s+/g, ' ')))
    ctx.appendChild(el('span', 'oc-err', errado))
    ctx.appendChild(document.createTextNode(d.texto.slice(m.offset + m.length, b).replace(/\s+/g, ' ') + (b < d.texto.length ? '…' : '')))
    it.appendChild(ctx)
    if (m.message) it.appendChild(el('div', 'oc-msg', m.message))
    const sug = el('div', 'oc-sug')
    ;(m.replacements || []).forEach((r, i) => {
      const bt = el('button', i ? '' : 'oc-pri', r === '' ? t('(apagar)') : r)
      bt.type = 'button'
      bt.addEventListener('click', (e) => { e.stopPropagation(); aplicar(m, r) })
      sug.appendChild(bt)
    })
    const ign = el('button', 'oc-sec', t('Ignorar'))
    ign.type = 'button'
    ign.addEventListener('click', (e) => { e.stopPropagation(); retirar(m, 0) })
    sug.appendChild(ign)
    if (m.ortografia) {
      const dic = el('button', 'oc-sec', t('Juntar ao dicionário'))
      dic.type = 'button'
      dic.addEventListener('click', (e) => {
        e.stopPropagation()
        juntarAoDicionario(errado)
        estado.erros = estado.erros.filter((o) => !(o.ortografia && estado.doc.texto.substr(o.offset, o.length) === errado))
        painel()
      })
      sug.appendChild(dic)
    }
    it.appendChild(sug)
    it.addEventListener('click', () => estado.alvo.seleccionar(estado.doc, m.offset, m.length))
    return it
  }

  function retirar(m, delta) {
    estado.erros = estado.erros.filter((o) => o !== m)
    if (delta) estado.erros.forEach((o) => { if (o.offset > m.offset) o.offset += delta })
    painel()
  }

  function aplicar(m, novo) {
    const { alvo, doc } = estado
    if (!alvo.el.isConnected) { fecharPainel(); return }
    const agora = alvo.ler()
    if (agora.texto.substr(0, m.offset + m.length) !== doc.texto.substr(0, m.offset + m.length) || !alvo.trocar(agora, m.offset, m.length, novo)) {
      revisar(alvo)
      return
    }
    estado.doc = alvo.ler()
    estado.trocas = (estado.trocas || 0) + 1
    retirar(m, novo.length - m.length)
    if (estado && !estado.erros.length) revisar(alvo) // uma troca pode revelar outro erro
  }

  async function revisar(alvo) {
    if (aRever || !alvo) return
    const doc = alvo.ler()
    if (!doc.texto.replace(/\s/g, '')) { estado = null; painel(t('Ainda não há nada escrito para rever.')); return }
    aRever = true
    estado = null
    painel(t('A rever…'))
    try {
      const r = await rever(doc.texto)
      const dic = dicionario()
      const erros = (r.erros || []).filter((m) => !(m.ortografia && dic.includes(doc.texto.substr(m.offset, m.length))))
      estado = { alvo, doc, erros, lingua: r.lingua }
      painel()
    } catch (e) {
      estado = null
      painel((e && e.message) || t('Não foi possível rever o texto.'))
    } finally {
      aRever = false
    }
  }

  // ── O botão no canto do editor ─────────────────────────────────────────────
  let actual = null
  let botao = null
  function criarBotao() {
    estilo()
    botao = el('button')
    botao.id = 'orbit-corrector-botao'
    botao.type = 'button'
    botao.title = t('Rever texto (ortografia e gramática)')
    botao.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONE}"/></svg>`
    botao.appendChild(el('span', null, t('Rever texto')))
    botao.addEventListener('mousedown', (e) => e.preventDefault()) // o editor não perde o foco
    botao.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); revisar(actual) })
    document.body.appendChild(botao)
  }
  function colocar() {
    if (!botao || !actual) return
    const r = actual.el.getBoundingClientRect()
    if (!actual.el.isConnected || r.width < 120 || r.bottom < 0 || r.top > innerHeight) { botao.style.display = 'none'; return }
    botao.style.display = 'inline-flex'
    const w = botao.offsetWidth || 110
    botao.style.left = Math.round(Math.min(r.right, innerWidth - 8) - w - 6) + 'px'
    botao.style.top = Math.round(Math.max(4, Math.min(r.bottom, innerHeight - 4) - 32)) + 'px'
  }
  document.addEventListener('focusin', (e) => {
    prenderQuill()
    const a = alvoDe(e.target)
    if (!a) return
    actual = a
    if (!botao) criarBotao()
    colocar()
  })
  document.addEventListener('focusout', () => {
    setTimeout(() => {
      if (actual && actual.el.contains(document.activeElement)) return
      if (botao) botao.style.display = 'none'
    }, 150)
  })
  addEventListener('scroll', colocar, true)
  addEventListener('resize', colocar)
  document.addEventListener('input', () => { if (actual && actual.el.contains(document.activeElement)) colocar() }, true)
  // Editor fechado (diálogo do email, comentário enviado): o painel deixa de ter a que se referir.
  setInterval(() => { if (estado && !estado.alvo.el.isConnected) fecharPainel() }, 1500)

  prenderQuill()
  window.orbitCorrector = { rever: () => revisar(actual), _alvoDe: alvoDe }
})()
