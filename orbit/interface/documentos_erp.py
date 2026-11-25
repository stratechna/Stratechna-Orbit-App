# Botões dos documentos do ERPNext na interface nova (/orbit) — lote 5 do plano das opções dos originais (25-11-2026)
#
# docs/PLANO-ORBIT-OPCOES-DOS-ORIGINAIS.md §3, lote 5: «Obter artigos de», os botões de estado das encomendas e guias
# (Fechar, Em espera, Reabrir, Parar), «Atualizar artigos» numa encomenda submetida, e os fluxos de trabalho
# (estado + botões de aprovação). As funções são as do próprio ERPNext/Frappe que o ecrã antigo chama nos scripts
# dos formulários; as permissões são as de quem está a usar.
import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from orbit.interface.api import _guarda

# destino ← [(origem, método mapeador que aceita target_doc, campo da parte)]
OBTER = {
    "Sales Invoice": [("Sales Order", "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice", "customer"),
                      ("Delivery Note", "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice", "customer"),
                      ("Quotation", "erpnext.selling.doctype.quotation.quotation.make_sales_invoice", "party_name")],
    "Delivery Note": [("Sales Order", "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note", "customer"),
                      ("Sales Invoice", "erpnext.accounts.doctype.sales_invoice.sales_invoice.make_delivery_note", "customer")],
    "Sales Order": [("Quotation", "erpnext.selling.doctype.quotation.quotation.make_sales_order", "party_name")],
    "Purchase Invoice": [("Purchase Order", "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice", "supplier"),
                         ("Purchase Receipt", "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice", "supplier")],
    "Purchase Receipt": [("Purchase Order", "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt", "supplier")],
    "Purchase Order": [("Material Request", "erpnext.stock.doctype.material_request.material_request.make_purchase_order", None),
                       ("Supplier Quotation", "erpnext.buying.doctype.supplier_quotation.supplier_quotation.make_purchase_order", "supplier")],
    "Supplier Quotation": [("Material Request", "erpnext.stock.doctype.material_request.material_request.make_supplier_quotation", None)],
    "Material Request": [("Sales Order", "erpnext.selling.doctype.sales_order.sales_order.make_material_request", "customer")],
    "Stock Entry": [("Material Request", "erpnext.stock.doctype.material_request.material_request.make_stock_entry", None)],
}
PARTE_DESTINO = {"Sales Invoice": "customer", "Delivery Note": "customer", "Sales Order": "customer",
                 "Purchase Invoice": "supplier", "Purchase Receipt": "supplier", "Purchase Order": "supplier",
                 "Supplier Quotation": "supplier"}
# estados que se podem pôr num documento submetido, e a função do ERPNext que o faz
ESTADOS = {
    "Sales Order": ("erpnext.selling.doctype.sales_order.sales_order.update_status", "status_name",
                    {"Closed": "Fechar", "On Hold": "Pôr em espera", "": "Reabrir"}),
    "Purchase Order": ("erpnext.buying.doctype.purchase_order.purchase_order.update_status", "status_name",
                       {"Closed": "Fechar", "On Hold": "Pôr em espera", "": "Reabrir"}),
    "Delivery Note": ("erpnext.stock.doctype.delivery_note.delivery_note.update_delivery_note_status", "docname_status",
                      {"Closed": "Fechar", "": "Reabrir"}),
    "Purchase Receipt": ("erpnext.stock.doctype.purchase_receipt.purchase_receipt.update_purchase_receipt_status", "docname_status",
                         {"Closed": "Fechar", "": "Reabrir"}),
    "Material Request": ("erpnext.stock.doctype.material_request.material_request.update_status", "name_status",
                         {"Stopped": "Parar", "Submitted": "Retomar"}),
}


@frappe.whitelist()
def botoes(doctype: str, name: str = None):
    """O que o ecrã do documento oferece além de gravar/submeter: obter artigos, estados, atualizar artigos, fluxo."""
    _guarda()
    out = {"obter": [], "estados": [], "atualizar_artigos": False, "fluxo": None}
    for origem, _m, _p in OBTER.get(doctype, []):
        if frappe.has_permission(origem, "read"):
            out["obter"].append({"doctype": origem, "rotulo": _(origem)})
    if not name or not frappe.db.exists(doctype, name):
        return out
    d = frappe.get_doc(doctype, name)
    d.check_permission("read")
    pode = frappe.has_permission(doctype, "write", name) or frappe.has_permission(doctype, "submit", name)
    if doctype in ESTADOS and cint(d.docstatus) == 1 and pode:
        st = d.get("status") or ""
        parado = st in ("Closed", "On Hold", "Stopped")
        for valor, rot in ESTADOS[doctype][2].items():
            if valor in ("", "Submitted"):          # reabrir / retomar: só quando está fechado, em espera ou parado
                if parado:
                    out["estados"].append({"valor": valor, "rotulo": _("Retomar") if st == "On Hold" else _(rot)})
            elif not parado and st not in ("Completed", "Cancelled"):
                out["estados"].append({"valor": valor, "rotulo": _(rot)})
    if doctype in ("Sales Order", "Purchase Order") and cint(d.docstatus) == 1 and d.get("status") not in ("Closed", "Completed", "On Hold") and pode:
        out["atualizar_artigos"] = True
    # fluxo de trabalho (Workflow activo para o tipo)
    from frappe.model.workflow import get_workflow_name
    wf = get_workflow_name(doctype)
    if wf:
        from frappe.model.workflow import get_transitions
        campo = frappe.db.get_value("Workflow", wf, "workflow_state_field") or "workflow_state"
        try:
            trans = get_transitions(d)
        except Exception:  # noqa: BLE001
            trans = []
        out["fluxo"] = {"estado": d.get(campo), "acoes": [{"acao": t.action, "para": t.next_state} for t in trans]}
    return out


@frappe.whitelist()
def candidatos(doctype: str, origem: str, parte: str = None, q: str = ""):
    """Documentos de onde se podem trazer artigos: submetidos, da mesma parte, ainda por faturar/entregar."""
    _guarda()
    linha = next((x for x in OBTER.get(doctype, []) if x[0] == origem), None)
    if not linha or not frappe.has_permission(origem, "read"):
        frappe.throw(_("Não se obtêm artigos de {0}.").format(_(origem)))
    f = {"docstatus": 1}
    m = frappe.get_meta(origem)
    if parte and linha[2] and m.has_field(linha[2]):
        f[linha[2]] = parte
    if m.has_field("status"):
        f["status"] = ["not in", ["Closed", "Completed", "Cancelled", "Stopped", "On Hold", "Lost", "Expired"]]
    if doctype == "Sales Invoice" and m.has_field("per_billed"):
        f["per_billed"] = ["<", 99.99]
    if doctype == "Delivery Note" and m.has_field("per_delivered"):
        f["per_delivered"] = ["<", 99.99]
    if doctype in ("Purchase Receipt",) and m.has_field("per_received"):
        f["per_received"] = ["<", 99.99]
    campos = ["name", "modified"] + [c for c in ("grand_total", "transaction_date", "posting_date", "schedule_date", "status", linha[2]) if c and m.has_field(c)]
    ou = [["name", "like", f"%{q}%"]] + ([[linha[2], "like", f"%{q}%"]] if linha[2] else []) if q else None
    return [{"name": r.name, "parte": r.get(linha[2]) if linha[2] else "", "data": str(r.get("transaction_date") or r.get("posting_date") or r.get("schedule_date") or ""),
             "total": flt(r.get("grand_total")), "estado": r.get("status") or ""}
            for r in frappe.get_list(origem, filters=f, or_filters=ou, fields=list(dict.fromkeys(campos)), order_by="modified desc", limit=30)]


@frappe.whitelist(methods=["POST"])
def obter(doctype: str, dados: str, origem: str, nomes: str):
    """Junta ao documento (por gravar) os artigos dos documentos escolhidos, pelo mapeador do ERPNext."""
    _guarda()
    linha = next((x for x in OBTER.get(doctype, []) if x[0] == origem), None)
    if not linha:
        frappe.throw(_("Não se obtêm artigos de {0}.").format(_(origem)))
    alvo = frappe.get_doc(json.loads(dados))
    if alvo.doctype != doctype or cint(alvo.get("docstatus")) != 0:
        frappe.throw(_("Só num documento em rascunho."))
    f = frappe.get_attr(linha[1])
    # o ERPNext espera o documento de destino em JSON (como o «Get Items From» do ecrã antigo)
    atual = alvo.as_dict()
    for n in json.loads(nomes or "[]")[:20]:
        frappe.get_doc(origem, n).check_permission("read")
        r = f(n, target_doc=frappe.as_json(atual))
        atual = r.as_dict() if hasattr(r, "as_dict") else r
    # sem linhas vazias que o ecrã tenha deixado (artigo por escolher)
    atual["items"] = [i for i in atual.get("items") or [] if i.get("item_code")]
    return {"doc": atual}


@frappe.whitelist(methods=["POST"])
def mudar_estado(doctype: str, name: str, estado: str = ""):
    _guarda()
    if doctype not in ESTADOS:
        frappe.throw(_("Este documento não tem estes estados."))
    d = frappe.get_doc(doctype, name)
    if not (frappe.has_permission(doctype, "write", name) or frappe.has_permission(doctype, "submit", name)):
        frappe.throw(_("Sem permissão."), frappe.PermissionError)
    metodo, assinatura, validos = ESTADOS[doctype]
    if estado not in validos:
        frappe.throw(_("Estado inválido."))
    f = frappe.get_attr(metodo)
    if assinatura == "status_name":
        f(estado or "Draft", name)          # «Reabrir»/«Retomar» = Draft (é o que o ecrã antigo manda)
    elif assinatura == "docname_status":
        f(name, estado or "Submitted")
    else:
        f(name, estado)
    return {"ok": 1, "status": frappe.db.get_value(doctype, name, "status")}


@frappe.whitelist(methods=["POST"])
def atualizar_artigos(doctype: str, name: str, linhas: str):
    """«Atualizar artigos» de uma encomenda submetida (quantidade, preço, data), pelo ERPNext."""
    _guarda()
    if doctype not in ("Sales Order", "Purchase Order"):
        frappe.throw(_("Só em encomendas."))
    frappe.get_doc(doctype, name).check_permission("write")
    from erpnext.controllers.accounts_controller import update_child_qty_rate
    itens = []
    for ln in json.loads(linhas or "[]"):
        x = {"docname": ln.get("name"), "item_code": ln.get("item_code"), "qty": flt(ln.get("qty")), "rate": flt(ln.get("rate")),
             "conversion_factor": flt(ln.get("conversion_factor")) or 1, "uom": ln.get("uom")}
        if ln.get("data"):
            x["delivery_date" if doctype == "Sales Order" else "schedule_date"] = ln["data"]
        itens.append(x)
    update_child_qty_rate(doctype, json.dumps(itens), name)
    return {"ok": 1}


@frappe.whitelist(methods=["POST"])
def aplicar_fluxo(doctype: str, name: str, acao: str):
    _guarda()
    d = frappe.get_doc(doctype, name)
    d.check_permission("read")
    from frappe.model.workflow import apply_workflow
    r = apply_workflow(d, acao)
    return {"ok": 1, "estado": r.get(frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1}, "workflow_state_field") or "workflow_state")}
