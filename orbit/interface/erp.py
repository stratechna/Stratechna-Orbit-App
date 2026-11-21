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
            if frappe.db.exists("Report", i.link_to) and frappe.has_permission("Report", "read"):
                atual["itens"].append({"tipo": "desk", "rotulo": _(i.label or i.link_to),
                                       "url": "/desk/query-report/" + i.link_to if frappe.db.get_value("Report", i.link_to, "report_type") != "Report Builder"
                                       else "/desk/" + frappe.scrub(frappe.db.get_value("Report", i.link_to, "ref_doctype") or "").replace("_", "-") + "/view/report",
                                       "icone": i.icon})
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
