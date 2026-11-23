"""Género: só quatro opções em todo o Orbit (23-11-2026, pedido do Vítor).

Masculino · Feminino · Outro · Prefiro não dizer — no CRM, no Desk, nos contactos, nos utilizadores e no RH (todos
ligam ao mesmo DocType «Gender»). Os valores de origem do Frappe passam a estes nomes por renomeação com fusão (o
Frappe actualiza todos os registos que os usam); os restantes (Transgender, Genderqueer, Non-Conforming, …) fundem-se
em «Outro». Corre em cada migração (after_migrate), por isso os tenants novos ficam iguais.
"""
import frappe

FICAM = ("Masculino", "Feminino", "Outro", "Prefiro não dizer")
MAPA = {"Male": "Masculino", "Female": "Feminino", "Other": "Outro", "Prefer not to say": "Prefiro não dizer",
        "Masculine": "Masculino", "Feminine": "Feminino"}


def acertar():
    if not frappe.db.exists("DocType", "Gender"):
        return
    for nome in FICAM:
        if not frappe.db.exists("Gender", nome):
            frappe.get_doc({"doctype": "Gender", "gender": nome}).insert(ignore_permissions=True)
    for g in frappe.get_all("Gender", pluck="name"):
        if g in FICAM:
            continue
        alvo = MAPA.get(g, "Outro")
        frappe.rename_doc("Gender", g, alvo, merge=True, force=True, show_alert=False)
    frappe.db.commit()
