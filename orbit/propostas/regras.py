"""Regras do Orçamento antes de validar (doc_events Quotation.before_validate).

Corre ANTES do `validate` do ERPNext, que é onde se calculam os totais e o IVA — por isso as linhas de transporte
e montagem que aqui se acrescentam já entram nas contas, na encomenda e na fatura.

As linhas automáticas vão sempre para o FIM da tabela: o ERPNext reconhece uma alternativa pela posição (a linha
logo a seguir à principal), e uma linha de transporte metida no meio partia essa ligação.
"""
import json
import uuid

import frappe
from frappe.utils import add_days, cint, flt

from orbit.propostas.instalar import SERVICOS

_SEM_MODO = "Não incluir"


def antes_de_inserir(doc, method=None):
    """A série tem de estar certa ANTES de o Frappe dar o nome (o nome nasce antes do before_validate)."""
    marca = _marca(doc)
    if marca:
        _serie(doc, marca)


def _serie(doc, marca):
    serie = (marca.get("orbit_serie") or "").strip().upper()
    if not serie:
        return
    opcoes = (frappe.get_meta("Quotation").get_field("naming_series").options or "").split("\n")
    alvo = next((o for o in opcoes if f"-{serie}-" in o), None)
    if alvo:
        doc.naming_series = alvo


def antes_de_validar(doc, method=None):
    if doc.docstatus != 0:
        return
    marca = _marca(doc)
    if marca:
        _aplicar_marca(doc, marca)
    _iva_por_omissao(doc)
    _linhas_automaticas(doc)


def _marca(doc):
    if not doc.get("orbit_marca") or not frappe.db.exists("Brand", doc.orbit_marca):
        return None
    return frappe.get_cached_doc("Brand", doc.orbit_marca)


def _aplicar_marca(doc, marca):
    if doc.is_new():
        _serie(doc, marca)
        dias = cint(marca.get("orbit_validade_dias")) or 15
        if not doc.valid_till and doc.transaction_date:
            doc.valid_till = add_days(doc.transaction_date, dias)
        for campo in ("orbit_garantia", "orbit_pagamento", "orbit_prazo", "orbit_texto_intro"):
            if not doc.get(campo) and marca.get(campo):
                doc.set(campo, marca.get(campo))
    timbre = f"Timbre {marca.name}"
    if not doc.letter_head and frappe.db.exists("Letter Head", timbre):
        doc.letter_head = timbre
    for linha in doc.items or []:
        if not linha.get("brand") and not linha.get("orbit_de"):
            linha.brand = marca.name


def _iva_por_omissao(doc):
    """Sem impostos escolhidos: o modelo de IVA da empresa, se houver um só (ou o marcado por omissão)."""
    if doc.get("taxes") or doc.get("taxes_and_charges"):
        return
    filtros = {"company": doc.company, "disabled": 0}
    modelos = frappe.get_all("Sales Taxes and Charges Template", filters=filtros, fields=["name", "is_default"])
    escolhido = next((m.name for m in modelos if m.is_default), None) or (modelos[0].name if len(modelos) == 1 else None)
    if not escolhido:
        return
    from erpnext.controllers.accounts_controller import get_taxes_and_charges
    doc.taxes_and_charges = escolhido
    for t in get_taxes_and_charges("Sales Taxes and Charges Template", escolhido) or []:
        doc.append("taxes", t)


def _linhas_automaticas(doc):
    """Refaz as linhas TRANSPORTE/MONTAGEM a partir dos valores de cada produto (ou dos totais)."""
    manuais = [l for l in doc.items or [] if not l.get("orbit_de")]
    for l in manuais:
        if not l.get("orbit_chave"):
            l.orbit_chave = uuid.uuid4().hex[:12]
    modo = doc.get("orbit_transporte_modo") or "Por produto"
    novas = []
    if modo == "Por produto":
        for l in manuais:
            if l.is_alternative or l.item_code in SERVICOS:
                continue   # a alternativa mostra o transporte dela na impressão, mas não soma
            for codigo, valor in (("TRANSPORTE", l.get("orbit_transporte")), ("MONTAGEM", l.get("orbit_montagem"))):
                if flt(valor) > 0:
                    novas.append((codigo, flt(valor), l.orbit_chave, f"{SERVICOS[codigo]} — {l.item_name or l.item_code}"))
    elif modo == "No total":
        for codigo, valor in (("TRANSPORTE", doc.get("orbit_transporte_total")),
                              ("MONTAGEM", doc.get("orbit_montagem_total"))):
            if flt(valor) > 0:
                novas.append((codigo, flt(valor), "total", SERVICOS[codigo]))

    antigas = {(l.item_code, l.orbit_de): l for l in doc.items or [] if l.get("orbit_de")}
    desejadas = {(c, de) for c, _v, de, _d in novas}
    if set(antigas) == desejadas and all(flt(antigas[(c, de)].rate) == v for c, v, de, _d in novas):
        return   # nada mudou: não mexer (evita gravar o documento como alterado)
    doc.set("items", manuais)
    for codigo, valor, de, descricao in novas:
        if not frappe.db.exists("Item", codigo):
            continue
        uom = frappe.db.get_value("Item", codigo, "stock_uom")
        anterior = antigas.get((codigo, de))
        doc.append("items", {
            "item_code": codigo, "item_name": SERVICOS[codigo], "description": descricao, "qty": 1,
            "uom": uom, "stock_uom": uom, "conversion_factor": 1, "rate": valor, "price_list_rate": 0,
            "orbit_de": de, "brand": doc.get("orbit_marca"),
            "item_tax_template": anterior.item_tax_template if anterior else None,
        })
    for i, l in enumerate(doc.items, 1):
        l.idx = i


def taxa_iva(doc, linha) -> float:
    """A taxa de IVA de uma linha, para a impressão («1 000,00 € + IVA 23 %»)."""
    try:
        taxas = json.loads(linha.get("item_tax_rate") or "{}")
        if taxas:
            return flt(next(iter(taxas.values())))
    except ValueError:
        pass
    for t in doc.get("taxes") or []:
        if t.charge_type == "On Net Total":
            return flt(t.rate)
    return 0.0
