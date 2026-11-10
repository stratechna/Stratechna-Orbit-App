"""A marca de um artigo pelo prefixo da referência (10-11-2026, pedido do Vítor para a JF).

Na JF cada marca tem o seu armazém e as referências dizem de que marca são: A seguido de número → JFusados,
N seguido de número → Arnox. Cada marca (Brand) ganha o campo «Prefixo das referências»; um artigo cujo código
comece pelo prefixo seguido de um algarismo fica com essa marca — e, pela marca, com o armazém por omissão dela
(`Brand.brand_defaults`, que o ERPNext usa nas encomendas, guias e faturas).

O prefixo ganha sempre que bate: é a regra da casa, e um artigo da Arnox proposto pela Shopinox continua a sair
do armazém da Arnox. Sem prefixo que bata, a marca fica como estiver.
"""
import re

import frappe

CAMPO = {"fieldname": "orbit_prefixo", "fieldtype": "Data", "label": "Prefixo das referências",
         "insert_after": "description",
         "description": "Ex.: A — os artigos com código A seguido de número (A1234) ficam com esta marca e com o "
                        "armazém por omissão dela."}


def garantir():
    if not frappe.db.exists("DocType", "Brand"):
        return
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        if not frappe.db.exists("Custom Field", {"dt": "Brand", "fieldname": CAMPO["fieldname"]}):
            create_custom_field("Brand", {**CAMPO, "module": "Orbit"})
            frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.marcas_artigos.garantir")


def _prefixos() -> list[tuple[str, str]]:
    if not frappe.get_meta("Brand").has_field("orbit_prefixo"):
        return []
    linhas = frappe.get_all("Brand", filters={"orbit_prefixo": ["is", "set"]}, fields=["name", "orbit_prefixo"])
    # o prefixo mais comprido primeiro (AB antes de A)
    return sorted(((l.orbit_prefixo.strip().upper(), l.name) for l in linhas if l.orbit_prefixo.strip()),
                  key=lambda p: -len(p[0]))


def marca_do_codigo(codigo: str) -> str | None:
    codigo = (codigo or "").strip().upper()
    for prefixo, marca in _prefixos():
        if re.match(rf"^{re.escape(prefixo)}\d", codigo):
            return marca
    return None


def antes_de_validar_artigo(doc, method=None):
    marca = marca_do_codigo(doc.item_code)
    if marca and doc.brand != marca:
        doc.brand = marca
