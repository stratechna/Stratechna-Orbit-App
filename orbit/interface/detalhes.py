"""Separador «Detalhes» da ficha do CRM: todos os campos, por secções (23-11-2026, pedido do Vítor).

A coluna lateral da ficha («Sobre este registo») fica com o resumo; aqui está tudo o que o registo tem, organizado em
secções com nomes portugueses, para o ecrã as mostrar em 2–3 colunas. As secções estão escritas à mão (`SECOES`); um
campo que não esteja em nenhuma (por exemplo um que venha a ser acrescentado) vai para «Outros campos»; os criados em
Definições › Campos personalizados (`oc_…`) para «Campos personalizados». Nada fica de fora sem querer.

Tabelas: emails e telefones do contacto (editáveis, com o principal), produtos das leads e negócios (só leitura —
editam-se no CRM clássico, onde estão os preços e os impostos).
"""
from __future__ import annotations

import json
import re

import frappe
from frappe import _

_MKT = ["mkt_estado", "mkt_base_legal", "mkt_data", "mkt_origem", "mkt_idioma", "mkt_segmento", "mkt_assuntos", "mkt_texto"]
_SLA = ["sla", "sla_status", "communication_status", "sla_creation", "response_by", "first_response_time",
        "first_responded_on", "last_response_time", "last_responded_on"]
_REDES = ["website", "linkedin", "twitter", "facebook"]

# doctype → [(título, [campos] | "@tabela")]
SECOES = {
    "Contact": [
        ("Identificação", ["salutation", "first_name", "middle_name", "last_name", "gender", "designation", "department",
                           "company_name", "nif", "status"]),
        ("Emails e telefones", ["@emails", "@telefones"]),
        ("Morada", ["@morada"]),
        ("Relação com o cliente", ["orbit_responsavel", "orbit_ciclo", "origem", "marcas", "is_billing_contact",
                                   "is_primary_contact", "orbit_ultima_atividade", "user"]),
        ("Marketing e consentimento", _MKT + ["aprova_publicidade_digital", "aprova_redes_sociais", "unsubscribed"]),
        ("Sincronização e origem dos dados", ["zoho_id", "zoho_desk_id", "google_contacts", "google_contacts_id",
                                             "sync_with_google_contacts", "pulled_from_google_contacts"]),
    ],
    "CRM Lead": [
        ("Pessoa", ["salutation", "first_name", "middle_name", "last_name", "lead_name", "gender", "job_title"]),
        ("Emails e telefones", ["@emails", "@telefones"]),
        ("Empresa", ["organization", "nipc", "industry", "territory", "no_of_employees", "annual_revenue"] + _REDES +
         ["company_description"]),
        ("Morada", ["codigo_postal", "cidade", "distrito", "pais"]),
        ("Qualificação", ["status", "lead_owner", "source", "marca", "lead_score", "lead_temperature", "converted",
                          "orbit_ultima_atividade"]),
        ("Produtos", ["@produtos", "total", "net_total"]),
        ("Marketing e consentimento", _MKT),
        ("Atendimento (prazos de resposta)", _SLA),
        ("Perda", ["lost_reason", "lost_notes"]),
        ("Sincronização e origem dos dados", ["zoho_id", "facebook_lead_id", "facebook_form_id"]),
    ],
    "CRM Organization": [
        ("Empresa", ["organization_name", "nipc", "industry", "territory", "no_of_employees", "annual_revenue",
                     "currency", "exchange_rate", "company_description"]),
        ("Emails e telefones", ["@emails", "@telefones", "email_contabilidade"]),
        ("Site e redes sociais", _REDES),
        ("Morada", ["@morada"]),
        ("Relação com o cliente", ["orbit_responsavel", "orbit_ciclo", "marca", "tipo_conta", "estado_conta",
                                   "orbit_ultima_atividade"]),
        ("Faturação e portal", ["customer", "id_cliente_moloni", "faturar_moloni", "crm_account_id", "saas_slug",
                                "mbontime_cc", "webgate_cc"]),
        ("Sincronização e origem dos dados", ["zoho_id", "zoho_account_number"]),
    ],
    "CRM Deal": [
        ("Negócio", ["titulo", "status", "deal_owner", "marca", "deal_value", "expected_deal_value", "probability",
                     "expected_closure_date", "closed_date", "next_step", "source", "currency", "exchange_rate",
                     "orbit_ultima_atividade"]),
        ("Produtos", ["@produtos", "total", "net_total"]),
        ("Cliente", ["organization", "organization_name", "lead", "lead_name", "contact", "salutation", "first_name",
                     "last_name", "gender", "job_title", "email", "mobile_no", "phone"]),
        ("Empresa do cliente", ["industry", "territory", "no_of_employees", "annual_revenue"] + _REDES + ["company_description"]),
        ("Atendimento (prazos de resposta)", _SLA),
        ("Perda", ["lost_reason", "lost_notes"]),
        ("Origem", ["orbit_referencia_loja", "orbit_referencia_booking", "moloni_document_id", "zoho_id"]),
    ],
}
# nunca: estrutura interna ou já noutro sítio da ficha
_NUNCA = {"naming_series", "image", "organization_logo", "links", "rolling_responses", "status_change_log", "contacts",
          "full_name", "address", "email_ids", "phone_nos", "products", "email_id", "amended_from", "orbit_meios"}
# rótulos melhores do que os do Frappe
_ROTULOS = {"mobile_no": "Telemóvel", "phone": "Telefone", "email": "Email", "designation": "Cargo", "company_name": "Empresa (texto)",
            "organization": "Empresa", "organization_name": "Nome da empresa", "industry": "Setor", "lead_owner": "Responsável",
            "deal_owner": "Responsável", "last_name": "Apelido", "status": "Estado", "orbit_ultima_atividade": "Última atividade",
            "user": "Utilizador do Orbit", "is_primary_contact": "Contacto principal da empresa",
            "is_billing_contact": "Contacto de faturação", "unsubscribed": "Pediu para não receber emails",
            "lead_score": "Pontuação", "lead_temperature": "Temperatura", "deal_value": "Valor",
            "expected_deal_value": "Valor esperado", "expected_closure_date": "Fecho previsto", "closed_date": "Data de fecho",
            "nipc": "NIPC", "first_name": "Nome próprio", "lead_name": "Nome completo", "lead": "Lead de origem",
            "lead_name_deal": "Nome da lead", "contact": "Contacto principal", "website": "Site", "currency": "Moeda",
            "next_step": "Próximo passo", "sla": "Acordo de serviço (SLA)", "sla_status": "Estado do SLA",
            "communication_status": "Estado da comunicação", "titulo": "Título", "converted": "Convertida em negócio"}
_LARGOS = {"Small Text", "Text", "Long Text", "Text Editor"}


def _secao_do_campo(dt):
    out = {}
    for tit, campos in SECOES.get(dt, []):
        for c in campos:
            out[c] = tit
    return out


@frappe.whitelist()
def detalhes(doctype: str, name: str):
    from orbit.interface import api as A
    from orbit.interface import fiscal as F
    from orbit.interface import marcas as M
    A._guarda()
    if doctype not in SECOES:
        frappe.throw("Tipo de registo desconhecido")
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    pode = frappe.has_permission(doctype, "write", doc)
    meta = frappe.get_meta(doctype)

    def prop(f):
        p = A._prop_campo(doc, meta, f, pode)
        p["rotulo"] = _ROTULOS.get(f.fieldname, p["rotulo"])
        if (doctype, f.fieldname) in (("Contact", "nif"), ("CRM Organization", "nipc")):
            p["tipo"] = "Fiscal"
        p["largo"] = f.fieldtype in _LARGOS
        return p

    secoes = []
    usados = set()
    from orbit.interface.formularios import secoes as _secoes   # a disposição editável (CRM Fields Layout «Data Fields»)
    for sec in _secoes(doctype, "detalhes"):
        tit, campos = sec["titulo"], sec["campos"]
        s = {"titulo": tit, "campos": [], "tabelas": []}
        for c in campos:
            if c == "@morada":
                if meta.has_field("address"):
                    s["morada"] = {"valores": F.morada_de(doctype, name), "campos": [{"campo": a, "rotulo": r} for a, r in F.MORADA]}
                continue
            if c in ("@emails", "@telefones"):
                em, tl = meios_de(doc)
                s["tabelas"].append({"tipo": "emails", "linhas": em} if c == "@emails" else {"tipo": "telefones", "linhas": tl})
                continue
            if c == "@produtos":
                linhas = [{"artigo": p.get("product_name") or p.get("product_code"), "qtd": p.get("qty"), "preco": p.get("rate"),
                           "desconto": p.get("discount_percentage"), "total": p.get("net_amount") or p.get("amount")}
                          for p in doc.get("products") or []]
                s["tabelas"].append({"tipo": "produtos", "linhas": linhas})
                continue
            if c == "marcas" and doctype == "Contact" and meta.has_field("marcas"):
                usados.add(c)
                s["campos"].append({"campo": "marcas", "rotulo": "Marcas", "tipo": "Marcas", "valor": M.marcas_do_contacto(name),
                                    "editavel": bool(pode), "opcoes": M.lista(), "rotulos": {}, "largo": True})
                continue
            f = meta.get_field(c)
            if not f or f.hidden:
                continue
            usados.add(c)
            s["campos"].append(prop(f))
        if s["campos"] or s["tabelas"] or s.get("morada"):
            secoes.append(s)

    from orbit.interface.campos import personalizados
    extra, pers = [], []
    for f in meta.fields:
        if f.fieldname in usados or f.fieldname in _NUNCA or f.hidden or f.fieldtype not in A._TIPOS_FICHA:
            continue
        if (doctype == "Contact" and f.fieldname in ("mobile_no", "phone")) or \
                (doctype == "CRM Lead" and f.fieldname in ("email", "mobile_no", "phone")) or \
                (doctype == "CRM Organization" and f.fieldname in ("email_geral", "telefone")):
            continue   # são os principais da tabela de telefones, que está em «Emails e telefones»
        (pers if f.fieldname.startswith("oc_") else extra).append(prop(f))
    if pers:
        secoes.append({"titulo": "Campos personalizados", "campos": pers, "tabelas": []})
    if extra:
        secoes.append({"titulo": "Outros campos", "campos": extra, "tabelas": []})
    return {"secoes": secoes, "pode_editar": bool(pode),
            "paises": ["Portugal", "Spain", "France", "Italy", "Germany", "Belgium", "Netherlands", "Luxembourg",
                       "United Kingdom", "Switzerland", "Brazil", "Angola", "Mozambique", "Cape Verde"]}


def instalar():
    """after_migrate: a tabela de emails e telefones nas leads (o Frappe só tem um de cada)."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    # a mesma tabela (o nome do doctype ficou o da 1.ª vez) serve as leads e as empresas
    for dt, depois in (("CRM Lead", "phone"), ("CRM Organization", "telefone")):
        if frappe.db.exists("DocType", "Meio de Contacto da Lead") and frappe.db.exists("DocType", dt) \
                and not frappe.get_meta(dt).has_field("orbit_meios"):
            create_custom_field(dt, {"fieldname": "orbit_meios", "label": "Emails e telefones", "fieldtype": "Table",
                                     "options": "Meio de Contacto da Lead", "insert_after": depois})


def meios_de(doc) -> tuple[list, list]:
    """→ (emails, telefones) de um contacto ou de uma lead, [{valor, principal, movel}]."""
    if doc.doctype == "Contact":
        em = [{"valor": e.email_id, "principal": bool(e.is_primary)} for e in doc.get("email_ids") or []]
        tl = [{"valor": t.phone, "principal": bool(t.is_primary_mobile_no or t.is_primary_phone), "movel": bool(t.is_primary_mobile_no)}
              for t in doc.get("phone_nos") or []]
        return em, tl
    em, tl = [], []
    for r in doc.get("orbit_meios") or []:
        if r.tipo == "Email":
            em.append({"valor": r.valor, "principal": bool(r.principal)})
        else:
            tl.append({"valor": r.valor, "principal": bool(r.principal), "movel": r.tipo == "Telemóvel"})
    # registo antigo, sem tabela: os campos de origem
    if doc.doctype == "CRM Organization":
        if not em and doc.get("email_geral"):
            em.append({"valor": doc.email_geral, "principal": True})
        if not tl and doc.get("telefone"):
            tl.append({"valor": doc.telefone, "principal": True, "movel": str(doc.telefone).replace(" ", "").lstrip("+351")[:1] == "9"})
        return em, tl
    if not em and doc.get("email"):
        em.append({"valor": doc.email, "principal": True})
    if not tl:
        if doc.get("mobile_no"):
            tl.append({"valor": doc.mobile_no, "principal": True, "movel": True})
        if doc.get("phone"):
            tl.append({"valor": doc.phone, "principal": True, "movel": False})
    return em, tl


def _limpar(emails, telefones):
    em, vistos = [], set()
    for e in emails:
        v = str(e.get("valor") or "").strip().lower()[:140]
        if v and v not in vistos:
            vistos.add(v)
            em.append({"valor": v, "principal": bool(e.get("principal"))})
    if em and not any(e["principal"] for e in em):
        em[0]["principal"] = True
    um = False
    for e in em:
        e["principal"], um = (e["principal"] and not um), um or e["principal"]
    tl = [{"valor": str(t.get("valor") or "").strip()[:40], "principal": bool(t.get("principal")), "movel": bool(t.get("movel"))}
          for t in telefones if str(t.get("valor") or "").strip()]
    for movel in (True, False):
        um = False
        for t in tl:
            if t["movel"] == movel:
                t["principal"], um = (t["principal"] and not um), um or t["principal"]
    return em, tl


@frappe.whitelist(methods=["POST"])
def meios(doctype: str, name: str, emails: str = "[]", telefones: str = "[]"):
    """Grava os emails e telefones de um contacto ou de uma lead."""
    if doctype == "Contact":
        return contacto_meios(name, emails, telefones)
    from orbit.interface.api import _guarda
    _guarda()
    if doctype not in ("CRM Lead", "CRM Organization"):
        frappe.throw("Este registo não tem emails e telefones.")
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")
    em, tl = _limpar(json.loads(emails or "[]"), json.loads(telefones or "[]"))
    if doc.meta.has_field("orbit_meios"):
        doc.set("orbit_meios", [])
        for e in em:
            doc.append("orbit_meios", {"tipo": "Email", "valor": e["valor"], "principal": 1 if e["principal"] else 0})
        for t in tl:
            doc.append("orbit_meios", {"tipo": "Telemóvel" if t["movel"] else "Fixo", "valor": t["valor"], "principal": 1 if t["principal"] else 0})
    # o principal de cada um fica nos campos de origem (o resto do CRM lê-os daí)
    principal_email = next((e["valor"] for e in em if e["principal"]), None)
    movel = next((t["valor"] for t in tl if t["movel"] and t["principal"]), None)
    fixo = next((t["valor"] for t in tl if not t["movel"] and t["principal"]), None)
    if doctype == "CRM Organization":
        doc.email_geral = principal_email
        doc.telefone = fixo or movel
    else:
        doc.email, doc.mobile_no, doc.phone = principal_email, movel, fixo
    doc.save()
    return {"ok": True}


def copiar_para_contacto(lead: str, contacto: str):
    """Na conversão: os emails e telefones extra da lead passam para o contacto (sem repetir os que ele já tem)."""
    if not (lead and contacto and frappe.db.exists("CRM Lead", lead) and frappe.db.exists("Contact", contacto)):
        return
    l = frappe.get_doc("CRM Lead", lead)
    if not l.get("orbit_meios"):
        return
    c = frappe.get_doc("Contact", contacto)
    tem_e = {(e.email_id or "").lower() for e in c.get("email_ids") or []}
    tem_t = {re.sub(r"\D", "", t.phone or "") for t in c.get("phone_nos") or []}
    mudou = False
    for r in l.orbit_meios:
        if r.tipo == "Email" and r.valor.lower() not in tem_e:
            c.append("email_ids", {"email_id": r.valor, "is_primary": 0 if tem_e else 1})
            tem_e.add(r.valor.lower())
            mudou = True
        elif r.tipo != "Email" and re.sub(r"\D", "", r.valor) not in tem_t:
            c.append("phone_nos", {"phone": r.valor, "is_primary_mobile_no": 0, "is_primary_phone": 0})
            tem_t.add(re.sub(r"\D", "", r.valor))
            mudou = True
    if mudou:
        c.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def contacto_meios(name: str, emails: str = "[]", telefones: str = "[]"):
    """Grava os emails e telefones do contacto. [{valor, principal}], telefones com `movel`."""
    from orbit.interface.api import _guarda
    _guarda()
    doc = frappe.get_doc("Contact", name)
    doc.check_permission("write")
    em = [e for e in json.loads(emails or "[]") if str(e.get("valor") or "").strip()]
    tl = [t for t in json.loads(telefones or "[]") if str(t.get("valor") or "").strip()]
    if em and not any(e.get("principal") for e in em):
        em[0]["principal"] = True
    vistos = set()
    doc.set("email_ids", [])
    principal_feito = False
    for e in em:
        v = str(e["valor"]).strip().lower()[:140]
        if v in vistos:
            continue
        vistos.add(v)
        p = bool(e.get("principal")) and not principal_feito
        principal_feito = principal_feito or p
        doc.append("email_ids", {"email_id": v, "is_primary": 1 if p else 0})
    doc.set("phone_nos", [])
    movel_feito = fixo_feito = False
    for t in tl:
        v = str(t["valor"]).strip()[:40]
        movel = bool(t.get("movel"))
        p = bool(t.get("principal"))
        doc.append("phone_nos", {"phone": v,
                                 "is_primary_mobile_no": 1 if (p and movel and not movel_feito) else 0,
                                 "is_primary_phone": 1 if (p and not movel and not fixo_feito) else 0})
        movel_feito = movel_feito or (p and movel)
        fixo_feito = fixo_feito or (p and not movel)
    doc.save()
    return {"ok": True}
