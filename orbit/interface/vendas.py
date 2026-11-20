"""Propostas e faturas na ficha do cliente (A6 do plano da interface única, 20-11-2026).

Duas origens, a mesma vista:
* **ERPNext do tenant** (JF e os outros clientes): Orçamentos (as propostas do Orbit, orbit/propostas), Encomendas
  e Faturas pelo Customer ligado à empresa do CRM (`CRM Organization.customer`) e pelos negócios.
  O ERP nunca emite documentos fiscais (DP8): a fatura certificada vem do Moloni pelo conector.
* **Portal da Stratechna** (só no Orbit da casa): as propostas P-AAAA-NNNN e as faturas do Moloni vivem no portal;
  pergunta-se em POST /api/v1/orbit/cliente-documentos, assinado com o segredo do tempo, pelo `crm_account_id`.
"""
from __future__ import annotations

import hashlib
import hmac
import json

import frappe
import requests
from frappe.utils import flt

ROT_Q = {"Draft": "Rascunho", "Open": "Enviada", "Replied": "Respondida", "Partially Ordered": "Encomendada em parte",
         "Ordered": "Encomendada", "Lost": "Perdida", "Cancelled": "Anulada", "Expired": "Expirada"}
ROT_SI = {"Draft": "Rascunho", "Unpaid": "Por pagar", "Overdue": "Em atraso", "Paid": "Paga", "Partly Paid": "Paga em parte",
          "Cancelled": "Anulada", "Return": "Devolução", "Credit Note Issued": "Com nota de crédito"}
ROT_P = {"rascunho": "Rascunho", "enviada": "Enviada", "vista": "Vista", "aprovada": "Aprovada", "recusada": "Recusada",
         "expirada": "Expirada", "pedido": "Pedido"}
ROT_F = {"paga": "Paga", "emitida": "Por pagar", "isenta": "Isenta", "cancelada": "Anulada", "erro": "Por emitir",
         "retida_fiscal": "Retida"}


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _portal(contas: list) -> dict | None:
    from orbit.portal import _destino
    url, seg = _destino()
    if not url or not contas:
        return None
    alvo = url.rsplit("/api/", 1)[0] + "/api/v1/orbit/cliente-documentos"
    import os
    # o nome verdadeiro da pasta do site (orbit.stratechna.com é um atalho para stratechna.orbit.stratechna.com)
    site = os.path.basename(os.path.realpath(frappe.get_site_path()))
    corpo = json.dumps({"site": site, "contas": contas}).encode()
    ass = hmac.new(seg.encode(), corpo, hashlib.sha256).hexdigest()
    try:
        r = requests.post(alvo, data=corpo, timeout=15, headers={"Content-Type": "application/json", "X-Orbit-Assinatura": ass})
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    return r.json()


@frappe.whitelist()
def do_registo(doctype: str, name: str):
    _guarda()
    from orbit.interface.api import _relacionados
    frappe.get_doc(doctype, name).check_permission("read")
    rel, _e = _relacionados(doctype, name)
    orgs = list(rel["CRM Organization"])
    clientes = {c for c in (frappe.db.get_value("CRM Organization", o, "customer") for o in orgs) if c}
    contas = sorted({c for c in (frappe.db.get_value("CRM Organization", o, "crm_account_id") for o in orgs) if c})
    propostas, faturas, em_divida, origem = [], [], 0.0, []

    # ERPNext
    partes = list(clientes) + list(rel["CRM Deal"])
    if partes and frappe.has_permission("Quotation", "read"):
        for q in frappe.get_list("Quotation", filters={"party_name": ["in", partes], "docstatus": ["<", 2]},
                                 fields=["name", "status", "grand_total", "currency", "transaction_date", "valid_till", "orbit_marca"],
                                 order_by="transaction_date desc", limit=20):
            propostas.append({"ref": q.name, "estado": ROT_Q.get(q.status, q.status), "valor": flt(q.grand_total),
                              "data": str(q.transaction_date), "url": f"/app/quotation/{q.name}", "origem": "orbit"})
    if clientes and frappe.has_permission("Sales Invoice", "read"):
        for si in frappe.get_list("Sales Invoice", filters={"customer": ["in", list(clientes)], "docstatus": ["<", 2]},
                                  fields=["name", "status", "grand_total", "outstanding_amount", "posting_date", "due_date",
                                          "orbit_numero_certificado"], order_by="posting_date desc", limit=30):
            faturas.append({"ref": si.orbit_numero_certificado or si.name, "estado": ROT_SI.get(si.status, si.status),
                            "valor": flt(si.grand_total), "data": str(si.posting_date), "vence": str(si.due_date or ""),
                            "url": f"/app/sales-invoice/{si.name}", "origem": "orbit",
                            "aberto": si.status in ("Unpaid", "Overdue", "Partly Paid")})
            if si.docstatus == 1:
                em_divida += flt(si.outstanding_amount)
    if propostas or faturas:
        origem.append("orbit")

    # Portal (só no Orbit da casa)
    pt = _portal(contas)
    if pt:
        origem.append("portal")
        base = "https://portal.stratechna.com"
        for p in pt.get("propostas", []):
            valor = flt(p.get("valor_unico_final")) + flt(p.get("valor_mensal_final"))
            propostas.append({"ref": p["referencia"], "estado": ROT_P.get(p["estado"], p["estado"]),
                              "valor": valor, "mensal": flt(p.get("valor_mensal_final")), "unico": flt(p.get("valor_unico_final")),
                              "data": (p.get("enviada_at") or p.get("created_at") or "")[:10],
                              "url": f"{base}/admin/propostas", "origem": "portal"})
        for f in pt.get("faturas", []):
            faturas.append({"ref": f.get("moloni_document_num") or f"#{f['id']}", "estado": ROT_F.get(f["estado"], f["estado"]),
                            "valor": flt(f.get("valor_total")), "data": f.get("data_fatura") or "", "vence": f.get("data_vencimento") or "",
                            "url": f"{base}/admin/faturacao", "origem": "portal",
                            "aberto": f["estado"] in ("emitida", "erro", "retida_fiscal") and not f.get("paga_at"),
                            "periodo": f"{f.get('periodo_inicio') or ''} a {f.get('periodo_fim') or ''}" if f.get("periodo_inicio") else ""})
        em_divida += flt(pt.get("em_divida"))
    propostas.sort(key=lambda x: x["data"] or "", reverse=True)
    faturas.sort(key=lambda x: x["data"] or "", reverse=True)
    nova = None
    if frappe.has_permission("Quotation", "create") and clientes:
        nova = f"/app/quotation/new?quotation_to=Customer&party_name={sorted(clientes)[0]}"
    elif pt is not None:
        nova = "https://portal.stratechna.com/admin/propostas"
    return {"propostas": propostas[:15], "faturas": faturas[:20], "em_divida": round(em_divida, 2), "origem": origem,
            "nova_proposta": nova, "tem_cliente": bool(clientes or contas)}
