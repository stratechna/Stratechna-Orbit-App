"""Disponibilidade de um artigo num canal (21-11-2026, docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md §4.2).

disponível = stock próprio dos armazéns do canal − reservado
             + (canal «Próprio + fornecedor» e fornecedor que o permite) stock do fornecedor
               lido dentro da frescura, menos a margem de segurança.

O stock do fornecedor nunca entra no livro de stock: vem da «Oferta do Fornecedor».
"""
import frappe
from frappe.utils import add_to_date, flt, get_datetime, now_datetime

MODO_SO_PROPRIO = "Só stock próprio"


def _proprio(item_code: str, armazens: list) -> float:
    if not armazens:
        return 0.0
    r = frappe.db.sql("""select coalesce(sum(actual_qty - reserved_qty), 0) from `tabBin`
                         where item_code=%s and warehouse in %s""", (item_code, tuple(armazens)))
    return max(0.0, flt(r[0][0] if r else 0))


def _fornecedores(item_code: str) -> list:
    ofertas = frappe.get_all("Oferta do Fornecedor", filters={"item_code": item_code, "activa": 1, "pode_vender": 1},
                             fields=["supplier", "quantidade", "quantidade_conhecida", "estado_stock", "lida_em",
                                     "prazo_entrega", "ausente_desde"])
    out = []
    for o in ofertas:
        if o.ausente_desde:
            continue
        sup = frappe.db.get_value("Supplier", o.supplier, ["orbit_vende_com_stock", "orbit_frescura_horas",
                                                           "orbit_margem_stock"], as_dict=True) or {}
        if sup.get("orbit_vende_com_stock") == 0:
            continue
        horas = int(sup.get("orbit_frescura_horas") or 12)
        fresca = bool(o.lida_em) and get_datetime(o.lida_em) >= add_to_date(now_datetime(), hours=-horas)
        qtd = None
        if o.quantidade_conhecida:
            qtd = max(0.0, flt(o.quantidade) - int(sup.get("orbit_margem_stock") or 0)) if fresca else 0.0
        out.append(frappe._dict(supplier=o.supplier, qtd=qtd, fresca=fresca, estado=o.estado_stock,
                                prazo=o.prazo_entrega))
    return out


def calcular(item_code: str, canal: str) -> dict:
    """{quantidade, estado: Em stock|Sob encomenda|Esgotado, prazo, fonte: próprio|fornecedor|nenhuma}."""
    c = frappe.get_cached_doc("Canal de Venda", canal)
    proprio = _proprio(item_code, [a.warehouse for a in c.armazens])
    if proprio > 0:
        return {"quantidade": proprio, "estado": "Em stock", "prazo": None, "fonte": "próprio"}
    if c.modo_stock == MODO_SO_PROPRIO:
        return {"quantidade": 0, "estado": "Esgotado", "prazo": None, "fonte": "nenhuma"}
    melhores = [f for f in _fornecedores(item_code) if f.fresca]
    com_qtd = [f for f in melhores if f.qtd]
    if com_qtd:
        f = max(com_qtd, key=lambda x: x.qtd)
        return {"quantidade": f.qtd, "estado": "Em stock", "prazo": f.prazo, "fonte": "fornecedor"}
    # quantidade desconhecida mas o fornecedor diz que tem (fresco) → em stock sem número
    em_stock = [f for f in melhores if f.qtd is None and f.estado == "Em stock"]
    if em_stock:
        return {"quantidade": None, "estado": "Em stock", "prazo": em_stock[0].prazo, "fonte": "fornecedor"}
    if any(f.estado == "Sob encomenda" for f in melhores) or _fornecedores_sob_encomenda(item_code):
        return {"quantidade": 0, "estado": "Sob encomenda", "prazo": None, "fonte": "fornecedor"}   # sem prazo (regra)
    return {"quantidade": 0, "estado": "Esgotado", "prazo": None, "fonte": "nenhuma"}


def _fornecedores_sob_encomenda(item_code: str) -> bool:
    return bool(frappe.db.exists("Oferta do Fornecedor", {"item_code": item_code, "activa": 1,
                                                         "estado_stock": "Sob encomenda", "ausente_desde": ["is", "not set"]}))
