"""A barra de apps do Orbit em TODAS as apps (22-11-2026, pedido do Vítor: «em todas deve existir o ícone de apps para
que o utilizador possa saltar rápido de umas para outras»).

Um só guião, servido por cada tenant em `/api/method/orbit.barra.barra_js`, desenha o botão de apps e o seletor com os
endereços certos desse tenant (os mesmos do ecrã de apps: `marca.ATALHOS` + as apps do /orbit). Qualquer app o carrega
com uma linha `<script src=…>` — também as que vivem noutro domínio (Mail, Chat, Docs, Meet, Booking, Sign), porque um
<script> não precisa de CORS. Escolher uma app volta ao separador onde ela já está (janela com nome `orbit-<chave>`) ou
abre um novo.

Parâmetros do endereço do guião: `app` = chave da app onde está (fica marcada) e `sitio` = onde fica o botão quando a
app não tem sítio próprio: `baixo-esquerda` (por omissão), `baixo-direita`, `topo-esquerda`, `topo-direita`.
"""
from __future__ import annotations

import json

import frappe
from werkzeug.wrappers import Response


def _base() -> str:
    return frappe.utils.get_url().rstrip("/")


def apps_do_tenant() -> list[dict]:
    from orbit import apps as A
    from orbit import marca
    base = _base()
    try:
        activas = A.activas()
    except Exception:  # noqa: BLE001
        activas = None
    ok = lambda chave: activas is None or chave in activas or "completo" in (activas or set())  # noqa: E731
    icone = lambda s: f"{base}/assets/orbit/icons/apps/{s}.svg"  # noqa: E731
    nova = bool(frappe.conf.get("orbit_interface_nova"))
    itens = [{"chave": "inicio", "nome": "Início", "url": f"{base}/desk", "icone": icone("orbit")}]
    if nova:
        for chave, nome, sim, pre in (("crm", "CRM", "crm", "crm"), ("desk", "Desk", "desk", "helpdesk"),
                                      ("projetos", "Projetos", "erp", None), ("rh", "RH", "rh", None),
                                      ("gestao", "Gestão", "erp", None), ("operacoes", "Operações", "erp", None),
                                      ("marketing", "Marketing", "marketing", "marketing")):
            if pre and not ok(pre):
                continue
            itens.append({"chave": chave, "nome": nome, "url": f"{base}/orbit?app={chave}", "icone": icone(sim)})
    else:
        if ok("crm"):
            itens.append({"chave": "crm", "nome": "CRM", "url": f"{base}/crm", "icone": icone("crm")})
        if ok("helpdesk"):
            itens.append({"chave": "desk", "nome": "Desk", "url": f"{base}/helpdesk", "icone": icone("desk")})
    try:
        valores = {"mail": marca._mail_do_tenant(), "docs": marca._docs_do_tenant(), "chat": marca._chat_do_tenant(),
                   "dominio": marca._dominio_do_tenant()}
    except Exception:  # noqa: BLE001
        valores = {}
    for a in sorted(marca.ATALHOS, key=lambda x: x.get("ordem", 99)):
        chave = a["nome"].lower()
        if nova and chave == "marketing":
            continue
        if a.get("precisa") and not frappe.db.exists("DocType", a["precisa"]):
            continue
        if not ok(chave):
            continue
        try:
            url = a["url"].format(**valores)
        except KeyError:
            continue
        if url.startswith("/"):
            url = base + url
        itens.append({"chave": chave, "nome": a["nome"], "url": url, "icone": icone(a.get("simbolo") or chave)})
    if ok("wiki") and "wiki" in frappe.get_installed_apps():
        itens.append({"chave": "wiki", "nome": "Wiki", "url": f"{base}/wiki", "icone": icone("wiki")})
    return itens


@frappe.whitelist(allow_guest=True)
def barra_js(app: str = "", sitio: str = ""):
    dados = {"apps": apps_do_tenant(), "base": _base()}
    js = "window.__orbitBarraDados = " + json.dumps(dados, ensure_ascii=False) + ";\n" + _GUIAO
    return Response(js, mimetype="application/javascript",
                    headers={"Cache-Control": "public, max-age=300", "Access-Control-Allow-Origin": "*"})


_GUIAO = r"""
(function () {
  if (window.__orbitBarra) { return; }
  window.__orbitBarra = true;
  var D = window.__orbitBarraDados || { apps: [] };
  // No próprio Orbit sem sessão (ecrã de entrada, páginas públicas) não aparece.
  if (/^\/(login|update-password|signup)/.test(location.pathname)) { return; }
  if (location.origin === D.base && /(?:^|; )user_id=Guest(?:;|$)/.test(document.cookie)) { return; }
  var src = (document.currentScript && document.currentScript.src) || '';
  var qs = {}; (src.split('?')[1] || '').split('&').forEach(function (p) { var k = p.split('='); if (k[0]) { qs[k[0]] = decodeURIComponent(k[1] || ''); } });
  var atual = qs.app || '';
  var sitio = qs.sitio || 'baixo-esquerda';
  var css = [
    '#orbit-barra-botao{position:fixed;z-index:2147483000;width:44px;height:44px;border-radius:50%;border:0;cursor:pointer;',
    'background:#161a1d;color:#fff;display:grid;place-items:center;box-shadow:0 4px 14px rgba(0,0,0,.28);padding:0}',
    '#orbit-barra-botao:hover{background:#b20009}',
    '#orbit-barra-botao svg{width:20px;height:20px}',
    '#orbit-barra-botao.baixo-esquerda{left:16px;bottom:16px}#orbit-barra-botao.baixo-direita{right:16px;bottom:16px}',
    '#orbit-barra-botao.topo-esquerda{left:12px;top:12px}#orbit-barra-botao.topo-direita{right:12px;top:12px}',
    // no telemóvel as apps têm uma barra de navegação em baixo: o botão fica por cima dela
    '@media (max-width:767px){#orbit-barra-botao.baixo-esquerda,#orbit-barra-botao.baixo-direita{bottom:76px}}',
    '#orbit-barra-botao.embutido{position:static;width:34px;height:34px;box-shadow:none;background:transparent;color:inherit}',
    '#orbit-barra-botao.embutido:hover{background:rgba(127,127,127,.15)}',
    '#orbit-barra-painel{position:fixed;z-index:2147483001;width:400px;max-width:calc(100vw - 24px);background:#fff;color:#1c2a31;',
    'border:1px solid #e1e6e9;border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,.22);padding:14px;',
    'font:13px "DM Sans",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;display:none}',
    '#orbit-barra-painel.on{display:block}',
    '#orbit-barra-painel h6{margin:2px 4px 10px;font:600 11px inherit;text-transform:uppercase;letter-spacing:.06em;color:#7a8a93}',
    '#orbit-barra-painel .g{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}',
    '#orbit-barra-painel a{display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 4px;border-radius:10px;',
    'text-decoration:none;color:#4a5a63;text-align:center;font-size:12.5px;line-height:1.2}',
    '#orbit-barra-painel a:hover{background:#f4f6f7}',
    '#orbit-barra-painel a img{width:40px;height:40px;border-radius:10px}',
    '#orbit-barra-painel a.atual img{box-shadow:0 0 0 2px #b20009}',
    '@media (prefers-color-scheme: dark){#orbit-barra-painel{background:#1a252b;color:#e6ecef;border-color:#2c3a42}',
    '#orbit-barra-painel a{color:#b2bfc6}#orbit-barra-painel a:hover{background:#1f2b32}}'
  ].join('');
  var ICONE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    + '<rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/>'
    + '<rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/></svg>';
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function montar() {
    if (document.getElementById('orbit-barra-botao') || !document.body) { return; }
    var st = document.createElement('style'); st.id = 'orbit-barra-css'; st.textContent = css; document.head.appendChild(st);
    var b = document.createElement('button');
    b.id = 'orbit-barra-botao'; b.type = 'button'; b.title = 'Apps do Orbit'; b.setAttribute('aria-label', 'Apps do Orbit');
    b.innerHTML = ICONE;
    var p = document.createElement('div');
    p.id = 'orbit-barra-painel';
    p.innerHTML = '<h6>As suas apps</h6><div class="g">' + D.apps.map(function (a) {
      return '<a href="' + esc(a.url) + '" data-chave="' + esc(a.chave) + '" class="' + (a.chave === atual ? 'atual' : '') + '">'
        + '<img alt="" src="' + esc(a.icone) + '">' + esc(a.nome) + '</a>';
    }).join('') + '</div>';
    p.addEventListener('click', function (e) {
      var a = e.target.closest('a'); if (!a) { return; }
      e.preventDefault(); p.classList.remove('on');
      if (a.getAttribute('data-chave') === atual) { return; }
      var w = window.open(a.href, 'orbit-' + a.getAttribute('data-chave')); if (w) { w.focus(); }
    });
    // Sítios conhecidos: a barra do Wiki e a da secretária do Frappe — o botão entra a seguir à marca.
    if (!document.querySelector('[data-orbit-barra]')) {
      var marca = document.querySelector('.wiki-navbar .navbar-brand, header.navbar .navbar-brand, .navbar .navbar-home');
      if (marca && marca.parentNode) {
        var s0 = document.createElement('span'); s0.setAttribute('data-orbit-barra', '');
        s0.style.cssText = 'display:inline-flex;align-items:center;margin:0 6px';
        marca.parentNode.insertBefore(s0, marca.nextSibling);
      }
    }
    // Sítio próprio na app (um elemento com data-orbit-barra), senão flutuante.
    var casa = document.querySelector('[data-orbit-barra]');
    if (casa) { b.classList.add('embutido'); casa.appendChild(b); } else { b.classList.add(sitio); document.body.appendChild(b); }
    document.body.appendChild(p);
    // As apps de página única redesenham as barras: o botão volta ao sítio dele se for tirado.
    setInterval(function () {
      var c = document.querySelector('[data-orbit-barra]');
      if (c && b.parentNode !== c) { b.className = 'embutido'; c.appendChild(b); }
      else if (!c && !document.body.contains(b)) { b.className = sitio; document.body.appendChild(b); }
    }, 1500);
    function posicionar() {
      var r = b.getBoundingClientRect(), w = Math.min(400, window.innerWidth - 24);
      var left = Math.min(Math.max(12, r.left), window.innerWidth - w - 12);
      p.style.left = left + 'px';
      if (r.top > window.innerHeight / 2) { p.style.top = ''; p.style.bottom = (window.innerHeight - r.top + 8) + 'px'; }
      else { p.style.bottom = ''; p.style.top = (r.bottom + 8) + 'px'; }
    }
    b.addEventListener('click', function (e) { e.stopPropagation(); posicionar(); p.classList.toggle('on'); });
    document.addEventListener('click', function (e) { if (!p.contains(e.target) && e.target !== b) { p.classList.remove('on'); } });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { p.classList.remove('on'); } });
    try { if (!window.name || window.name.indexOf('orbit-') !== 0) { window.name = 'orbit-' + (atual || 'app'); } } catch (e) {}
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', montar); } else { montar(); }
  // O corrector do Orbit também nas apps de outro domínio (o Mail tem o seu).
  // No Wiki (mesmo domínio, páginas do site) o corrector entra pela via normal, com a sessão.
  if (location.origin === D.base && atual === 'wiki' && !window.__orbitCorrectorCarregado && !document.querySelector('script[src*="orbit-corrector"]')) {
    window.__orbitCorrectorCarregado = true;
    var w = document.createElement('script'); w.src = '/assets/orbit/js/orbit-corrector.js?v=3'; w.async = true; document.head.appendChild(w);
  }
  if (location.origin !== D.base && atual !== 'mail' && !window.__orbitCorrectorCarregado) {
    window.__orbitCorrectorCarregado = true;
    window.ORBIT_CORRECTOR_EXTERNO = D.base + '/api/method/orbit.corrector.verificar_externo';
    var c = document.createElement('script'); c.src = D.base + '/assets/orbit/js/orbit-corrector.js?v=3'; c.async = true;
    document.head.appendChild(c);
  }
})();
"""
