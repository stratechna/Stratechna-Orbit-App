"""Emitir fatura, guia e recibo no /orbit (25-11-2026, maquete aprovada pelo Vítor: docs/orbit-interface/emitir/).

* «Importar de…»: qualquer documento pode trazer as linhas de outro do mesmo cliente — proposta, encomenda ou guia
  para a fatura; encomenda ou fatura para a guia. Usa as funções de conversão do próprio ERPNext (as mesmas dos
  botões «Criar» e «Obter artigos de»), que já deixam de fora o que foi faturado/enviado e guardam as ligações por
  linha. A ligação que o ERPNext não guarda (proposta → fatura, guia → fatura sem encomenda…) fica em
  `orbit_origens` («Doctype|nome» por linha).
* «Documentos associados»: a cadeia nos dois sentidos — pelas ligações das linhas, por `orbit_origens` e pelos
  pagamentos.
* Recibo: um pagamento recebido que liquida uma ou várias faturas em aberto do cliente (Payment Entry).
"""
import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from orbit.interface.api import _guarda

CAMPO_ORIGENS = {"fieldname": "orbit_origens", "fieldtype": "Small Text", "label": "Documentos de origem",
                 "read_only": 1, "no_copy": 1, "hidden": 1}
DOCTYPES_ORIGENS = ("Sales Invoice", "Delivery Note", "Sales Order")

# destino → {origem: função de conversão do ERPNext}
CONVERSAO = {
    "Sales Invoice": {
        "Quotation": "erpnext.selling.doctype.quotation.quotation.make_sales_invoice",
        "Sales Order": "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice",
        "Delivery Note": "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice",
    },
    "Delivery Note": {
        "Sales Order": "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note",
        "Sales Invoice": "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note",
    },
}
ROTULO = {"Quotation": "Proposta", "Sales Order": "Encomenda", "Delivery Note": "Guia", "Sales Invoice": "Fatura",
          "Payment Entry": "Recibo"}


def garantir():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        for dt in DOCTYPES_ORIGENS:
            if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": CAMPO_ORIGENS["fieldname"]}):
                create_custom_field(dt, {**CAMPO_ORIGENS, "insert_after": "amended_from", "module": "Orbit"})
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.interface.emitir.garantir")


def _cliente_de(doctype, d):
    if doctype == "Quotation":
        if d.get("quotation_to") == "Customer":
            return d.get("party_name")
        from erpnext.selling.doctype.quotation.quotation import get_existing_customer_name   # Prospect/Lead já convertido
        return get_existing_customer_name(d.get("quotation_to"), d.get("party_name"))
    return d.get("customer")


@frappe.whitelist()
def importaveis(destino: str, cliente: str = None, q: str = None):
    """Os documentos do cliente que ainda têm alguma coisa por faturar (destino fatura) ou por enviar (guia)."""
    _guarda()
    if destino not in CONVERSAO:
        frappe.throw(_("Não há importação para este documento."))
    out = []
    for origem in CONVERSAO[destino]:
        if not frappe.has_permission(origem, "read"):
            continue
        filtros = {"docstatus": 1}
        campos = ["name", "transaction_date" if origem in ("Quotation", "Sales Order") else "posting_date",
                  "grand_total", "net_total", "status", "currency"]
        if origem == "Quotation":
            filtros["status"] = ["in", ["Open", "Replied", "Partially Ordered"]]
            campos += ["quotation_to", "party_name", "customer_name", "orbit_marca"]
            if cliente:
                filtros["party_name"] = cliente
        else:
            campos += ["customer", "customer_name"]
            if cliente:
                filtros["customer"] = cliente
            if origem == "Sales Order":
                filtros["status"] = ["not in", ["Closed", "Completed", "On Hold"]]
                if destino == "Sales Invoice":
                    filtros["per_billed"] = ["<", 100]
                else:
                    filtros["per_delivered"] = ["<", 100]
            elif origem == "Delivery Note":
                filtros["per_billed"] = ["<", 100]
                filtros["is_return"] = 0
            elif origem == "Sales Invoice":
                filtros["update_stock"] = 0
                filtros["is_return"] = 0
        if q:
            filtros["name"] = ["like", f"%{q}%"]
        for d in frappe.get_list(origem, filters=filtros, fields=campos, order_by="creation desc", limit=40):
            if origem == "Sales Invoice" and _ja_enviada(d.name):
                continue
            out.append({"doctype": origem, "tipo": ROTULO[origem], "name": d.name,
                        "data": str(d.get("transaction_date") or d.get("posting_date") or ""),
                        "total": flt(d.grand_total), "sem_iva": flt(d.net_total), "estado": d.status,
                        "cliente": d.get("customer_name") or d.get("party_name") or d.get("customer"),
                        "marca": d.get("orbit_marca")})
    out.sort(key=lambda x: x["data"], reverse=True)
    return out


def _ja_enviada(fatura):
    return bool(frappe.db.sql("""select 1 from `tabDelivery Note Item` i join `tabDelivery Note` d on d.name = i.parent
                                 where i.against_sales_invoice = %s and d.docstatus < 2 limit 1""", fatura))


@frappe.whitelist()
def linhas_de(doctype: str, name: str, destino: str):
    """As linhas que a conversão traria (já sem o faturado/enviado), para escolher na janela."""
    _guarda()
    metodo = CONVERSAO.get(destino, {}).get(doctype)
    if not metodo:
        frappe.throw(_("Não se importa {0} para {1}.").format(_(doctype), _(destino)))
    frappe.get_doc(doctype, name).check_permission("read")
    novo = frappe.get_attr(metodo)(name)
    return [{"i": i, "item_code": l.item_code, "item_name": l.item_name, "qty": flt(l.qty), "uom": l.uom,
             "rate": flt(l.rate), "amount": flt(l.amount)} for i, l in enumerate(novo.items or [])]


@frappe.whitelist(methods=["POST"])
def importar(destino: str, fontes: str, dados: str = None):
    """Junta ao documento por gravar (`dados`) as linhas escolhidas de cada fonte ([{doctype, name, linhas:[i…]}]).
    Devolve o documento como ficaria — nada é gravado."""
    _guarda()
    fontes = json.loads(fontes) if isinstance(fontes, str) else fontes
    base = json.loads(dados) if isinstance(dados, str) and dados else (dados or None)
    alvo = None
    if base:
        base["doctype"] = destino
        for t in ("items",):
            for r in base.get(t) or []:
                if str(r.get("name") or "").startswith("novo-"):
                    r.pop("name")
        alvo = frappe.get_doc(base)
    origens = set((alvo.get("orbit_origens") or "").splitlines()) if alvo is not None else set()
    try:
        for f in fontes or []:
            metodo = CONVERSAO.get(destino, {}).get(f.get("doctype"))
            if not metodo:
                frappe.throw(_("Não se importa {0} para {1}.").format(_(f.get("doctype")), _(destino)))
            frappe.get_doc(f["doctype"], f["name"]).check_permission("read")
            antes = len(alvo.items) if alvo is not None else 0
            alvo = frappe.get_attr(metodo)(f["name"], target_doc=alvo)
            escolhidas = f.get("linhas")
            if escolhidas is not None:   # só as linhas marcadas desta fonte (pela posição em que a conversão as pôs)
                novas = alvo.items[antes:]
                manter = [l for i, l in enumerate(novas) if i in set(int(x) for x in escolhidas)]
                alvo.set("items", list(alvo.items[:antes]) + manter)
            origens.add(f"{f['doctype']}|{f['name']}")
        alvo.orbit_origens = "\n".join(sorted(o for o in origens if o))
        if hasattr(alvo, "set_missing_values"):
            alvo.set_missing_values(for_validate=True)
        if hasattr(alvo, "calculate_taxes_and_totals"):
            alvo.calculate_taxes_and_totals()
    finally:
        frappe.db.rollback()
    for i, l in enumerate(alvo.items or []):
        if not l.name:
            l.name = f"novo-imp-{i}"
    return {"doc": alvo.as_dict()}


# ── documentos associados ────────────────────────────────────────────────────────────────────────────────
def _juntar(acc, doctype, name):
    if name and frappe.db.exists(doctype, name):
        acc.add((doctype, name))


def _vizinhos(doctype, name):
    acc = set()
    d = frappe.get_doc(doctype, name)
    for o in (d.get("orbit_origens") or "").splitlines():
        if "|" in o:
            _juntar(acc, *o.split("|", 1))
    if doctype == "Sales Invoice":
        for l in d.items:
            _juntar(acc, "Sales Order", l.get("sales_order"))
            _juntar(acc, "Delivery Note", l.get("delivery_note"))
        for r in frappe.get_all("Payment Entry Reference", filters={"reference_doctype": doctype, "reference_name": name,
                                                                    "docstatus": ["<", 2]}, pluck="parent"):
            _juntar(acc, "Payment Entry", r)
        for r in frappe.get_all("Delivery Note Item", filters={"against_sales_invoice": name}, pluck="parent"):
            _juntar(acc, "Delivery Note", r)
    elif doctype == "Delivery Note":
        for l in d.items:
            _juntar(acc, "Sales Order", l.get("against_sales_order"))
            _juntar(acc, "Sales Invoice", l.get("against_sales_invoice"))
        for r in frappe.get_all("Sales Invoice Item", filters={"delivery_note": name}, pluck="parent"):
            _juntar(acc, "Sales Invoice", r)
    elif doctype == "Sales Order":
        for l in d.items:
            _juntar(acc, "Quotation", l.get("prevdoc_docname"))
        for r in frappe.get_all("Sales Invoice Item", filters={"sales_order": name}, pluck="parent"):
            _juntar(acc, "Sales Invoice", r)
        for r in frappe.get_all("Delivery Note Item", filters={"against_sales_order": name}, pluck="parent"):
            _juntar(acc, "Delivery Note", r)
    elif doctype == "Quotation":
        for r in frappe.get_all("Sales Order Item", filters={"prevdoc_docname": name}, pluck="parent"):
            _juntar(acc, "Sales Order", r)
    elif doctype == "Payment Entry":
        for r in d.get("references") or []:
            _juntar(acc, r.reference_doctype, r.reference_name)
    # o que aponta para este por orbit_origens
    chave = f"{doctype}|{name}"
    for dt in DOCTYPES_ORIGENS:
        if frappe.get_meta(dt).has_field("orbit_origens"):
            for r in frappe.get_all(dt, filters={"orbit_origens": ["like", f"%{chave}%"]}, pluck="name"):
                _juntar(acc, dt, r)
    acc.discard((doctype, name))
    return acc


@frappe.whitelist()
def associados(doctype: str, name: str):
    """A cadeia inteira (proposta → encomenda → guia → fatura → recibo), nos dois sentidos, até 2 saltos."""
    _guarda()
    frappe.get_doc(doctype, name).check_permission("read")
    vistos, fila = {(doctype, name)}, [(doctype, name, 0)]
    while fila:
        dt, n, nivel = fila.pop(0)
        if nivel >= 3:
            continue
        for v in _vizinhos(dt, n):
            if v not in vistos:
                vistos.add(v)
                fila.append((v[0], v[1], nivel + 1))
    vistos.discard((doctype, name))
    ordem = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "Payment Entry"]
    out = []
    for dt, n in sorted(vistos, key=lambda x: (ordem.index(x[0]) if x[0] in ordem else 9, x[1])):
        if not frappe.has_permission(dt, "read"):
            continue
        v = frappe.db.get_value(dt, n, ["status", "docstatus"], as_dict=True) or {}
        out.append({"doctype": dt, "tipo": ROTULO.get(dt, _(dt)), "name": n, "estado": v.get("status"),
                    "docstatus": v.get("docstatus")})
    return out


# ── recibo ───────────────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def em_aberto(cliente: str):
    """As faturas do cliente com valor em dívida, a mais antiga primeiro."""
    _guarda()
    if not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw(_("Sem acesso às faturas."), frappe.PermissionError)
    hoje = nowdate()
    out = []
    for f in frappe.get_list("Sales Invoice", filters={"customer": cliente, "docstatus": 1, "outstanding_amount": [">", 0]},
                             fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount",
                                     "orbit_marca", "orbit_numero_certificado", "currency"], order_by="due_date asc", limit=100):
        out.append({"name": f.name, "numero": f.get("orbit_numero_certificado") or f.name, "data": str(f.posting_date),
                    "vencimento": str(f.due_date or ""), "vencida": bool(f.due_date and str(f.due_date) < hoje),
                    "total": flt(f.grand_total), "divida": flt(f.outstanding_amount), "marca": f.get("orbit_marca")})
    return out


@frappe.whitelist()
def contas_recebimento():
    _guarda()
    modos = frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name", order_by="name asc")
    return {"modos": modos}


@frappe.whitelist(methods=["POST"])
def gravar_recibo(cliente: str, data: str, valor: float, modo: str, referencia: str = None, faturas: str = None,
                  submeter: int = 0):
    """Payment Entry «Receber» com as faturas escolhidas ([{name, valor}]). Faturas de marcas diferentes → um recibo
    por marca (cada um sai na série da sua marca); devolve os recibos criados."""
    _guarda()
    if not frappe.has_permission("Payment Entry", "create"):
        frappe.throw(_("Sem permissão para registar recebimentos."), frappe.PermissionError)
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    faturas = json.loads(faturas) if isinstance(faturas, str) else (faturas or [])
    faturas = [f for f in faturas if flt(f.get("valor")) > 0]
    if not faturas:
        frappe.throw(_("Escolha pelo menos uma fatura."))
    grupos = {}
    for f in faturas:
        m = frappe.db.get_value("Sales Invoice", f["name"], "orbit_marca") or ""
        grupos.setdefault(m, []).append(f)
    criados = []
    resto = flt(valor) - sum(flt(f["valor"]) for f in faturas)
    for i, (marca, lista) in enumerate(grupos.items()):
        pe = get_payment_entry("Sales Invoice", lista[0]["name"])
        pe.posting_date = data or nowdate()
        pe.mode_of_payment = modo or pe.mode_of_payment
        pe.reference_no = (referencia or "")[:140] or None
        pe.reference_date = data or nowdate()
        pe.set("references", [])
        total = 0.0
        for f in lista:
            si = frappe.db.get_value("Sales Invoice", f["name"], ["grand_total", "outstanding_amount", "due_date"], as_dict=True)
            v = min(flt(f["valor"]), flt(si.outstanding_amount))
            pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": f["name"],
                                     "total_amount": si.grand_total, "outstanding_amount": si.outstanding_amount,
                                     "allocated_amount": v, "due_date": si.due_date})
            total += v
        if i == 0 and resto > 0:   # o que sobra fica como adiantamento do cliente, no primeiro recibo
            total += resto
        pe.paid_amount = pe.received_amount = round(total, 2)
        if hasattr(pe, "set_amounts"):
            pe.set_amounts()
        pe.insert()
        if int(submeter):
            pe.submit()
        criados.append({"name": pe.name, "marca": marca, "valor": round(total, 2), "docstatus": pe.docstatus})
    return {"recibos": criados}


# ── Fatura pró-forma (25-11-2026, pedido do Vítor): a fatura em rascunho gera a pró-forma (não fiscal) e, mais
# tarde, a fatura de facto — a mesma Sales Invoice, submetida, que fica associada à pró-forma. ─────────────────────
CAMPOS_PROFORMA = [
    {"fieldname": "orbit_proforma_numero", "fieldtype": "Data", "label": "Pró-forma", "read_only": 1, "no_copy": 1,
     "allow_on_submit": 1, "insert_after": "orbit_marca"},
    {"fieldname": "orbit_proforma_em", "fieldtype": "Datetime", "label": "Pró-forma emitida em", "read_only": 1,
     "no_copy": 1, "allow_on_submit": 1, "insert_after": "orbit_proforma_numero"},
    {"fieldname": "orbit_proforma_valor", "fieldtype": "Currency", "label": "Total da pró-forma", "read_only": 1,
     "no_copy": 1, "allow_on_submit": 1, "insert_after": "orbit_proforma_em"},
    {"fieldname": "orbit_proforma_id", "fieldtype": "Data", "label": "Pró-forma no programa certificado", "read_only": 1,
     "hidden": 1, "no_copy": 1, "allow_on_submit": 1, "insert_after": "orbit_proforma_valor"},
]
CAMPOS_GUIA = [
    {"fieldname": "orbit_marca", "fieldtype": "Link", "options": "Brand", "label": "Marca", "insert_after": "company",
     "in_standard_filter": 1},
    {"fieldname": "orbit_inicio_transporte", "fieldtype": "Datetime", "label": "Início do transporte",
     "insert_after": "posting_time"},
    {"fieldname": "orbit_numero_certificado", "fieldtype": "Data", "label": "N.º no programa certificado", "read_only": 1,
     "no_copy": 1, "allow_on_submit": 1, "in_list_view": 1, "insert_after": "orbit_inicio_transporte"},
    {"fieldname": "orbit_codigo_at", "fieldtype": "Data", "label": "Código AT", "read_only": 1, "no_copy": 1,
     "allow_on_submit": 1, "insert_after": "orbit_numero_certificado"},
    {"fieldname": "orbit_documento_certificado", "fieldtype": "Link", "options": "Documento Certificado",
     "label": "Documento certificado", "read_only": 1, "no_copy": 1, "allow_on_submit": 1, "insert_after": "orbit_codigo_at"},
]
FORMATO_PROFORMA = "Fatura pró-forma"
SERIE_PROFORMA = "PF-.YYYY.-.#####"


def garantir_proforma():
    if not frappe.db.exists("DocType", "Sales Invoice"):
        return
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        for c in CAMPOS_PROFORMA:
            if not frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": c["fieldname"]}):
                create_custom_field("Sales Invoice", {**c, "module": "Orbit"})
        for c in CAMPOS_GUIA:
            if not frappe.db.exists("Custom Field", {"dt": "Delivery Note", "fieldname": c["fieldname"]}):
                create_custom_field("Delivery Note", {**c, "module": "Orbit"})
        import os
        with open(os.path.join(os.path.dirname(__file__), "proforma.html"), encoding="utf-8") as f:
            html = f.read()
        dados = {"doc_type": "Sales Invoice", "module": "Orbit", "custom_format": 1, "print_format_type": "Jinja",
                 "standard": "No", "html": html, "disabled": 0}
        if frappe.db.exists("Print Format", FORMATO_PROFORMA):
            frappe.db.set_value("Print Format", FORMATO_PROFORMA, dados)
        else:
            frappe.get_doc({"doctype": "Print Format", "name": FORMATO_PROFORMA, **dados}).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.interface.emitir.garantir_proforma")


@frappe.whitelist(methods=["POST"])
def emitir_proforma(name: str):
    """Dá número de pró-forma à fatura em rascunho (série própria, não fiscal) e, com a faturação certificada
    ligada, regista-a também no programa como pró-forma. A fatura continua em rascunho."""
    _guarda()
    si = frappe.get_doc("Sales Invoice", name)
    si.check_permission("write")
    if si.docstatus != 0:
        frappe.throw(_("A pró-forma faz-se a partir da fatura em rascunho."))
    from frappe.model.naming import make_autoname
    numero = si.get("orbit_proforma_numero") or make_autoname(SERIE_PROFORMA)
    si.db_set({"orbit_proforma_numero": numero, "orbit_proforma_em": frappe.utils.now_datetime(),
               "orbit_proforma_valor": flt(si.grand_total)}, update_modified=False)
    certificado = None
    try:
        from orbit.faturacao.emissao import emitir_proforma_certificada
        certificado = emitir_proforma_certificada(si)
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001 — a pró-forma interna fica; o programa certificado tenta-se de novo
        frappe.log_error(title=f"Pró-forma {numero} no programa certificado")
        certificado = {"erro": str(e)[:300]}
    frappe.db.commit()
    return {"ok": True, "numero": numero, "certificado": certificado,
            "pdf": f"/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name={name}&format=Fatura%20pr%C3%B3-forma&no_letterhead=1"}
