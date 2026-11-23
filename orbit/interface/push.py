"""Notificações no telemóvel (Web Push) para o Orbit instalado como app (23-11-2026, pedido do Vítor).

Quando alguém é @mencionado (aviso «Mention» do Frappe), o aviso também sai como notificação para cada aparelho em que
a pessoa ligou os avisos — Android sempre que a app esteja instalada; iPhone com iOS 16.4+ e o Orbit gravado no ecrã
principal (regra da Apple). Chaves VAPID próprias por site (geradas uma vez, no site_config). As subscrições ficam
por pessoa (valores por omissão do utilizador, `orbit_push`); as que o serviço do browser recusa (404/410) saem sozinhas.
"""
from __future__ import annotations

import base64
import json

import frappe

CHAVE = "orbit_push"
TIPOS = ("Mention",)


def _chaves() -> dict:
    v = frappe.conf.get("orbit_vapid")
    if v and v.get("privada") and v.get("publica"):
        return v
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    priv = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                           serialization.NoEncryption()).decode()
    pub = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    v = {"privada": priv, "publica": base64.urlsafe_b64encode(pub).decode().rstrip("=")}
    from frappe.installer import update_site_config
    update_site_config("orbit_vapid", v)
    frappe.conf["orbit_vapid"] = v
    return v


def _subs(user: str) -> list:
    try:
        return json.loads(frappe.defaults.get_user_default(CHAVE, user=user) or "[]")
    except ValueError:
        return []


def _gravar(user: str, subs: list):
    frappe.defaults.set_user_default(CHAVE, json.dumps(subs[-8:]), user=user)


@frappe.whitelist()
def chave():
    from orbit.interface.api import _guarda
    _guarda()
    return {"publica": _chaves()["publica"], "aparelhos": len(_subs(frappe.session.user))}


@frappe.whitelist(methods=["POST"])
def subscrever(sub: str):
    from orbit.interface.api import _guarda
    _guarda()
    s = json.loads(sub)
    if not (s.get("endpoint") or "").startswith("https://") or not (s.get("keys") or {}).get("p256dh"):
        frappe.throw("Subscrição inválida.")
    subs = [x for x in _subs(frappe.session.user) if x.get("endpoint") != s["endpoint"]] + [s]
    _gravar(frappe.session.user, subs)
    return {"ok": True, "aparelhos": len(subs)}


@frappe.whitelist(methods=["POST"])
def retirar(endpoint: str):
    from orbit.interface.api import _guarda
    _guarda()
    _gravar(frappe.session.user, [x for x in _subs(frappe.session.user) if x.get("endpoint") != endpoint])
    return {"ok": True}


def enviar(user: str, titulo: str, texto: str, url: str, etiqueta: str | None = None) -> int:
    subs = _subs(user)
    if not subs:
        return 0
    from pywebpush import WebPushException, webpush
    v = _chaves()
    dados = json.dumps({"titulo": titulo[:120], "texto": texto[:240], "url": url, "tag": etiqueta}, ensure_ascii=False)
    ficam, enviados = [], 0
    for s in subs:
        try:
            webpush(subscription_info=s, data=dados, vapid_private_key=v["privada"],
                    vapid_claims={"sub": "mailto:it@stratechna.pt"}, ttl=86400, timeout=10)
            enviados += 1
            ficam.append(s)
        except WebPushException as e:
            if getattr(e, "response", None) is not None and e.response.status_code in (404, 410):
                continue   # o aparelho já não existe
            ficam.append(s)
        except Exception:  # noqa: BLE001
            ficam.append(s)
            frappe.log_error(title="Orbit push: envio")
    if len(ficam) != len(subs):
        _gravar(user, ficam)
    return enviados


ROTULOS = {"CRM Lead": "na lead", "Contact": "no contacto", "CRM Organization": "na empresa", "CRM Deal": "no negócio",
           "HD Ticket": "no ticket", "Communication": "no email"}


def aviso_criado(doc, method=None):
    """doc_events «Notification Log» after_insert: o aviso de menção em português e também no telemóvel (em fila,
    nunca atrasa quem escreveu)."""
    if doc.type != "Mention":
        return
    try:   # o Frappe escreve-o em inglês («mentioned you in a comment in CRM Deal …»)
        quem = frappe.utils.get_fullname(doc.from_user) if doc.from_user else "Alguém"
        titulo = frappe.utils.strip_html(str(frappe.get_value(doc.document_type, doc.document_name, "name") and
                                             __import__("frappe.desk.notifications", fromlist=["get_title"]).get_title(doc.document_type, doc.document_name) or doc.document_name))
        assunto = f"<b>{frappe.utils.escape_html(quem)}</b> mencionou-o num comentário {ROTULOS.get(doc.document_type, 'em')} <b>{frappe.utils.escape_html(titulo)}</b>"
        frappe.db.set_value("Notification Log", doc.name, "subject", assunto, update_modified=False)
        doc.subject = assunto
    except Exception:  # noqa: BLE001
        frappe.log_error(title="Orbit push: texto do aviso")
    if doc.type not in TIPOS or not _subs(doc.for_user):
        return
    frappe.enqueue("orbit.interface.push._enviar_aviso", queue="short", nome=doc.name, enqueue_after_commit=True)


def _enviar_aviso(nome: str):
    n = frappe.get_doc("Notification Log", nome)
    from orbit.interface.conversa import ligacao_do_aviso
    from frappe.utils import strip_html
    enviar(n.for_user, strip_html(n.subject or "Foi mencionado"), strip_html(n.email_content or "")[:240],
           ligacao_do_aviso(n.document_type, n.document_name), etiqueta=f"{n.document_type}:{n.document_name}")


# ── O service worker e o manifesto de cada app (servidos daqui: o Frappe não serve .js/.json de www) ─────────────────
SW = r"""
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { titulo: 'Orbit', texto: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.titulo || 'Stratechna Orbit', {
    body: d.texto || '', tag: d.tag || undefined, renotify: !!d.tag, data: { url: d.url || '/orbit' },
    icon: '/assets/orbit/pwa/crm-192.png', badge: '/assets/orbit/pwa/crm-192.png' }));
});
self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || '/orbit';
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (cs) {
    for (var i = 0; i < cs.length; i++) { if (cs[i].url.indexOf('/orbit') >= 0 && 'focus' in cs[i]) { cs[i].navigate(url); return cs[i].focus(); } }
    return self.clients.openWindow(url);
  }));
});
"""

APPS = {   # a mesma lista da interface (app.js APPS): nome, cor do ícone
    "crm": ("CRM", "#b20009"), "desk": ("Desk", "#2563eb"), "projetos": ("Projetos", "#16a34a"),
    "rh": ("RH", "#9333ea"), "gestao": ("Gestão", "#d97706"), "operacoes": ("Operações", "#0891b2"),
    "marketing": ("Marketing", "#db2777"), "admin": ("Administração", "#475569"),
}


@frappe.whitelist(allow_guest=True)
def sw():
    frappe.response["type"] = "download"
    frappe.response["filename"] = "orbit-sw.js"
    frappe.response["content_type"] = "application/javascript"
    frappe.response["display_content_as"] = "inline"
    frappe.response["filecontent"] = SW.encode()


@frappe.whitelist(allow_guest=True)
def manifesto(app: str = "crm"):
    app = app if app in APPS else "crm"
    nome, cor = APPS[app]
    m = {"id": f"/orbit?app={app}", "name": f"Orbit {nome}", "short_name": nome if len(nome) <= 12 else nome[:12],
         "start_url": f"/orbit?app={app}", "scope": "/orbit", "display": "standalone", "lang": "pt-PT",
         "background_color": "#161a1d", "theme_color": "#161a1d",
         "icons": [{"src": f"/assets/orbit/pwa/{app}-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                   {"src": f"/assets/orbit/pwa/{app}-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                   {"src": f"/assets/orbit/pwa/{app}-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
    frappe.response["type"] = "download"
    frappe.response["filename"] = f"orbit-{app}.webmanifest"
    frappe.response["content_type"] = "application/manifest+json"
    frappe.response["display_content_as"] = "inline"
    frappe.response["filecontent"] = json.dumps(m, ensure_ascii=False).encode()


def cabecalhos(response=None, request=None):
    """after_request: o service worker servido em /api/method/… pode cuidar de /orbit."""
    try:
        if request is not None and request.path.endswith("orbit.interface.push.sw"):
            response.headers["Service-Worker-Allowed"] = "/orbit"
            response.headers["Cache-Control"] = "no-cache"
    except Exception:  # noqa: BLE001
        pass
