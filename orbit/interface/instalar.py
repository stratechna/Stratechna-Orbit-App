"""Campos próprios da interface /orbit (20-11-2026), criados no after_migrate de cada tenant (idempotente).

* `orbit_responsavel` (Responsável, Link User) em Contact e CRM Organization — como o «Contact owner»/«Company owner»
  do HubSpot; as leads e os negócios já têm o seu (`lead_owner`, `deal_owner`).
"""
import frappe

_CAMPOS = {
    "Contact": [{"fieldname": "orbit_responsavel", "label": "Responsável", "fieldtype": "Link", "options": "User",
                 "insert_after": "full_name", "in_standard_filter": 1}],
    "CRM Organization": [{"fieldname": "orbit_responsavel", "label": "Responsável", "fieldtype": "Link", "options": "User",
                          "insert_after": "organization_name", "in_standard_filter": 1}],
}


def instalar() -> None:
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    for dt, campos in _CAMPOS.items():
        if not frappe.db.exists("DocType", dt):
            continue
        for c in campos:
            if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
                create_custom_field(dt, {**c, "module": "Orbit"})
