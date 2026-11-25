"""Sincronização bidireccional com o programa certificado (Moloni): inventário, compras e fornecedores.

25-11-2026 — docs/PLANO-SINCRONIZACAO-MOLONI-STOCK-COMPRAS.md, D1–D7 aceites (as recomendações):
* opção por Ligação Faturação, desligada por omissão: «Sincronizar inventário» e «Sincronizar compras e fornecedores»;
* o Orbit manda no stock (D1); a 1.ª sincronização compara e só aplica com o relatório visto (D2);
* documentos emitidos no programa entram no Orbit como emitidos, marcados `orbit_do_programa` (D3), e o C1 nunca os
  reenvia; compras feitas no programa entram por rever (D4); de 15 em 15 min + «Sincronizar agora» (D5);
* a fatura de compra actualiza o preço de custo dos dois lados (D6).

Tudo o que se sincroniza fica em «Correspondencia Programa» (id no programa ↔ documento no Orbit, de onde nasceu):
é o que trava duplicados e ciclos. Nos movimentos que o Orbit manda, as notas levam «orbit:<documento>».
"""
from __future__ import annotations

import hashlib
import json

import frappe
from frappe.utils import add_days, flt, getdate, now_datetime, nowdate

from orbit.faturacao.base import ErroFaturacao, Linha
from orbit.faturacao.ligacao import DT, adaptador_de

CP = "Correspondencia Programa"
FLAG = {"fieldname": "orbit_do_programa", "fieldtype": "Check", "label": "Veio do programa certificado", "read_only": 1,
        "no_copy": 1, "allow_on_submit": 1}
DOCTYPES_FLAG = ("Stock Entry", "Sales Invoice", "Delivery Note", "Purchase Order", "Purchase Invoice", "Supplier")
STOCK_DOCS = ("Stock Entry", "Stock Reconciliation", "Purchase Receipt")


def garantir():
    if not frappe.db.exists("DocType", "Stock Entry"):
        return
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        for dt in DOCTYPES_FLAG:
            if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": FLAG["fieldname"]}):
                create_custom_field(dt, {**FLAG, "insert_after": "amended_from" if dt != "Supplier" else "tax_id",
                                         "module": "Orbit"})
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.faturacao.sincronizacao.garantir")


# ── correspondências ───────────────────────────────────────────────────────────────────────────────────────────
def _corr(lig, tipo, id_externo=None, nome_orbit=None):
    f = {"ligacao": lig, "tipo": tipo}
    if id_externo:
        f["id_externo"] = str(id_externo)
    if nome_orbit:
        f["nome_orbit"] = nome_orbit
    return frappe.db.get_value(CP, f, ["name", "id_externo", "nome_orbit", "assinatura"], as_dict=True)


def _registar(lig, tipo, doctype_orbit, nome_orbit, id_externo, origem, assinatura="", nota=""):
    ja = _corr(lig, tipo, id_externo=id_externo) if id_externo else _corr(lig, tipo, nome_orbit=nome_orbit)
    dados = {"doctype_orbit": doctype_orbit, "nome_orbit": nome_orbit, "id_externo": str(id_externo or ""),
             "origem": origem, "assinatura": assinatura, "sincronizado_em": now_datetime(), "nota": (nota or "")[:500]}
    if ja:
        frappe.db.set_value(CP, ja.name, dados, update_modified=False)
    else:
        frappe.get_doc({"doctype": CP, "ligacao": lig, "tipo": tipo, **dados}).insert(ignore_permissions=True)


def _assinatura(*v):
    return hashlib.sha1(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _ligacoes(campo):
    if not frappe.db.table_exists(DT) or not frappe.get_meta(DT).has_field(campo):
        return []
    return [frappe.get_doc(DT, n) for n in frappe.get_all(DT, filters={"activa": 1, campo: 1}, pluck="name")]


def _da_empresa(company, campo):
    return next((l for l in _ligacoes(campo) if l.company == company), None)


def _armazem_externo(lig, armazem):
    return next((r.id_externo for r in lig.get("armazens_programa") or [] if r.armazem == armazem), None)


def _armazem_orbit(lig, id_externo):
    return next((r.armazem for r in lig.get("armazens_programa") or [] if str(r.id_externo) == str(id_externo)), None)


def _estado(lig, texto):
    lig.db_set({"sinc_estado": f"{now_datetime():%d/%m %H:%M} — {texto}"[:1000]}, update_modified=False)


def _linha_artigo(item_code, preco=0.0):
    it = frappe.db.get_value("Item", item_code, ["item_name", "is_stock_item"], as_dict=True) or {}
    return Linha(codigo=item_code, nome=it.get("item_name") or item_code, quantidade=1, preco_unitario=flt(preco),
                 taxa_iva=23, servico=not it.get("is_stock_item"))


# ══ Orbit → programa ═════════════════════════════════════════════════════════════════════════════════════════════
def ao_mexer_stock(doc, method=None):
    """on_submit / on_cancel de Stock Entry, Stock Reconciliation e Purchase Receipt."""
    if doc.get("orbit_do_programa") or not _da_empresa(doc.company, "sinc_inventario"):
        return
    frappe.enqueue("orbit.faturacao.sincronizacao.enviar_stock", queue="short", doctype=doc.doctype, name=doc.name,
                   enqueue_after_commit=True)


def enviar_stock(doctype, name):
    company = frappe.db.get_value(doctype, name, "company")
    lig = _da_empresa(company, "sinc_inventario")
    if not lig:
        return
    ad = adaptador_de(lig)
    feitos, falhas = 0, []
    for sle in frappe.get_all("Stock Ledger Entry", filters={"voucher_type": doctype, "voucher_no": name},
                              fields=["name", "item_code", "warehouse", "actual_qty", "posting_date", "is_cancelled",
                                      "valuation_rate"]):
        if _corr(lig.name, "movimento", nome_orbit=sle.name) or not flt(sle.actual_qty):
            continue
        armazem = _armazem_externo(lig, sle.warehouse)
        if not armazem:
            continue
        try:
            pid = ad.garantir_artigo(_linha_artigo(sle.item_code, sle.valuation_rate))
            mid = ad.inserir_movimento(pid, flt(sle.actual_qty), armazem, str(sle.posting_date),
                                       f"orbit:{doctype}:{name}")
            _registar(lig.name, "movimento", "Stock Ledger Entry", sle.name, mid or f"orbit-{sle.name}", "Orbit")
            feitos += 1
        except ErroFaturacao as e:
            falhas.append(f"{sle.item_code}: {e}")
    frappe.db.commit()
    if falhas:
        _estado(lig, f"{doctype} {name}: {feitos} movimentos enviados, {len(falhas)} falharam — {falhas[0]}")


def ao_gravar_fornecedor(doc, method=None):
    if doc.get("orbit_do_programa") or doc.flags.get("orbit_do_programa"):
        return
    for lig in _ligacoes("sinc_compras"):
        frappe.enqueue("orbit.faturacao.sincronizacao.enviar_fornecedor", queue="short", ligacao=lig.name,
                       fornecedor=doc.name, enqueue_after_commit=True)


def _dados_fornecedor(s):
    morada = None
    end = frappe.db.get_value("Dynamic Link", {"link_doctype": "Supplier", "link_name": s.name, "parenttype": "Address"}, "parent")
    if end:
        morada = frappe.db.get_value("Address", end, ["address_line1", "pincode", "city", "country", "email_id", "phone"], as_dict=True)
    pais = (frappe.db.get_value("Country", s.country, "code") or "pt").upper() if s.get("country") else "PT"
    return {"nome": s.supplier_name, "nif": (s.tax_id or "").replace("PT", "").strip(), "pais": pais,
            "morada": (morada or {}).get("address_line1") or "", "cp": (morada or {}).get("pincode") or "",
            "cidade": (morada or {}).get("city") or "", "email": s.get("email_id") or (morada or {}).get("email_id") or "",
            "telefone": s.get("mobile_no") or (morada or {}).get("phone") or ""}


def enviar_fornecedor(ligacao, fornecedor):
    lig = frappe.get_doc(DT, ligacao)
    s = frappe.get_doc("Supplier", fornecedor)
    d = _dados_fornecedor(s)
    ass = _assinatura(d)
    ja = _corr(lig.name, "fornecedor", nome_orbit=s.name)
    if ja and ja.assinatura == ass:
        return ja.id_externo
    sid = adaptador_de(lig).garantir_fornecedor(id_externo=ja.id_externo if ja else None, **d)
    _registar(lig.name, "fornecedor", "Supplier", s.name, sid, "Orbit" if not ja else None or "Orbit", ass)
    frappe.db.commit()
    return sid


def ao_submeter_compra(doc, method=None):
    """Purchase Order / Purchase Invoice submetidas → programa (encomenda ou fatura de compra)."""
    if doc.get("orbit_do_programa") or not _da_empresa(doc.company, "sinc_compras"):
        return
    frappe.enqueue("orbit.faturacao.sincronizacao.enviar_compra", queue="short", doctype=doc.doctype, name=doc.name,
                   enqueue_after_commit=True)


def enviar_compra(doctype, name):
    d = frappe.get_doc(doctype, name)
    lig = _da_empresa(d.company, "sinc_compras")
    if not lig:
        return
    tipo = "fatura_compra" if doctype == "Purchase Invoice" else "encomenda_compra"
    if _corr(lig.name, tipo, nome_orbit=name):
        return
    ad = adaptador_de(lig)
    try:
        sid = enviar_fornecedor(lig.name, d.supplier)
        linhas = []
        for it in d.items:
            taxa = 23.0
            try:
                from orbit.faturacao.emissao import _taxa
                taxa = _taxa(d, it)
            except Exception:  # noqa: BLE001
                pass
            l = _linha_artigo(it.item_code, it.net_rate or it.rate)
            l.nome, l.quantidade, l.taxa_iva = it.item_name, abs(flt(it.qty)), taxa
            linhas.append(l)
        did = ad.inserir_compra(tipo, sid, d.get("bill_no") or "", str(d.get("bill_date") or d.get("posting_date")
                                or d.get("transaction_date")), str(d.get("due_date") or d.get("schedule_date") or ""),
                                linhas, name, serie=lig.get(f"serie_{tipo}"), notas=(d.get("remarks") or "")[:500])
        _registar(lig.name, tipo, doctype, name, did, "Orbit")
        if tipo == "fatura_compra":   # D6: o preço de custo acompanha a compra
            for l in linhas:
                ad.actualizar_preco_custo(ad.garantir_artigo(l), l.preco_unitario)
        frappe.db.commit()
    except ErroFaturacao as e:
        _estado(lig, f"{doctype} {name}: {e}")
        frappe.db.commit()


# ══ programa → Orbit (de 15 em 15 min, D5) ═══════════════════════════════════════════════════════════════════════
def periodico():
    for lig in {l.name: l for l in _ligacoes("sinc_inventario") + _ligacoes("sinc_compras")}.values():
        try:
            sincronizar(lig.name)
        except Exception as e:  # noqa: BLE001
            frappe.db.rollback()
            frappe.log_error(title=f"Sincronização {lig.name}")
            _estado(lig, f"erro: {str(e)[:300]}")
            frappe.db.commit()


@frappe.whitelist(methods=["POST"])
def sincronizar_agora(ligacao: str):
    frappe.get_doc(DT, ligacao).check_permission("write")
    return sincronizar(ligacao)


def sincronizar(ligacao):
    lig = frappe.get_doc(DT, ligacao)
    ad = adaptador_de(lig)
    desde = str(getdate(lig.ultima_sinc)) if lig.ultima_sinc else str(lig.sinc_desde or nowdate())
    inicio = now_datetime()
    r = {"fornecedores": 0, "movimentos": 0, "vendas": 0, "compras": 0, "erros": []}
    if lig.sinc_compras:
        r["fornecedores"] = _receber_fornecedores(lig, ad, r["erros"])
    if lig.sinc_inventario:
        r["vendas"] = _receber_vendas(lig, ad, desde, r["erros"])
        r["movimentos"] = _receber_movimentos(lig, ad, desde, r["erros"])
    if lig.sinc_compras:
        r["compras"] = _receber_compras(lig, ad, desde, r["erros"])
    lig.db_set("ultima_sinc", inicio, update_modified=False)
    _estado(lig, f"{r['fornecedores']} fornecedores, {r['movimentos']} movimentos, {r['vendas']} documentos de venda, "
                 f"{r['compras']} compras" + (f"; {len(r['erros'])} erros — {r['erros'][0]}" if r["erros"] else ""))
    frappe.db.commit()
    return r


def _item(ad, product_id, referencia=None, nome=None):
    """O artigo do Orbit para um artigo do programa (pela referência); cria-o se não existir."""
    ref = referencia
    if not ref:
        p = ad._post("products/getOne", {"product_id": int(product_id)})
        p = (p[0] if isinstance(p, list) and p else p) or {}
        ref, nome = p.get("reference"), nome or p.get("name")
    ref = str(ref or f"MOLONI-{product_id}")[:140]
    if frappe.db.exists("Item", ref):
        return ref
    grupo = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
    uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
    frappe.get_doc({"doctype": "Item", "item_code": ref, "item_name": (nome or ref)[:140], "item_group": grupo,
                    "stock_uom": uom, "is_stock_item": 1, "include_item_in_manufacturing": 0}).insert(ignore_permissions=True)
    return ref


def _receber_fornecedores(lig, ad, erros):
    n = 0
    for f in ad.fornecedores():
        sid = str(f.get("supplier_id") or "")
        nif = str(f.get("vat") or "").strip()
        dados = {"nome": f.get("name"), "nif": nif}
        ass = _assinatura(dados, f.get("address"), f.get("email"))
        ja = _corr(lig.name, "fornecedor", id_externo=sid)
        if ja and ja.assinatura == ass:
            continue
        try:
            nome = (ja and ja.nome_orbit) or (frappe.db.get_value("Supplier", {"tax_id": ["in", [nif, f"PT{nif}"]]}, "name") if nif else None)
            if nome and frappe.db.exists("Supplier", nome):
                s = frappe.get_doc("Supplier", nome)
                if s.supplier_name != f.get("name"):
                    s.supplier_name = (f.get("name") or s.supplier_name)[:140]
                    s.flags.orbit_do_programa = True
                    s.save(ignore_permissions=True)
            else:
                s = frappe.get_doc({"doctype": "Supplier", "supplier_name": (f.get("name") or nif or sid)[:140],
                                    "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
                                    "tax_id": nif or None, "orbit_do_programa": 1})
                s.flags.orbit_do_programa = True
                s.insert(ignore_permissions=True)
            _registar(lig.name, "fornecedor", "Supplier", s.name, sid, "Programa" if not ja else "Orbit", ass)
            n += 1
        except Exception as e:  # noqa: BLE001
            erros.append(f"fornecedor {f.get('name')}: {str(e)[:120]}")
    return n


def _do_orbit(referencia):
    """our_reference de um documento que o Orbit mandou (nome de um documento do Orbit)."""
    ref = str(referencia or "")
    return bool(ref) and any(frappe.db.exists(dt, ref) for dt in ("Sales Invoice", "Delivery Note", "Payment Entry",
                                                                 "Purchase Invoice", "Purchase Order"))


def _cliente(ad, d):
    cid = d.get("customer_id")
    c = d.get("customer") or {}
    if not c and cid:
        c = ad._post("customers/getOne", {"customer_id": int(cid)})
        c = (c[0] if isinstance(c, list) and c else c) or {}
    nif = str(c.get("vat") or d.get("entity_vat") or "").strip()
    nome = c.get("name") or d.get("entity_name") or nif or "Consumidor final"
    if nif and nif != "999999990":
        ja = frappe.db.get_value("Customer", {"tax_id": ["in", [nif, f"PT{nif}"]]}, "name")
        if ja:
            return ja
    elif frappe.db.exists("Customer", "Consumidor final"):
        return "Consumidor final"
    cust = frappe.get_doc({"doctype": "Customer", "customer_name": nome[:140], "tax_id": nif if nif != "999999990" else None,
                           "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
                           "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name")})
    cust.insert(ignore_permissions=True)
    return cust.name


def _receber_vendas(lig, ad, desde, erros):
    """D3: documentos emitidos directamente no programa entram no Orbit como emitidos (com stock)."""
    n = 0
    armazem_omissao = next((r.armazem for r in lig.get("armazens_programa") or []), None)
    for d in ad.vendas_desde(desde):
        did = str(d.get("document_id"))
        tipo = "guia" if d["_tipo"] == "guia" else "venda"
        if _corr(lig.name, tipo, id_externo=did) or _do_orbit(d.get("our_reference")):
            continue
        try:
            full = ad.documento(did)
            cliente = _cliente(ad, full)
            doctype = "Delivery Note" if tipo == "guia" else "Sales Invoice"
            itens = []
            for p in full.get("products") or []:
                wh = _armazem_orbit(lig, p.get("warehouse_id")) or armazem_omissao
                itens.append({"item_code": _item(ad, p.get("product_id"), p.get("reference"), p.get("name")),
                              "qty": flt(p.get("qty")), "rate": flt(p.get("price")), "warehouse": wh,
                              "discount_percentage": flt(p.get("discount"))})
            if not itens:
                continue
            doc = frappe.get_doc({"doctype": doctype, "company": lig.company, "customer": cliente,
                                  "posting_date": str(full.get("date") or nowdate())[:10], "set_posting_time": 1,
                                  "items": itens, "orbit_do_programa": 1,
                                  "orbit_numero_certificado": f"{(full.get('document_set') or {}).get('name', '')}/{full.get('number', '')}".strip("/")})
            if doctype == "Sales Invoice":
                doc.update_stock = 1 if any(i["warehouse"] for i in itens) else 0
                doc.due_date = str(full.get("expiration_date") or full.get("date") or nowdate())[:10]
            doc.flags.orbit_do_programa = True
            doc.insert(ignore_permissions=True)
            doc.submit()
            _registar(lig.name, tipo, doctype, doc.name, did, "Programa")
            frappe.db.commit()
            n += 1
        except Exception as e:  # noqa: BLE001
            frappe.db.rollback()
            erros.append(f"documento {did}: {str(e)[:150]}")
    return n


def _receber_movimentos(lig, ad, desde, erros):
    """Movimentos feitos no programa fora de documentos → Stock Entry no Orbit (entrada ou saída)."""
    n = 0
    dia, hoje = getdate(desde), getdate(nowdate())
    while dia <= hoje:
        for m in ad.movimentos_stock(str(dia)):
            mid = str(m.get("product_stock_id") or m.get("id") or "")
            notas = str(m.get("notes") or "")
            if not mid or notes_orbit(notas) or m.get("document_id") or _corr(lig.name, "movimento", id_externo=mid):
                continue
            wh = _armazem_orbit(lig, m.get("warehouse_id"))
            qty = flt(m.get("qty"))
            if not wh or not qty:
                continue
            try:
                item = _item(ad, m.get("product_id"))
                se = frappe.get_doc({"doctype": "Stock Entry", "company": lig.company, "orbit_do_programa": 1,
                                     "stock_entry_type": "Material Receipt" if qty > 0 else "Material Issue",
                                     "posting_date": str(m.get("movement_date") or dia)[:10], "set_posting_time": 1,
                                     "remarks": f"Movimento do programa certificado ({notas[:100]})",
                                     "items": [{"item_code": item, "qty": abs(qty),
                                                ("t_warehouse" if qty > 0 else "s_warehouse"): wh}]})
                se.flags.orbit_do_programa = True
                se.insert(ignore_permissions=True)
                se.submit()
                _registar(lig.name, "movimento", "Stock Entry", se.name, mid, "Programa")
                frappe.db.commit()
                n += 1
            except Exception as e:  # noqa: BLE001
                frappe.db.rollback()
                erros.append(f"movimento {mid}: {str(e)[:150]}")
        dia = add_days(dia, 1)
    return n


def notes_orbit(notas: str) -> bool:
    return notas.startswith("orbit:") or " orbit:" in notas


def _receber_compras(lig, ad, desde, erros):
    """D4: faturas de compra do programa → «Faturas de compra» por rever (o mesmo circuito das do Docs);
    encomendas a fornecedor → Purchase Order em rascunho."""
    n = 0
    for tipo in ("fatura_compra", "encomenda_compra"):
        for d in ad.compras_desde(tipo, desde):
            did = str(d.get("document_id"))
            if _corr(lig.name, tipo, id_externo=did) or _do_orbit(d.get("our_reference")):
                continue
            try:
                full = ad.compra(tipo, did)
                forn = full.get("supplier") or {}
                if tipo == "fatura_compra":
                    _fatura_compra_por_rever(lig, full, forn)
                else:
                    _encomenda_compra(lig, ad, full, forn)
                n += 1
                frappe.db.commit()
            except Exception as e:  # noqa: BLE001
                frappe.db.rollback()
                erros.append(f"compra {did}: {str(e)[:150]}")
    return n


def _fatura_compra_por_rever(lig, full, forn):
    did = str(full.get("document_id"))
    linhas = [{"referencia": p.get("reference"), "descricao": p.get("name"), "quantidade": flt(p.get("qty")),
               "preco_unitario": flt(p.get("price")), "desconto_percentagem": flt(p.get("discount")),
               "taxa_iva": flt(((p.get("taxes") or [{}])[0] or {}).get("value") or 0),
               "total_sem_iva": flt(p.get("qty")) * flt(p.get("price")) * (1 - flt(p.get("discount")) / 100)}
              for p in full.get("products") or []]
    empresa_nif = frappe.db.get_value("Company", lig.company, "tax_id") or ""
    lido = {"tipo": "Fatura", "emitente": {"nome": forn.get("name"), "nif": str(forn.get("vat") or ""), "pais": "PT"},
            "destinatario": {"nif": empresa_nif}, "numero": full.get("your_reference") or f"{full.get('number')}",
            "data": str(full.get("date") or "")[:10], "vencimento": str(full.get("expiration_date") or "")[:10],
            "moeda": "EUR", "linhas": linhas, "total_sem_iva": flt(full.get("net_value")),
            "total_iva": flt(full.get("taxes_value")), "total": flt(full.get("gross_value"))}
    from orbit.compras.docs import conferir
    estado, motivos, extra = conferir(lido, empresa_nif)
    f = frappe.get_doc({"doctype": "Fatura do Docs", "docs_id": -int(did),
                        "titulo": f"Moloni — {forn.get('name') or ''} {lido['numero']}"[:140],
                        "estado": estado if estado != "Lida" else "Lida",
                        "motivo": "\n".join(["Lançada no programa certificado (Moloni)."] + motivos),
                        "tipo_documento": "Fatura", "fornecedor_nome": forn.get("name"),
                        "fornecedor_nif": extra.get("nif") or "", "fornecedor_pais": extra.get("pais") or "PT",
                        "nif_valido": 1 if extra.get("nif_valido") else 0, "destinatario_nif": extra.get("dest") or "",
                        "numero": lido["numero"], "data_fatura": lido["data"] or None, "vencimento": lido["vencimento"] or None,
                        "moeda": "EUR", "total_sem_iva": lido["total_sem_iva"], "total_iva": lido["total_iva"],
                        "total": lido["total"], "contas_certas": 1 if extra.get("contas_certas") else 0,
                        "linhas": json.dumps(linhas, ensure_ascii=False, indent=1),
                        "resposta": json.dumps(lido, ensure_ascii=False, indent=1), "lida_em": now_datetime()})
    f.insert(ignore_permissions=True)
    if f.estado in ("Lida", "Por rever"):
        from orbit.compras.rascunho import para_registo
        para_registo(f, etiquetas=[], dados=None)
        f.save(ignore_permissions=True)
    _registar(lig.name, "fatura_compra", "Fatura do Docs", f.name, did, "Programa")


def _encomenda_compra(lig, ad, full, forn):
    did = str(full.get("document_id"))
    nif = str(forn.get("vat") or "")
    fornecedor = frappe.db.get_value("Supplier", {"tax_id": ["in", [nif, f"PT{nif}"]]}, "name") if nif else None
    if not fornecedor:
        raise ErroFaturacao(f"fornecedor {forn.get('name')} ({nif}) ainda não está no Orbit")
    wh = next((r.armazem for r in lig.get("armazens_programa") or []), None)
    po = frappe.get_doc({"doctype": "Purchase Order", "company": lig.company, "supplier": fornecedor,
                         "transaction_date": str(full.get("date") or nowdate())[:10],
                         "schedule_date": str(full.get("expiration_date") or full.get("date") or nowdate())[:10],
                         "orbit_do_programa": 1, "set_warehouse": wh,
                         "items": [{"item_code": _item(ad, p.get("product_id"), p.get("reference"), p.get("name")),
                                    "qty": flt(p.get("qty")), "rate": flt(p.get("price")),
                                    "schedule_date": str(full.get("expiration_date") or full.get("date") or nowdate())[:10],
                                    "warehouse": wh} for p in full.get("products") or []]})
    po.flags.orbit_do_programa = True
    po.insert(ignore_permissions=True)   # em rascunho: nada se submete sozinho (D4)
    _registar(lig.name, "encomenda_compra", "Purchase Order", po.name, did, "Programa")


# ══ 1.ª sincronização do inventário (D2) ═════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def comparar_stock(ligacao: str):
    """Relatório: stock do Orbit vs do programa, por artigo e armazém mapeado. Nada é alterado."""
    lig = frappe.get_doc(DT, ligacao)
    lig.check_permission("read")
    ad = adaptador_de(lig)
    out = []
    for r in lig.get("armazens_programa") or []:
        for b in frappe.get_all("Bin", filters={"warehouse": r.armazem, "actual_qty": ["!=", 0]},
                                fields=["item_code", "actual_qty"], limit=2000):
            p = ad.artigo_por_referencia(b.item_code)
            no_prog = None
            if p:
                for w in p.get("warehouses") or []:
                    if str(w.get("warehouse_id")) == str(r.id_externo):
                        no_prog = flt(w.get("stock"))
                if no_prog is None and p.get("stock") is not None and len(lig.armazens_programa) == 1:
                    no_prog = flt(p.get("stock"))
            diferenca = flt(b.actual_qty) - flt(no_prog or 0)
            if abs(diferenca) > 0.0001:
                out.append({"artigo": b.item_code, "armazem": r.armazem, "orbit": flt(b.actual_qty),
                            "programa": no_prog, "acerto": round(diferenca, 4), "existe_no_programa": bool(p)})
    return {"diferencas": out, "total": len(out)}


@frappe.whitelist(methods=["POST"])
def aplicar_primeira(ligacao: str):
    """Envia para o programa os acertos do relatório (o Orbit manda no stock, D1/D2)."""
    lig = frappe.get_doc(DT, ligacao)
    lig.check_permission("write")
    ad = adaptador_de(lig)
    feitos, falhas = 0, []
    for d in comparar_stock(ligacao)["diferencas"]:
        try:
            pid = ad.garantir_artigo(_linha_artigo(d["artigo"]))
            ad.inserir_movimento(pid, d["acerto"], _armazem_externo(lig, d["armazem"]), nowdate(),
                                 "orbit:acerto-inicial")
            feitos += 1
        except ErroFaturacao as e:
            falhas.append(f"{d['artigo']}: {e}")
    if not lig.sinc_desde:
        lig.db_set("sinc_desde", nowdate(), update_modified=False)
    _estado(lig, f"1.ª sincronização: {feitos} acertos enviados" + (f", {len(falhas)} falharam — {falhas[0]}" if falhas else ""))
    frappe.db.commit()
    return {"acertos": feitos, "falhas": falhas}


@frappe.whitelist()
def armazens_programa(ligacao: str):
    lig = frappe.get_doc(DT, ligacao)
    lig.check_permission("read")
    return adaptador_de(lig).armazens()
