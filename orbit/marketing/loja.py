"""A loja, lida do ERPNext — quem comprou o quê, e que produtos mostrar.

As encomendas chegam ao ERPNext pela integração WooCommerce (`woocommerce_fusion`,
decidida a 03-10-2026), que grava em cada encomenda de venda o estado que ela
tem na loja (`woocommerce_status`) e, em cada artigo, o identificador do produto
na loja (`Item.woocommerce_servers`). Uma encomenda feita à mão no ERPNext, sem
estado da loja, conta como compra se estiver submetida e não cancelada.

Num tenant sem ERPNext tudo isto devolve vazio: as automações de loja ficam
sem candidatos e as regras de compra nos segmentos não apanham ninguém. É o
comportamento certo — sem loja não há compras.

Só lê. Nada aqui escreve no ERPNext nem na loja.
"""

import frappe
from frappe.utils import add_days, flt, fmt_money, get_url, nowdate

# Estados da loja que querem dizer «foi paga». O WooCommerce não tem um estado
# «concluída» nesta integração: a encomenda segue para enviada/entregue.
PAGAS = ("Processing", "Processing LP", "Shipped", "Partially Shipped", "Ready for Pickup",
         "Picked up", "Delivered", "Dispatched Pickup")
POR_PAGAR = ("Pending Payment", "Failed")


def tem_loja() -> bool:
    return bool(frappe.db.exists("DocType", "Sales Order"))


def _tem_campo(dt: str, campo: str) -> bool:
    return frappe.get_meta(dt).has_field(campo)


def _email_expr() -> str:
    """O email de quem comprou: o da encomenda, ou o do cliente."""
    return "LOWER(COALESCE(NULLIF(so.contact_email, ''), cu.email_id))"


def encomendas(pagas: bool = True, desde=None, email: str | None = None) -> list[dict]:
    """Encomendas de venda com o email de quem comprou e os artigos."""
    if not tem_loja():
        return []
    woo = _tem_campo("Sales Order", "woocommerce_status")
    if pagas:
        cond = (f"(so.woocommerce_status IN %(pagas)s OR (COALESCE(so.woocommerce_status, '') = '' "
                f"AND so.docstatus = 1 AND so.status NOT IN ('Cancelled', 'Closed')))") if woo else \
            "(so.docstatus = 1 AND so.status NOT IN ('Cancelled', 'Closed'))"
    else:
        if not woo:
            return []
        cond = "so.woocommerce_status IN %(por_pagar)s AND so.docstatus < 2"
    filtros = {"pagas": PAGAS, "por_pagar": POR_PAGAR, "desde": desde, "email": (email or "").lower()}
    extra = (" AND so.transaction_date >= %(desde)s" if desde else "") + \
            (f" AND {_email_expr()} = %(email)s" if email else "")
    linhas = frappe.db.sql(f"""
        SELECT so.name, {_email_expr()} AS email, so.transaction_date AS data, so.creation,
               so.grand_total AS total, so.customer
               {", so.woocommerce_server" if woo else ""}
        FROM `tabSales Order` so LEFT JOIN `tabCustomer` cu ON cu.name = so.customer
        WHERE {cond}{extra}
        ORDER BY so.transaction_date DESC""", filtros, as_dict=True)
    if not linhas:
        return []
    itens: dict = {}
    for i in frappe.db.sql("""SELECT parent, item_code, item_name, item_group, qty
            FROM `tabSales Order Item` WHERE parent IN %(nomes)s ORDER BY idx""",
                           {"nomes": [l.name for l in linhas]}, as_dict=True):
        itens.setdefault(i.parent, []).append(dict(i))
    return [{**l, "itens": itens.get(l.name, [])} for l in linhas if l.email]


def ultima_compra() -> dict:
    """Por email, a data da última compra paga e quantas encomendas tem."""
    saida: dict = {}
    for e in encomendas(True):
        x = saida.setdefault(e["email"], {"ultima": e["data"], "n": 0, "grupos": set()})
        x["n"] += 1
        x["ultima"] = max(x["ultima"], e["data"])
        x["grupos"] |= {i["item_group"] for i in e["itens"] if i.get("item_group")}
    return saida


# ── Produtos para uma mensagem ─────────────────────────────────────────────

def _url_na_loja(item_code: str) -> str | None:
    if not frappe.db.exists("DocType", "Item WooCommerce Server"):
        return None
    r = frappe.db.sql("""SELECT s.woocommerce_server_url AS base, i.woocommerce_id AS id
        FROM `tabItem WooCommerce Server` i JOIN `tabWooCommerce Server` s ON s.name = i.woocommerce_server
        WHERE i.parent = %s AND i.parenttype = 'Item' AND COALESCE(i.woocommerce_id, '') <> ''
        ORDER BY i.idx LIMIT 1""", item_code, as_dict=True)
    if not r:
        return None
    # O WordPress resolve ?post_type=product&p=<id> para o endereço do produto.
    # Guardar o permalink não serve: muda quando o produto muda de nome.
    return f"{r[0].base.rstrip('/')}/?post_type=product&p={r[0].id}"


def _preco(item_code: str) -> str:
    v = frappe.db.get_value("Item Price", {"item_code": item_code, "selling": 1}, ["price_list_rate", "currency"],
                            order_by="modified desc", as_dict=True)
    return fmt_money(flt(v.price_list_rate), currency=v.currency) if v and v.price_list_rate else ""


def produto(item_code: str) -> dict | None:
    """Um artigo pronto a entrar numa mensagem: só com endereço na loja."""
    i = frappe.db.get_value("Item", item_code, ["item_name", "image", "disabled", "item_group"], as_dict=True)
    if not i or i.disabled:
        return None
    url = _url_na_loja(item_code)
    if not url:
        return None
    imagem = i.image if (i.image or "").startswith("http") else (get_url(i.image) if i.image else None)
    return {"item_code": item_code, "nome": i.item_name, "url": url, "imagem": imagem,
            "preco": _preco(item_code), "grupo": i.item_group}


def mais_vendidos(grupos: set | None = None, excluir: set | None = None, quantos: int = 3,
                  dias: int = 90) -> list[dict]:
    """Os artigos que mais saíram nos últimos dias, nos grupos indicados."""
    if not tem_loja():
        return []
    filtros = {"desde": add_days(nowdate(), -dias), "grupos": tuple(grupos or ()) or ("",),
               "excluir": tuple(excluir or ()) or ("",)}
    cond_grupo = "AND soi.item_group IN %(grupos)s" if grupos else ""
    saida = []
    for r in frappe.db.sql(f"""SELECT soi.item_code, SUM(soi.qty) AS q
            FROM `tabSales Order Item` soi JOIN `tabSales Order` so ON so.name = soi.parent
            WHERE so.docstatus = 1 AND so.transaction_date >= %(desde)s {cond_grupo}
              AND soi.item_code NOT IN %(excluir)s
            GROUP BY soi.item_code ORDER BY q DESC LIMIT 30""", filtros, as_dict=True):
        p = produto(r.item_code)
        if p:
            saida.append(p)
        if len(saida) >= quantos:
            break
    return saida


def novidades(quantos: int = 3) -> list[dict]:
    if not tem_loja():
        return []
    saida = []
    for code in frappe.get_all("Item", filters={"disabled": 0, "is_sales_item": 1}, pluck="name",
                               order_by="creation desc", limit=40):
        p = produto(code)
        if p:
            saida.append(p)
        if len(saida) >= quantos:
            break
    return saida
