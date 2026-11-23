"""Armazéns virtuais dos fornecedores (23-11-2026, pedido do Vítor: «fichas abertas com stock do fornecedor e fazerem
parte de armazéns diferentes, sem contabilização de stock»).

Cada fornecedor do importador tem um armazém «<Fornecedor> (fornecedor)», marcado `orbit_virtual`, debaixo de
«Fornecedores (virtual)». **Nunca recebe movimentos de stock** — a quantidade que lá se vê vem da Oferta do fornecedor
(o feed), por isso não entra no valor do stock nem na contabilidade. Os canais de venda continuam a decidir se o
stock do fornecedor conta para a disponibilidade (disponibilidade.py).
"""
import frappe

GRUPO = "Fornecedores (virtual)"


def _empresa():
    return frappe.defaults.get_global_default("company") or (frappe.get_all("Company", pluck="name") or [None])[0]


def nome_do_virtual(supplier: str) -> str | None:
    return frappe.db.get_value("Warehouse", {"orbit_virtual": 1, "orbit_fornecedor": supplier}, "name")


def garantir() -> int:
    if not (frappe.db.exists("DocType", "Warehouse") and frappe.get_meta("Warehouse").has_field("orbit_virtual")):
        return 0
    empresa = _empresa()
    if not empresa:
        return 0
    abrev = frappe.db.get_value("Company", empresa, "abbr")
    grupo = frappe.db.get_value("Warehouse", {"warehouse_name": GRUPO, "company": empresa}, "name")
    if not grupo:
        pai = frappe.db.get_value("Warehouse", {"is_group": 1, "company": empresa, "parent_warehouse": ["in", ["", None]]}, "name")
        grupo = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": GRUPO, "is_group": 1, "company": empresa,
                                "parent_warehouse": pai}).insert(ignore_permissions=True).name
    novos = 0
    for s in frappe.get_all("Supplier", filters={"orbit_importador_id": [">", 0]}, fields=["name", "supplier_name"]):
        if nome_do_virtual(s.name):
            continue
        frappe.get_doc({"doctype": "Warehouse", "warehouse_name": f"{s.supplier_name} (fornecedor)"[:120], "company": empresa,
                        "parent_warehouse": grupo, "orbit_virtual": 1, "orbit_fornecedor": s.name}).insert(ignore_permissions=True)
        novos += 1
    frappe.db.commit()
    return novos


def instalar():
    try:
        garantir()
    except Exception:  # noqa: BLE001
        frappe.log_error(title="Orbit inventário: armazéns virtuais")
