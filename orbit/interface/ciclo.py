"""Fase do ciclo de vida e última actividade (H4 do plano da interface única, 20-11-2026) — como no HubSpot.

* `orbit_ciclo` (Select) em Contact e CRM Organization: Subscritor → Lead → Lead qualificada (marketing) → Lead
  qualificada (vendas) → Oportunidade → Cliente → Promotor (e Outro). **Sobe sozinha, nunca desce sozinha**; à mão
  muda-se para qualquer uma.
  - contacto/empresa novos sem fase → Lead (Subscritor se só tem consentimento de marketing)
  - negócio em curso → Oportunidade para os contactos e a empresa dele
  - negócio ganho, ou empresa com `tipo_conta = Cliente`/`estado_conta = Activo` → Cliente
* `orbit_ultima_atividade` (Datetime) em Contact, CRM Organization, CRM Lead e CRM Deal: cada email, nota, chamada,
  tarefa ou reunião ligada actualiza-a — no registo, na empresa do contacto e na do negócio.
"""
from __future__ import annotations

import frappe
from frappe.utils import get_datetime, now_datetime

FASES = ["Subscritor", "Lead", "Lead qualificada (marketing)", "Lead qualificada (vendas)", "Oportunidade", "Cliente",
         "Promotor", "Outro"]
ORDEM = {f: i for i, f in enumerate(FASES[:-1])}   # «Outro» fica fora da escada

CAMPOS = {
    "Contact": [{"fieldname": "orbit_ciclo", "label": "Fase do ciclo de vida", "fieldtype": "Select",
                 "options": "\n" + "\n".join(FASES), "insert_after": "orbit_responsavel", "in_standard_filter": 1},
                {"fieldname": "orbit_ultima_atividade", "label": "Última actividade", "fieldtype": "Datetime",
                 "insert_after": "orbit_ciclo", "read_only": 1}],
    "CRM Organization": [{"fieldname": "orbit_ciclo", "label": "Fase do ciclo de vida", "fieldtype": "Select",
                          "options": "\n" + "\n".join(FASES), "insert_after": "orbit_responsavel", "in_standard_filter": 1},
                         {"fieldname": "orbit_ultima_atividade", "label": "Última actividade", "fieldtype": "Datetime",
                          "insert_after": "orbit_ciclo", "read_only": 1}],
    "CRM Lead": [{"fieldname": "orbit_ultima_atividade", "label": "Última actividade", "fieldtype": "Datetime",
                  "insert_after": "lead_owner", "read_only": 1}],
    "CRM Deal": [{"fieldname": "orbit_ultima_atividade", "label": "Última actividade", "fieldtype": "Datetime",
                  "insert_after": "deal_owner", "read_only": 1}],
}


def instalar():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    for dt, campos in CAMPOS.items():
        if not frappe.db.exists("DocType", dt):
            continue
        for c in campos:
            if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
                create_custom_field(dt, {**c, "module": "Orbit"})


def _tem(dt, campo):
    return frappe.db.has_column(dt, campo)


def subir(dt: str, nome: str, fase: str):
    """Sobe a fase se a nova for mais alta (nunca desce; «Outro» e «Promotor» escolhidos à mão ficam)."""
    if not nome or not _tem(dt, "orbit_ciclo") or not frappe.db.exists(dt, nome):
        return
    atual = frappe.db.get_value(dt, nome, "orbit_ciclo") or ""
    if atual == "Outro":
        return
    if not atual or ORDEM.get(fase, -1) > ORDEM.get(atual, -1):
        frappe.db.set_value(dt, nome, "orbit_ciclo", fase, update_modified=False)


def _orgs_do_contacto(c):
    emp = frappe.db.get_value("Contact", c, "company_name")
    return [emp] if emp and frappe.db.exists("CRM Organization", emp) else []


def _contactos_do_negocio(d):
    out = set(frappe.get_all("CRM Contacts", filters={"parenttype": "CRM Deal", "parent": d}, pluck="contact"))
    c = frappe.db.get_value("CRM Deal", d, "contact")
    if c:
        out.add(c)
    return [x for x in out if x]


# ── ganchos ─────────────────────────────────────────────────────────────────────────────────────────
def contacto_gravado(doc, method=None):
    if not _tem("Contact", "orbit_ciclo") or doc.get("orbit_ciclo"):
        return
    fase = "Subscritor" if doc.get("mkt_estado") and doc.get("mkt_base_legal") == "consentimento" else "Lead"
    frappe.db.set_value("Contact", doc.name, "orbit_ciclo", fase, update_modified=False)


def empresa_gravada(doc, method=None):
    if not _tem("CRM Organization", "orbit_ciclo"):
        return
    if doc.get("tipo_conta") == "Cliente" or doc.get("estado_conta") == "Activo":
        subir("CRM Organization", doc.name, "Cliente")
    elif not doc.get("orbit_ciclo"):
        frappe.db.set_value("CRM Organization", doc.name, "orbit_ciclo", "Lead", update_modified=False)


def negocio_gravado(doc, method=None):
    tipo = frappe.db.get_value("CRM Deal Status", doc.status, "type") if doc.status else None
    if tipo == "Lost":
        return
    fase = "Cliente" if tipo == "Won" else "Oportunidade"
    for c in _contactos_do_negocio(doc.name):
        subir("Contact", c, fase)
    if doc.organization:
        subir("CRM Organization", doc.organization, fase)


def tocar(dt: str, nome: str, quando=None):
    if not nome or not _tem(dt, "orbit_ultima_atividade"):
        return
    q = get_datetime(quando) if quando else now_datetime()
    atual = frappe.db.get_value(dt, nome, "orbit_ultima_atividade")
    if not atual or get_datetime(atual) < q:
        frappe.db.set_value(dt, nome, "orbit_ultima_atividade", q, update_modified=False)


def _tocar_com_empresa(dt, nome, quando):
    if not nome or not frappe.db.exists(dt, nome):
        return
    tocar(dt, nome, quando)
    if dt == "Contact":
        for o in _orgs_do_contacto(nome):
            tocar("CRM Organization", o, quando)
    elif dt == "CRM Deal":
        o = frappe.db.get_value("CRM Deal", nome, "organization")
        if o:
            tocar("CRM Organization", o, quando)


def atividade(doc, method=None):
    """after_insert de Communication, FCRM Note, CRM Task, CRM Call Log e Event."""
    try:
        quando = doc.get("communication_date") or doc.get("start_time") or doc.get("starts_on") or doc.get("creation") or now_datetime()
        alvos = []
        if doc.doctype == "Communication":
            if doc.reference_doctype:
                alvos.append((doc.reference_doctype, doc.reference_name))
            alvos += [(l.link_doctype, l.link_name) for l in (doc.get("timeline_links") or [])]
        else:
            if doc.get("reference_doctype") and doc.get("reference_docname"):
                alvos.append((doc.reference_doctype, doc.reference_docname))
        for dt, nome in dict.fromkeys(alvos):
            if dt in ("Contact", "CRM Organization", "CRM Lead", "CRM Deal"):
                _tocar_com_empresa(dt, nome, quando)
    except Exception:  # noqa: BLE001 — nunca impedir o registo de uma actividade
        frappe.log_error(title="orbit.interface.ciclo.atividade")


# ── preencher o que já existe (corre uma vez por tenant, e de novo sem estragos) ────────────────────────
def preencher():
    instalar()
    for c in frappe.get_all("Contact", filters={"orbit_ciclo": ["in", ["", None]]}, fields=["name", "mkt_estado", "mkt_base_legal"]):
        frappe.db.set_value("Contact", c.name, "orbit_ciclo",
                            "Subscritor" if c.mkt_estado and c.mkt_base_legal == "consentimento" else "Lead", update_modified=False)
    for o in frappe.get_all("CRM Organization", fields=["name", "tipo_conta", "estado_conta", "orbit_ciclo"]):
        if o.tipo_conta == "Cliente" or o.estado_conta == "Activo":
            subir("CRM Organization", o.name, "Cliente")
        elif not o.orbit_ciclo:
            frappe.db.set_value("CRM Organization", o.name, "orbit_ciclo", "Lead", update_modified=False)
    for d in frappe.get_all("CRM Deal", fields=["name", "status", "organization"]):
        negocio_gravado(frappe._dict(d, doctype="CRM Deal"))
    # última actividade a partir do que já está registado
    for tabela, data, ref_dt, ref_dn in (("tabCommunication", "communication_date", "reference_doctype", "reference_name"),
                                         ("`tabFCRM Note`", "creation", "reference_doctype", "reference_docname"),
                                         ("`tabCRM Call Log`", "start_time", "reference_doctype", "reference_docname"),
                                         ("`tabCRM Task`", "creation", "reference_doctype", "reference_docname")):
        for dt, nome, q in frappe.db.sql(f"""select {ref_dt}, {ref_dn}, max({data}) from {tabela}
                where {ref_dt} in ('Contact','CRM Organization','CRM Lead','CRM Deal') and ifnull({ref_dn},'')!=''
                group by {ref_dt}, {ref_dn}"""):
            _tocar_com_empresa(dt, nome, q)
    for dt, nome, q in frappe.db.sql("""select l.link_doctype, l.link_name, max(c.communication_date) from `tabCommunication Link` l
            join tabCommunication c on c.name = l.parent where l.parenttype='Communication'
            and l.link_doctype in ('Contact','CRM Organization','CRM Lead','CRM Deal') group by l.link_doctype, l.link_name"""):
        _tocar_com_empresa(dt, nome, q)
    frappe.db.commit()
    return {"contactos": frappe.db.sql("select orbit_ciclo, count(*) from tabContact group by orbit_ciclo"),
            "empresas": frappe.db.sql("select orbit_ciclo, count(*) from `tabCRM Organization` group by orbit_ciclo")}
