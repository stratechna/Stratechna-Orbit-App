"""Campos, artigos de serviço e o modelo de impressão das propostas (after_migrate). Só onde há ERPNext."""
import os

import frappe

FORMATO = "Proposta Orbit"

# Os dois artigos de serviço que levam o transporte e a montagem para os totais, o IVA, a encomenda e a fatura.
SERVICOS = {"TRANSPORTE": "Transporte", "MONTAGEM": "Montagem"}

_VALIDADE = 15
_GARANTIA = "1 ano contra defeitos de fabrico."
_PAGAMENTO = ("50 % na adjudicação da encomenda e 50 % com os equipamentos disponíveis na nossa loja, "
              "antes da entrega.")
_PRAZO = "Sob confirmação e disponibilidade."

CAMPOS = {
    "Brand": [
        {"fieldname": "orbit_prop_tab", "fieldtype": "Section Break", "label": "Propostas comerciais",
         "insert_after": "description", "collapsible": 1},
        {"fieldname": "orbit_cor", "fieldtype": "Color", "label": "Cor da marca", "insert_after": "orbit_prop_tab",
         "description": "Filetes, títulos e rodapé da proposta. O logótipo é a imagem da marca."},
        {"fieldname": "orbit_serie", "fieldtype": "Data", "label": "Série", "insert_after": "orbit_cor",
         "description": "ARX, JFS, SHX… — as propostas desta marca saem com a série ORC-<série>-."},
        {"fieldname": "orbit_site", "fieldtype": "Data", "label": "Site (no rodapé)", "insert_after": "orbit_serie"},
        {"fieldname": "orbit_loja", "fieldtype": "Data", "label": "Loja WooCommerce (procura por referência)",
         "insert_after": "orbit_site", "description": "Endereço onde se procuram as referências, ex.: shopinox.eu"},
        {"fieldname": "orbit_prop_col1", "fieldtype": "Column Break", "insert_after": "orbit_loja"},
        {"fieldname": "orbit_morada", "fieldtype": "Small Text", "label": "Morada", "insert_after": "orbit_prop_col1"},
        {"fieldname": "orbit_nif", "fieldtype": "Data", "label": "NIF", "insert_after": "orbit_morada"},
        {"fieldname": "orbit_telefones", "fieldtype": "Data", "label": "Telefones", "insert_after": "orbit_nif"},
        {"fieldname": "orbit_email", "fieldtype": "Data", "label": "Email", "options": "Email",
         "insert_after": "orbit_telefones"},
        {"fieldname": "orbit_iban", "fieldtype": "Data", "label": "IBAN", "insert_after": "orbit_email"},
        {"fieldname": "orbit_prop_omissao", "fieldtype": "Section Break", "label": "Textos por omissão das propostas",
         "insert_after": "orbit_iban", "collapsible": 1},
        {"fieldname": "orbit_validade_dias", "fieldtype": "Int", "label": "Validade (dias)", "default": str(_VALIDADE),
         "insert_after": "orbit_prop_omissao"},
        {"fieldname": "orbit_garantia", "fieldtype": "Small Text", "label": "Garantia", "default": _GARANTIA,
         "insert_after": "orbit_validade_dias"},
        {"fieldname": "orbit_pagamento", "fieldtype": "Small Text", "label": "Condições de pagamento",
         "default": _PAGAMENTO, "insert_after": "orbit_garantia"},
        {"fieldname": "orbit_prazo", "fieldtype": "Small Text", "label": "Prazo de entrega", "default": _PRAZO,
         "insert_after": "orbit_pagamento"},
        {"fieldname": "orbit_texto_intro", "fieldtype": "Small Text", "label": "Texto de introdução",
         "insert_after": "orbit_prazo"},
        {"fieldname": "orbit_condicoes", "fieldtype": "Text Editor", "label": "Condições comerciais (página anexa)",
         "insert_after": "orbit_texto_intro",
         "description": "Sai numa página própria no fim de cada proposta desta marca. Vazio = sem página anexa."},
    ],
    "Quotation": [
        {"fieldname": "orbit_marca", "fieldtype": "Link", "options": "Brand", "label": "Marca",
         "insert_after": "naming_series", "in_standard_filter": 1, "in_list_view": 1,
         "description": "Escolhe o logótipo, a série, o rodapé e os textos por omissão."},
        {"fieldname": "orbit_prop_sec", "fieldtype": "Section Break", "label": "Proposta",
         "insert_after": "ignore_pricing_rule"},
        {"fieldname": "orbit_texto_intro", "fieldtype": "Text Editor", "label": "Texto de introdução",
         "insert_after": "orbit_prop_sec"},
        {"fieldname": "orbit_prop_sec2", "fieldtype": "Section Break", "insert_after": "orbit_texto_intro"},
        {"fieldname": "orbit_transporte_modo", "fieldtype": "Select", "label": "Transporte e montagem",
         "options": "Por produto\nNo total\nNão incluir", "default": "Por produto",
         "insert_after": "orbit_prop_sec2"},
        {"fieldname": "orbit_transporte_total", "fieldtype": "Currency", "label": "Transporte (total)",
         "depends_on": "eval:doc.orbit_transporte_modo=='No total'", "insert_after": "orbit_transporte_modo"},
        {"fieldname": "orbit_montagem_total", "fieldtype": "Currency", "label": "Montagem (total)",
         "depends_on": "eval:doc.orbit_transporte_modo=='No total'", "insert_after": "orbit_transporte_total"},
        {"fieldname": "orbit_mostrar_iva", "fieldtype": "Check", "label": "Mostrar o IVA e o total com IVA",
         "default": "1", "insert_after": "orbit_montagem_total"},
        {"fieldname": "orbit_anexar_condicoes", "fieldtype": "Check", "label": "Anexar as condições comerciais da marca",
         "default": "1", "insert_after": "orbit_mostrar_iva"},
        {"fieldname": "orbit_prop_col", "fieldtype": "Column Break", "insert_after": "orbit_anexar_condicoes"},
        {"fieldname": "orbit_garantia", "fieldtype": "Small Text", "label": "Garantia",
         "insert_after": "orbit_prop_col"},
        {"fieldname": "orbit_pagamento", "fieldtype": "Small Text", "label": "Condições de pagamento",
         "insert_after": "orbit_garantia"},
        {"fieldname": "orbit_prazo", "fieldtype": "Small Text", "label": "Prazo de entrega",
         "insert_after": "orbit_pagamento"},
    ],
    "Item": [
        {"fieldname": "orbit_caracteristicas", "fieldtype": "Small Text", "label": "Características",
         "insert_after": "description",
         "description": "Uma por linha, «Nome: valor». Passam para as propostas com o artigo."},
    ],
    "Quotation Item": [
        {"fieldname": "orbit_caracteristicas", "fieldtype": "Small Text", "label": "Características",
         "insert_after": "description", "fetch_from": "item_code.orbit_caracteristicas", "fetch_if_empty": 1,
         "description": "Uma por linha, «Nome: valor». Saem na proposta debaixo da descrição."},
        {"fieldname": "orbit_observacoes", "fieldtype": "Small Text", "label": "Observações",
         "insert_after": "orbit_caracteristicas", "in_list_view": 0},
        {"fieldname": "orbit_transporte", "fieldtype": "Currency", "label": "Transporte desta linha",
         "insert_after": "rate", "depends_on": "eval:!doc.orbit_de",
         "description": "Total da linha, sem IVA. Só conta com «Transporte e montagem: Por produto»."},
        {"fieldname": "orbit_montagem", "fieldtype": "Currency", "label": "Montagem desta linha",
         "insert_after": "orbit_transporte", "depends_on": "eval:!doc.orbit_de"},
        {"fieldname": "orbit_chave", "fieldtype": "Data", "label": "Chave da linha", "hidden": 1, "no_copy": 0,
         "read_only": 1, "insert_after": "orbit_montagem"},
        {"fieldname": "orbit_de", "fieldtype": "Data", "label": "Transporte/montagem da linha", "hidden": 1,
         "read_only": 1, "insert_after": "orbit_chave"},
        {"fieldname": "orbit_fonte", "fieldtype": "Data", "label": "Dados vindos de", "read_only": 1,
         "insert_after": "orbit_de"},
    ],
}


def garantir():
    if not frappe.db.exists("DocType", "Quotation"):
        return   # tenant sem ERPNext
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        for dt, campos in CAMPOS.items():
            for c in campos:
                if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
                    create_custom_field(dt, {**c, "module": "Orbit"})
        _servicos()
        _formato()
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.propostas.garantir")


def _servicos():
    """TRANSPORTE e MONTAGEM: artigos sem stock, que as regras acrescentam ao Orçamento."""
    if not frappe.db.get_value("Company", {}, "name"):
        return   # sem empresa configurada ainda (assistente por correr)
    grupo = "Services" if frappe.db.exists("Item Group", "Services") else \
        frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
    for codigo, nome in SERVICOS.items():
        if frappe.db.exists("Item", codigo):
            continue
        frappe.get_doc({"doctype": "Item", "item_code": codigo, "item_name": nome, "description": nome,
                        "item_group": grupo, "stock_uom": uom, "is_stock_item": 0, "include_item_in_manufacturing": 0,
                        "is_sales_item": 1, "is_purchase_item": 0}).insert(ignore_permissions=True)


def _formato():
    """O modelo de impressão vive no ficheiro e é reposto a cada migração (alterações à mão perdem-se)."""
    with open(os.path.join(os.path.dirname(__file__), "proposta.html"), encoding="utf-8") as f:
        html = f.read()
    dados = {"doc_type": "Quotation", "module": "Orbit", "custom_format": 1, "print_format_type": "Jinja",
             "html": html, "standard": "No", "disabled": 0, "pdf_generator": "wkhtmltopdf",
             "margin_top": 12, "margin_bottom": 30, "margin_left": 0, "margin_right": 0,
             "print_format_builder": 0, "raw_printing": 0}
    if frappe.db.exists("Print Format", FORMATO):
        pf = frappe.get_doc("Print Format", FORMATO)
        if any(pf.get(k) != v for k, v in dados.items()):
            pf.update(dados)
            pf.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Print Format", "name": FORMATO, **dados}).insert(ignore_permissions=True)
    # o formato por omissão do Orçamento passa a ser este (Property Setter, como faz o ecrã «Personalizar»)
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    if frappe.db.get_value("Property Setter", {"doc_type": "Quotation", "property": "default_print_format"},
                           "value") != FORMATO:
        make_property_setter("Quotation", None, "default_print_format", FORMATO, "Data", for_doctype=True,
                             validate_fields_for_doctype=False)
