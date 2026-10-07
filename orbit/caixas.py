"""Caixas partilhadas — o que tem de existir para o DocType funcionar.

Corre no `after_migrate`, como o resto. Cria o papel que decide quem pode mexer
nisto: sem ele, o DocType ficava só para o System Manager e a razão de o pôr no
Orbit — ter permissões a sério — perdia-se.
"""
import frappe

PAPEL = "Gestor de Correio"


def garantir():
    """O papel, em todos os inquilinos."""
    if not frappe.db.exists("Role", PAPEL):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": PAPEL,
            "desk_access": 1,
            # Não é um papel de gestão geral: quem o tem administra caixas
            # partilhadas e mais nada. Daí não herdar nada de outro.
            "is_custom": 1,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
