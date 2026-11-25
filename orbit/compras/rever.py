"""Faturas de compra do Docs → Orbit, F3: rever, confirmar, aprender e devolver ao Docs (24-11-2026).

docs/PLANO-DOCS-FATURA-COMPRA-ERP.md §5 (D1–D12). É o ecrã «Faturas de compra» da app Operações (/orbit?app=operacoes
#/compras). A F2 (rascunho.py) deixa a fatura de compra em RASCUNHO; aqui uma pessoa:

- liga cada linha por ligar/sugerida: escolhe um artigo, usa a sugestão, cria um artigo novo ou marca «é um custo»;
- **Confirmar** — submete a fatura de compra (stock ou custo, IVA, fornecedor), grava o NIF lido no fornecedor que
  ainda não o tinha (D6), aprende a referência do fornecedor ↔ artigo (`Item Supplier`, a próxima liga sozinha) e
  devolve ao Docs o «Processo» (n.º da fatura de compra), o «Valor total», o «Vencimento», a etiqueta «Por pagar»
  (só nas faturas a crédito) e uma nota;
- **Devolver ao Docs** — apaga o rascunho, deixa uma nota no Docs com o motivo e o registo «Devolvida»; quando o
  documento mudar no Docs volta a ler-se sozinho (docs.processar);
- **Não é uma compra** — apaga o rascunho e fecha o registo, com nota no Docs.
Nunca se submete nada sem esta confirmação (D1).
"""
import json
import re
from urllib.parse import quote

import frappe
from frappe.utils import cint, flt, getdate

from orbit.compras import preparar as F0
from orbit.compras import rascunho as R

ABERTOS = ("Em rascunho", "Por rever")
OUTROS = ("Devolvida", "Não é compra", "Sem créditos", "Erro", "Por ler", "A ler", "Lida")
PENDENTES = ("Por ligar", "Sugerido")


# ── Docs (escrita) ───────────────────────────────────────────────────────────
def _docs_pedir(metodo: str, caminho: str, corpo=None):
    import requests
    base = (frappe.conf.get("orbit_docs_url") or "").rstrip("/")
    token = frappe.conf.get("orbit_docs_token")
    if not base or not token:
        raise RuntimeError("Docs não ligado a este Orbit.")
    r = requests.request(metodo, f"{base}{caminho}", json=corpo, timeout=60,
                         headers={"Authorization": f"Token {token}", "Accept": "application/json"})
    r.raise_for_status()
    return r.json() if r.content else {}


def _eur(v):
    return f"{flt(v):,.2f} €".replace(",", " ").replace(".", ",")


def _docs_nota(docs_id, texto):
    if not docs_id or int(docs_id) <= 0:
        return True   # 25-11: veio do programa certificado
    try:
        _docs_pedir("POST", f"/api/documents/{int(docs_id)}/notes/", {"note": texto[:2000]})
        return True
    except Exception as e:  # noqa: BLE001
        frappe.log_error(f"Docs {docs_id}: nota não gravada: {e}", "orbit compras F3")
        return False


def _por_nome(caminho, nome):
    r = _docs_pedir("GET", f"{caminho}?page_size=100&name__iexact={quote(nome)}")
    return next((x["id"] for x in r.get("results") or [] if x.get("name") == nome), None)


def devolver_docs(f, pi) -> list:
    if not f.docs_id or int(f.docs_id) <= 0:
        return []   # 25-11: veio do programa certificado — nada a devolver ao Docs
    """Processo, Valor total, Vencimento, «Por pagar» e uma nota no documento do Docs. Devolve o que ficou por fazer."""
    falhas = []
    meta = _docs_pedir("GET", f"/api/documents/{int(f.docs_id)}/")
    ids = {}
    for nome in ("Processo", "Valor total", "Vencimento"):
        ids[nome] = _por_nome("/api/custom_fields/", nome)
        if not ids[nome]:
            falhas.append(f"o Docs não tem o campo «{nome}»")
    valores = {c["field"]: c.get("value") for c in meta.get("custom_fields") or []}
    if ids["Processo"]:
        valores[ids["Processo"]] = pi.name
    if ids["Valor total"]:
        valores[ids["Valor total"]] = f"EUR{flt(pi.grand_total):.2f}"
    if ids["Vencimento"] and pi.due_date:
        valores[ids["Vencimento"]] = str(getdate(pi.due_date))
    etiquetas = set(meta.get("tags") or [])
    por_pagar, pago = _por_nome("/api/tags/", "Por pagar"), _por_nome("/api/tags/", "Pago")
    if pi.get("is_paid") or (f.tipo_documento or "Fatura") in R.PAGAS:   # fatura-recibo / simplificada: já paga
        if pago:
            etiquetas.add(pago)
            etiquetas.discard(por_pagar)
    elif (f.tipo_documento or "Fatura") == "Fatura" and not pi.get("is_return"):
        if por_pagar and pago not in etiquetas:
            etiquetas.add(por_pagar)
    _docs_pedir("PATCH", f"/api/documents/{int(f.docs_id)}/", {
        "custom_fields": [{"field": k, "value": v} for k, v in valores.items()], "tags": sorted(etiquetas)})
    quem = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    como = "nota de crédito " + pi.name + (f", devolução da {pi.return_against}" if pi.get("return_against") else "") \
        if pi.get("is_return") else pi.name
    if not _docs_nota(f.docs_id, f"Lançada no ERP do Orbit como {como} ({_eur(pi.grand_total)}), "
                                 f"confirmada por {quem}."):
        falhas.append("a nota no Docs")
    return falhas


# ── leitura ──────────────────────────────────────────────────────────────────
def _ver():
    frappe.has_permission("Fatura do Docs", "read", throw=True)


def _mexer():
    frappe.has_permission("Fatura do Docs", "write", throw=True)
    frappe.has_permission("Purchase Invoice", "write", throw=True)


def contar() -> int:
    if not frappe.db.exists("DocType", "Fatura do Docs") or not frappe.has_permission("Fatura do Docs", "read"):
        return 0
    return frappe.db.count("Fatura do Docs", {"estado": ["in", ABERTOS]})


@frappe.whitelist()
def lista(filtro="abertas"):
    _ver()
    estados = {"abertas": ABERTOS, "confirmadas": ("Confirmada",), "outras": OUTROS}
    linhas = frappe.get_all("Fatura do Docs", filters={"estado": ["in", estados.get(filtro, ABERTOS)]},
                            fields=["name", "docs_id", "estado", "tipo_documento", "fornecedor_nome", "fornecedor",
                                    "numero", "data_fatura", "vencimento", "total", "linhas_ligadas", "linhas_total",
                                    "fatura_compra", "motivo", "modified"],
                            order_by="modified desc", limit=300)
    contagens = {k: frappe.db.count("Fatura do Docs", {"estado": ["in", v]}) for k, v in estados.items()}
    return {"linhas": linhas, "contagens": contagens}


def _abrir(nome):
    f = frappe.get_doc("Fatura do Docs", nome)
    pi = frappe.get_doc("Purchase Invoice", f.fatura_compra) \
        if f.fatura_compra and frappe.db.exists("Purchase Invoice", f.fatura_compra) else None
    return f, pi


def _impedimento_forcar(f, pi):
    if pi:
        return "Já tem fatura de compra."
    if f.estado not in ABERTOS:
        return f"Estado «{f.estado}»."
    if f.duplicada_de:
        return f"É repetida de {f.duplicada_de}."
    if (f.moeda or "EUR") != "EUR":
        return f"Moeda {f.moeda}: só EUR."
    if not (f.fornecedor_nome or f.fornecedor_nif):
        return "Sem fornecedor lido."
    return None


@frappe.whitelist()
def detalhe(nome):
    _ver()
    f, pi = _abrir(nome)
    reg = {k: f.get(k) for k in ("name", "docs_id", "estado", "motivo", "tipo_documento", "fornecedor_nome",
                                 "fornecedor_nif", "fornecedor_pais", "fornecedor", "numero", "data_fatura",
                                 "vencimento", "atcud", "moeda", "total_sem_iva", "total_iva", "total", "contas_certas",
                                 "nif_valido", "duplicada_de", "fatura_compra", "area", "docs_actualizado",
                                 "fatura_original", "devolve")}
    fatura, linhas = None, []
    if pi:
        fatura = {k: pi.get(k) for k in ("name", "docstatus", "supplier", "supplier_name", "posting_date", "due_date",
                                         "bill_no", "net_total", "total_taxes_and_charges", "grand_total",
                                         "update_stock", "taxes_and_charges", "is_return", "return_against",
                                         "is_paid", "cash_bank_account")}
        fatura["supplier_nif"] = frappe.db.get_value("Supplier", pi.supplier, "tax_id") or ""
        stock = set(frappe.get_all("Item", filters={"name": ["in", [l.item_code for l in pi.items]], "is_stock_item": 1},
                                   pluck="name")) if pi.items else set()
        for l in pi.items:
            sug = frappe.db.get_value("Item", l.orbit_sugestao, "item_name") if l.orbit_sugestao else None
            linhas.append({
                "name": l.name, "idx": l.idx, "ligacao": l.orbit_ligacao or "", "ref": l.orbit_ref_lida or "",
                "item_code": "" if l.item_code == F0.ARTIGO_GASTO else l.item_code,
                "item_name": l.item_name, "description": re.sub(r"<[^>]+>", "", l.description or "")[:300],
                "qty": l.qty, "uom": l.uom, "rate": l.rate, "amount": l.amount, "warehouse": l.warehouse or "",
                "expense_account": l.expense_account or "", "purchase_order": l.purchase_order or "",
                "sugestao": l.orbit_sugestao or "", "sugestao_nome": sug or "", "stock": l.item_code in stock,
                "iva": l.item_tax_template or "", "categoria": l.get("orbit_categoria") or ""})
    impedimento = _impedimento_forcar(f, pi)
    return {"registo": reg, "fatura": fatura, "linhas": linhas,
            "lidas": json.loads(f.linhas or "[]") if not pi else [],
            "pode_forcar": None if impedimento else True, "impedimento": impedimento,
            "pode_confirmar": bool(pi and pi.docstatus == 0 and not any(l["ligacao"] in PENDENTES for l in linhas)),
            "pode_submeter": bool(pi and frappe.has_permission("Purchase Invoice", "submit", doc=pi))}


@frappe.whitelist()
def pdf(nome):
    """O documento original do Docs, para ver ao lado das linhas (inline)."""
    _ver()
    from orbit.compras.docs import _docs
    docs_id = int(frappe.db.get_value("Fatura do Docs", nome, "docs_id"))
    if docs_id < 0:   # 25-11: veio do programa certificado — sem PDF no Docs
        frappe.local.response.update({"type": "raw", "filename": "moloni.html", "content_type": "text/html",
                                      "filecontent": f"<p style='font-family:sans-serif'>Fatura de compra lançada no programa certificado (Moloni, documento {-docs_id}). O original está no Moloni.</p>"})
        return
    try:
        meta = _docs(f"/api/documents/{docs_id}/")
        mime = (meta.get("mime_type") or "").lower()
        caminho = f"/api/documents/{docs_id}/download/" + \
            ("?original=true" if mime == "application/pdf" or mime.startswith("image/") else "")
        dados, tipo = _docs(caminho, binario=True)
    except Exception as e:  # noqa: BLE001 — um aviso legível no lugar do documento, nunca a página de erro
        from html import escape
        dados = ("<!doctype html><meta charset=utf-8><body style=\"font:14px system-ui;color:#555;padding:24px\">"
                 f"<b>O documento n.º {docs_id} não se pôde abrir no Docs.</b><br><small>{escape(str(e)[:200])}</small>"
                 ).encode()
        tipo = "text/html"
    if dados[:4] == b"%PDF":
        tipo, ext = "application/pdf", "pdf"
    elif tipo == "text/html":
        ext = "html"
    else:
        ext = (tipo or "/bin").split("/")[-1]
    frappe.local.response.update({"type": "raw", "filename": f"fatura-docs-{docs_id}.{ext}", "filecontent": dados,
                                  "content_type": tipo or "application/octet-stream", "display_content_as": "inline"})


# ── linhas ───────────────────────────────────────────────────────────────────
def _rascunho(nome):
    f, pi = _abrir(nome)
    if not pi:
        frappe.throw("Esta fatura não tem fatura de compra em rascunho.")
    if pi.docstatus != 0:
        frappe.throw(f"A fatura de compra {pi.name} já não está em rascunho.")
    return f, pi


def _conta_gasto(item_code, company):
    return frappe.db.get_value("Item Default", {"parent": item_code, "parenttype": "Item", "company": company},
                               "expense_account") or frappe.db.get_value("Company", company, "default_expense_account")


def _limpar(l):
    for k in ("warehouse", "purchase_order", "po_detail", "orbit_sugestao", "expense_account"):
        l.set(k, None)


def _ligar(l, item_code, pi, como):
    it = frappe.db.get_value("Item", item_code, ["name", "item_name", "stock_uom", "is_stock_item", "disabled"],
                             as_dict=True)
    if not it:
        frappe.throw(f"O artigo «{item_code}» não existe.")
    if it.disabled:
        frappe.throw(f"O artigo «{item_code}» está desactivado.")
    R.compravel(it.name)
    _limpar(l)
    l.item_code, l.item_name = it.name, it.item_name[:140]
    l.uom = l.stock_uom = it.stock_uom
    l.conversion_factor = 1
    l.orbit_ligacao = como
    if it.is_stock_item and not pi.is_return:
        po = R._encomenda(pi.supplier, it.name, l.qty)
        if po:
            l.purchase_order, l.po_detail = po.parent, po.name
    else:
        l.expense_account = _conta_gasto(it.name, pi.company)


def _custo(l, f, pi):
    _limpar(l)
    etiquetas = []
    try:
        etiquetas = R._etiquetas(f.docs_id)
    except Exception:  # noqa: BLE001
        pass
    l.item_code = F0.ARTIGO_GASTO
    l.item_name = (l.description and re.sub(r"<[^>]+>", "", l.description)[:140]) or l.item_name
    l.uom = l.stock_uom = frappe.db.get_value("Item", F0.ARTIGO_GASTO, "stock_uom")
    l.conversion_factor = 1
    l.orbit_ligacao = "Custo"
    l.expense_account = R.conta_gasto(pi.company, etiquetas, l.get("orbit_categoria"))


def _codigo_livre(base):
    base = re.sub(r"\s+", "-", (base or "").strip())[:120] or "ART"
    codigo, n = base, 1
    while frappe.db.exists("Item", codigo):
        n += 1
        codigo = f"{base}-{n}"
    return codigo


def _criar_artigo(novo, l, pi):
    frappe.has_permission("Item", "create", throw=True)
    nome = (novo.get("nome") or l.item_name or "").strip()[:140]
    if not nome:
        frappe.throw("Falta o nome do artigo.")
    grupo = novo.get("grupo") or frappe.db.get_single_value("Stock Settings", "item_group")
    if not grupo or not frappe.db.exists("Item Group", grupo):
        grupo = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
    uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or \
        next((u for u in ("Unidade", "Unit", "Nos") if frappe.db.exists("UOM", u)), None)
    item = frappe.get_doc({"doctype": "Item", "item_name": nome, "description": l.description or nome,
                           "item_group": grupo, "stock_uom": uom, "is_stock_item": cint(novo.get("stock", 1)),
                           "is_purchase_item": 1, "brand": novo.get("marca") or None})
    if frappe.db.get_default("item_naming_by") != "Naming Series":
        item.item_code = _codigo_livre(novo.get("codigo") or l.orbit_ref_lida or nome)
    if item.is_stock_item:   # o armazém real das outras linhas da fatura (senão a fatura inteira fica sem entrada em stock)
        w = next((x for x in (R.armazem(o.item_code, pi.company) for o in pi.items
                              if o.name != l.name and o.item_code != F0.ARTIGO_GASTO) if x), None)
        if w:
            item.append("item_defaults", {"company": pi.company, "default_warehouse": w})
    if l.orbit_ref_lida:
        item.append("supplier_items", {"supplier": pi.supplier, "supplier_part_no": l.orbit_ref_lida[:140]})
    item.insert()
    return item.name


def _gravar(f, pi):
    """Armazém real em todas as linhas de stock → actualiza stock; senão nenhuma (como na F2). Mantém os preços lidos."""
    precos = {l.name: (l.qty, l.rate) for l in pi.items}
    stock = [l for l in pi.items if l.item_code != F0.ARTIGO_GASTO
             and frappe.db.get_value("Item", l.item_code, "is_stock_item")]
    armazens = {l.name: R.armazem(l.item_code, pi.company) for l in stock}
    pode_stock = True
    if pi.is_return:   # devolução: só mexe no stock se a original mexeu e todos os artigos são dela (D12)
        if pi.return_against and not {l.item_code for l in stock} <= set(frappe.get_all(
                "Purchase Invoice Item", filters={"parent": pi.return_against}, pluck="item_code")):
            pi.return_against = None
        pode_stock = bool(pi.return_against and frappe.db.get_value("Purchase Invoice", pi.return_against, "update_stock"))
        f.devolve = pi.return_against
    pi.update_stock = 1 if pode_stock and stock and all(armazens.values()) else 0
    for l in pi.items:
        l.warehouse = armazens.get(l.name) if pi.update_stock else None
    pi.flags.ignore_permissions = True
    pi.save()
    mudou = [l for l in pi.items if l.name in precos and (flt(l.qty), flt(l.rate)) != tuple(map(flt, precos[l.name]))]
    if mudou:   # uma regra de preço do ERP não pode mudar o que a fatura diz
        for l in mudou:
            l.qty, l.rate = precos[l.name]
        pi.save()
    if pi.is_paid and flt(pi.paid_amount) != flt(pi.grand_total):
        pi.paid_amount, pi.base_paid_amount = pi.grand_total, pi.base_grand_total
        pi.save()
    f.linhas_ligadas = sum(1 for l in pi.items if l.orbit_ligacao not in PENDENTES)
    f.linhas_total = len(pi.items)
    f.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def linha(nome, linha, acao, item_code=None, novo=None):
    """acao: «artigo» (item_code), «sugestao», «criar» (novo = {nome, stock, marca, codigo}) ou «custo»."""
    _mexer()
    f, pi = _rascunho(nome)
    l = next((x for x in pi.items if x.name == linha), None)
    if not l:
        frappe.throw("Linha não encontrada.")
    if acao == "custo":
        _custo(l, f, pi)
    elif acao == "sugestao":
        if not l.orbit_sugestao:
            frappe.throw("Esta linha não tem sugestão.")
        _ligar(l, l.orbit_sugestao, pi, "Escolhido")
    elif acao == "artigo":
        _ligar(l, item_code, pi, "Escolhido")
    elif acao == "criar":
        novo = json.loads(novo) if isinstance(novo, str) else (novo or {})
        _ligar(l, _criar_artigo(novo, l, pi), pi, "Criado")
    else:
        frappe.throw("Acção desconhecida.")
    _gravar(f, pi)
    frappe.db.commit()
    return detalhe(nome)


# ── decisões ─────────────────────────────────────────────────────────────────
@frappe.whitelist(methods=["POST"])
def confirmar(nome):
    _mexer()
    f, pi = _rascunho(nome)
    frappe.has_permission("Purchase Invoice", "submit", doc=pi, throw=True)
    falta = [str(l.idx) for l in pi.items if l.orbit_ligacao in PENDENTES]
    if falta:
        frappe.throw(f"Ligue primeiro as linhas {', '.join(falta)} (artigo, artigo novo ou custo).")
    notas = []
    # D6: o NIF lido completa a ficha do fornecedor que ainda não o tinha
    if f.fornecedor_nif and not frappe.db.get_value("Supplier", pi.supplier, "tax_id"):
        outro = frappe.db.get_value("Supplier", {"tax_id": f.fornecedor_nif, "name": ["!=", pi.supplier]}, "name")
        if outro:
            notas.append(f"NIF {f.fornecedor_nif} não gravado em «{pi.supplier}»: já é de «{outro}».")
        else:
            frappe.db.set_value("Supplier", pi.supplier, "tax_id", f.fornecedor_nif)
            notas.append(f"NIF {f.fornecedor_nif} gravado no fornecedor «{pi.supplier}».")
    # a referência do fornecedor ↔ artigo: a próxima fatura liga sozinha
    aprendidas = 0
    for l in pi.items:
        if l.item_code != F0.ARTIGO_GASTO and l.orbit_ref_lida:
            antes = frappe.db.get_value("Item Supplier", {"parent": l.item_code, "parenttype": "Item",
                                                          "supplier": pi.supplier}, "supplier_part_no")
            F0.ligar_oferta(l.item_code, pi.supplier, l.orbit_ref_lida)
            if not antes:
                aprendidas += 1
    if aprendidas:
        notas.append(f"{aprendidas} referência(s) do fornecedor aprendida(s).")
    _gravar(f, pi)
    pi.reload()
    pi.flags.ignore_permissions = True
    pi.submit()
    f.reload()
    f.estado = "Confirmada"
    try:
        falhas = devolver_docs(f, pi)
        f.docs_actualizado = 0 if any("campo" in x for x in falhas) else 1
        if falhas:
            notas.append("Docs: faltou " + ", ".join(falhas) + ".")
    except Exception as e:  # noqa: BLE001
        f.docs_actualizado = 0
        notas.append(f"Docs por actualizar: {str(e)[:160]}")
        frappe.log_error(f"Fatura do Docs {f.docs_id}: devolver ao Docs: {e}", "orbit compras F3")
    f.motivo = "\n".join(x for x in [(f.motivo or "").strip(), *notas] if x)
    f.save(ignore_permissions=True)
    frappe.db.commit()
    return detalhe(nome)


@frappe.whitelist(methods=["POST"])
def repetir_docs(nome):
    """Voltar a escrever no Docs (quando falhou ao confirmar)."""
    _mexer()
    f, pi = _abrir(nome)
    if not pi or pi.docstatus != 1:
        frappe.throw("Só depois de confirmada.")
    falhas = devolver_docs(f, pi)
    f.docs_actualizado = 0 if any("campo" in x for x in falhas) else 1
    f.save(ignore_permissions=True)
    frappe.db.commit()
    return detalhe(nome)


def _fechar(nome, estado, motivo, prefixo):
    _mexer()
    f, pi = _abrir(nome)
    if pi and pi.docstatus != 0:
        frappe.throw(f"A fatura de compra {pi.name} já foi confirmada.")
    if f.estado == "Confirmada":
        frappe.throw("Já confirmada.")
    motivo = (motivo or "").strip()
    if pi:
        frappe.delete_doc("Purchase Invoice", pi.name, ignore_permissions=True, force=True)
    quem = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    nota = f"{prefixo} por {quem}" + (f": {motivo}" if motivo else ".")
    f.reload()
    f.fatura_compra = None
    f.linhas_ligadas = f.linhas_total = 0
    f.estado = estado
    f.motivo = "\n".join(x for x in [nota, (f.motivo or "").strip()] if x)
    f.save(ignore_permissions=True)
    frappe.db.commit()
    _docs_nota(f.docs_id, nota)
    return detalhe(nome)


@frappe.whitelist(methods=["POST"])
def devolver(nome, motivo=""):
    if not (motivo or "").strip():
        frappe.throw("Diga o que está mal, para quem trata o Docs.")
    return _fechar(nome, "Devolvida", motivo, "Devolvida ao Docs pelo ERP do Orbit")


@frappe.whitelist(methods=["POST"])
def nao_compra(nome, motivo=""):
    return _fechar(nome, "Não é compra", motivo, "Marcada no ERP do Orbit como «não é uma compra»")


@frappe.whitelist(methods=["POST"])
def preparar_mesmo_assim(nome):
    """Rascunho para uma fatura «Por rever» (contas, NIF ou destinatário) — quem revê corrige no rascunho."""
    _mexer()
    frappe.has_permission("Purchase Invoice", "create", throw=True)
    f, pi = _abrir(nome)
    impedimento = _impedimento_forcar(f, pi)
    if impedimento:
        frappe.throw(impedimento)
    r = R.para_registo(f, ignorar=True)
    f.save(ignore_permissions=True)
    frappe.db.commit()
    if not r.get("ok"):
        frappe.throw(r.get("motivo") or "Não foi possível preparar.")
    return detalhe(nome)
