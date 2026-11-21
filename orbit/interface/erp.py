"""O ERP inteiro na interface do Orbit (21-11-2026, docs/PLANO-ORBIT-INTERFACE-UNICA.md §14 — U1 e U2).

Em vez de refazer centenas de ecrãs do ERPNext, a interface lê a definição de cada tipo de documento (a mesma que
o ERPNext usa: campos, secções, separadores, tabelas, ligações, obrigatórios) e desenha uma lista e uma ficha
genéricas. O motor continua a ser o do ERPNext: tudo é lido e gravado pelo próprio Frappe (`get_list`,
`get_doc().save()`), com as permissões da pessoa — nenhuma regra, validação ou lançamento é refeito aqui.

| Função | Para quê |
|---|---|
| `modulos` | os módulos do ERP e do RH a que a pessoa tem acesso (os mesmos ícones da secretária) |
| `menu` | as entradas de um módulo (Workspace Sidebar do Frappe 16): documentos, relatórios, páginas, por secções |
| `meta` | a definição de um tipo de documento, já traduzida, com as tabelas-filhas e o que a pessoa pode fazer |
| `lista` | uma página da lista, com pesquisa e filtros simples |
| `documento` / `gravar` / `apagar` / `submeter` / `cancelar` | o registo |
| `procurar` | a pesquisa de um campo de ligação (a mesma do ERPNext: `search_link`) |
"""
import json

import frappe
from frappe import _

from orbit.interface.api import _guarda

# Títulos de secção que o ERPNext não traduz para pt.
_SECOES = {"Tools": "Ferramentas", "Setup": "Configuração", "Reports": "Relatórios", "Settings": "Definições",
           "Masters": "Dados mestre", "Transactions": "Transações", "Other Reports": "Outros relatórios",
           "Key Reports": "Relatórios principais", "Payments": "Pagamentos", "Taxes": "Impostos"}


def _tr(t: str) -> str:
    x = _(t or "")
    return _SECOES.get(x, _SECOES.get(t, x)) if x == t else x


# Tipos de campo que a ficha genérica não desenha (estrutura ou só para o desk).
_ESTRUTURA = {"Section Break", "Column Break", "Tab Break"}
_SEM_UI = {"HTML", "Button", "Fold", "Heading", "Image", "Geolocation", "Signature", "Barcode", "Icon",
           "Table MultiSelect", "Markdown Editor", "HTML Editor", "Code", "JSON", "Rating", "Duration", "Autocomplete"}
_PADRAO = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "parent", "parentfield",
           "parenttype", "doctype", "_user_tags", "_comments", "_assign", "_liked_by", "_seen"}
_PROPS = ("fieldname", "fieldtype", "options", "reqd", "read_only", "hidden", "depends_on", "mandatory_depends_on",
          "read_only_depends_on", "in_list_view", "in_standard_filter", "default", "collapsible", "bold",
          "fetch_from", "no_copy", "allow_on_submit", "precision", "length", "non_negative")


def _ler(doctype: str) -> None:
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(_("Tipo de documento desconhecido."), frappe.DoesNotExistError)
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(_("Sem acesso a {0}.").format(_(doctype)), frappe.PermissionError)


# ── U1: módulos e menus ────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def modulos():
    """Os módulos (grupo, nome, barra lateral) — a mesma escolha do contexto, mas a apontar para o /orbit."""
    _guarda()
    from orbit.interface.api import _modulos
    out = []
    for m in _modulos():
        barra = m.get("barra")
        if barra and frappe.db.exists("Workspace Sidebar", barra):
            out.append({"nome": m["nome"], "grupo": m["grupo"], "barra": barra})
    return out


@frappe.whitelist()
def menu(barra: str):
    """As entradas de um módulo, por secções. Documentos abrem na interface; o resto (relatórios, páginas,
    painéis) ainda abre o ecrã do ERPNext dentro do Orbit (U5)."""
    _guarda()
    if not frappe.db.exists("Workspace Sidebar", barra):
        frappe.throw(_("Módulo desconhecido."), frappe.DoesNotExistError)
    s = frappe.get_doc("Workspace Sidebar", barra)
    secoes, atual = [], {"titulo": "", "itens": []}
    for i in s.items:
        if i.type == "Section Break":
            if atual["itens"]:
                secoes.append(atual)
            atual = {"titulo": _tr(i.label or ""), "itens": []}
            continue
        if i.type != "Link" or not i.link_to or i.link_type in ("Workspace", "Dashboard"):
            continue
        if i.link_type == "DocType":
            if not frappe.db.exists("DocType", i.link_to) or not frappe.has_permission(i.link_to, "read"):
                continue
            atual["itens"].append({"tipo": "doc", "rotulo": _(i.label or i.link_to), "doctype": i.link_to,
                                   "single": frappe.get_meta(i.link_to).issingle, "icone": i.icon})
        elif i.link_type == "Report":
            # U5 (21-11): os relatórios abrem na interface (#/erp-rel/<nome>)
            if frappe.db.exists("Report", i.link_to) and frappe.has_permission("Report", "read"):
                atual["itens"].append({"tipo": "rel", "rotulo": _(i.label or i.link_to), "relatorio": i.link_to, "icone": i.icon})
        elif i.link_type == "Page":
            atual["itens"].append({"tipo": "desk", "rotulo": _(i.label or i.link_to), "url": "/desk/" + i.link_to, "icone": i.icon})
        elif i.link_type == "URL" and i.url:
            atual["itens"].append({"tipo": "desk", "rotulo": _(i.label or i.url), "url": i.url, "icone": i.icon})
    if atual["itens"]:
        secoes.append(atual)
    return {"titulo": _(s.title or barra), "secoes": secoes}


# ── U2: definição, lista e registo ─────────────────────────────────────────────────────────────────────
def _campos(meta) -> list:
    out = []
    for f in meta.fields:
        if f.fieldtype in _SEM_UI and f.fieldtype not in _ESTRUTURA:
            continue
        d = {k: f.get(k) for k in _PROPS if f.get(k) not in (None, "", 0) or k in ("fieldname", "fieldtype")}
        d["label"] = _(f.label) if f.label else ""
        if f.fieldtype == "Select" and f.options:
            d["opcoes"] = [{"v": o, "r": _(o) if o else ""} for o in f.options.split("\n")]
        if f.description:
            d["descricao"] = _(f.description)
        out.append(d)
    return out


@frappe.whitelist()
def meta(doctype: str):
    _guarda()
    _ler(doctype)
    m = frappe.get_meta(doctype)
    filhas = {}
    for f in m.fields:
        if f.fieldtype in ("Table",) and f.options and frappe.db.exists("DocType", f.options):
            fm = frappe.get_meta(f.options)
            filhas[f.options] = {"campos": _campos(fm)}
    pode = {p: bool(frappe.has_permission(doctype, p)) for p in ("create", "write", "delete")}
    pode.update({p: bool(m.is_submittable and frappe.has_permission(doctype, p)) for p in ("submit", "cancel")})
    return {
        "doctype": doctype, "rotulo": _(doctype), "single": m.issingle, "submetivel": m.is_submittable,
        "titulo": m.title_field or ("item_name" if doctype == "Item" else None), "imagem": m.image_field,
        "pesquisa": [c.strip() for c in (m.search_fields or "").split(",") if c.strip()],
        "nomeacao": m.autoname or "", "campos": _campos(m), "filhas": filhas, "pode": pode,
        "transacao": doctype in TRANSACOES,
        "lista": [f.fieldname for f in m.fields if f.in_list_view and f.fieldtype not in _ESTRUTURA][:6],
        "filtros": [{"fieldname": f.fieldname, "label": _(f.label or f.fieldname), "fieldtype": f.fieldtype,
                     "options": f.options} for f in m.fields if f.in_standard_filter][:8],
    }


@frappe.whitelist()
def lista(doctype: str, q: str = None, filtros: str = None, pagina: int = 0, ordem: str = None):
    _guarda()
    _ler(doctype)
    m = frappe.get_meta(doctype)
    titulo = m.title_field if m.title_field and m.has_field(m.title_field) else None
    colunas = [f.fieldname for f in m.fields if f.in_list_view and f.fieldtype not in _ESTRUTURA and f.fieldtype != "Table"][:6]
    campos = ["name", "modified"] + ([titulo] if titulo else []) + colunas
    if m.is_submittable:
        campos.append("docstatus")
    if m.has_field("status") and "status" not in campos:
        campos.append("status")
    f = []
    for c, op, v in json.loads(filtros or "[]")[:10]:
        if m.has_field(c) or c == "name":
            f.append([doctype, c, op if op in ("=", "!=", "like", ">", "<", ">=", "<=", "is") else "=", v])
    ou = None
    if q and q.strip():
        alvo = f"%{q.strip()}%"
        ou = [[doctype, "name", "like", alvo]] + [[doctype, c, "like", alvo] for c in
                                                   ([titulo] if titulo else []) + [s.strip() for s in (m.search_fields or "").split(",") if s.strip() and m.has_field(s.strip())]]
    por = 50
    ordem = ordem if ordem and ordem.split(" ")[0] in campos and ordem.split(" ")[-1] in ("asc", "desc") else "modified desc"
    linhas = frappe.get_list(doctype, fields=list(dict.fromkeys(campos)), filters=f, or_filters=ou,
                             order_by=ordem, start=int(pagina) * por, page_length=por + 1)
    return {"linhas": linhas[:por], "mais": len(linhas) > por, "colunas": colunas, "titulo": titulo}


@frappe.whitelist()
def documento(doctype: str, name: str = None):
    _guarda()
    _ler(doctype)
    m = frappe.get_meta(doctype)
    if m.issingle:
        name = doctype
    if not name:   # novo: os valores por omissão do ERPNext
        d = frappe.new_doc(doctype)
        return {"doc": d.as_dict(), "novo": True}
    d = frappe.get_doc(doctype, name)
    d.check_permission("read")
    return {"doc": d.as_dict(), "novo": False, "pode_gravar": bool(d.has_permission("write"))}


def _aplicar(d, dados: dict) -> None:
    """Só os campos que a definição permite editar; as tabelas-filhas são substituídas linha a linha."""
    m = d.meta
    for f in m.fields:
        if f.fieldname not in dados or f.fieldtype in _ESTRUTURA or f.fieldtype in _SEM_UI:
            continue
        if f.read_only and not f.fieldtype == "Table":
            continue
        if d.docstatus == 1 and not f.allow_on_submit:
            continue
        if f.fieldtype == "Table":
            linhas = []
            for r in dados.get(f.fieldname) or []:
                limpa = {k: v for k, v in r.items() if k not in _PADRAO or k == "name"}
                if not str(limpa.get("name") or "").strip() or str(limpa.get("name")).startswith("novo-"):
                    limpa.pop("name", None)
                linhas.append(limpa)
            d.set(f.fieldname, linhas)
        else:
            d.set(f.fieldname, dados[f.fieldname])


@frappe.whitelist(methods=["POST"])
def gravar(doctype: str, dados: str):
    _guarda()
    _ler(doctype)
    dados = json.loads(dados) if isinstance(dados, str) else dados
    m = frappe.get_meta(doctype)
    nome = doctype if m.issingle else dados.get("name")
    existe = m.issingle or bool(nome and not str(nome).startswith("novo-") and frappe.db.exists(doctype, nome))
    if existe:
        d = frappe.get_doc(doctype, nome)
        d.check_permission("write")
        _aplicar(d, dados)
        d.save()
    else:
        if not frappe.has_permission(doctype, "create"):
            frappe.throw(_("Sem permissão para criar {0}.").format(_(doctype)), frappe.PermissionError)
        d = frappe.new_doc(doctype)
        _aplicar(d, dados)
        if dados.get("__nome") and (not m.autoname or m.autoname.lower() == "prompt"):
            d.name = dados.get("__nome")
        d.insert()
    return {"doc": d.as_dict()}


@frappe.whitelist(methods=["POST"])
def apagar(doctype: str, name: str):
    _guarda()
    _ler(doctype)
    frappe.delete_doc(doctype, name)   # o Frappe confirma a permissão e as ligações
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def submeter(doctype: str, name: str):
    _guarda()
    d = frappe.get_doc(doctype, name)
    d.check_permission("submit")
    d.submit()
    return {"doc": d.as_dict()}


@frappe.whitelist(methods=["POST"])
def cancelar(doctype: str, name: str):
    _guarda()
    d = frappe.get_doc(doctype, name)
    d.check_permission("cancel")
    d.cancel()
    return {"doc": d.as_dict()}


@frappe.whitelist()
def procurar(doctype: str, txt: str = "", filtros: str = None):
    """A pesquisa de um campo de ligação, a mesma do ERPNext (respeita as permissões e os filtros por omissão)."""
    _guarda()
    if not frappe.db.exists("DocType", doctype):
        return []
    from frappe.desk.search import search_link
    r = search_link(doctype, txt or "", filters=json.loads(filtros) if filtros else None, page_length=12)
    return [{"v": x.get("value"), "r": x.get("label") or x.get("value"), "d": x.get("description") or ""} for x in (r or [])]


# ── U3: documentos de venda e compra (21-11-2026) ──────────────────────────────────────────────────────
# Os cálculos são os do ERPNext: o documento por gravar vai ao servidor, que preenche o que o ERPNext
# preencheria (preço da lista, nome, unidade, impostos do modelo) e calcula os totais — sem gravar nada.
TRANSACOES = {"Quotation", "Sales Order", "Sales Invoice", "Delivery Note", "Purchase Order", "Purchase Invoice",
              "Purchase Receipt", "Material Request", "Supplier Quotation", "Request for Quotation",
              # U4 (21-11): stock e RH
              "Stock Entry", "Stock Reconciliation", "Timesheet", "Leave Application", "Expense Claim"}

# Criar o documento seguinte a partir de um submetido (as mesmas funções dos botões «Criar» do ERPNext).
CRIAR = {
    "Quotation": [("Sales Order", "erpnext.selling.doctype.quotation.quotation.make_sales_order")],
    "Sales Order": [("Delivery Note", "erpnext.selling.doctype.sales_order.sales_order.make_delivery_note"),
                    ("Sales Invoice", "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice")],
    "Delivery Note": [("Sales Invoice", "erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice")],
    "Purchase Order": [("Purchase Receipt", "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_receipt"),
                       ("Purchase Invoice", "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice")],
    "Purchase Receipt": [("Purchase Invoice", "erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_invoice")],
    "Material Request": [("Purchase Order", "erpnext.stock.doctype.material_request.material_request.make_purchase_order")],
    "Supplier Quotation": [("Purchase Order", "erpnext.buying.doctype.supplier_quotation.supplier_quotation.make_purchase_order")],
}


_TABELAS = ("items", "taxes", "time_logs", "expenses")


def _artigo_basico(r) -> None:
    """Nome, unidade e conversão de uma linha de artigo, como o ecrã do ERPNext preenche ao escolher o artigo."""
    if not r.item_code or r.item_name:
        return
    i = frappe.db.get_value("Item", r.item_code, ["item_name", "stock_uom", "description"], as_dict=True) or {}
    r.item_name = i.get("item_name")
    r.description = r.description or i.get("description")
    r.stock_uom = i.get("stock_uom")
    r.uom = r.uom or i.get("stock_uom")
    r.conversion_factor = r.conversion_factor or 1


def _calc_movimento(d) -> None:
    for r in d.items:
        _artigo_basico(r)
        r.transfer_qty = (r.qty or 0) * (r.conversion_factor or 1)
    d.set_actual_qty()
    d.calculate_rate_and_amount(raise_error_if_no_rate=False)


def _calc_inventario(d) -> None:
    from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_stock_balance_for
    for r in d.items:
        if not (r.item_code and r.warehouse):
            continue
        if not r.item_name:
            r.item_name = frappe.db.get_value("Item", r.item_code, "item_name")
        b = get_stock_balance_for(r.item_code, r.warehouse, d.posting_date, d.posting_time, company=d.company) or {}
        r.current_qty = b.get("qty") or 0
        r.current_valuation_rate = b.get("rate") or 0
        if r.qty is None or r.qty == "":
            r.qty = r.current_qty
        if not r.valuation_rate:
            r.valuation_rate = r.current_valuation_rate
        r.amount = (r.qty or 0) * (r.valuation_rate or 0)
        r.current_amount = r.current_qty * r.current_valuation_rate
        r.quantity_difference = (r.qty or 0) - r.current_qty
        r.amount_difference = r.amount - r.current_amount


def _calc_horas(d) -> None:
    d.calculate_hours() if hasattr(d, "calculate_hours") else None
    d.calculate_total_amounts()


def _calc_ausencia(d) -> None:
    from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on, get_number_of_leave_days
    if d.employee and d.leave_type and d.from_date and d.to_date:
        d.total_leave_days = get_number_of_leave_days(d.employee, d.leave_type, d.from_date, d.to_date,
                                                      d.half_day, d.half_day_date)
        saldo = get_leave_balance_on(d.employee, d.leave_type, d.from_date, d.to_date,
                                     consider_all_leaves_in_the_allocation_period=True, for_consumption=True)
        d.leave_balance = saldo.get("leave_balance") if isinstance(saldo, dict) else saldo


def _calc_despesas(d) -> None:
    d.calculate_total_amount()
    if hasattr(d, "calculate_taxes"):
        d.calculate_taxes()


_CALCULO_U4 = {"Stock Entry": _calc_movimento, "Stock Reconciliation": _calc_inventario, "Timesheet": _calc_horas,
               "Leave Application": _calc_ausencia, "Expense Claim": _calc_despesas}


@frappe.whitelist(methods=["POST"])
def recalcular(doctype: str, dados: str):
    """O documento como ficaria: valores em falta preenchidos e totais calculados. Nunca grava."""
    _guarda()
    _ler(doctype)
    if doctype not in TRANSACOES:
        frappe.throw(_("Este documento não tem cálculo de totais."))
    dados = json.loads(dados) if isinstance(dados, str) else dados
    dados["doctype"] = doctype
    nomes = {}   # as linhas novas da interface («novo-…») voltam com o mesmo nome, pela posição
    for t in _TABELAS:
        nomes[t] = [r.get("name") for r in dados.get(t) or []]
        for r in dados.get(t) or []:
            if str(r.get("name") or "").startswith("novo-"):
                r.pop("name")
    d = frappe.get_doc(dados)
    try:
        if doctype in _CALCULO_U4:
            _CALCULO_U4[doctype](d)
        else:
            if hasattr(d, "set_missing_values"):
                d.set_missing_values(for_validate=True)
            if hasattr(d, "calculate_taxes_and_totals"):
                d.calculate_taxes_and_totals()
    except frappe.ValidationError as e:
        return {"doc": None, "aviso": str(e)[:300]}
    finally:
        frappe.db.rollback()   # nada do que o ERPNext tenha tocado fica gravado
    out = d.as_dict()
    for t in _TABELAS:
        for i, r in enumerate(out.get(t) or []):
            if i < len(nomes.get(t, [])) and str(nomes[t][i] or "").startswith("novo-"):
                r["name"] = nomes[t][i]
    return {"doc": out}


@frappe.whitelist()
def criar_opcoes(doctype: str):
    _guarda()
    return [{"doctype": dt, "rotulo": _(dt)} for dt, _m in CRIAR.get(doctype, []) if frappe.has_permission(dt, "create")]


@frappe.whitelist(methods=["POST"])
def criar_de(doctype: str, name: str, destino: str):
    """O documento seguinte por gravar (ex.: encomenda → fatura), como o botão «Criar» do ERPNext."""
    _guarda()
    metodo = dict(CRIAR.get(doctype, [])).get(destino)
    if not metodo:
        frappe.throw(_("Não se cria {0} a partir de {1}.").format(_(destino), _(doctype)))
    origem = frappe.get_doc(doctype, name)
    origem.check_permission("read")
    if not frappe.has_permission(destino, "create"):
        frappe.throw(_("Sem permissão para criar {0}.").format(_(destino)), frappe.PermissionError)
    novo = frappe.get_attr(metodo)(name)
    return {"doc": novo.as_dict()}



# ── U4: ecrãs Stock e Pessoas (21-11-2026) ─────────────────────────────────────────────────────────────
@frappe.whitelist()
def stock_artigo(item_code: str):
    """Um artigo: stock por armazém (próprio), últimos movimentos e, se houver, o stock dos fornecedores."""
    _guarda()
    _ler("Item")
    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Artigo desconhecido."), frappe.DoesNotExistError)
    art = frappe.get_doc("Item", item_code)
    art.check_permission("read")
    bins = frappe.get_list("Bin", filters={"item_code": item_code},
                           fields=["warehouse", "actual_qty", "reserved_qty", "ordered_qty", "projected_qty",
                                   "valuation_rate", "stock_value"], order_by="actual_qty desc") \
        if frappe.has_permission("Bin", "read") else []
    movs = frappe.get_list("Stock Ledger Entry", filters={"item_code": item_code, "is_cancelled": 0},
                           fields=["posting_date", "posting_time", "voucher_type", "voucher_no", "warehouse", "actual_qty",
                                   "qty_after_transaction", "valuation_rate"],
                           order_by="posting_date desc, posting_time desc, creation desc", limit_page_length=20) \
        if frappe.has_permission("Stock Ledger Entry", "read") else []
    ofertas = []
    if frappe.db.exists("DocType", "Oferta do Fornecedor") and frappe.has_permission("Oferta do Fornecedor", "read"):
        ofertas = frappe.get_list("Oferta do Fornecedor", filters={"item_code": item_code},
                                  fields=["supplier", "estado_stock", "quantidade", "quantidade_conhecida", "custo",
                                          "lida_em", "ausente_desde"])
    for m in movs:
        m["voucher_rotulo"] = _(m.voucher_type)
    return {"artigo": {"item_code": art.item_code, "item_name": art.item_name, "stock_uom": art.stock_uom,
                       "image": art.image, "is_stock_item": art.is_stock_item},
            "armazens": bins, "movimentos": movs, "ofertas": ofertas,
            "total": sum((b.actual_qty or 0) for b in bins), "valor": sum((b.stock_value or 0) for b in bins)}


@frappe.whitelist()
def stock_resumo():
    """Valor e quantidade por armazém (só os armazéns que a pessoa vê)."""
    _guarda()
    if not frappe.has_permission("Bin", "read"):
        return []
    acc = {}
    for b in frappe.get_list("Bin", fields=["warehouse", "actual_qty", "stock_value"], filters={"actual_qty": ["!=", 0]},
                             limit_page_length=20000):
        a = acc.setdefault(b.warehouse, {"warehouse": b.warehouse, "artigos": 0, "valor": 0.0})
        a["artigos"] += 1
        a["valor"] += b.stock_value or 0
    return sorted(acc.values(), key=lambda x: -x["valor"])


@frappe.whitelist()
def pessoas():
    """Diretório, quem está ausente hoje e o saldo de férias de quem está a ver."""
    _guarda()
    if not frappe.db.exists("DocType", "Employee") or not frappe.has_permission("Employee", "read"):
        return {"sem_rh": True}
    hoje = frappe.utils.today()
    equipa = frappe.get_list("Employee", filters={"status": "Active"},
                             fields=["name", "employee_name", "designation", "department", "image", "company_email",
                                     "cell_number", "user_id"], order_by="employee_name asc", limit_page_length=500)
    ausentes = []
    if frappe.db.exists("DocType", "Leave Application") and frappe.has_permission("Leave Application", "read"):
        ausentes = frappe.get_list("Leave Application",
                                   filters={"status": "Approved", "docstatus": 1, "from_date": ["<=", hoje], "to_date": [">=", hoje]},
                                   fields=["employee", "employee_name", "leave_type", "from_date", "to_date"])
    eu = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
    saldo = []
    if eu:
        try:
            from hrms.hr.doctype.leave_application.leave_application import get_leave_details
            det = get_leave_details(eu, hoje) or {}
            for tipo, v in (det.get("leave_allocation") or {}).items():
                saldo.append({"tipo": _(tipo), "atribuidos": v.get("total_leaves"), "gozados": v.get("leaves_taken"),
                              "pendentes": v.get("leaves_pending_approval"), "restam": v.get("remaining_leaves")})
        except Exception:  # noqa: BLE001 — sem atribuições ou sem acesso: fica sem saldo
            saldo = []
    for p in equipa:
        p["designacao"] = _(p.designation) if p.designation else ""
    for a in ausentes:
        a["tipo"] = _(a.leave_type)
    return {"equipa": equipa, "ausentes_hoje": ausentes, "eu": eu, "saldo": saldo}


# ── U5: relatórios e cartões de número (21-11-2026) ────────────────────────────────────────────────────
# O motor é o do ERPNext (frappe.desk.query_report.run); a interface desenha filtros, resumo, gráfico e tabela.
MAX_LINHAS_RELATORIO = 3000


def _relatorio_permitido(nome: str):
    if not frappe.db.exists("Report", nome):
        frappe.throw(_("Relatório desconhecido."), frappe.DoesNotExistError)
    r = frappe.get_doc("Report", nome)
    if not r.is_permitted():
        frappe.throw(_("Sem acesso a este relatório."), frappe.PermissionError)
    return r


@frappe.whitelist()
def relatorio_meta(nome: str):
    """O script do relatório (os filtros estão nele, como no ERPNext), o ficheiro partilhado das demonstrações
    financeiras quando é preciso, e os valores por omissão da pessoa (empresa, ano fiscal, moeda)."""
    _guarda()
    r = _relatorio_permitido(nome)
    if r.report_type == "Report Builder":
        return {"tipo": "builder", "doctype": r.ref_doctype, "rotulo": _(r.name)}
    from frappe.desk.query_report import get_script
    sc = get_script(nome) or {}
    script = sc.get("script") or ""
    partilhado = ""
    if "erpnext.financial_statements" in script:
        try:
            with open(frappe.get_app_path("erpnext", "public", "js", "financial_statements.js")) as f:
                partilhado = f.read()
        except OSError:
            partilhado = ""
    empresa = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company") \
        or frappe.db.get_value("Company", {}, "name")
    ano, ano_ini, ano_fim = None, None, None
    try:
        from erpnext.accounts.utils import get_fiscal_year
        fy = get_fiscal_year(frappe.utils.today(), company=empresa)
        ano, ano_ini, ano_fim = fy[0], str(fy[1]), str(fy[2])
    except Exception:  # noqa: BLE001 — sem ano fiscal configurado: fica vazio
        ano = None
    import re as _re
    textos = set(_re.findall(r'__\(\s*["\']([^"\']{1,120})["\']', script + partilhado))
    for bloco in _re.findall(r'options:\s*\[([^\]]{0,600})\]', script + partilhado):   # escolhas sem __()
        textos.update(_re.findall(r'["\']([^"\']{1,60})["\']', bloco))
    return {"tipo": r.report_type, "rotulo": _(r.name), "script": script, "partilhado": partilhado,
            "traducoes": {t: _(t) for t in textos},
            "omissao": {"company": empresa, "fiscal_year": ano, "ano_inicio": ano_ini, "ano_fim": ano_fim,
                        "currency": frappe.db.get_value("Company", empresa, "default_currency") if empresa else "EUR",
                        "today": frappe.utils.today()}}


def _colunas(cols: list) -> list:
    out = []
    for c in cols or []:
        if isinstance(c, str):   # forma antiga «Rótulo:Tipo/Opções:Largura»
            partes = c.split(":")
            tipo, opcoes = (partes[1].split("/") + [None])[:2] if len(partes) > 1 else ("Data", None)
            c = {"label": partes[0], "fieldtype": tipo or "Data", "options": opcoes, "fieldname": frappe.scrub(partes[0])}
        out.append({"fieldname": c.get("fieldname") or frappe.scrub(c.get("label") or ""), "label": _(c.get("label") or ""),
                    "fieldtype": c.get("fieldtype") or "Data", "options": c.get("options"), "width": c.get("width")})
    return out


@frappe.whitelist(methods=["POST"])
def relatorio(nome: str, filtros: str = None):
    _guarda()
    _relatorio_permitido(nome)
    from frappe.desk.query_report import run
    f = json.loads(filtros) if isinstance(filtros, str) and filtros else (filtros or {})
    r = run(report_name=nome, filters=f, ignore_prepared_report=True, are_default_filters=False) or {}
    cols = _colunas(r.get("columns"))
    linhas = []
    for row in (r.get("result") or [])[:MAX_LINHAS_RELATORIO]:
        if isinstance(row, (list, tuple)):
            row = {cols[i]["fieldname"]: v for i, v in enumerate(row) if i < len(cols)}
        linhas.append(row)
    resumo = [{"rotulo": _(s.get("label") or ""), "valor": s.get("value"), "tipo": s.get("datatype"),
               "cor": s.get("indicator")} for s in (r.get("report_summary") or []) if isinstance(s, dict)]
    return {"colunas": cols, "linhas": linhas, "cortado": len(r.get("result") or []) > MAX_LINHAS_RELATORIO,
            "grafico": r.get("chart"), "resumo": resumo, "mensagem": r.get("message"),
            "total": bool(r.get("add_total_row"))}


@frappe.whitelist()
def numeros(barra: str):
    """Os cartões de número do painel do módulo (os mesmos da secretária do ERPNext), já calculados."""
    _guarda()
    if not frappe.db.exists("Workspace", barra):
        return []
    from frappe.desk.doctype.number_card.number_card import get_result
    out = []
    for nc in frappe.get_doc("Workspace", barra).number_cards or []:
        nome = nc.number_card_name
        if not nome or not frappe.db.exists("Number Card", nome):
            continue
        card = frappe.get_doc("Number Card", nome)
        try:
            if card.type == "Document Type":
                if not frappe.has_permission(card.document_type, "read"):
                    continue
                valor = get_result(card.as_dict(), card.filters_json or "[]")
                tipo = "Currency" if card.function in ("Sum", "Average") and card.aggregate_function_based_on else "Int"
            elif card.type == "Custom" and card.method:
                res = frappe.get_attr(card.method)(json.loads(card.filters_json or "{}")) or {}
                valor, tipo = res.get("value"), res.get("fieldtype") or "Int"
            else:
                continue
        except Exception:  # noqa: BLE001 — um cartão com problema não estraga o painel
            continue
        out.append({"rotulo": _(nc.label or card.label or nome), "valor": valor, "tipo": tipo, "cor": card.color})
    return out[:8]
