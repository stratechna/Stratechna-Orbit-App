"""Vários funis no CRM (27-11-2026, docs/PLANO-FUNIS-CRM-ORBIT.md, F1–F7).

O Frappe CRM só tem um funil: `CRM Deal.status` → `CRM Deal Status` (nome, tipo Open/Ongoing/On Hold/Won/Lost, cor,
posição). Os funis do Orbit ficam por cima, sem tirar nada ao CRM:

* doctype «Funil» (nome, por omissão, mostra valor, marcas, ordem, desligado);
* `CRM Deal Status.orbit_funil` — cada fase pertence a um funil; cada funil tem as suas fases de tipo Won e Lost;
  nas fases criadas no Orbit o nome interno é «<Funil> · <Fase>» (único no tenant) e o nome à vista é `orbit_rotulo`;
* `CRM Deal.orbit_funil` e `CRM Deal.orbit_tipo_fase` (o tipo da fase, para os fluxos e filtros).

Regra única (`antes_de_validar`): a fase de um negócio é sempre uma fase do funil dele. Se o código pede uma fase de
outro funil (ex.: «Won» vindo do Booking ou do portal), fica a do mesmo tipo no funil do negócio; uma fase aberta de
outro funil passa à 1.ª fase aberta. Mudar o negócio de funil (F6) faz o mesmo. Por isso ganho/perdido decide-se
sempre pelo TIPO da fase, nunca pelo nome.
"""
from __future__ import annotations

import frappe
from frappe.utils import cint, nowdate

DT = "Funil"
FASE = "CRM Deal Status"
FECHADOS = ("Won", "Lost")
ABERTOS = ("Open", "Ongoing", "On Hold")


# ── instalação ───────────────────────────────────────────────────────────────────────────────────────────────
def instalar() -> None:
    """Campos, funil «Vendas» por omissão e migração das fases e negócios existentes (idempotente; after_migrate)."""
    if not frappe.db.exists("DocType", DT) or not frappe.db.exists("DocType", FASE):
        return
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    campos = [
        (FASE, {"fieldname": "orbit_funil", "label": "Funil", "fieldtype": "Link", "options": DT, "insert_after": "type",
                "in_list_view": 1, "in_standard_filter": 1}),
        ("CRM Deal", {"fieldname": "orbit_funil", "label": "Funil", "fieldtype": "Link", "options": DT,
                      "insert_after": "status", "in_standard_filter": 1,
                      "description": "Ao mudar de funil, o negócio passa à 1.ª fase do funil novo (ganho/perdido mantêm-se)."}),
        ("CRM Deal", {"fieldname": "orbit_tipo_fase", "label": "Tipo da fase", "fieldtype": "Data", "read_only": 1,
                      "hidden": 1, "insert_after": "orbit_funil", "search_index": 1}),
    ]
    for dt, f in campos:
        if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": f["fieldname"]}):
            create_custom_field(dt, f)
    for dt, campo in (("Supplier Quotation", "orbit_negocio"), ("Purchase Order", "orbit_negocio")):
        if frappe.db.exists("DocType", dt) and not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": campo}):
            create_custom_field(dt, {"fieldname": campo, "label": "Negócio (CRM)", "fieldtype": "Link", "options": "CRM Deal",
                                     "insert_after": "supplier", "allow_on_submit": 1,
                                     "description": "Negócio de um funil do CRM (ex.: «Compras») que esta compra fecha."})
    frappe.clear_cache(doctype="CRM Deal")
    frappe.clear_cache(doctype=FASE)
    if not frappe.db.count(DT):
        frappe.get_doc({"doctype": DT, "nome": "Vendas", "por_omissao": 1, "mostra_valor": 1, "ordem": 1,
                        "modelo": "vendas"}).insert(ignore_permissions=True)
    om = omissao()
    frappe.db.sql(f"update `tab{FASE}` set orbit_funil=%s where ifnull(orbit_funil,'')=''", om)
    frappe.db.sql("update `tabCRM Deal` set orbit_funil=%s where ifnull(orbit_funil,'')=''", om)
    frappe.db.sql(f"""update `tabCRM Deal` d join `tab{FASE}` s on s.name=d.status
                      set d.orbit_tipo_fase=s.type where ifnull(d.orbit_tipo_fase,'')<>ifnull(s.type,'')""")


# ── leitura ──────────────────────────────────────────────────────────────────────────────────────────────────
def _todas():
    m = getattr(frappe.local, "orbit_fases_funis", None)
    if m is None:
        campos = ["name", "type", "color", "position", "probability"]
        if frappe.db.has_column(FASE, "orbit_funil"):   # antes da migração do tenant: tudo num funil só
            campos.append("orbit_funil")
        m = frappe.get_all(FASE, fields=campos, order_by="position asc, name asc")
        for x in m:
            x.setdefault("orbit_funil", None)
        frappe.local.orbit_fases_funis = m
    return m


def _esquecer():
    for k in ("orbit_fases_funis", "orbit_rotulos", "orbit_funil_omissao"):
        if hasattr(frappe.local, k):
            delattr(frappe.local, k)


def omissao() -> str | None:
    if hasattr(frappe.local, "orbit_funil_omissao"):
        return frappe.local.orbit_funil_omissao
    n = None
    if frappe.db.exists("DocType", DT):
        n = frappe.db.get_value(DT, {"por_omissao": 1, "desligado": 0}, "name") or \
            frappe.db.get_value(DT, {"desligado": 0}, "name", order_by="ordem asc")
    frappe.local.orbit_funil_omissao = n
    return n


def tipo(fase: str | None) -> str | None:
    return next((s.type for s in _todas() if s.name == fase), None) if fase else None


def funil_da_fase(fase: str | None) -> str | None:
    return next((s.orbit_funil for s in _todas() if s.name == fase), None) if fase else None


def fases(funil: str | None = None) -> list:
    """As fases de um funil, pela ordem (sem funil = o por omissão)."""
    funil = funil or omissao()
    return [s for s in _todas() if (s.orbit_funil or omissao()) == funil]


def fechadas(funil: str | None = None) -> list[str]:
    """Nomes de todas as fases de tipo ganho/perdido (de todos os funis, ou de um)."""
    base = fases(funil) if funil else _todas()
    return [s.name for s in base if s.type in FECHADOS]


def ganhas(funil: str | None = None) -> list[str]:
    base = fases(funil) if funil else _todas()
    return [s.name for s in base if s.type == "Won"]


def perdidas(funil: str | None = None) -> list[str]:
    base = fases(funil) if funil else _todas()
    return [s.name for s in base if s.type == "Lost"]


def primeira(funil: str | None = None) -> str | None:
    fs = fases(funil)
    return next((s.name for s in fs if s.type not in FECHADOS), None) or (fs[0].name if fs else None)


def do_tipo(funil: str | None, t: str) -> str | None:
    return next((s.name for s in fases(funil) if s.type == t), None)


def equivalente(funil: str | None, fase: str | None) -> str | None:
    """A fase deste funil que corresponde a `fase` (a própria se for do funil; ganho/perdido pelo tipo; senão None)."""
    if not fase:
        return None
    funil = funil or omissao()
    nomes = [s.name for s in fases(funil)]
    if fase in nomes:
        return fase
    t = tipo(fase) or (fase if fase in FECHADOS else None)
    if t in FECHADOS:
        return do_tipo(funil, t)
    return None


def visiveis(marca: str | None = None) -> list[dict]:
    """Funis ligados para o seletor (com marca: os sem marcas e os dessa marca)."""
    if not frappe.db.exists("DocType", DT):
        return []
    out = []
    for f in frappe.get_all(DT, filters={"desligado": 0}, fields=["name", "nome", "por_omissao", "mostra_valor", "cor", "ordem"],
                            order_by="ordem asc, nome asc"):
        ms = frappe.get_all("Marca do Contacto", filters={"parent": f.name, "parenttype": DT}, pluck="marca")
        if marca and ms and marca not in ms:
            continue
        f.marcas = ms
        out.append(f)
    return out


# ── regras ───────────────────────────────────────────────────────────────────────────────────────────────────
def antes_de_validar(doc, method=None):
    """CRM Deal (before_validate): funil sempre preenchido e fase sempre do funil do negócio."""
    if not doc.meta.has_field("orbit_funil"):
        return
    if not doc.orbit_funil or not frappe.db.exists(DT, doc.orbit_funil):
        doc.orbit_funil = funil_da_fase(doc.status) or omissao()
    mudou_funil = not doc.is_new() and doc.has_value_changed("orbit_funil")
    if doc.status and funil_da_fase(doc.status) not in (None, doc.orbit_funil):
        novo = equivalente(doc.orbit_funil, doc.status)
        if not novo:
            # fase aberta de outro funil: se o que mudou foi a fase (e não o funil), o negócio passa a esse funil
            if not mudou_funil and not doc.is_new() and doc.has_value_changed("status"):
                doc.orbit_funil = funil_da_fase(doc.status)
                novo = doc.status
                mudou_funil = True
            else:
                novo = primeira(doc.orbit_funil)
        doc.status = novo
    elif not doc.status:
        doc.status = primeira(doc.orbit_funil)
    t = tipo(doc.status)
    if doc.meta.has_field("orbit_tipo_fase"):
        doc.orbit_tipo_fase = t
    # o Frappe CRM só põe a data de fecho quando a fase se chama «Won»
    if t == "Won" and not doc.closed_date:
        doc.closed_date = nowdate()
    if mudou_funil:
        doc.add_comment("Info", f"Passou para o funil «{doc.orbit_funil}».")


def fase_actualizada(doc, method=None):
    """CRM Deal Status (on_update): o tipo copiado para os negócios e cache do pedido limpa."""
    _esquecer()
    if frappe.db.has_column("CRM Deal", "orbit_tipo_fase"):
        frappe.db.sql("update `tabCRM Deal` set orbit_tipo_fase=%s where status=%s", (doc.type, doc.name))


def fase_antes_de_gravar(doc, method=None):
    """CRM Deal Status (validate): fase nova sem funil vai para o por omissão."""
    if doc.meta.has_field("orbit_funil") and not doc.orbit_funil:
        doc.orbit_funil = omissao()


def validar_funil(doc):
    if not doc.nome or not doc.nome.strip():
        frappe.throw("Escreva o nome do funil.")
    if "·" in doc.nome:
        frappe.throw("O nome do funil não pode ter «·».")
    if cint(doc.por_omissao):
        if cint(doc.desligado):
            frappe.throw("O funil por omissão não pode estar desligado.")
        frappe.db.sql(f"update `tab{DT}` set por_omissao=0 where name<>%s", doc.name or "")
    elif not frappe.db.get_value(DT, {"por_omissao": 1, "name": ["!=", doc.name or ""]}):
        doc.por_omissao = 1   # há sempre um por omissão
    _esquecer()


# ── compras ligadas a um negócio (N4) ───────────────────────────────────────────────────────────────────────
def compra_submetida(doc, method=None):
    """Purchase Order (on_submit): o negócio ligado fica com o valor das encomendas e passa a ganho (adjudicado)."""
    neg = doc.get("orbit_negocio")
    if not neg or not frappe.db.exists("CRM Deal", neg):
        return
    total = sum(frappe.get_all("Purchase Order", filters={"orbit_negocio": neg, "docstatus": 1}, pluck="net_total"))
    d = frappe.get_doc("CRM Deal", neg)
    d.deal_value = total
    if tipo(d.status) not in FECHADOS:
        g = do_tipo(d.orbit_funil, "Won")
        if g:
            d.status = g
            d.probability = 100
    d.flags.ignore_permissions = True
    d.save()
    d.add_comment("Info", f"Encomenda a fornecedor {doc.name} submetida ({doc.net_total:.2f} €).")
