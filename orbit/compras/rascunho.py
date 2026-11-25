"""Faturas de compra do Docs → Orbit, F2: fornecedor, artigos, encomenda e Fatura de compra em RASCUNHO (24-11-2026).

docs/PLANO-DOCS-FATURA-COMPRA-ERP.md (D1–D12). Depois de a F1 ler e conferir uma fatura, `preparar` liga-a ao que
existe no ERP e cria uma Purchase Invoice em rascunho — nunca a submete (D1: confirma sempre uma pessoa, F3).

- Só se prepara quando as contas batem, o NIF é válido, o destinatário é a empresa, não é repetida, é em EUR e não
  é nota de crédito (essas são da F4). Senão fica «Por rever» com o motivo.
- Fornecedor: pelo NIF; senão pelo nome entre os que ainda não têm NIF (usa-o sem gravar o NIF — isso é ao
  confirmar, D6); senão cria-o com o NIF lido.
- Linhas: Áreas 03/04 do Docs → custo (artigo GASTO-DOCS na conta da etiqueta). Área 02 → artigo pela referência do
  fornecedor, pelo EAN, pela referência do importador; nome parecido só como sugestão; sem ligação → «Por ligar».
- IVA: modelo de compra pelo país/autoliquidação e modelo de artigo pela taxa de cada linha.
- Stock: só com armazém real (o do artigo ou o da marca); nunca os «(fornecedor)».
- Encomenda: liga-se à Purchase Order submetida e aberta do mesmo fornecedor com o mesmo artigo (D11).
A guarda `antes_de_submeter` recusa submeter com linhas por ligar ou só sugeridas.
"""
import json
import re
import unicodedata

import frappe
from frappe.utils import flt, getdate

from orbit.compras import preparar as F0

UE = {"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "EL", "HR", "HU", "IE", "IT", "LT",
      "LU", "LV", "MT", "NL", "PL", "RO", "SE", "SI", "SK"}
LIGACOES = ["Referência do fornecedor", "EAN", "Referência do importador", "Sugerido", "Por ligar", "Custo",
            "Escolhido", "Criado"]   # as duas últimas: escolha de quem revê (F3, rever.py)
_VIRTUAIS = ("(fornecedor)", "Goods In Transit", "Work In Progress", "Finished Goods")
_SOCIEDADE = re.compile(r"\b(lda|limitada|sa|s a|unipessoal|sl|s l|slu|gmbh|srl|spa|bv|sas|sarl|ltd|inc|e filhos)\b")


# ── campos ───────────────────────────────────────────────────────────────────
def garantir_campos(forcar=False):
    campo = frappe.get_meta("Purchase Invoice Item").get_field("orbit_ligacao")
    if not forcar and campo and "Escolhido" in (campo.options or "") \
            and frappe.get_meta("Purchase Invoice Item").has_field("orbit_categoria") \
            and frappe.get_meta("Purchase Invoice").has_field("orbit_docs_id"):
        return
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({
        "Purchase Invoice": [
            {"fieldname": "orbit_docs_id", "label": "Documento do Docs", "fieldtype": "Int", "insert_after": "bill_date",
             "read_only": 1, "no_copy": 1, "module": "Orbit"},
        ],
        "Purchase Invoice Item": [
            {"fieldname": "orbit_ligacao", "label": "Ligação", "fieldtype": "Select",
             "options": "\n" + "\n".join(LIGACOES), "insert_after": "item_name", "in_list_view": 0, "no_copy": 1,
             "module": "Orbit"},
            {"fieldname": "orbit_sugestao", "label": "Artigo sugerido", "fieldtype": "Link", "options": "Item",
             "insert_after": "orbit_ligacao", "no_copy": 1, "module": "Orbit"},
            {"fieldname": "orbit_ref_lida", "label": "Referência na fatura", "fieldtype": "Data",
             "insert_after": "orbit_sugestao", "no_copy": 1, "module": "Orbit"},
            {"fieldname": "orbit_categoria", "label": "Categoria lida", "fieldtype": "Data",
             "insert_after": "orbit_ref_lida", "no_copy": 1, "module": "Orbit"},
        ],
    }, update=True)


# ── guarda ───────────────────────────────────────────────────────────────────
def antes_de_submeter(doc, method=None):
    if not doc.get("orbit_docs_id"):
        return
    falta = [str(l.idx) for l in doc.items if l.get("orbit_ligacao") in ("Por ligar", "Sugerido")]
    if falta:
        frappe.throw(f"Linhas {', '.join(falta)} ainda por ligar a um artigo (ou marcar como custo).",
                     title="Fatura do Docs por rever")


# ── fornecedor ───────────────────────────────────────────────────────────────
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = _SOCIEDADE.sub(" ", t)
    return " ".join(t.split())


def fornecedor(f, criar=True) -> tuple[str | None, str]:
    """(Supplier, como): «NIF», «Nome» (sem NIF gravado) ou «Criado»."""
    if f.fornecedor_nif:
        s = frappe.db.get_value("Supplier", {"tax_id": f.fornecedor_nif}, "name")
        if s:
            return s, "NIF"
    alvo = _norm(f.fornecedor_nome)
    if alvo:
        for s in frappe.get_all("Supplier", filters={"tax_id": ["in", ["", None]]}, fields=["name", "supplier_name"]):
            n = _norm(s.supplier_name or s.name)
            if n and (n == alvo or (len(n) >= 4 and (alvo.startswith(n + " ") or n.startswith(alvo + " ")))):
                return s.name, "Nome"
    if not criar or not f.fornecedor_nome:
        return None, ""
    pais = frappe.db.get_value("Country", {"code": (f.fornecedor_pais or "pt").lower()}, "name") or "Portugal"
    grupo = frappe.db.get_single_value("Buying Settings", "supplier_group") or \
        ("Distributor" if frappe.db.exists("Supplier Group", "Distributor") else
         frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))
    s = frappe.get_doc({"doctype": "Supplier", "supplier_name": f.fornecedor_nome.strip()[:140],
                        "supplier_group": grupo, "supplier_type": "Company", "country": pais,
                        "tax_id": f.fornecedor_nif or None})
    s.insert(ignore_permissions=True)
    return s.name, "Criado"


# ── artigos ──────────────────────────────────────────────────────────────────
def _tem(campo):
    return frappe.get_meta("Item").has_field(campo)


def _um(sql, vals):
    r = frappe.db.sql(sql, vals)
    nomes = {x[0] for x in r}
    return next(iter(nomes)) if len(nomes) == 1 else None


def artigo(linha: dict, supplier: str | None) -> tuple[str | None, str, str | None]:
    """(item_code, ligação, sugestão)."""
    ref = (linha.get("referencia") or "").strip()
    ean = re.sub(r"\D", "", linha.get("ean") or "")
    if ref:
        if supplier:
            i = _um("select parent from `tabItem Supplier` where parenttype='Item' and supplier=%s and supplier_part_no=%s",
                    (supplier, ref))
            if i:
                return i, "Referência do fornecedor", None
        i = _um("select parent from `tabItem Supplier` where parenttype='Item' and supplier_part_no=%s", (ref,))
        if i:
            return i, "Referência do fornecedor", None
    if len(ean) >= 8:
        i = _um("select parent from `tabItem Barcode` where barcode=%s", (ean,)) or \
            (_um("select name from tabItem where orbit_ean=%s", (ean,)) if _tem("orbit_ean") else None)
        if i:
            return i, "EAN", None
    if ref:
        campos = [c for c in ("orbit_ref_feed", "orbit_mpn") if _tem(c)] + ["name"]
        i = _um("select name from tabItem where " + " or ".join(f"{c}=%s" for c in campos), tuple(ref for _ in campos))
        if i:
            return i, "Referência do importador", None
    # sugestão pelo nome (nunca automática)
    palavras = [p for p in _norm(linha.get("descricao")).split() if len(p) >= 4][:4]
    if palavras:
        cond = " and ".join(["item_name like %s"] * len(palavras))
        r = frappe.db.sql(f"select name from tabItem where disabled=0 and {cond} limit 2",
                          tuple(f"%{p}%" for p in palavras))
        if len(r) == 1:
            return None, "Sugerido", r[0][0]
    return None, "Por ligar", None


def compravel(item_code: str) -> None:
    """Um artigo que aparece numa fatura de fornecedor é comprado: o ERP recusa-o se não estiver marcado (VELA, 24-11)."""
    if item_code and not frappe.db.get_value("Item", item_code, "is_purchase_item"):
        frappe.db.set_value("Item", item_code, "is_purchase_item", 1)


def _real(w):
    return w and frappe.db.get_value("Warehouse", w, "is_group") == 0 and not any(v in w for v in _VIRTUAIS)


def armazem(item_code: str, company: str) -> str | None:
    w = frappe.db.get_value("Item Default", {"parent": item_code, "parenttype": "Item", "company": company},
                            "default_warehouse")
    if _real(w):
        return w
    marca = frappe.db.get_value("Item", item_code, "brand")
    if marca:
        w = frappe.db.get_value("Item Default", {"parent": marca, "parenttype": "Brand", "company": company},
                                "default_warehouse")
        if _real(w):
            return w
    return None


def _encomenda(supplier, item_code, qty):
    r = frappe.db.sql("""select poi.parent, poi.name, poi.qty - ifnull(poi.received_qty,0) falta
        from `tabPurchase Order Item` poi join `tabPurchase Order` po on po.name=poi.parent
        where po.docstatus=1 and po.supplier=%s and poi.item_code=%s and po.status not in ('Closed','Completed','On Hold')
          and poi.qty > ifnull(poi.received_qty,0) and ifnull(poi.billed_amt,0) < poi.amount
        order by po.transaction_date limit 1""", (supplier, item_code), as_dict=True)
    return r[0] if r else None


# ── IVA ──────────────────────────────────────────────────────────────────────
def _modelo(lido, pais, abbr, so_custos=False):
    taxas = {flt(l.get("taxa_iva")) for l in lido.get("linhas") or []}
    # UE ≠ PT: intracomunitária; fora da UE só com serviços/custos: o adquirente autoliquida (art. 6.º CIVA). Bens de
    # fora da UE pagam o IVA na alfândega — ficam no modelo pelas taxas lidas.
    if lido.get("autoliquidacao") or (pais in UE and pais != "PT") or (so_custos and pais not in UE and pais != "PT"):
        return f"Autoliquidação intracomunitária (compras) - {abbr}", True
    if taxas <= {0.0}:
        return f"Isento de IVA (compras) - {abbr}", False
    return f"IVA Portugal (compras) - {abbr}", False


def _modelo_artigo(taxa, abbr):
    t = int(round(flt(taxa)))
    nome = f"IVA compras {t} % - {abbr}" if t in (23, 13, 6) else f"IVA compras isento - {abbr}"
    return nome if frappe.db.exists("Item Tax Template", nome) else None


# ── o trabalho ───────────────────────────────────────────────────────────────
def pode(f) -> str | None:
    """None se se pode preparar; senão o motivo."""
    if f.fatura_compra and frappe.db.exists("Purchase Invoice", f.fatura_compra):
        return f"Já tem a fatura de compra {f.fatura_compra}."
    if f.estado in ("Não é compra", "Sem créditos", "Erro", "Por ler", "A ler"):
        return f"Estado «{f.estado}»."
    if f.duplicada_de:
        return f"Repetida de {f.duplicada_de}."
    if not f.contas_certas:
        return "As contas não batem."
    if not f.nif_valido:
        return "NIF do fornecedor inválido."
    if (f.moeda or "EUR") != "EUR":
        return f"Moeda {f.moeda}: só EUR por agora."
    emp = frappe.db.get_value("Company", _empresa(f), "tax_id") or ""
    if emp and f.destinatario_nif and re.sub(r"\D", "", f.destinatario_nif) != re.sub(r"\D", "", emp):
        return "O destinatário não é a empresa."
    return None


def _empresa(f=None):
    """25-11-2026: a empresa do NIF do adquirente (várias empresas, D5); sem ele, a principal."""
    from orbit.empresas import por_nif, principal
    return (por_nif(f.get("destinatario_nif")) if f is not None else None) or principal()


def _etiquetas(docs_id):
    if not docs_id or int(docs_id) <= 0:
        return []   # 25-11: fatura de compra vinda do programa certificado, não do Docs
    from orbit.compras.docs import _docs, _nome
    meta = _docs(f"/api/documents/{docs_id}/")
    return [_nome("/api/tags/", t) for t in meta.get("tags") or []]


def _anexar(pi, docs_id, dados=None):
    if (not docs_id or int(docs_id) <= 0) and not dados:
        return
    from orbit.compras.docs import _docs
    if dados is None:
        dados, _ = _docs(f"/api/documents/{docs_id}/download/", binario=True)
    ext = "pdf" if dados[:4] == b"%PDF" else "png" if dados[:4] == b"\x89PNG" else "jpg" if dados[:2] == b"\xff\xd8" else "pdf"
    frappe.get_doc({"doctype": "File", "file_name": f"fatura-docs-{docs_id}.{ext}", "attached_to_doctype": "Purchase Invoice",
                    "attached_to_name": pi.name, "is_private": 1, "content": dados}).insert(ignore_permissions=True)


def so_custos() -> bool:
    """Empresa sem artigos de stock (a Stratechna): todas as linhas são gastos (D5, F4)."""
    return not frappe.db.exists("Item", {"is_stock_item": 1, "disabled": 0})


def conta_da_categoria(company, categoria) -> str | None:
    if categoria and categoria in F0.CONTAS:
        c = f"{categoria} - {F0._abbr(company)}"
        return c if frappe.db.exists("Account", c) else None
    return None


def conta_gasto(company, etiquetas, categoria=None) -> str:
    """Etiqueta específica do Docs > categoria lida pela IA > Área do Docs > «Outras despesas» > gasto por omissão."""
    return F0.conta_para_etiquetas(company, [e for e in etiquetas or [] if not e[:2].isdigit()]) or \
        conta_da_categoria(company, categoria) or F0.conta_para_etiquetas(company, etiquetas) or \
        conta_da_categoria(company, "Outras despesas") or \
        frappe.db.get_value("Company", company, "default_expense_account")   # (no SNC é o CMVMC — só em último caso)


def _original(supplier, numero):
    """A fatura de compra que a nota de crédito corrige (submetida, do mesmo fornecedor)."""
    if not (supplier and numero):
        return None
    alvo = re.sub(r"\s+", "", numero).lower()
    for p in frappe.get_all("Purchase Invoice", filters={"supplier": supplier, "docstatus": 1, "is_return": 0},
                            fields=["name", "bill_no", "update_stock"], order_by="posting_date desc", limit=500):
        if re.sub(r"\s+", "", p.bill_no or "").lower() == alvo:
            return p
    return None


def conta_pagamento(company) -> str | None:
    return frappe.db.get_value("Company", company, "default_cash_account") or \
        frappe.db.get_value("Company", company, "default_bank_account")


PAGAS = ("Fatura-recibo", "Fatura simplificada")


def criar(f, etiquetas=None, dados=None, ignorar=False) -> dict:
    """Cria a fatura de compra em rascunho para o registo «Fatura do Docs» `f`. `ignorar` só em ensaio."""
    motivo = pode(f)
    if motivo and not (ignorar and not f.fatura_compra):
        return {"ok": False, "motivo": motivo}
    garantir_campos()
    company = _empresa(f)
    abbr = F0._abbr(company)
    lido = json.loads(f.resposta or "{}")
    etiquetas = etiquetas if etiquetas is not None else _etiquetas(f.docs_id)
    tem_02 = any(e.startswith("02 ") for e in etiquetas)
    custo = (not tem_02 and any(e[:3] in ("03 ", "04 ") for e in etiquetas)) or so_custos()
    devolucao = f.tipo_documento == "Nota de crédito"
    supplier, como = fornecedor(f)
    if not supplier:
        return {"ok": False, "motivo": "Sem fornecedor (nem nome nem NIF lidos)."}
    linhas_lidas = lido.get("linhas") or []
    # sem Área de mercadoria, a categoria lida pela IA decide: tudo gasto → custos (D5)
    tudo_gasto = custo or (not tem_02 and linhas_lidas and all(
        (l.get("categoria") or "Mercadoria") != "Mercadoria" for l in linhas_lidas))
    modelo, autoliq = _modelo(lido, f.fornecedor_pais or "PT", abbr, so_custos=tudo_gasto)
    original = _original(supplier, f.fatura_original) if devolucao else None
    notas, itens, todas_stock = [], [], True
    for l in linhas_lidas:
        qty = flt(l.get("quantidade")) or 1
        total = flt(l.get("total_sem_iva"))
        rate = total / qty if total else flt(l.get("preco_unitario")) * (1 - flt(l.get("desconto_percentagem")) / 100)
        desc = (l.get("descricao") or l.get("referencia") or "Linha da fatura").strip()
        ref = (l.get("referencia") or "").strip()[:140]
        cat = l.get("categoria") or ""
        if custo or (not tem_02 and cat and cat != "Mercadoria" and cat in F0.CONTAS):
            item, lig, sug = None, "Custo", None
        else:
            item, lig, sug = artigo(l, supplier)
            compravel(item)
        linha = {"item_code": item or F0.ARTIGO_GASTO, "item_name": desc[:140], "description": desc,
                 "qty": -qty if devolucao else qty,
                 "rate": rate, "orbit_ligacao": lig, "orbit_sugestao": sug, "orbit_ref_lida": ref,
                 "orbit_categoria": cat[:140] or None,
                 "item_tax_template": _modelo_artigo(23 if autoliq else l.get("taxa_iva"), abbr)}
        if not item:
            linha["expense_account"] = conta_gasto(company, etiquetas, cat)
            linha["uom"] = frappe.db.get_value("Item", F0.ARTIGO_GASTO, "stock_uom")
        elif frappe.db.get_value("Item", item, "is_stock_item"):
            w = armazem(item, company)
            if w:
                linha["warehouse"] = w
            else:
                todas_stock = False
                notas.append(f"{item}: sem armazém real — a entrada em stock fica para quem confirmar.")
            po = None if devolucao else _encomenda(supplier, item, qty)
            if po:
                linha.update(purchase_order=po.parent, po_detail=po.name)
            elif not devolucao:
                rasc = frappe.db.sql("""select distinct po.name from `tabPurchase Order Item` poi join `tabPurchase Order` po
                    on po.name=poi.parent where po.docstatus=0 and po.supplier=%s and poi.item_code=%s""", (supplier, item))
                if rasc:
                    notas.append(f"{item}: há encomenda em rascunho ({', '.join(r[0] for r in rasc)}) — submeta-a para ligar.")
        itens.append(linha)
    if flt(lido.get("portes")):
        portes = f"Portes de compras - {abbr}"
        taxa = max((flt(l.get("taxa_iva")) for l in lido.get("linhas") or []), default=23)
        itens.append({"item_code": F0.ARTIGO_GASTO, "item_name": "Portes", "description": "Portes",
                      "qty": -1 if devolucao else 1, "rate": flt(lido.get("portes")), "orbit_ligacao": "Custo",
                      "uom": frappe.db.get_value("Item", F0.ARTIGO_GASTO, "stock_uom"),
                      "expense_account": portes if frappe.db.exists("Account", portes) else conta_gasto(company, etiquetas),
                      "item_tax_template": _modelo_artigo(23 if autoliq else taxa, abbr)})
    stock = any(i.get("warehouse") for i in itens) and todas_stock
    devolve = None
    if devolucao:
        # D12: devolução ligada à original quando os artigos de stock são dela; mexe no stock só se a original mexeu
        codigos = {i["item_code"] for i in itens if i["item_code"] != F0.ARTIGO_GASTO}
        if original:
            da_original = set(frappe.get_all("Purchase Invoice Item", filters={"parent": original.name},
                                             pluck="item_code"))
            if codigos <= da_original:
                devolve = original.name
            else:
                notas.append(f"A fatura {original.name} não tem todos estes artigos — devolução sem ligação a ela.")
        elif f.fatura_original:
            notas.append(f"A fatura corrigida ({f.fatura_original}) não está no ERP — devolução sem ligação a ela.")
        else:
            notas.append("A nota de crédito não diz que fatura corrige.")
        stock = bool(stock and devolve and original.update_stock)
    data = getdate(f.data_fatura) if f.data_fatura else None
    pi = frappe.get_doc({
        "doctype": "Purchase Invoice", "company": company, "supplier": supplier, "currency": "EUR",
        "bill_no": f.numero, "bill_date": data, "orbit_docs_id": f.docs_id,
        "set_posting_time": 1 if data else 0, "posting_date": data or getdate(),
        "update_stock": 1 if stock else 0,
        "taxes_and_charges": modelo if frappe.db.exists("Purchase Taxes and Charges Template", modelo) else None,
        "items": [{k: v for k, v in i.items() if v is not None} if stock else
                  {k: v for k, v in i.items() if v is not None and k != "warehouse"} for i in itens],
        "remarks": f"{'Nota de crédito' if devolucao else 'Fatura'} do Docs n.º {f.docs_id} ({f.fornecedor_nome}, {f.numero}).",
        "is_return": 1 if devolucao else 0, "return_against": devolve,
    })
    if not devolucao and f.vencimento and data and getdate(f.vencimento) >= data:
        pi.due_date = getdate(f.vencimento)
    if pi.taxes_and_charges:
        from erpnext.controllers.accounts_controller import get_taxes_and_charges
        pi.set("taxes", get_taxes_and_charges("Purchase Taxes and Charges Template", pi.taxes_and_charges))
    pi.flags.ignore_permissions = True
    pi.insert()
    if f.tipo_documento in PAGAS and not devolucao:
        conta = conta_pagamento(company)
        if conta:   # fatura-recibo / simplificada: já vem paga
            pi.is_paid, pi.cash_bank_account = 1, conta
            pi.paid_amount, pi.base_paid_amount = pi.grand_total, pi.base_grand_total
            pi.save()
        else:
            notas.append("Fatura já paga, mas a empresa não tem conta de caixa/banco por omissão — fica em aberto.")
    dif = abs(flt(pi.grand_total)) - flt(f.total)
    if abs(dif) > 0.05:
        notas.append(f"O ERP calcula {pi.grand_total:.2f} € e a fatura diz {flt(f.total):.2f} € (diferença {dif:+.2f}).")
    if como == "Nome":
        notas.append(f"Fornecedor «{supplier}» escolhido pelo nome; o NIF {f.fornecedor_nif} grava-se ao confirmar.")
    elif como == "Criado":
        notas.append(f"Fornecedor «{supplier}» criado com o NIF {f.fornecedor_nif}.")
    try:
        _anexar(pi, f.docs_id, dados)
    except Exception as e:  # noqa: BLE001
        notas.append(f"PDF não anexado: {str(e)[:120]}")
    ligadas = sum(1 for i in itens if i["orbit_ligacao"] not in ("Por ligar", "Sugerido"))
    return {"ok": True, "fatura_compra": pi.name, "fornecedor": supplier, "como": como, "ligadas": ligadas,
            "devolve": devolve,
            "total_linhas": len(itens), "notas": notas, "total_erp": flt(pi.grand_total)}


def para_registo(f, etiquetas=None, dados=None, ignorar=False):
    """Prepara e grava o resultado no registo (sem commit)."""
    try:
        r = criar(f, etiquetas, dados, ignorar)
    except Exception as e:  # noqa: BLE001
        frappe.db.rollback()
        frappe.log_error(f"Fatura do Docs {f.docs_id} (rascunho): {e}", "orbit compras F2")
        r = {"ok": False, "motivo": f"Erro ao preparar: {str(e)[:300]}"}
    if r.get("ok"):
        f.fatura_compra = r["fatura_compra"]
        f.fornecedor = r["fornecedor"]
        f.devolve = r.get("devolve")
        f.linhas_ligadas, f.linhas_total = r["ligadas"], r["total_linhas"]
        f.estado = "Em rascunho"
        f.motivo = "\n".join([x for x in [(f.motivo or "").strip()] if x] + r["notas"])
    elif f.estado == "Lida":
        f.estado = "Por rever"
        f.motivo = ((f.motivo + "\n") if f.motivo else "") + r["motivo"]
    return r


@frappe.whitelist(methods=["POST"])
def preparar(docs_id, ensaio=0):
    """Preparar (de novo) o rascunho de uma fatura já lida — a pedido de quem trata das compras."""
    frappe.has_permission("Purchase Invoice", "create", throw=True)
    nome = frappe.db.get_value("Fatura do Docs", {"docs_id": int(docs_id)})
    if not nome:
        frappe.throw("Este documento ainda não foi lido.")
    f = frappe.get_doc("Fatura do Docs", nome)
    r = para_registo(f, ignorar=bool(int(ensaio or 0)) and "System Manager" in frappe.get_roles())
    f.save(ignore_permissions=True)
    frappe.db.commit()
    return r
