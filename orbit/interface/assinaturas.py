"""Assinaturas dentro da interface /orbit (A4 do plano da interface única, 20-11-2026).

O Sign (DocuSeal) do tenant fica como motor: modelos, envio dos pedidos por email, assinatura, documento final.
Aqui fala-se com a API dele (`X-Auth-Token`): a chave da conta do Sign do tenant guarda-se cifrada pelo Frappe
(`set_encrypted_password("System Settings", …, "orbit_sign_token")`), nunca no site_config nem em claro. No DocuSeal
todos os utilizadores de uma conta vêem os mesmos pedidos — por isso uma chave por tenant não abre nada a mais.

Quem pode: quem pode ler contactos do CRM vê; quem pode criar notas no CRM envia.
"""
from __future__ import annotations

import re

import frappe
import requests
from frappe.utils import cint

CAMPO = "orbit_sign_token"
ESTADOS = {"pending": "À espera", "awaiting": "À espera", "sent": "Enviado", "opened": "Aberto", "completed": "Assinado",
           "declined": "Recusado", "expired": "Expirado"}


def _guarda():
    from orbit.interface.api import _guarda as g
    g()
    if not frappe.has_permission("Contact", "read"):
        frappe.throw("Sem permissão.", frappe.PermissionError)


def _base() -> str:
    from orbit import marca
    return f"https://sign.{marca._dominio_do_tenant()}/api"


def _token():
    from frappe.utils.password import get_decrypted_password
    return get_decrypted_password("System Settings", "System Settings", CAMPO, raise_exception=False)


def guardar_token(token: str = None):
    """Chamado por bench (o token chega pelo stdin, nunca na linha de comandos)."""
    import sys
    from frappe.utils.password import set_encrypted_password
    t = (token or sys.stdin.read()).strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{20,128}", t):
        return "token inválido"
    set_encrypted_password("System Settings", "System Settings", t, CAMPO)
    frappe.db.commit()
    return "ok"


def _api(metodo, caminho, **kw):
    t = _token()
    if not t:
        return None
    r = requests.request(metodo, _base() + caminho, headers={"X-Auth-Token": t, "Accept": "application/json"}, timeout=30, **kw)
    if r.status_code in (401, 403):
        frappe.throw("O Sign recusou a chave deste Orbit.")
    r.raise_for_status()
    return r.json() if r.content else {}


def _sub(s):
    pessoas = [{"nome": x.get("name") or "", "email": x.get("email"), "papel": x.get("role"),
                "estado": ESTADOS.get(x.get("status"), x.get("status")), "estado_c": x.get("status"),
                "quando": (x.get("completed_at") or x.get("opened_at") or x.get("sent_at") or "")[:16]} for x in s.get("submitters", [])]
    estado = s.get("status") or ("completed" if s.get("completed_at") else "pending")
    return {"id": s.get("id"), "modelo": (s.get("template") or {}).get("name") or "", "estado": ESTADOS.get(estado, estado),
            "estado_c": estado, "criado": (s.get("created_at") or "")[:16], "concluido": (s.get("completed_at") or "")[:16],
            "pessoas": pessoas, "arquivado": bool(s.get("archived_at"))}


@frappe.whitelist()
def estado():
    _guarda()
    return {"ligado": bool(_token()), "base": _base().replace("/api", "")}


@frappe.whitelist()
def lista(q: str = "", estado_f: str = "", depois: str = ""):
    _guarda()
    p = {"limit": 50}
    if (q or "").strip():
        p["q"] = q.strip()[:120]
    if estado_f in ("pending", "completed", "declined", "expired"):
        p["status"] = estado_f
    if (depois or "").isdigit():
        p["after"] = depois
    d = _api("GET", "/submissions", params=p)
    if d is None:
        return {"ligado": False, "itens": []}
    itens = [_sub(s) for s in d.get("data", [])]
    return {"ligado": True, "itens": itens, "seguinte": (d.get("pagination") or {}).get("next")}


@frappe.whitelist()
def modelos(q: str = ""):
    _guarda()
    p = {"limit": 100, "archived": "false"}
    if (q or "").strip():
        p["q"] = q.strip()[:120]
    d = _api("GET", "/templates", params=p)
    if d is None:
        return []
    return [{"id": t["id"], "nome": t.get("name"), "papeis": [s.get("name") for s in t.get("submitters", [])],
             "criado": (t.get("created_at") or "")[:10]} for t in d.get("data", [])]


@frappe.whitelist()
def do_registo(doctype: str, name: str):
    _guarda()
    from orbit.interface.api import _relacionados
    frappe.get_doc(doctype, name).check_permission("read")
    _rel, emails = _relacionados(doctype, name)
    vistos, out = set(), []
    for e in sorted(emails)[:4]:
        d = _api("GET", "/submissions", params={"q": e, "limit": 20})
        if d is None:
            return {"ligado": False, "itens": []}
        for s in d.get("data", []):
            if s["id"] not in vistos:
                vistos.add(s["id"])
                out.append(_sub(s))
    out.sort(key=lambda x: x["criado"], reverse=True)
    return {"ligado": True, "itens": out[:10]}


@frappe.whitelist(methods=["POST"])
def enviar(modelo: int, pessoas: str, mensagem: str = "", doctype: str = None, name: str = None):
    """Envia um pedido de assinatura a partir de um modelo do Sign; o Sign manda os emails. `pessoas` = JSON
    [{papel, email, nome}]. Com um registo do CRM, fica uma nota na cronologia dele."""
    _guarda()
    if not frappe.has_permission("FCRM Note", "create"):
        frappe.throw("Sem permissão para enviar.", frappe.PermissionError)
    import json
    lst = json.loads(pessoas or "[]")
    subs = []
    for x in lst[:10]:
        e = (x.get("email") or "").strip().lower()
        if not re.fullmatch(r"[\w.+'-]+@[\w-]+(\.[\w-]+)+", e):
            frappe.throw(f"Email inválido: {e or '(vazio)'}")
        s = {"email": e, "name": (x.get("nome") or "").strip()[:120] or None}
        if x.get("papel"):
            s["role"] = str(x["papel"])[:60]
        subs.append(s)
    if not subs:
        frappe.throw("Falta quem assina.")
    corpo = {"template_id": cint(modelo), "send_email": True, "submitters": subs}
    if (mensagem or "").strip():
        corpo["message"] = {"subject": "Documento para assinar", "body": mensagem.strip()[:2000] + "\n\n{{submitter.link}}"}
    r = _api("POST", "/submissions", json=corpo)
    if r is None:
        frappe.throw("Este Orbit ainda não está ligado ao Sign.")
    if doctype and name:
        frappe.get_doc(doctype, name).check_permission("read")
        nomes = ", ".join(s["email"] for s in subs)
        modelo_nome = next((m["nome"] for m in modelos() if m["id"] == cint(modelo)), f"modelo {modelo}")
        frappe.get_doc({"doctype": "FCRM Note", "title": f"Enviado para assinar: {modelo_nome}",
                        "content": f"<p>Enviado para assinar pelo Sign: <b>{frappe.utils.escape_html(modelo_nome)}</b> — "
                                   f"{frappe.utils.escape_html(nomes)}.</p>",
                        "reference_doctype": doctype, "reference_docname": name}).insert()
    return {"ok": True}


@frappe.whitelist()
def documento(id: int):
    """O documento assinado (passa pelo Orbit: o browser não tem sessão no Sign)."""
    _guarda()
    d = _api("GET", f"/submissions/{cint(id)}/documents")
    docs = (d or {}).get("documents") or []
    if not docs:
        frappe.throw("Ainda não há documento final.")
    r = requests.get(docs[0]["url"], timeout=60)
    r.raise_for_status()
    frappe.local.response.filename = (docs[0].get("name") or f"assinado-{cint(id)}") + ".pdf"
    frappe.local.response.filecontent = r.content
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"
