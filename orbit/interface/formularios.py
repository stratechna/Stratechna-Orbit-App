"""Editor dos formulários do CRM na interface nova (23-11-2026, pedido do Vítor).

Sem nada novo por baixo: a disposição guarda-se no `CRM Fields Layout` do próprio CRM —
* «Detalhes» (separador da ficha com todos os campos) = tipo **Data Fields**;
* «Sobre este registo» (coluna lateral, o resumo) = tipo **Side Panel**.
Formato do CRM: `[{"name", "label", "columns": [{"name", "fields": [...]}]}]`. Cada secção nossa leva `"orbit": 1`; a
1.ª vez (`instalar`) a disposição do CRM clássico (incompleta, em inglês) é substituída pela nossa, em português.
Além dos campos, há blocos especiais: `@emails`, `@telefones`, `@morada`, `@produtos`.
"""
from __future__ import annotations

import json

import frappe
from frappe import _

DTS = {"CRM Lead": "Leads", "Contact": "Contactos", "CRM Organization": "Empresas", "CRM Deal": "Negócios"}
PARTES = {"detalhes": "Data Fields", "resumo": "Side Panel"}
ESPECIAIS = {"@emails": "Emails (vários, com o principal)", "@telefones": "Telefones (vários, com o principal)",
             "@morada": "Morada", "@produtos": "Produtos"}
_ESTRUTURA = ("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold", "Heading")


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _padrao(dt: str, parte: str) -> list:
    if parte == "detalhes":
        from orbit.interface.detalhes import SECOES
        return [{"titulo": t, "campos": c} for t, c in SECOES.get(dt, [])]
    from orbit.interface.api import _PROPS
    campos = [c for c, *_r in _PROPS.get(dt, [])]
    if dt == "Contact":
        campos.insert(2, "marcas")
    return [{"titulo": "Sobre este registo", "campos": campos}]


def _para_crm(secoes: list) -> list:
    return [{"name": f"orbit_sec_{i}", "label": s["titulo"], "opened": True, "orbit": 1,
             "columns": [{"name": f"orbit_col_{i}", "fields": list(s["campos"])}]} for i, s in enumerate(secoes, 1)]


def ler(dt: str, parte: str) -> list | None:
    """A disposição nossa guardada no CRM, ou None (usa-se a de omissão)."""
    nome = frappe.db.get_value("CRM Fields Layout", {"dt": dt, "type": PARTES[parte]}, "layout") \
        if frappe.db.exists("DocType", "CRM Fields Layout") else None
    if not nome:
        return None
    try:
        lay = json.loads(nome)
    except ValueError:
        return None
    if not lay or not all(isinstance(s, dict) and s.get("orbit") for s in lay):
        return None
    out = []
    for s in lay:
        campos = []
        for c in s.get("columns") or []:
            campos += c.get("fields") or []
        campos += s.get("fields") or []
        out.append({"titulo": s.get("label") or "", "campos": campos})
    return out


def secoes(dt: str, parte: str) -> list:
    return ler(dt, parte) or _padrao(dt, parte)


def _gravar(dt: str, parte: str, lista: list):
    tipo = PARTES[parte]
    nome = frappe.db.get_value("CRM Fields Layout", {"dt": dt, "type": tipo}, "name")
    doc = frappe.get_doc("CRM Fields Layout", nome) if nome else frappe.get_doc({"doctype": "CRM Fields Layout", "dt": dt, "type": tipo})
    doc.layout = json.dumps(_para_crm(lista), ensure_ascii=False)
    doc.save(ignore_permissions=True) if nome else doc.insert(ignore_permissions=True)


def instalar():
    """after_migrate: a disposição nossa onde ainda está a do CRM clássico (uma vez; nunca desfaz uma edição nossa)."""
    if not frappe.db.exists("DocType", "CRM Fields Layout"):
        return
    for dt in DTS:
        if not frappe.db.exists("DocType", dt):
            continue
        for parte in PARTES:
            if ler(dt, parte) is None:
                try:
                    _gravar(dt, parte, _padrao(dt, parte))
                except Exception:
                    frappe.log_error(title=f"Orbit: formulário {dt} {parte}")


@frappe.whitelist()
def obter(doctype: str, parte: str):
    _guarda()
    frappe.only_for("System Manager")
    if doctype not in DTS or parte not in PARTES:
        frappe.throw("Formulário desconhecido.")
    meta = frappe.get_meta(doctype)
    disponiveis = [{"campo": f.fieldname, "rotulo": _(f.label or frappe.unscrub(f.fieldname)), "tipo": f.fieldtype}
                   for f in meta.fields if f.fieldtype not in _ESTRUTURA and not f.hidden and f.fieldtype != "Table"]
    disponiveis.append({"campo": "creation", "rotulo": "Criado", "tipo": "Datetime"})
    if parte == "detalhes":
        esp = {"Contact": ["@emails", "@telefones", "@morada"], "CRM Organization": ["@emails", "@telefones", "@morada"],
               "CRM Lead": ["@emails", "@telefones", "@produtos"], "CRM Deal": ["@produtos"]}.get(doctype, [])
        disponiveis += [{"campo": e, "rotulo": ESPECIAIS[e], "tipo": "bloco"} for e in esp]
    if doctype == "Contact" and meta.has_field("marcas"):
        disponiveis.append({"campo": "marcas", "rotulo": "Marcas", "tipo": "Table MultiSelect"})
    rot = {d["campo"]: d["rotulo"] for d in disponiveis}
    secs = secoes(doctype, parte)
    return {"secoes": [{"titulo": s["titulo"], "campos": [{"campo": c, "rotulo": rot.get(c, c)} for c in s["campos"] if c in rot]}
                       for s in secs],
            "disponiveis": sorted(disponiveis, key=lambda x: x["rotulo"].lower()),
            "registos": [{"v": k, "r": v} for k, v in DTS.items()]}


@frappe.whitelist(methods=["POST"])
def gravar(doctype: str, parte: str, secoes_json: str):
    _guarda()
    frappe.only_for("System Manager")
    if doctype not in DTS or parte not in PARTES:
        frappe.throw("Formulário desconhecido.")
    meta = frappe.get_meta(doctype)
    lista = []
    for s in json.loads(secoes_json or "[]"):
        campos = [c for c in dict.fromkeys(s.get("campos") or [])
                  if c in ESPECIAIS or c in ("creation", "marcas") or meta.has_field(c)]
        titulo = (s.get("titulo") or "").strip()[:80]
        if campos:
            lista.append({"titulo": titulo or "Secção", "campos": campos})
    if not lista:
        frappe.throw("O formulário precisa de pelo menos uma secção com campos.")
    _gravar(doctype, parte, lista)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def repor(doctype: str, parte: str):
    """Volta à disposição de omissão do Orbit."""
    _guarda()
    frappe.only_for("System Manager")
    _gravar(doctype, parte, _padrao(doctype, parte))
    return {"ok": True}
