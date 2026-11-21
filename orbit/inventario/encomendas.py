"""Encomendas das lojas no inventário (21-11-2026, docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md F4).

Chamado pelo escritor das encomendas da ponte (`orbit_loja_escrever.py`, que já cria o negócio no CRM) — só
quando a loja da encomenda é um **Canal de Venda** deste tenant. Uma falha aqui nunca impede o registo no CRM.

| Loja | Orbit (ERPNext) |
|---|---|
| comprador | **Customer** (pelo NIF, depois pelo email da loja); criado se não existir |
| encomenda | **Sales Order** «<site>#<número>» (idempotente), preços SEM IVA — a fatura é do programa certificado |
| linha com stock próprio nos armazéns do canal | linha do armazém → ao submeter **reserva** o stock |
| linha sem stock próprio, com oferta de fornecedor | linha **entregue pelo fornecedor** (venda directa) → **Purchase Order em rascunho** ao fornecedor |
| portes | linha «PORTES-LOJA» (sem stock) |
| paga (processing/completed) | Sales Order **submetida** |
| em espera / pendente | Sales Order em rascunho |
| concluída | **Delivery Note** das linhas de stock próprio (baixa o stock) |
| cancelada / reembolsada / falhada | Sales Order cancelada (ou apagada se ainda era rascunho); POs em rascunho apagadas |

**As compras ficam em rascunho:** os fornecedores da Shopinox encomendam-se à mão, e na stratechna.pt as compras
automáticas são do circuito `/opt/compras` — enviar daqui duplicaria a compra. Enviar é sempre de uma pessoa.
"""
import re

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, today

from orbit.inventario.disponibilidade import _proprio

CAMPO = "orbit_referencia_loja"
PAGAS = {"processing", "completed"}
ANULADAS = {"cancelled", "refunded", "failed"}
ARTIGO_LIVRE = "ARTIGO-LOJA"
ARTIGO_PORTES = "PORTES-LOJA"


def _l(v, n=140) -> str:
    return (str(v) if v is not None else "").strip()[:n]


def garantir() -> None:
    if not frappe.db.exists("DocType", "Sales Order"):
        return   # tenant sem ERPNext
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    campo = {"fieldname": CAMPO, "fieldtype": "Data", "label": "Encomenda da loja", "read_only": 1, "no_copy": 1,
             "unique": 1, "search_index": 1, "module": "Inventario"}
    create_custom_fields({
        "Sales Order": [{**campo, "insert_after": "po_no", "in_standard_filter": 1}],
        "Customer": [{"fieldname": "orbit_email_loja", "fieldtype": "Data", "label": "Email nas lojas", "options": "Email",
                      "insert_after": "customer_name", "read_only": 1, "no_copy": 1, "search_index": 1,
                      "module": "Inventario"}],
    }, update=True)


def canal_do_site(site: str):
    site = _l(site, 200).lower().removeprefix("www.")
    for c in frappe.get_all("Canal de Venda", filters={"activo": 1}, fields=["name", "url"]):
        host = re.sub(r"^https?://(www\.)?", "", (c.url or "").lower()).split("/")[0]
        if host and host == site:
            return frappe.get_doc("Canal de Venda", c.name)
    return None


def _servico(codigo: str, nome: str) -> str:
    if not frappe.db.exists("Item", codigo):
        grupo = frappe.db.get_value("Item Group", {"is_group": 0, "name": ["in", ["Services", "Serviços"]]}, "name") \
            or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        frappe.get_doc({"doctype": "Item", "item_code": codigo, "item_name": nome, "item_group": grupo,
                        "stock_uom": frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos",
                        "is_stock_item": 0, "include_item_in_manufacturing": 0}).insert(ignore_permissions=True)
    return codigo


def _cliente(c: dict, empresa_canal: str) -> str:
    nif = re.sub(r"[^0-9A-Za-z]", "", _l(c.get("nif"), 30)).upper()
    if nif.startswith("PT") and len(nif) == 11:
        nif = nif[2:]   # regra da casa: o PT nunca se guarda
    email = _l(c.get("email"), 140).lower()
    nome = _l(c.get("empresa"), 140) or " ".join(x for x in (_l(c.get("nome")), _l(c.get("apelido"))) if x) or email
    existente = (nif and frappe.db.get_value("Customer", {"tax_id": nif}, "name")) or \
        (email and frappe.db.get_value("Customer", {"orbit_email_loja": email}, "name"))
    if existente:
        return existente
    grupo = frappe.db.get_single_value("Selling Settings", "customer_group") or \
        frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
    territorio = frappe.db.get_single_value("Selling Settings", "territory") or \
        frappe.db.get_value("Territory", {"is_group": 0}, "name")
    d = frappe.get_doc({"doctype": "Customer", "customer_name": nome or "Cliente da loja",
                        "customer_type": "Company" if _l(c.get("empresa")) else "Individual",
                        "customer_group": grupo, "territory": territorio, "tax_id": nif or None,
                        "orbit_email_loja": email or None})
    d.insert(ignore_permissions=True)
    return d.name


def _melhor_oferta(item_code: str):
    """O fornecedor por onde sai a linha: com stock fresco primeiro, depois sob encomenda; o mais barato."""
    ofertas = frappe.get_all("Oferta do Fornecedor", filters={"item_code": item_code, "activa": 1, "pode_vender": 1,
                                                             "ausente_desde": ["is", "not set"]},
                             fields=["supplier", "custo", "estado_stock", "quantidade", "quantidade_conhecida"])
    if not ofertas:
        return None
    ordem = {"Em stock": 0, "Sob encomenda": 1}
    return sorted(ofertas, key=lambda o: (ordem.get(o.estado_stock, 2), flt(o.custo) or 1e12))[0]


def _artigo(linha: dict) -> str | None:
    chave = _l(linha.get("chave"), 200)
    if chave:
        n = frappe.db.get_value("Item", {"orbit_chave_importador": chave}, "name")
        if n:
            return n
    sku = _l(linha.get("sku"), 140)
    if sku and frappe.db.exists("Item", sku):
        return sku
    return None


def _linhas(p: dict, canal, entrega) -> list:
    armazens = [a.warehouse for a in canal.armazens]
    armazem = armazens[0] if armazens else (frappe.db.get_single_value("Stock Settings", "default_warehouse") or
                                            frappe.db.get_value("Warehouse", {"is_group": 0, "company": canal.company}, "name"))
    out = []
    for a in p.get("artigos") or []:
        qtd = flt(a.get("quantidade")) or 1
        taxa = flt(a.get("total_sem_iva")) / qtd if flt(a.get("total_sem_iva")) else 0
        codigo = _artigo(a)
        if not codigo:
            out.append({"item_code": _servico(ARTIGO_LIVRE, "Artigo da loja (sem correspondência no inventário)"),
                        "description": _l(a.get("nome"), 500), "qty": qtd, "rate": taxa, "delivery_date": entrega})
            continue
        linha = {"item_code": codigo, "qty": qtd, "rate": taxa, "delivery_date": entrega, "warehouse": armazem}
        oferta = None if _proprio(codigo, armazens) >= qtd else _melhor_oferta(codigo)
        if oferta:
            linha.update({"delivered_by_supplier": 1, "supplier": oferta.supplier})
        out.append(linha)
    if flt(p.get("portes_sem_iva")) > 0:
        out.append({"item_code": _servico(ARTIGO_PORTES, "Portes da encomenda da loja"), "qty": 1,
                    "rate": flt(p.get("portes_sem_iva")), "delivery_date": entrega})
    return out


def _compras_em_rascunho(so) -> list:
    """Uma Purchase Order em rascunho por fornecedor, com as linhas entregues por ele (venda directa)."""
    feitas = []
    por_fornecedor: dict = {}
    for i in so.items:
        if cint(i.delivered_by_supplier) and i.supplier:
            por_fornecedor.setdefault(i.supplier, []).append(i)
    for fornecedor, itens in por_fornecedor.items():
        if frappe.db.exists("Purchase Order Item", {"sales_order": so.name, "docstatus": ["<", 2],
                                                     "parenttype": "Purchase Order"}) and \
                frappe.db.sql("""select 1 from `tabPurchase Order` po join `tabPurchase Order Item` pi on pi.parent=po.name
                                 where pi.sales_order=%s and po.supplier=%s and po.docstatus<2 limit 1""", (so.name, fornecedor)):
            continue
        po = frappe.new_doc("Purchase Order")
        po.update({"supplier": fornecedor, "company": so.company, "schedule_date": so.delivery_date,
                   "transaction_date": today()})
        for i in itens:
            custo = frappe.db.get_value("Oferta do Fornecedor", {"item_code": i.item_code, "supplier": fornecedor}, "custo")
            po.append("items", {"item_code": i.item_code, "qty": i.qty, "rate": flt(custo), "schedule_date": so.delivery_date,
                                "warehouse": i.warehouse, "sales_order": so.name, "sales_order_item": i.name,
                                "delivered_by_supplier": 1})
        po.flags.ignore_permissions = True
        po.insert()   # rascunho: quem envia ao fornecedor é uma pessoa
        feitas.append(po.name)
    return feitas


def _anular(nome: str) -> str:
    for po in frappe.db.sql_list("""select distinct po.name from `tabPurchase Order` po
                                    join `tabPurchase Order Item` pi on pi.parent=po.name
                                    where pi.sales_order=%s and po.docstatus=0""", nome):
        frappe.delete_doc("Purchase Order", po, ignore_permissions=True, force=True)
    so = frappe.get_doc("Sales Order", nome)
    if so.docstatus == 0:
        frappe.delete_doc("Sales Order", nome, ignore_permissions=True, force=True)
        return "apagada"
    if so.docstatus == 1:
        so.flags.ignore_permissions = True
        so.cancel()
        return "cancelada"
    return "já cancelada"


def _entregar(so) -> str | None:
    """Encomenda concluída: guia de remessa das linhas de stock próprio (as de venda directa saem do fornecedor)."""
    if not [i for i in so.items if not cint(i.delivered_by_supplier) and
            frappe.get_cached_value("Item", i.item_code, "is_stock_item") and flt(i.delivered_qty) < flt(i.qty)]:
        return None
    from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
    dn = make_delivery_note(so.name)
    dn.flags.ignore_permissions = True
    dn.insert()
    frappe.db.savepoint("orbit_guia")
    try:
        dn.submit()
        return dn.name
    except Exception:  # noqa: BLE001 — sem stock suficiente (ex.: inventário inicial por fazer) fica em rascunho
        frappe.db.rollback(save_point="orbit_guia")
        return f"{dn.name} (rascunho: {str(frappe.get_traceback())[-160:].strip()})"


def registar(p: dict) -> dict | None:
    """None quando a loja não é um canal deste tenant (nada a fazer)."""
    canal = canal_do_site(p.get("site") or "")
    if not canal:
        return None
    garantir()
    ref = _l(p.get("referencia"), 200)
    estado = _l(p.get("estado"), 30)
    nome = frappe.db.get_value("Sales Order", {CAMPO: ref}, "name")
    if estado in ANULADAS:
        return {"venda": nome, "estado": _anular(nome) if nome else "nada a anular"}
    if nome:
        so = frappe.get_doc("Sales Order", nome)
    else:
        if not p.get("artigos"):
            return {"venda": None, "estado": "sem artigos"}
        data = getdate(_l(p.get("data"), 10) or today())
        entrega = add_days(max(data, getdate(today())), 7)
        so = frappe.new_doc("Sales Order")
        so.update({CAMPO: ref, "customer": _cliente(p.get("cliente") or {}, canal.company), "company": canal.company,
                   "transaction_date": data, "delivery_date": entrega, "order_type": "Sales",
                   "selling_price_list": canal.lista_precos, "ignore_pricing_rule": 1, "currency": "EUR",
                   "po_no": ref, "po_date": data,
                   "remarks": "Encomenda da loja online. Preços sem IVA — a fatura é emitida pelo programa certificado."})
        for linha in _linhas(p, canal, entrega):
            so.append("items", linha)
        so.flags.ignore_permissions = True
        so.insert()
    out = {"venda": so.name, "estado": "rascunho"}
    if estado in PAGAS and so.docstatus == 0:
        so.submit()
        out["compras"] = _compras_em_rascunho(so)
    if so.docstatus == 1:
        out["estado"] = "submetida"
        if estado == "completed":
            out["guia"] = _entregar(so)
    return out
