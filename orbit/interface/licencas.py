"""Definições › Utilizadores: criar e desactivar utilizadores no próprio Orbit, com aviso de licenças (25-11-2026,
docs/PLANO-ORBIT-UTILIZADORES-LICENCAS.md, D1–D6 aceites).

O contratado vive no portal (quantidade da subscrição W15…). Cada acção vai ao portal, assinada com o segredo do tenant
(`orbit_portal_segredo`, HMAC-SHA256 em `X-Orbit-Assinatura`), para `POST /api/v1/orbit/utilizadores`, que usa as mesmas
funções do bloco Pessoas do portal e aplica a pessoa ao tenant (verbo `marcas-tenant`). O Orbit só mostra e pede.
"""
import hashlib
import hmac
import json
from urllib.parse import urlparse

import frappe


def _base():
    url = frappe.conf.get("orbit_portal_url") or (frappe.conf.get("orbit_portal_tempo_url") or "").split("/api/")[0]
    return (url or "").rstrip("/"), frappe.conf.get("orbit_portal_segredo")


def _admin():
    return "System Manager" in frappe.get_roles() or frappe.session.user == "Administrator"


def _pedir(acao: str, **dados):
    if frappe.session.user == "Guest":
        frappe.throw("Sem sessão.", frappe.PermissionError)
    base, seg = _base()
    if not base or not seg:
        return {"disponivel": False, "mensagem": "Este Orbit não está ligado ao portal Stratechna."}
    import requests
    corpo = json.dumps({"acao": acao, "site": frappe.local.site, "host": urlparse(frappe.utils.get_url()).hostname,
                        "quem": frappe.session.user, "admin": _admin(), **dados}, ensure_ascii=False).encode()
    r = requests.post(f"{base}/api/v1/orbit/utilizadores", data=corpo, timeout=120,
                      headers={"Content-Type": "application/json",
                               "X-Orbit-Assinatura": hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()})
    if r.status_code >= 300:
        frappe.throw(f"O portal não respondeu ({r.status_code}). Tente daqui a pouco.")
    return r.json()


@frappe.whitelist()
def estado():
    return _pedir("estado")


@frappe.whitelist()
def candidatas():
    return _pedir("candidatas")


@frappe.whitelist(methods=["POST"])
def novo(pessoa, aceito_custo=0):
    if isinstance(pessoa, str):
        pessoa = json.loads(pessoa)
    return _pedir("novo", pessoa=pessoa, aceito_custo=bool(int(aceito_custo or 0)))


@frappe.whitelist(methods=["POST"])
def desactivar(email, reactivar=0):
    return _pedir("desactivar", email=email, reactivar=bool(int(reactivar or 0)))
