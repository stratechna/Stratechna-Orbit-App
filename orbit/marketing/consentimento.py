"""O consentimento de marketing no CRM — os campos, o painel e o histórico.

Corre em `after_migrate`, em todos os tenants: é assim que um tenant novo já
nasce com eles, e é assim que a regra se mantém transversal. Até 03-10-2026
isto era um guião à parte (`/opt/orbit/scripts/orbit_consentimento.py`),
corrido à mão; os quatro tenants que existiam já os têm, e aqui só se
confirma.

Só configuração — campos personalizados, painel do CRM e `track_changes` —,
nenhuma alteração ao código do CRM, que é AGPL.

O histórico de versões do Frappe (`track_changes`) é o registo de prova do
consentimento: quem o mudou, de quê para quê, e quando. Não se inventa outro.

Os estados são «Sem registo», «Pode receber», «Recusou» e «Retirou». Não
«Consentiu»: a base legal pode ser cliente ou contacto profissional, que não
são consentimento — e chamar-lhes isso seria escrever uma coisa falsa no
registo que serve de prova.
"""

import json

import frappe

SECCAO = "marketing_section"
DOCTYPES = {"CRM Lead": "status", "Contact": "company_name"}

CAMPOS = [
    {"fieldname": "mkt_estado", "label": "Comunicações de marketing", "fieldtype": "Select",
     "options": "\nSem registo\nPode receber\nRecusou\nRetirou", "default": "Sem registo"},
    {"fieldname": "mkt_base_legal", "label": "Base legal", "fieldtype": "Select",
     "options": "\nconsentimento\ncliente\nb2b",
     "description": "consentimento: aceitou expressamente · cliente: comprou e recebe sobre o que é análogo "
                    "· b2b: contacto profissional de uma empresa"},
    {"fieldname": "mkt_data", "label": "Data do registo", "fieldtype": "Date"},
    {"fieldname": "mkt_origem", "label": "Origem", "fieldtype": "Select",
     "options": "\nFormulário do site\nLoja online\nContrato ou proposta\nFeira ou evento\nTelefone\nImportação\nOutra"},
    {"fieldname": "mkt_texto", "label": "Texto aceite", "fieldtype": "Small Text",
     "description": "O que a pessoa leu quando aceitou"},
    {"fieldname": "mkt_assuntos", "label": "Assuntos de interesse", "fieldtype": "Small Text",
     "description": "Separados por vírgulas: Novidades, Promoções…"},
    {"fieldname": "mkt_segmento", "label": "Segmento", "fieldtype": "Data"},
    {"fieldname": "mkt_idioma", "label": "Idioma", "fieldtype": "Select", "options": "\npt\nen\nes\nfr"},
]
NOMES = [c["fieldname"] for c in CAMPOS]


def _campos(dt: str, depois_de: str) -> None:
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    anterior = depois_de
    for c in CAMPOS:
        if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
            create_custom_field(dt, {**c, "insert_after": anterior})
        anterior = c["fieldname"]


def _painel(dt: str) -> None:
    """Um campo personalizado que não está no painel não aparece no ecrã do
    CRM — e um campo que não se vê não se preenche."""
    nome = f"{dt}-Side Panel"
    if not frappe.db.exists("DocType", "CRM Fields Layout") or not frappe.db.exists("CRM Fields Layout", nome):
        return
    doc = frappe.get_doc("CRM Fields Layout", nome)
    layout = json.loads(doc.layout or "[]")
    if any(s.get("name") == SECCAO for s in layout):
        return
    layout.append({"label": "Comunicações de marketing", "name": SECCAO, "opened": False,
                   "columns": [{"name": "column_mkt", "fields": NOMES}]})
    doc.layout = json.dumps(layout)
    doc.save(ignore_permissions=True)


def _historico(dt: str) -> None:
    if frappe.get_meta(dt).track_changes:
        return
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    make_property_setter(dt, None, "track_changes", 1, "Check", for_doctype=True)


def garantir() -> None:
    for dt, depois in DOCTYPES.items():
        if not frappe.db.exists("DocType", dt):
            continue
        _campos(dt, depois)
        _painel(dt)
        _historico(dt)
    frappe.db.commit()
