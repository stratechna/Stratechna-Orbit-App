"""Documentos dentro da interface /orbit (A3 do plano da interface única, 20-11-2026).

O arquivo continua no Stratechna Docs (Paperless) do tenant. Aqui fala-se com a API dele **como a própria pessoa**:
email + palavra-passe da caixa (a mesma credencial cifrada do calendário — orbit/interface/calendario.py), que o
Docs aceita pelo backend `stratechna_caixa` (DP2). Assim valem as permissões do Docs: os documentos pessoais só para
o dono, contabilidade/RH só para a Administração (docs/PLANO-DOCS-ORGANIZACAO.md).

As miniaturas e a pré-visualização passam por aqui (o browser não tem sessão no Docs).
"""
from __future__ import annotations

import json
import re

import frappe
import requests
from frappe.utils import cint

from orbit.interface.calendario import _credenciais, _guarda


def _base() -> str:
    from orbit import marca
    return f"https://{marca._docs_do_tenant()}"


def _pedir(metodo: str, caminho: str, params=None, timeout=25, **kw):
    user, pwd = _credenciais()
    if not pwd:
        return None
    r = requests.request(metodo, _base() + caminho, params=params, auth=(user, pwd), timeout=timeout,
                         headers={"Accept": "application/json; version=9"}, **kw)
    return r


def _json(caminho, params=None):
    r = _pedir("GET", caminho, params)
    if r is None:
        return None, "sem_credencial"
    if r.status_code in (401, 403):
        return None, "recusado"
    if r.status_code == 404:
        return None, "sem_docs"
    r.raise_for_status()
    return r.json(), None


@frappe.whitelist()
def filtros():
    _guarda()
    out = {}
    for chave, caminho in (("tags", "/api/tags/"), ("tipos", "/api/document_types/"), ("correspondentes", "/api/correspondents/"),
                           ("campos", "/api/custom_fields/")):
        d, erro = _json(caminho, {"page_size": 500, "ordering": "name"})
        if erro:
            return {"erro": erro}
        out[chave] = [{"id": x["id"], "nome": x["name"], "cor": x.get("color"), "pai": x.get("parent"),
                       "tipo": x.get("data_type")} for x in d.get("results", [])]
    return out


def _resumo(doc, mapas):
    return {"id": doc["id"], "titulo": doc.get("title") or doc.get("original_file_name"), "criado": (doc.get("created") or "")[:10],
            "adicionado": (doc.get("added") or "")[:10], "tipo": mapas["tipos"].get(doc.get("document_type")),
            "correspondente": mapas["correspondentes"].get(doc.get("correspondent")),
            "tags": [mapas["tags"][t] for t in doc.get("tags", []) if t in mapas["tags"]],
            "campos": {mapas["campos"].get(c["field"], str(c["field"])): c.get("value") for c in doc.get("custom_fields", [])
                       if c.get("value") not in (None, "")},
            "paginas": doc.get("page_count"), "ficheiro": doc.get("original_file_name"),
            "notas": doc.get("notes") if isinstance(doc.get("notes"), int) else len(doc.get("notes") or [])}


def _mapas():
    chave = f"orbit:docs:mapas:{frappe.session.user}"
    m = frappe.cache.get_value(chave)
    if m:
        return m
    f = filtros()
    if f.get("erro"):
        return None
    m = {"tags": {t["id"]: {"nome": t["nome"], "cor": t["cor"]} for t in f["tags"]},
         "tipos": {t["id"]: t["nome"] for t in f["tipos"]},
         "correspondentes": {t["id"]: t["nome"] for t in f["correspondentes"]},
         "campos": {t["id"]: t["nome"] for t in f["campos"]}}
    frappe.cache.set_value(chave, m, expires_in_sec=300)
    return m


@frappe.whitelist()
def lista(q: str = "", tag: str = "", tipo: str = "", correspondente: str = "", pagina: int = 1, ordem: str = "-created"):
    _guarda()
    mapas = _mapas()
    if mapas is None:
        _, erro = _json("/api/tags/", {"page_size": 1})
        return {"erro": erro or "recusado"}
    p = {"page": max(cint(pagina), 1), "page_size": 30,
         "ordering": ordem if ordem in ("-created", "created", "-added", "title", "-title") else "-created",
         "truncate_content": "true"}
    if (q or "").strip():
        p["query"] = q.strip()[:200]
    if tag:
        p["tags__id__all"] = re.sub(r"[^0-9,]", "", tag)
    if tipo:
        p["document_type__id__in"] = re.sub(r"[^0-9,]", "", tipo)
    if correspondente:
        p["correspondent__id__in"] = re.sub(r"[^0-9,]", "", correspondente)
    d, erro = _json("/api/documents/", p)
    if erro:
        return {"erro": erro}
    return {"total": d.get("count", 0), "mais": bool(d.get("next")), "docs": [_resumo(x, mapas) for x in d.get("results", [])]}


@frappe.whitelist()
def do_registo(doctype: str, name: str):
    """Documentos de um contacto/empresa/negócio: pesquisa pelo nome da empresa e pelos emails (texto e metadados)."""
    _guarda()
    from orbit.interface.api import _relacionados, _titulo
    frappe.get_doc(doctype, name).check_permission("read")
    rel, emails = _relacionados(doctype, name)
    termos = sorted(emails)[:3] + [_titulo("CRM Organization", o) for o in list(rel["CRM Organization"])[:2]]
    if doctype == "Contact":
        termos.append(_titulo("Contact", name))
    termos = [t for t in termos if t and len(t) > 3]
    if not termos:
        return {"docs": []}
    q = " OR ".join(f'"{t}"' for t in termos)
    r = lista(q=q)
    r["docs"] = (r.get("docs") or [])[:8]
    r["pesquisa"] = q
    return r


def _binario(caminho: str, nome: str, inline=True):
    r = _pedir("GET", caminho, timeout=60, stream=False)
    if r is None or r.status_code != 200:
        frappe.throw("Documento indisponível.", frappe.PermissionError if (r is not None and r.status_code in (401, 403)) else frappe.DoesNotExistError)
    frappe.local.response.filename = nome
    frappe.local.response.filecontent = r.content
    frappe.local.response.type = "binary" if not inline else "download"
    frappe.local.response.display_content_as = "inline" if inline else "attachment"
    frappe.local.response["content_type"] = r.headers.get("Content-Type", "application/octet-stream")


@frappe.whitelist()
def miniatura(id: int):
    _guarda()
    _binario(f"/api/documents/{cint(id)}/thumb/", f"doc-{cint(id)}.webp")


@frappe.whitelist()
def ver(id: int):
    _guarda()
    _binario(f"/api/documents/{cint(id)}/preview/", f"documento-{cint(id)}.pdf")


@frappe.whitelist()
def descarregar(id: int):
    _guarda()
    r = _pedir("GET", f"/api/documents/{cint(id)}/", timeout=20)
    nome = (r.json().get("original_file_name") if r is not None and r.status_code == 200 else None) or f"documento-{cint(id)}"
    _binario(f"/api/documents/{cint(id)}/download/", nome, inline=False)


@frappe.whitelist(methods=["POST"])
def carregar(titulo: str = "", tags: str = "", tipo: str = "", processo: str = ""):
    """Carrega um ficheiro para o Docs (fica a ser processado: OCR, regras de arquivo)."""
    _guarda()
    f = frappe.request.files.get("ficheiro") if frappe.request and frappe.request.files else None
    if not f:
        frappe.throw("Falta o ficheiro.")
    conteudo = f.read()
    if len(conteudo) > 50 * 1024 * 1024:
        frappe.throw("O ficheiro passa dos 50 MB.")
    dados = []
    if titulo.strip():
        dados.append(("title", titulo.strip()[:120]))
    for t in [x for x in re.split(r"[,\s]+", tags or "") if x.isdigit()][:10]:
        dados.append(("tags", t))
    if (tipo or "").isdigit():
        dados.append(("document_type", tipo))
    if processo.strip():
        mapas = _mapas() or {"campos": {}}
        cid = next((k for k, v in mapas["campos"].items() if v.lower() == "processo"), None)
        if cid:
            dados.append(("custom_fields", json.dumps({str(cid): processo.strip()[:60]})))
    r = _pedir("POST", "/api/documents/post_document/", timeout=120, data=dados,
               files={"document": (f.filename, conteudo, f.mimetype or "application/octet-stream")})
    if r is None:
        frappe.throw("Ligue primeiro a sua conta (palavra-passe da caixa).")
    if r.status_code not in (200, 201, 202):
        frappe.throw(f"O Docs recusou o ficheiro ({r.status_code}).")
    return {"ok": True, "tarefa": r.text.strip('"')[:60]}
