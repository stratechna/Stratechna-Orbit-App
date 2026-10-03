"""A barra lateral do Marketing.

No Frappe 16 cada módulo precisa de um registo «Workspace Sidebar»; sem ele o
desk improvisa uma lista a partir do que encontra, e a primeira versão do
Marketing aparecia só com Envios, Assuntos e Campanhas — faltavam os
Segmentos, as Automações, a Supressão e as Definições, que existiam mas só se
alcançavam pelo endereço. Cria-se aqui, em `after_migrate`, com a ordem do
trabalho: o que se faz todos os dias em cima, o que se consulta e configura em
baixo.
"""

import frappe

NOME = "Marketing"
ITENS = [
    ("Campanhas", "DocType", "Campanha de Marketing", "mail"),
    ("Automações", "DocType", "Automacao de Marketing", "repeat"),
    ("Modelos de email", "Page", "modelos-de-email", "layout"),
    ("Segmentos", "DocType", "Segmento de Marketing", "users"),
    ("Assuntos", "DocType", "Assunto de Marketing", "tag"),
    ("Envios", "DocType", "Envio de Marketing", "send"),
    ("Supressão", "DocType", "Supressao de Marketing", "ban"),
    ("Definições", "DocType", "Definicoes de Marketing", "settings"),
]


def garantir() -> None:
    if not frappe.db.exists("DocType", "Workspace Sidebar"):
        return
    doc = frappe.get_doc("Workspace Sidebar", NOME) if frappe.db.exists("Workspace Sidebar", NOME) \
        else frappe.new_doc("Workspace Sidebar")
    doc.update({"title": NOME, "header_icon": "mail", "module": "Marketing", "app": "orbit", "standard": 1})
    doc.set("items", [{"label": r, "link_type": t, "link_to": alvo, "icon": i, "type": "Link",
                       "collapsible": 1, "child": 0, "indent": 0, "keep_closed": 0, "show_arrow": 0}
                      for r, t, alvo, i in ITENS])
    if doc.is_new():
        doc.name = NOME
        doc.insert(ignore_permissions=True, set_name=NOME)
    else:
        doc.save(ignore_permissions=True)
    frappe.db.commit()
