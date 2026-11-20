"""Fundir duplicados (H6 do plano da interface única, 20-11-2026) — contactos e empresas, como no HubSpot.

* Encontrar: contactos com o mesmo email ou telemóvel ou o mesmo nome normalizado; empresas com o mesmo nome
  normalizado (sem «Lda», «Unipessoal», acentos…), o mesmo site ou o mesmo NIPC.
* Fundir: o que falta no principal vem dos outros (campos vazios, emails, telefones); depois
  `frappe.rename_doc(…, merge=True)` passa TODAS as ligações (negócios, emails, notas, tarefas, reuniões, tickets) para
  o principal e apaga o duplicado. Nas empresas actualiza-se também o `company_name` dos contactos (é texto, não
  ligação). Fica uma nota no principal com o que foi fundido. Precisa de permissão de escrita e de apagar.
"""
from __future__ import annotations

import re
import unicodedata

import frappe

_SUFIXOS = re.compile(r"\b(lda|limitada|unipessoal|sa|s\.a|sociedade|unip|crl|eireli|sl|s\.l|ltd|inc)\b\.?", re.I)


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _SUFIXOS.sub(" ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _tel(s):
    d = re.sub(r"\D", "", s or "")
    return d[-9:] if len(d) >= 9 else ""


def _dom(url):
    u = (url or "").lower()
    u = re.sub(r"^https?://", "", u).split("/")[0]
    return u[4:] if u.startswith("www.") else u


@frappe.whitelist()
def grupos(tipo: str):
    _guarda()
    grupos_, visto = [], set()

    def junta(chave_motivo, nomes):
        nomes = sorted(set(nomes))
        if len(nomes) < 2:
            return
        k = tuple(nomes)
        if k in visto:
            return
        visto.add(k)
        grupos_.append({"motivo": chave_motivo, "registos": nomes})

    if tipo == "contactos":
        if not frappe.has_permission("Contact", "read"):
            return []
        por = {}
        for r in frappe.get_all("Contact Email", filters={"parenttype": "Contact"}, fields=["parent", "email_id"]):
            if r.email_id:
                por.setdefault(("email", r.email_id.lower()), set()).add(r.parent)
        for r in frappe.get_all("Contact Phone", filters={"parenttype": "Contact"}, fields=["parent", "phone"]):
            t = _tel(r.phone)
            if t:
                por.setdefault(("telefone", t), set()).add(r.parent)
        for c in frappe.get_all("Contact", fields=["name", "full_name", "mobile_no"]):
            n = _norm(c.full_name)
            if len(n) > 5:
                por.setdefault(("nome", n), set()).add(c.name)
            t = _tel(c.mobile_no)
            if t:
                por.setdefault(("telefone", t), set()).add(c.name)
        for (motivo, valor), nomes in por.items():
            junta(f"mesmo {motivo}: {valor}" if motivo != "nome" else "nome igual", nomes)
        dt = "Contact"
    else:
        if not frappe.has_permission("CRM Organization", "read"):
            return []
        por = {}
        for o in frappe.get_all("CRM Organization", fields=["name", "organization_name", "website", "nipc"]):
            n = _norm(o.organization_name or o.name)
            if len(n) > 3:
                por.setdefault(("nome", n), set()).add(o.name)
            d = _dom(o.website)
            if d and "." in d:
                por.setdefault(("site", d), set()).add(o.name)
            nif = re.sub(r"\D", "", o.nipc or "")[-9:]
            if len(nif) == 9:
                por.setdefault(("NIPC", nif), set()).add(o.name)
        for (motivo, valor), nomes in por.items():
            junta(f"mesmo {motivo}: {valor}" if motivo != "nome" else "nome igual", nomes)
        dt = "CRM Organization"
    from orbit.interface.api import _titulo
    out = []
    for g in grupos_:
        regs = []
        for n in g["registos"]:
            if not frappe.db.exists(dt, n):
                continue
            info = {"name": n, "titulo": _titulo(dt, n)}
            if dt == "Contact":
                info["sub"] = frappe.db.get_value("Contact", n, "email_id") or frappe.db.get_value("Contact", n, "company_name") or ""
                info["negocios"] = frappe.db.count("CRM Contacts", {"parenttype": "CRM Deal", "contact": n})
            else:
                info["sub"] = frappe.db.get_value("CRM Organization", n, "website") or ""
                info["negocios"] = frappe.db.count("CRM Deal", {"organization": n})
            info["emails"] = frappe.db.count("Communication", {"reference_doctype": dt, "reference_name": n})
            regs.append(info)
        if len(regs) >= 2:
            out.append({"motivo": g["motivo"], "registos": regs})
    return out[:200]


def _completar(dt, principal, outro):
    p = frappe.get_doc(dt, principal)
    o = frappe.get_doc(dt, outro)
    meta = frappe.get_meta(dt)
    for f in meta.fields:
        if f.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table", "Table MultiSelect", "HTML", "Button") or f.read_only:
            continue
        if not p.get(f.fieldname) and o.get(f.fieldname):
            p.set(f.fieldname, o.get(f.fieldname))
    if dt == "Contact":
        ja = {(e.email_id or "").lower() for e in p.get("email_ids") or []}
        for e in o.get("email_ids") or []:
            if (e.email_id or "").lower() not in ja:
                p.append("email_ids", {"email_id": e.email_id, "is_primary": 0})
        tj = {_tel(t.phone) for t in p.get("phone_nos") or []}
        for t in o.get("phone_nos") or []:
            if _tel(t.phone) not in tj:
                p.append("phone_nos", {"phone": t.phone, "is_primary_phone": 0, "is_primary_mobile_no": 0})
    p.save()


@frappe.whitelist(methods=["POST"])
def fundir(tipo: str, principal: str, outros: str):
    _guarda()
    import json
    dt = "Contact" if tipo == "contactos" else "CRM Organization"
    lista = [x for x in json.loads(outros) if x and x != principal]
    if not lista:
        frappe.throw("Escolha pelo menos um duplicado.")
    for perm in ("write", "delete"):
        if not frappe.has_permission(dt, perm):
            frappe.throw("Sem permissão para fundir.", frappe.PermissionError)
    from orbit.interface.api import _titulo
    feitos = []
    for o in lista:
        if not frappe.db.exists(dt, o):
            continue
        titulo = _titulo(dt, o)
        _completar(dt, principal, o)
        if dt == "CRM Organization":
            frappe.db.set_value("Contact", {"company_name": o}, "company_name", principal, update_modified=False)
        frappe.rename_doc(dt, o, principal, merge=True, force=True, show_alert=False)
        feitos.append(titulo)
    if feitos and frappe.db.exists("DocType", "FCRM Note"):
        frappe.get_doc({"doctype": "FCRM Note", "title": "Registos fundidos",
                        "content": "<p>Fundidos neste registo: " + ", ".join(frappe.utils.escape_html(x) for x in feitos) + ".</p>",
                        "reference_doctype": dt, "reference_docname": principal}).insert(ignore_permissions=True)
    return {"ok": True, "fundidos": len(feitos)}
