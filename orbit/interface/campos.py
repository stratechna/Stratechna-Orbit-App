"""Campos personalizados do CRM, criados na interface /orbit (23-11-2026, pedido do Vítor).

O administrador do Orbit (System Manager) cria campos em Leads, Contactos, Empresas e Negócios sem ir ao
«Personalizar formulário» do Frappe. São Custom Fields normais (ficam só neste Orbit), com o nome técnico começado por
`oc_` para se distinguirem dos que vêm com a app. Aparecem sozinhos na ficha («Sobre este registo», editáveis) e nas
listas (colunas e filtros).

Apagar só se nenhum registo tiver valor nesse campo; com valores, esconde-se (os dados ficam).
"""
from __future__ import annotations

import json
import re
import unicodedata

import frappe

OBJETOS = {"leads": "CRM Lead", "contactos": "Contact", "empresas": "CRM Organization", "negocios": "CRM Deal"}
TIPOS = {"texto": ("Data", "Texto curto"), "texto_longo": ("Small Text", "Texto longo"), "numero": ("Float", "Número"),
         "inteiro": ("Int", "Número inteiro"), "valor": ("Currency", "Valor (€)"), "data": ("Date", "Data"),
         "sim_nao": ("Check", "Sim / Não"), "lista": ("Select", "Lista de opções")}
PREFIXO = "oc_"


def _guarda_admin():
    from orbit.interface.api import _guarda
    _guarda()
    frappe.only_for("System Manager")


def _slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", t)).strip("_")[:40]


def personalizados(dt: str, com_ocultos: bool = False) -> list:
    """Os campos oc_ de um doctype, pela ordem do formulário."""
    meta = frappe.get_meta(dt)
    out = []
    for f in meta.fields:
        if not f.fieldname.startswith(PREFIXO) or (f.hidden and not com_ocultos):
            continue
        out.append(f)
    return out


def tipo_de(fieldtype: str) -> str:
    return next((k for k, (ft, _r) in TIPOS.items() if ft == fieldtype), "texto")


@frappe.whitelist()
def listar():
    _guarda_admin()
    out = []
    for objeto, dt in OBJETOS.items():
        if not frappe.db.exists("DocType", dt):
            continue
        for f in personalizados(dt, com_ocultos=True):
            out.append({"objeto": objeto, "nome": f"{dt}-{f.fieldname}", "campo": f.fieldname, "rotulo": f.label,
                        "tipo": tipo_de(f.fieldtype), "opcoes": [o for o in (f.options or "").split("\n") if o] if f.fieldtype == "Select" else [],
                        "oculto": bool(f.hidden)})
    return {"campos": out, "tipos": [{"v": k, "r": r} for k, (_ft, r) in TIPOS.items()],
            "objetos": [{"v": k, "r": r} for k, r in (("leads", "Leads"), ("contactos", "Contactos"), ("empresas", "Empresas"), ("negocios", "Negócios"))]}


@frappe.whitelist(methods=["POST"])
def criar(objeto: str, rotulo: str, tipo: str, opcoes: str = "[]"):
    _guarda_admin()
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    dt = OBJETOS.get(objeto)
    rotulo = (rotulo or "").strip()[:80]
    if not dt or not rotulo or tipo not in TIPOS:
        frappe.throw("Escolha o registo, o nome e o tipo do campo.")
    meta = frappe.get_meta(dt)
    base = PREFIXO + (_slug(rotulo) or "campo")
    nome, i = base, 2
    while meta.has_field(nome):
        nome, i = f"{base}_{i}", i + 1
    if any((f.label or "").strip().lower() == rotulo.lower() for f in meta.fields):
        frappe.throw(f"Já existe um campo «{rotulo}» neste registo.")
    ft = TIPOS[tipo][0]
    ops = [o.strip()[:80] for o in json.loads(opcoes or "[]") if str(o).strip()] if ft == "Select" else []
    if ft == "Select" and not ops:
        frappe.throw("Escreva as opções da lista (uma por linha).")
    ultimo = personalizados(dt, com_ocultos=True)
    depois = ultimo[-1].fieldname if ultimo else (meta.fields[-1].fieldname if meta.fields else None)
    create_custom_field(dt, {"fieldname": nome, "label": rotulo, "fieldtype": ft,
                             "options": "\n".join([""] + ops) if ft == "Select" else None,
                             "insert_after": depois, "in_standard_filter": 0})
    frappe.clear_cache(doctype=dt)
    return {"ok": True, "campo": nome}


@frappe.whitelist(methods=["POST"])
def editar(nome: str, rotulo: str = None, opcoes: str = None, oculto: int = None):
    _guarda_admin()
    cf = frappe.get_doc("Custom Field", nome)
    if not cf.fieldname.startswith(PREFIXO) or cf.dt not in OBJETOS.values():
        frappe.throw("Este campo não foi criado aqui e não se muda aqui.")
    if rotulo is not None and rotulo.strip():
        cf.label = rotulo.strip()[:80]
    if opcoes is not None and cf.fieldtype == "Select":
        ops = [o.strip()[:80] for o in json.loads(opcoes or "[]") if str(o).strip()]
        if not ops:
            frappe.throw("A lista precisa de pelo menos uma opção.")
        cf.options = "\n".join([""] + ops)
    if oculto is not None:
        cf.hidden = 1 if int(oculto) else 0
    cf.save(ignore_permissions=True)
    frappe.clear_cache(doctype=cf.dt)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def apagar(nome: str):
    _guarda_admin()
    cf = frappe.get_doc("Custom Field", nome)
    if not cf.fieldname.startswith(PREFIXO) or cf.dt not in OBJETOS.values():
        frappe.throw("Este campo não foi criado aqui e não se apaga aqui.")
    vazio = 0 if cf.fieldtype == "Check" else ""
    com_valor = frappe.db.sql(f"SELECT COUNT(*) FROM `tab{cf.dt}` WHERE `{cf.fieldname}` IS NOT NULL AND `{cf.fieldname}` != %s",
                              (vazio,))[0][0]
    if com_valor:
        frappe.throw(f"{com_valor} registo(s) têm valor neste campo. Esconda-o em vez de o apagar — os dados ficam guardados.")
    dt = cf.dt
    cf.delete(ignore_permissions=True)
    frappe.clear_cache(doctype=dt)
    return {"ok": True}
