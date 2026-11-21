"""Campos do inventário central nos doctypes do ERPNext (21-11-2026, docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md F1).

Só campos acrescentados (Custom Field, módulo Inventario) — nenhum ficheiro do ERPNext é alterado, por isso
sobrevivem às actualizações. Corre em cada `bench migrate` (after_migrate) e é idempotente.
"""
import frappe

ITEM = [
    {"fieldname": "orbit_sec_inventario", "fieldtype": "Section Break", "label": "Inventário central",
     "insert_after": "description", "collapsible": 1},
    {"fieldname": "orbit_fabricante", "fieldtype": "Link", "options": "Manufacturer", "label": "Fabricante",
     "insert_after": "orbit_sec_inventario", "in_standard_filter": 1,
     "description": "A marca do fabricante. A «Marca» do artigo é a do negócio (ex.: Arnox, JFusados, Shopinox)."},
    {"fieldname": "orbit_chave_importador", "fieldtype": "Data", "label": "Chave do importador",
     "insert_after": "orbit_fabricante", "read_only": 1, "no_copy": 1, "search_index": 1,
     "description": "«<id do fornecedor>:<referência>» — o produto do feed de onde este artigo vem."},
    {"fieldname": "orbit_pai_ref", "fieldtype": "Data", "label": "Produto-pai no feed",
     "insert_after": "orbit_chave_importador", "read_only": 1, "no_copy": 1},
    {"fieldname": "orbit_origem_stock", "fieldtype": "Data", "label": "Origem do stock (feed)",
     "insert_after": "orbit_pai_ref", "read_only": 1, "no_copy": 1},
    {"fieldname": "orbit_col_inventario", "fieldtype": "Column Break", "insert_after": "orbit_origem_stock"},
    {"fieldname": "orbit_comprimento", "fieldtype": "Float", "label": "Comprimento (cm)", "insert_after": "orbit_col_inventario"},
    {"fieldname": "orbit_largura", "fieldtype": "Float", "label": "Largura (cm)", "insert_after": "orbit_comprimento"},
    {"fieldname": "orbit_altura", "fieldtype": "Float", "label": "Altura (cm)", "insert_after": "orbit_largura"},
    {"fieldname": "orbit_categorias_loja", "fieldtype": "Small Text", "label": "Categorias na loja",
     "insert_after": "orbit_altura", "read_only": 1, "no_copy": 1},
    {"fieldname": "orbit_imagens", "fieldtype": "Long Text", "label": "Imagens (endereços)",
     "insert_after": "orbit_categorias_loja", "read_only": 1, "no_copy": 1,
     "description": "Endereços alojados, um por linha — as galerias não entram nos ficheiros do Orbit."},
    {"fieldname": "orbit_hash_espelho", "fieldtype": "Data", "label": "Assinatura do espelho",
     "insert_after": "orbit_imagens", "hidden": 1, "read_only": 1, "no_copy": 1},
]

SUPPLIER = [
    {"fieldname": "orbit_sec_inventario", "fieldtype": "Section Break", "label": "Inventário central",
     "insert_after": "supplier_group", "collapsible": 1},
    {"fieldname": "orbit_importador_id", "fieldtype": "Int", "label": "Id no importador",
     "insert_after": "orbit_sec_inventario", "read_only": 1, "no_copy": 1, "search_index": 1},
    {"fieldname": "orbit_vende_com_stock", "fieldtype": "Check", "label": "Pode vender-se com o stock deste fornecedor",
     "insert_after": "orbit_importador_id", "default": "1"},
    {"fieldname": "orbit_frescura_horas", "fieldtype": "Int", "label": "Frescura máxima do stock (horas)",
     "insert_after": "orbit_vende_com_stock", "default": "12",
     "description": "Stock lido há mais tempo do que isto conta como zero (D8: 12 h por omissão)."},
    {"fieldname": "orbit_margem_stock", "fieldtype": "Int", "label": "Margem de segurança (unidades)",
     "insert_after": "orbit_frescura_horas", "default": "0",
     "description": "Mostra-se a quantidade do fornecedor menos esta margem."},
]


def garantir():
    if not frappe.db.exists("DocType", "Item"):
        return   # tenant sem ERPNext
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
        create_custom_fields({"Item": [{**c, "module": "Inventario"} for c in ITEM],
                              "Supplier": [{**c, "module": "Inventario"} for c in SUPPLIER]}, update=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.inventario.campos.garantir")
