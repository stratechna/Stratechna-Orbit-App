"""Campos próprios da faturação certificada (after_migrate). Só onde o ERPNext está instalado."""
import frappe

from orbit.faturacao.base import MOTIVOS_ISENCAO

CAMPOS = {
    "Customer": [
        {"fieldname": "orbit_fat_ids", "fieldtype": "Code", "label": "Ids nos programas de faturação",
         "options": "JSON", "read_only": 1, "hidden": 1, "no_copy": 1, "insert_after": "tax_id"},
    ],
    "Item": [
        {"fieldname": "orbit_fat_ids", "fieldtype": "Code", "label": "Ids nos programas de faturação",
         "options": "JSON", "read_only": 1, "hidden": 1, "no_copy": 1, "insert_after": "item_code"},
    ],
    "Sales Invoice": [
        {"fieldname": "orbit_motivo_isencao", "fieldtype": "Select", "label": "Motivo de isenção de IVA",
         "options": "\n" + "\n".join(MOTIVOS_ISENCAO), "insert_after": "taxes_and_charges",
         "description": "Obrigatório nas linhas sem IVA quando a fatura é emitida num programa certificado."},
        {"fieldname": "orbit_motivo_nc", "fieldtype": "Small Text", "label": "Motivo da nota de crédito",
         "depends_on": "is_return", "insert_after": "orbit_motivo_isencao"},
        {"fieldname": "orbit_documento_certificado", "fieldtype": "Link", "options": "Documento Certificado",
         "label": "Documento certificado", "read_only": 1, "no_copy": 1, "allow_on_submit": 1,
         "insert_after": "orbit_motivo_nc"},
        {"fieldname": "orbit_numero_certificado", "fieldtype": "Data", "label": "N.º no programa certificado",
         "read_only": 1, "no_copy": 1, "allow_on_submit": 1, "in_list_view": 1,
         "insert_after": "orbit_documento_certificado"},
    ],
    "Payment Entry": [
        {"fieldname": "orbit_documento_certificado", "fieldtype": "Link", "options": "Documento Certificado",
         "label": "Recibo certificado", "read_only": 1, "no_copy": 1, "allow_on_submit": 1,
         "insert_after": "reference_date"},
    ],
}


def garantir():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return   # tenant sem ERPNext
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    for dt, campos in CAMPOS.items():
        for c in campos:
            if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
                create_custom_field(dt, {**c, "module": "Orbit"})
