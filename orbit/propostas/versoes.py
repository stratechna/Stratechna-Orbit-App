"""Versões de uma proposta e procura de produtos no ERP (24-11-2026, layout novo da proposta).

Decisão do Vítor (24-11): as alternativas deixam de estar DENTRO da proposta (enviesavam o total) — «Criar proposta
alternativa» copia a proposta para uma versão nova (ORC-SHX-2026-0007-B), com o seu próprio total. A original fica
como versão A; todas apontam para a primeira em `orbit_proposta_base`.
"""
import re

import frappe
from frappe.utils import cint, flt

from orbit.propostas.caracteristicas import do_artigo

_LETRAS = "BCDEFGHIJKLMNOPQRSTUVWXYZ"
_SERVICOS = ("TRANSPORTE", "MONTAGEM", "GASTO-DOCS")


def _principal(name: str) -> str:
    l = frappe.db.sql("""select item_name from `tabQuotation Item` where parent=%s and ifnull(orbit_de,'')=''
                         and item_code not in %s order by idx limit 1""", (name, _SERVICOS))
    return l[0][0] if l else ""


@frappe.whitelist()
def versoes(name: str):
    frappe.has_permission("Quotation", "read", throw=True)
    base = frappe.db.get_value("Quotation", name, "orbit_proposta_base") or name
    linhas = frappe.get_list("Quotation", filters=[["name", "=", base]], fields=["name", "orbit_versao", "grand_total",
                             "docstatus", "status"]) + \
        frappe.get_list("Quotation", filters={"orbit_proposta_base": base}, fields=["name", "orbit_versao", "grand_total",
                        "docstatus", "status"], order_by="orbit_versao asc")
    if len(linhas) < 2:
        return []
    return [{"name": l.name, "versao": l.orbit_versao or "A", "total": flt(l.grand_total), "docstatus": l.docstatus,
             "estado": l.status, "principal": _principal(l.name)} for l in linhas]


@frappe.whitelist(methods=["POST"])
def criar_alternativa(name: str):
    """Copia a proposta para a versão seguinte (B, C…). Devolve o nome da nova."""
    o = frappe.get_doc("Quotation", name)
    o.check_permission("read")
    frappe.has_permission("Quotation", "create", throw=True)
    base = o.get("orbit_proposta_base") or o.name
    if base == o.name and not o.get("orbit_versao"):
        o.db_set("orbit_versao", "A", update_modified=False)
    usadas = set(frappe.get_all("Quotation", filters={"orbit_proposta_base": base}, pluck="orbit_versao")) | {"A"}
    letra = next((c for c in _LETRAS if c not in usadas), None)
    if not letra:
        frappe.throw("Esta proposta já tem demasiadas versões.")
    n = frappe.copy_doc(o)
    n.docstatus = 0
    for l in n.items or []:
        l.docstatus = 0
    n.orbit_proposta_base = base
    n.orbit_versao = letra
    n.status = "Draft"
    n.insert(set_name=f"{base}-{letra}")
    return {"name": n.name}


# ── procurar no ERP ──────────────────────────────────────────────────────────
def _lista_da_marca(marca: str | None) -> str | None:
    if marca and frappe.db.exists("DocType", "Canal de Venda"):
        lista = frappe.db.get_value("Canal de Venda", {"marca": marca}, "lista_precos")
        if lista:
            return lista
    return frappe.db.get_single_value("Selling Settings", "selling_price_list")


def _preco(item_code: str, lista: str | None) -> float | None:
    if lista:
        v = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": lista, "selling": 1}, "price_list_rate")
        if v:
            return flt(v)
    v = frappe.db.get_value("Item Price", {"item_code": item_code, "selling": 1}, "price_list_rate")
    return flt(v) if v else (flt(frappe.db.get_value("Item", item_code, "standard_rate")) or None)


@frappe.whitelist()
def sugestoes(txt: str, marca: str | None = None):
    """Artigos do ERP pela referência (nossa ou do fornecedor), EAN, ou palavras do nome. Até 10."""
    frappe.has_permission("Quotation", "create", throw=True)
    txt = (txt or "").strip()
    if len(txt) < 2:
        return []
    # 27-11-2026: na JF (13 370 artigos, tabela de 106 MB) as procuras por campos sem índice liam a tabela toda — 2 a 4,5 s.
    # Cada consulta usa agora um índice (name, orbit_ref_feed, orbit_ean, orbit_mpn, item_name); nada de upper()/OR que
    # obrigue a ler a tabela. As palavras do nome procuram-se só no índice de item_name.
    achados = []
    for sql, args in (
        ("select name from tabItem where name=%s", (txt,)),
        ("select parent from `tabItem Supplier` where parenttype='Item' and supplier_part_no=%s", (txt,)),
        ("select parent from `tabItem Barcode` where barcode=%s", (txt,)),
        ("select name from tabItem where orbit_ref_feed=%s", (txt,)),
        ("select name from tabItem where orbit_ean=%s", (txt,)),
        ("select name from tabItem where orbit_mpn=%s", (txt,)),
        ("select name from tabItem where name like %s limit 10", (txt + "%",)),
        ("select name from tabItem where orbit_ref_feed like %s limit 10", (txt + "%",)),
    ):
        try:
            achados += [r[0] for r in frappe.db.sql(sql, args)]
        except Exception:
            pass   # tenant sem os campos do importador
        if len(set(achados)) >= 10:
            break
    palavras = [p for p in re.split(r"\s+", txt) if len(p) >= 2][:5]
    if len(set(achados)) < 10 and palavras:
        cond = " and ".join(["item_name like %s"] * len(palavras))
        args = tuple(f"%{p}%" for p in palavras)
        try:
            linhas = frappe.db.sql(f"select name from tabItem force index (item_name) where {cond} limit 40", args)
        except Exception:
            linhas = frappe.db.sql(f"select name from tabItem where {cond} limit 40", args)
        achados += [r[0] for r in linhas]
    vistos, out = set(), []
    lista = _lista_da_marca(marca)
    for codigo in achados:
        if codigo in vistos or codigo in _SERVICOS:
            continue
        vistos.add(codigo)
        it = frappe.db.get_value("Item", codigo, ["name", "item_name", "image", "brand", "stock_uom", "disabled",
                                                  "orbit_caracteristicas", "orbit_atributos", "orbit_atributos_locais",
                                                  "orbit_fabricante"] if frappe.get_meta("Item").has_field("orbit_atributos")
                                 else ["name", "item_name", "image", "brand", "stock_uom", "disabled"], as_dict=True)
        if not it or (cint(it.disabled) and codigo != txt):
            continue   # desactivados só aparecem pela referência exacta
        caract = do_artigo(it)
        out.append({"item_code": it.name, "item_name": it.item_name, "image": it.image, "marca": it.brand,
                    "fabricante": it.get("orbit_fabricante"), "uom": it.stock_uom, "inactivo": cint(it.disabled),
                    "preco": _preco(it.name, lista), "caracteristicas": caract,
                    "n_caracteristicas": len([l for l in caract.splitlines() if l.strip()])})
        if len(out) >= 10:
            break
    return out


@frappe.whitelist()
def caracteristicas(item_code: str):
    frappe.has_permission("Quotation", "read", throw=True)
    return do_artigo(item_code)


# ── ecrã da proposta (interface /orbit) ─────────────────────────────────────
@frappe.whitelist()
def marcas():
    frappe.has_permission("Quotation", "read", throw=True)
    campos = ["name", "image"] + [c for c in ("orbit_cor", "orbit_serie") if frappe.get_meta("Brand").has_field(c)]
    return frappe.get_all("Brand", fields=campos, order_by="name asc", limit=50)


@frappe.whitelist(methods=["POST"])
def enviar(name: str, para: str, assunto: str, mensagem: str = ""):
    """Envia a proposta em PDF (modelo «Proposta Orbit») pela caixa de saída do Orbit; fica na cronologia."""
    d = frappe.get_doc("Quotation", name)
    d.check_permission("read")
    para = ",".join(e.strip() for e in (para or "").replace(";", ",").split(",") if "@" in e)
    if not para:
        frappe.throw("Indique o email do cliente.")
    from frappe.core.doctype.communication.email import make
    from frappe.utils import escape_html
    corpo = "<br>".join(escape_html(l) for l in (mensagem or "").splitlines())
    make(doctype="Quotation", name=name, recipients=para, subject=(assunto or f"Proposta {name}")[:140], content=corpo,
         send_email=1, print_format="Proposta Orbit", attach_document_print=1, print_letterhead=0)
    return {"ok": True}


def garantir_indices():
    """Índices para a procura de artigos nas propostas (after_migrate). Sem eles a procura lia a tabela toda."""
    meta = frappe.get_meta("Item")
    for campo in ("orbit_ean", "orbit_mpn", "orbit_ref_feed"):
        if meta.has_field(campo):
            try:
                frappe.db.add_index("Item", [campo])
            except Exception:  # noqa: BLE001
                frappe.log_error(title=f"Orbit: índice de {campo}")
