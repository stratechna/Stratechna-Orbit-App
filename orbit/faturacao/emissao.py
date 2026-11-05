"""A emissão no programa certificado, a partir das faturas e dos pagamentos do ERPNext (DP8, C1).

Regras (docs/PLANO-PENDENCIAS-ORBIT-PRIMEIRO.md §10.1):
- Só com uma Ligacao Faturacao ACTIVA para a empresa da fatura. Sem ela, nada muda.
- Submeter uma Sales Invoice NÃO emite nada dentro do submit: cria um Documento Certificado «Por emitir» e põe a
  emissão na fila (C-D1). Uma falha do programa externo não desfaz a fatura nem deixa documentos sem dono.
- O nome da fatura vai como referência no programa: repetir a emissão encontra o documento já criado.
- Em modo Ensaio cria-se um rascunho e apaga-se; em modo Real o documento é definitivo.
- Uma fatura já emitida não se cancela no ERPNext: corrige-se com nota de crédito (devolução) ou anula-se no
  próprio programa (a leitura de volta traz a anulação).
- Os pagamentos submetidos contra faturas emitidas dão recibos no programa (C-D2).
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import add_to_date, flt, now_datetime

from orbit.faturacao.base import Cliente, ErroFaturacao, Linha, Pedido
from orbit.faturacao.ligacao import adaptador_de, da_empresa

DC = "Documento Certificado"
MAX_TENTATIVAS = 5
FEITOS = ("Emitido", "Ensaio concluído", "Anulado")


# ── ganchos (hooks.py › doc_events) ─────────────────────────────────────────

def validar_fatura(doc, method=None):
    lig = da_empresa(doc.company)
    if not lig:
        return
    motivo = doc.get("orbit_motivo_isencao") or lig.motivo_isencao
    if not motivo:
        for it in doc.items:
            if _taxa(doc, it) == 0:
                frappe.throw(f"A linha «{it.item_name}» está sem IVA: indique o motivo de isenção (M01…M99) no "
                             f"campo «Motivo de isenção» — o programa certificado não emite sem ele.")


def ao_submeter_fatura(doc, method=None):
    lig = da_empresa(doc.company)
    if not lig:
        return
    tipo = "nota_credito" if doc.is_return else ("fatura_recibo" if doc.get("is_pos") else "fatura")
    nome = _novo_documento("Sales Invoice", doc.name, lig, tipo)
    doc.db_set("orbit_documento_certificado", nome, update_modified=False)
    frappe.enqueue("orbit.faturacao.emissao.emitir", queue="short", documento=nome, enqueue_after_commit=True)


def antes_de_cancelar_fatura(doc, method=None):
    nome = frappe.db.get_value(DC, {"documento_tipo": "Sales Invoice", "documento": doc.name,
                                     "estado": "Emitido"}, "numero")
    if nome is not None:
        frappe.throw(f"Esta fatura já foi emitida no programa certificado ({nome or 'sem número'}). Não se "
                     f"cancela no Orbit: emita uma nota de crédito (devolução) ou anule-a no programa — a anulação "
                     f"chega ao Orbit sozinha.")


def ao_submeter_pagamento(doc, method=None):
    lig = da_empresa(doc.company)
    if not lig or doc.payment_type != "Receive":
        return
    tem = any(r.reference_doctype == "Sales Invoice" and frappe.db.exists(
        DC, {"documento_tipo": "Sales Invoice", "documento": r.reference_name, "estado": "Emitido",
             "tipo": "fatura"}) for r in doc.references)
    if not tem:
        return
    nome = _novo_documento("Payment Entry", doc.name, lig, "recibo")
    doc.db_set("orbit_documento_certificado", nome, update_modified=False)
    frappe.enqueue("orbit.faturacao.emissao.emitir", queue="short", documento=nome, enqueue_after_commit=True)


# ── fila ────────────────────────────────────────────────────────────────────

def _novo_documento(doctype, nome, lig, tipo) -> str:
    ja = frappe.db.get_value(DC, {"documento_tipo": doctype, "documento": nome}, "name")
    if ja:
        return ja
    d = frappe.get_doc({"doctype": DC, "documento_tipo": doctype, "documento": nome, "company": lig.company,
                        "programa": lig.programa, "tipo": tipo, "estado": "Por emitir", "modo": lig.modo})
    d.insert(ignore_permissions=True)
    return d.name


def emitir(documento: str):
    dc = frappe.get_doc(DC, documento)
    if dc.estado in FEITOS:
        return
    lig = da_empresa(dc.company)
    if not lig:
        return
    ad = adaptador_de(lig)
    ensaio = lig.modo != "Real"
    try:
        if dc.tipo == "recibo":
            res = _emitir_recibo(dc, ad, ensaio)
        else:
            si = frappe.get_doc("Sales Invoice", dc.documento)
            pedido = pedido_da_fatura(si, lig, rascunho=ensaio)
            res = ad.emitir(pedido)
            _guardar_ids(si, pedido)
        dc.id_externo, dc.numero, dc.atcud = res.id_externo, res.numero, res.atcud
        dc.total, dc.resposta, dc.erro = res.total, json.dumps(res.bruto, default=str), ""
        dc.data = (res.bruto or {}).get("date", "")[:10] or None
        dc.modo = lig.modo
        if ensaio:
            if res.estado == "rascunho":
                ad.apagar_rascunho("recibo" if dc.tipo == "recibo" else dc.tipo, res.id_externo)
            dc.estado = "Ensaio concluído"
        else:
            dc.estado = "Anulado" if res.estado == "anulado" else "Emitido"
            try:
                dc.pdf_url = ad.obter_pdf(dc.tipo, res.id_externo)
            except ErroFaturacao:
                pass   # o PDF lê-se depois; o documento está emitido
            if dc.documento_tipo == "Sales Invoice":
                frappe.db.set_value("Sales Invoice", dc.documento, "orbit_numero_certificado", res.numero,
                                    update_modified=False)
        dc.save(ignore_permissions=True)
    except ErroFaturacao as e:
        dc.reload()
        dc.tentativas = (dc.tentativas or 0) + 1
        dc.erro = str(e)[:1000]
        dc.estado = "Erro" if (e.permanente or dc.tentativas >= MAX_TENTATIVAS) else "Por emitir"
        if e.resposta is not None:
            dc.resposta = json.dumps(e.resposta, default=str)[:20000]
        dc.save(ignore_permissions=True)
        lig.db_set("ultimo_erro", f"{now_datetime():%Y-%m-%d %H:%M} {dc.name}: {e}"[:1000], update_modified=False)
    frappe.db.commit()


def _emitir_recibo(dc, ad, ensaio):
    pe = frappe.get_doc("Payment Entry", dc.documento)
    documentos, cliente_id = [], None
    for r in pe.references:
        if r.reference_doctype != "Sales Invoice":
            continue
        f = frappe.db.get_value(DC, {"documento_tipo": "Sales Invoice", "documento": r.reference_name,
                                      "estado": "Emitido", "tipo": "fatura"}, ["id_externo"], as_dict=True)
        if f:
            documentos.append((f.id_externo, flt(r.allocated_amount)))
            cliente_id = cliente_id or _id_de("Customer", pe.party, ad.nome)
    if not documentos:
        raise ErroFaturacao("o pagamento não está ligado a nenhuma fatura emitida no programa")
    if not cliente_id:
        raise ErroFaturacao(f"o cliente {pe.party} ainda não tem ficha no programa")
    return ad.registar_pagamento(cliente_id, str(pe.posting_date), sum(v for _, v in documentos), documentos,
                                 referencia=pe.name, notas=pe.get("remarks") or "", rascunho=ensaio)


def periodico():
    """De 15 em 15 min: volta a tentar o que ficou por emitir e lê do programa as anulações."""
    if not frappe.db.table_exists("tabDocumento Certificado"):
        return
    limite = add_to_date(now_datetime(), minutes=-10)
    for nome in frappe.get_all(DC, filters={"estado": "Por emitir", "modified": ["<", limite],
                                            "tentativas": ["<", MAX_TENTATIVAS]}, pluck="name", limit=50):
        frappe.enqueue("orbit.faturacao.emissao.emitir", queue="short", documento=nome)
    for lig_nome in frappe.get_all("Ligacao Faturacao", filters={"activa": 1, "modo": "Real"}, pluck="name"):
        lig = frappe.get_doc("Ligacao Faturacao", lig_nome)
        desde = str(lig.ultima_leitura or add_to_date(now_datetime(), days=-2))[:19]
        agora = now_datetime()
        try:
            mudados = adaptador_de(lig).alterados_desde(desde)
        except ErroFaturacao as e:
            lig.db_set("ultimo_erro", f"leitura de volta: {e}"[:1000], update_modified=False)
            continue
        for r in mudados:
            nome = frappe.db.get_value(DC, {"programa": lig.programa, "id_externo": r.id_externo,
                                            "company": lig.company}, "name")
            if nome and r.estado == "anulado":
                frappe.db.set_value(DC, nome, "estado", "Anulado")
        lig.db_set("ultima_leitura", agora, update_modified=False)
    frappe.db.commit()


# ── da fatura do ERPNext para o pedido ──────────────────────────────────────

def _taxa(si, it) -> float:
    """A percentagem de IVA de uma linha: do modelo de imposto do artigo, senão dos impostos da fatura sobre o
    total líquido."""
    if it.get("item_tax_rate"):
        try:
            taxas = json.loads(it.item_tax_rate) or {}
            if taxas:
                return round(sum(flt(v) for v in taxas.values()), 2)
        except ValueError:
            pass
    return round(sum(flt(t.rate) for t in (si.get("taxes") or []) if t.charge_type == "On Net Total"), 2)


def _ids(doctype, nome) -> dict:
    try:
        return json.loads(frappe.db.get_value(doctype, nome, "orbit_fat_ids") or "{}")
    except ValueError:
        return {}


def _id_de(doctype, nome, programa):
    return _ids(doctype, nome).get(programa)


def _guardar_ids(si, pedido):
    lig_programa = frappe.db.get_value(DC, {"documento_tipo": "Sales Invoice", "documento": si.name}, "programa")
    # o adaptador deixa no pedido os ids que resolveu; guardam-se na ficha para não voltar a procurar
    for doctype, nome, idx in [("Customer", si.customer, pedido.cliente.id_externo)] + \
            [("Item", l.codigo, l.id_externo) for l in pedido.linhas]:
        if idx and lig_programa:
            ids = _ids(doctype, nome)
            if ids.get(lig_programa) != idx:
                ids[lig_programa] = idx
                frappe.db.set_value(doctype, nome, "orbit_fat_ids", json.dumps(ids), update_modified=False)


def pedido_da_fatura(si, lig, rascunho: bool) -> Pedido:
    cust = frappe.get_doc("Customer", si.customer)
    morada = frappe.get_doc("Address", si.customer_address) if si.get("customer_address") else None
    pais = "PT"
    if morada and morada.country:
        pais = (frappe.db.get_value("Country", morada.country, "code") or "pt").upper()
    cliente = Cliente(nome=si.customer_name or cust.customer_name, nif=cust.get("tax_id") or "",
                      email=si.get("contact_email") or "", pais=pais,
                      morada=(morada.address_line1 + (" " + morada.address_line2 if morada.address_line2 else ""))
                      if morada else "", cidade=morada.city if morada else "",
                      codigo_postal=morada.pincode if morada else "",
                      id_externo=_id_de("Customer", si.customer, lig.programa))
    motivo = si.get("orbit_motivo_isencao") or lig.motivo_isencao or ""
    linhas = []
    for it in si.items:
        taxa = _taxa(si, it)
        linhas.append(Linha(codigo=it.item_code, nome=it.item_name, quantidade=abs(flt(it.qty)),
                            preco_unitario=abs(flt(it.net_rate or it.rate)), taxa_iva=taxa,
                            motivo_isencao=motivo if taxa == 0 else "", resumo=(it.get("description") or "")[:200],
                            servico=not frappe.db.get_value("Item", it.item_code, "is_stock_item"),
                            id_externo=_id_de("Item", it.item_code, lig.programa)))
    tipo = "nota_credito" if si.is_return else ("fatura_recibo" if si.get("is_pos") else "fatura")
    origem, origem_valor = None, 0.0
    if tipo == "nota_credito":
        origem = frappe.db.get_value(DC, {"documento_tipo": "Sales Invoice", "documento": si.return_against,
                                           "estado": "Emitido"}, "id_externo")
        if not origem:
            raise ErroFaturacao(f"a fatura de origem {si.return_against} não está emitida no programa certificado")
        origem_valor = abs(flt(si.grand_total))
    return Pedido(tipo=tipo, referencia=si.name, data=str(si.posting_date), vencimento=str(si.due_date or si.posting_date),
                  cliente=cliente, linhas=linhas, notas=(si.get("remarks") or "")[:1000] if si.get("remarks") != "No Remarks" else "",
                  rascunho=rascunho, origem_id_externo=origem, origem_valor=origem_valor,
                  motivo=si.get("orbit_motivo_nc") or "")
