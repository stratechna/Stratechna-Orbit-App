"""Fotografias de quem escreve, no Orbit e no Orbit Mail (23-11-2026, pedido do Vítor).

Ordem (a 1.ª que houver; senão ficam as iniciais):
  1. a fotografia do contacto no CRM (ou o logótipo da empresa dele / da empresa com esse domínio);
  2. a fotografia do utilizador do Orbit (a equipa);
  3. de fora, pelo portal (`/api/v1/orbit/avatar`): Gravatar, BIMI, ícone do site — ver app/avatares.py do portal.

* `foto(email)` — para as apps (sessão do Orbit). Devolve a imagem ou 404.
* `local_portal` — o portal pede a 1.ª/2.ª para o Orbit Mail (pedido assinado com `orbit_portal_segredo`).
O que vem de fora guarda-se em `private/avatares/` do site (30 dias; «não há» 7 dias, na cache).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time

import frappe

LIVRES = re.compile(r"^(gmail|googlemail|hotmail|outlook|live|msn|yahoo|icloud|me|mac|aol|gmx|mail|proton|protonmail|sapo|"
                    r"netcabo|clix|iol|vodafone|meo|zoho|yandex)\.", re.I)
EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg",
       "image/x-icon": "ico", "image/vnd.microsoft.icon": "ico"}
TIPO_DE = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp",
           "svg": "image/svg+xml", "ico": "image/x-icon"}


def _conteudo_de(url: str):
    """Os bytes de um ficheiro do Frappe (/files/… ou /private/files/…)."""
    if not url or not url.startswith(("/files/", "/private/files/")):
        return None
    try:
        f = frappe.get_doc("File", {"file_url": url})
        dados = f.get_content()
        if isinstance(dados, str):
            dados = dados.encode()
        ext = url.rsplit(".", 1)[-1].lower()
        return (dados, TIPO_DE.get(ext, "image/png")) if dados else None
    except Exception:
        return None


def local(email: str):
    """CRM e equipa deste Orbit. → (bytes, tipo) ou None."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return None
    # 1. contacto
    c = frappe.db.get_value("Contact Email", {"email_id": email, "parenttype": "Contact"}, "parent") \
        or frappe.db.get_value("Contact", {"email_id": email}, "name")
    if c:
        r = _conteudo_de(frappe.db.get_value("Contact", c, "image"))
        if r:
            return r
    # 2. utilizador do Orbit
    u = frappe.db.get_value("User", {"name": email, "enabled": 1}, "user_image") \
        or frappe.db.get_value("User", {"email": email, "enabled": 1}, "user_image")
    r = _conteudo_de(u)
    if r:
        return r
    # 1b. logótipo da empresa: a do contacto, ou a que tem este domínio (só domínios de empresa)
    org = frappe.db.get_value("Contact", c, "company_name") if c else None
    dominio = email.split("@")[-1]
    if not org and not LIVRES.match(dominio) and frappe.db.exists("DocType", "CRM Organization"):
        org = frappe.db.get_value("CRM Organization", {"website": ["like", f"%{dominio}%"]}, "name")
        if not org and frappe.db.has_column("CRM Organization", "email_geral"):
            org = frappe.db.get_value("CRM Organization", {"email_geral": ["like", f"%@{dominio}"]}, "name")
    if org and frappe.db.exists("CRM Organization", org):
        r = _conteudo_de(frappe.db.get_value("CRM Organization", org, "organization_logo"))
        if r:
            return r
    return None


def _pasta():
    p = frappe.get_site_path("private", "avatares")
    os.makedirs(p, exist_ok=True)
    return p


def _guardada(email: str):
    """→ (bytes, tipo) | "nao" | None (ainda não se sabe)."""
    k = hashlib.sha256(email.encode()).hexdigest()
    base = os.path.join(_pasta(), k)
    for ext, tipo in TIPO_DE.items():
        p = f"{base}.{ext}"
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < 30 * 86400:
            with open(p, "rb") as f:
                return f.read(), tipo
    if frappe.cache().get_value(f"orbit:av:nao:{k}"):
        return "nao"
    return None


def buscar_fundo(email: str):
    """Trabalho de fundo: pede a fotografia de fora ao portal e guarda-a (a página seguinte já a mostra)."""
    try:
        _externa(email)
    finally:
        frappe.cache().delete_value(f"orbit:av:pedido:{hashlib.sha256(email.encode()).hexdigest()}")


def _externa(email: str):
    """Do portal, com cache em disco (30 dias) e o «não há» na cache do Frappe (7 dias)."""
    k = hashlib.sha256(email.encode()).hexdigest()
    base = os.path.join(_pasta(), k)
    g = _guardada(email)
    if g == "nao":
        return None
    if g:
        return g
    url = (frappe.conf.get("orbit_portal_url") or (frappe.conf.get("orbit_portal_tempo_url") or "").split("/api/")[0]).rstrip("/")
    seg = frappe.conf.get("orbit_portal_segredo")
    if not url or not seg:
        return None
    import requests
    corpo = json.dumps({"email": email}).encode()
    try:
        r = requests.post(f"{url}/api/v1/orbit/avatar", data=corpo, timeout=15,
                          headers={"Content-Type": "application/json",
                                   "X-Orbit-Assinatura": hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()})
    except Exception:
        return None
    tipo = (r.headers.get("content-type") or "").split(";")[0]
    if r.status_code == 200 and tipo in EXT:
        with open(f"{base}.{EXT[tipo]}", "wb") as f:
            f.write(r.content)
        return r.content, tipo
    if r.status_code == 404:
        frappe.cache().set_value(f"orbit:av:nao:{k}", 1, expires_in_sec=7 * 86400)
    return None


def _responder(res):
    if not res:
        frappe.local.response.http_status_code = 404
        frappe.local.response["message"] = None
        return
    dados, tipo = res
    ext = {v: k for k, v in TIPO_DE.items()}.get(tipo, "png")
    frappe.local.response.type = "binary"
    frappe.local.response.filename = f"avatar.{ext}"
    frappe.local.response.filecontent = dados
    frappe.local.response.display_content_as = "inline"


@frappe.whitelist(methods=["GET"])
def foto(email: str):
    """Para as apps do Orbit (sessão iniciada). Imagem ou 404 (o ecrã fica com as iniciais)."""
    if frappe.session.user == "Guest":
        raise frappe.PermissionError
    email = (email or "").strip().lower()[:200]
    res = local(email)
    if not res and "@" in email:
        g = _guardada(email)
        if g and g != "nao":
            res = g
        elif g is None:
            # 1.ª vez: a busca de fora (Gravatar, site…) demora — vai para o fundo e o ecrã fica com as iniciais
            k = hashlib.sha256(email.encode()).hexdigest()
            if not frappe.cache().get_value(f"orbit:av:pedido:{k}"):
                frappe.cache().set_value(f"orbit:av:pedido:{k}", 1, expires_in_sec=600)
                frappe.enqueue("orbit.avatares.buscar_fundo", queue="short", timeout=60, email=email)
    _responder(res)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def local_portal():
    """O portal pede a fotografia do CRM/equipa para o Orbit Mail. Pedido assinado; só a 1.ª e a 2.ª fontes."""
    seg = frappe.conf.get("orbit_portal_segredo") or ""
    corpo = frappe.request.get_data() or b""
    rec = (frappe.get_request_header("X-Orbit-Assinatura") or "").strip().lower()
    if not seg or not rec or not hmac.compare_digest(hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest(), rec):
        frappe.local.response.http_status_code = 401
        return
    try:
        email = (json.loads(corpo or b"{}").get("email") or "").strip().lower()[:200]
    except ValueError:
        email = ""
    _responder(local(email))
