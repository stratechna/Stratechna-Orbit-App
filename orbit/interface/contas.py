# Contas a receber e a pagar, e painéis dos módulos, na interface nova (/orbit) — 25-11-2026
#
# Pedido do Vítor (25-11): na Gestão, o bloco «A receber» abria a lista de clientes «e nada me diz o que receber»,
# e o «Painel» abria a secretária antiga do Frappe. Aqui: o que cada cliente deve (ou o que se deve a cada
# fornecedor), as vencidas e a antiguidade, a partir das faturas submetidas com valor em dívida — funciona também
# com a contabilidade desligada (o outstanding_amount da fatura é mantido pelos recibos). E os painéis (Dashboard)
# dos módulos lidos e calculados aqui (cartões de número e gráficos), sem abrir o /desk.
import json

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from orbit.interface.api import _guarda

LADOS = {
    "receber": {"doctype": "Sales Invoice", "parte": "customer", "nome": "customer_name", "entidade": "Customer",
                "titulo": "Contas a receber", "rotulo": "Cliente"},
    "pagar": {"doctype": "Purchase Invoice", "parte": "supplier", "nome": "supplier_name", "entidade": "Supplier",
              "titulo": "Contas a pagar", "rotulo": "Fornecedor"},
}
FAIXAS = [("Por vencer", None, 0), ("1–30 dias", 1, 30), ("31–60 dias", 31, 60), ("61–90 dias", 61, 90), ("Mais de 90 dias", 91, None)]


def _lado(lado):
    c = LADOS.get(lado)
    if not c:
        frappe.throw(_("Lado desconhecido."))
    if not frappe.has_permission(c["doctype"], "read"):
        frappe.throw(_("Sem acesso a estes documentos."), frappe.PermissionError)
    return c


def _faixa(dias):
    for i, (_r, de, ate) in enumerate(FAIXAS):
        if de is None and dias <= 0:
            return i
        if de is not None and dias >= de and (ate is None or dias <= ate):
            return i
    return 0


def _abertas(c, entidade=None):
    filtros = {"docstatus": 1, "outstanding_amount": ["!=", 0]}
    if entidade:
        filtros[c["parte"]] = entidade
    campos = ["name", c["parte"] + " as parte", c["nome"] + " as nome", "posting_date", "due_date", "grand_total",
              "outstanding_amount", "currency", "conversion_rate", "is_return"]
    meta = frappe.get_meta(c["doctype"])
    for extra in ("orbit_marca", "orbit_numero_certificado", "company"):
        if meta.has_field(extra) or extra == "company":
            campos.append(extra)
    if c["doctype"] == "Purchase Invoice":
        campos.append("bill_no")
    return frappe.get_list(c["doctype"], filters=filtros, fields=campos, order_by="due_date asc", limit_page_length=0)


@frappe.whitelist()
def resumo(lado: str = "receber", empresa: str = None, marca: str = None):
    """Totais, antiguidade e a lista por cliente/fornecedor do que está em dívida."""
    _guarda()
    c = _lado(lado)
    hoje = nowdate()
    tot = {"divida": 0.0, "vencido": 0.0, "a_30": 0.0, "documentos": 0}
    faixas = [{"rotulo": r, "valor": 0.0, "n": 0} for r, _a, _b in FAIXAS]
    por = {}
    empresas, marcas = set(), set()
    for f in _abertas(c):
        if f.get("company"):
            empresas.add(f.company)
        if f.get("orbit_marca"):
            marcas.add(f.orbit_marca)
        if empresa and f.get("company") != empresa:
            continue
        if marca and f.get("orbit_marca") != marca:
            continue
        v = flt(f.outstanding_amount) * (flt(f.conversion_rate) or 1)
        dias = date_diff(hoje, f.due_date) if f.due_date else 0
        tot["divida"] += v
        tot["documentos"] += 1
        if dias > 0:
            tot["vencido"] += v
        elif dias >= -30:
            tot["a_30"] += v
        k = _faixa(dias)
        faixas[k]["valor"] += v
        faixas[k]["n"] += 1
        p = por.setdefault(f.parte, {"entidade": f.parte, "nome": f.nome or f.parte, "divida": 0.0, "vencido": 0.0,
                                     "documentos": 0, "atraso": 0, "mais_antiga": None})
        p["divida"] += v
        p["documentos"] += 1
        if dias > 0:
            p["vencido"] += v
            p["atraso"] = max(p["atraso"], dias)
        if f.due_date and (not p["mais_antiga"] or str(f.due_date) < p["mais_antiga"]):
            p["mais_antiga"] = str(f.due_date)
    lista = sorted(por.values(), key=lambda x: (-x["vencido"], -x["divida"]))
    for x in [tot] + faixas + lista:
        for k in ("divida", "vencido", "a_30", "valor"):
            if k in x:
                x[k] = round(x[k], 2)
    return {"titulo": _(c["titulo"]), "rotulo": _(c["rotulo"]), "entidade_doctype": c["entidade"], "doctype": c["doctype"],
            "totais": tot, "faixas": faixas, "lista": lista, "empresas": sorted(empresas), "marcas": sorted(marcas),
            "moeda": frappe.db.get_default("currency") or "EUR"}


@frappe.whitelist()
def documentos(lado: str, entidade: str):
    """As faturas em dívida de um cliente/fornecedor (notas de crédito/débito em aberto incluídas, com valor negativo)."""
    _guarda()
    c = _lado(lado)
    hoje = nowdate()
    out = []
    for f in _abertas(c, entidade):
        dias = date_diff(hoje, f.due_date) if f.due_date else 0
        out.append({"name": f.name, "numero": f.get("orbit_numero_certificado") or f.get("bill_no") or f.name,
                    "data": str(f.posting_date), "vencimento": str(f.due_date or ""), "atraso": max(dias, 0),
                    "total": flt(f.grand_total), "divida": flt(f.outstanding_amount), "moeda": f.currency,
                    "devolucao": bool(f.is_return), "marca": f.get("orbit_marca")})
    return out


# ── Painéis (Dashboard) dos módulos, sem o /desk ───────────────────────────────────────────────────────
@frappe.whitelist()
def painel(nome: str):
    """Os cartões de número e os gráficos de um Dashboard do ERPNext, calculados aqui."""
    _guarda()
    if not frappe.db.exists("Dashboard", nome):
        frappe.throw(_("Painel desconhecido."), frappe.DoesNotExistError)
    from orbit import empresas as _E
    if nome in getattr(_E, "PAINEIS_CONTAB", ()) and not _E.contabilidade_ligada():
        frappe.throw(_("A contabilidade está desligada nesta empresa (Definições › Empresas)."), frappe.PermissionError)
    d = frappe.get_doc("Dashboard", nome)
    from frappe.desk.doctype.number_card.number_card import get_result
    from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as dados_grafico
    cartoes, graficos = [], []
    for linha in d.cards or []:
        if not linha.card or not frappe.db.exists("Number Card", linha.card):
            continue
        card = frappe.get_doc("Number Card", linha.card)
        try:
            if card.type == "Document Type":
                if not frappe.has_permission(card.document_type, "read"):
                    continue
                valor = get_result(card.as_dict(), card.filters_json or "[]")
                tipo = "Currency" if card.function in ("Sum", "Average") and card.aggregate_function_based_on else "Int"
                destino = card.document_type
            elif card.type == "Custom" and card.method:
                res = frappe.get_attr(card.method)(json.loads(card.filters_json or "{}")) or {}
                valor, tipo, destino = res.get("value"), res.get("fieldtype") or "Int", None
            else:
                continue
        except Exception:  # noqa: BLE001 — um cartão com problema não estraga o painel
            continue
        cartoes.append({"rotulo": _(card.label or linha.card), "valor": valor, "tipo": tipo, "doctype": destino})
    for linha in d.charts or []:
        nomeg = linha.chart
        if not nomeg or not frappe.db.exists("Dashboard Chart", nomeg):
            continue
        g = frappe.get_doc("Dashboard Chart", nomeg)
        try:
            if g.document_type and not frappe.has_permission(g.document_type, "read"):
                continue
            if g.chart_type == "Report" and g.report_name and not frappe.has_permission("Report", "read"):
                continue
            if g.chart_type == "Report":
                # os gráficos de relatório o /desk desenha-os a correr o relatório; faz-se o mesmo aqui
                from frappe.desk.query_report import run
                res = run(g.report_name, filters=json.loads(g.filters_json or "{}"), ignore_prepared_report=True) or {}
                r = (res.get("chart") or {}).get("data") or {}
            else:
                r = dados_grafico(chart_name=nomeg, refresh=1) or {}
        except Exception:  # noqa: BLE001
            continue
        ds = [{"name": _(x.get("name") or ""), "values": [flt(v) for v in (x.get("values") or [])]} for x in (r.get("datasets") or [])]
        if not r.get("labels") or not ds:
            continue
        graficos.append({"rotulo": _(g.chart_name or nomeg), "tipo": g.type, "labels": [str(x) for x in r["labels"]],
                         "series": ds[:3], "largo": (linha.width or "") == "Full", "relatorio": g.report_name if g.chart_type == "Report" else None,
                         "doctype": g.document_type})
    return {"titulo": _(d.dashboard_name or nome), "cartoes": cartoes, "graficos": graficos,
            "moeda": frappe.db.get_default("currency") or "EUR"}
