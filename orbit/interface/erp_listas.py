# Listas do ERP na interface nova (/orbit) — lote 4 do plano das opções dos originais (25-11-2026)
#
# docs/PLANO-ORBIT-OPCOES-DOS-ORIGINAIS.md §3, lote 4: o que a lista do desk do Frappe tem e a lista genérica do /orbit
# não tinha — filtros por qualquer campo com os operadores do Frappe, contagem total, colunas à escolha, ordem,
# vistas guardadas (pessoais e da equipa), selecção e acções em massa (editar um campo, atribuir, etiqueta, submeter,
# cancelar, apagar, PDF em lote) e exportar. Tudo por frappe.get_list / doc.save / frappe.delete_doc, com as
# permissões de quem está a usar — o browser nunca escreve SQL: os campos têm de existir na definição.
import csv
import io
import json

import frappe
from frappe import _
from frappe.utils import cint

from orbit.interface.api import _guarda

OPS = {"=": "=", "!=": "!=", "like": "like", "not like": "not like", ">": ">", "<": "<", ">=": ">=", "<=": "<=",
       "in": "in", "not in": "not in", "is": "is", "between": "between", "timespan": "timespan"}
SEM_COLUNA = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Heading", "Table", "Table MultiSelect",
              "Fold", "Image", "Code", "Text Editor", "HTML Editor", "Markdown Editor", "JSON", "Signature", "Geolocation"}
PERIODOS = {"hoje": "today", "ontem": "yesterday", "esta_semana": "this week", "este_mes": "this month", "este_ano": "this year",
            "semana_passada": "last week", "mes_passado": "last month", "ultimos_7": "last 7 days", "ultimos_30": "last 30 days",
            "ano_passado": "last year", "proxima_semana": "next week", "proximo_mes": "next month"}


def _ler_dt(doctype):
    _guarda()
    if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
        frappe.throw(_("Sem acesso a esta lista."), frappe.PermissionError)
    return frappe.get_meta(doctype)


def _filtros(m, filtros):
    out = []
    for f in (json.loads(filtros) if isinstance(filtros, str) else (filtros or []))[:20]:
        if len(f) < 2:
            continue
        c, op = f[0], OPS.get(str(f[1]).lower())
        v = f[2] if len(f) > 2 else None
        if not op or not (m.has_field(c) or c in ("name", "owner", "creation", "modified", "docstatus", "_assign", "_user_tags")):
            continue
        if op == "timespan":
            v = PERIODOS.get(v, v)
        if op in ("like", "not like") and v and "%" not in str(v):
            v = f"%{v}%"
        if op == "is":
            v = "set" if v in ("set", "preenchido", 1, "1") else "not set"
        out.append([m.name, c, op, v])
    return out


@frappe.whitelist()
def definicao(doctype: str):
    """Os campos que se podem filtrar e mostrar como coluna, com o tipo e as opções."""
    m = _ler_dt(doctype)
    campos = []
    for f in m.fields:
        if f.fieldtype in SEM_COLUNA or f.hidden and not f.in_standard_filter:
            continue
        campos.append({"campo": f.fieldname, "rotulo": _(f.label or f.fieldname), "tipo": f.fieldtype,
                       "opcoes": [o for o in (f.options or "").split("\n") if o] if f.fieldtype == "Select" else None,
                       "liga": f.options if f.fieldtype in ("Link", "Dynamic Link") else None,
                       "padrao": bool(f.in_list_view), "filtro": bool(f.in_standard_filter)})
    campos += [{"campo": "owner", "rotulo": _("Criado por"), "tipo": "Link", "liga": "User"},
               {"campo": "creation", "rotulo": _("Criado em"), "tipo": "Datetime"},
               {"campo": "modified", "rotulo": _("Alterado em"), "tipo": "Datetime"},
               {"campo": "_assign", "rotulo": _("Atribuído a"), "tipo": "Data"},
               {"campo": "_user_tags", "rotulo": _("Etiquetas"), "tipo": "Data"}]
    if m.is_submittable:
        campos.append({"campo": "docstatus", "rotulo": _("Estado do documento"), "tipo": "Select",
                       "opcoes": None, "opcoes_v": [{"v": 0, "r": _("Rascunho")}, {"v": 1, "r": _("Submetido")}, {"v": 2, "r": _("Cancelado")}]})
    # lote 6/7: vista em árvore, Kanban (por um campo de escolha) e Calendário (por um campo de data)
    escolha = [f.fieldname for f in m.fields if f.fieldtype == "Select" and f.options and not f.hidden and len([o for o in f.options.split("\n") if o]) <= 12]
    datas = [f.fieldname for f in m.fields if f.fieldtype in ("Date", "Datetime") and not f.hidden]
    return {"campos": campos, "submetivel": bool(m.is_submittable), "arvore": bool(m.is_tree),
            "processo": PROCESSO.get(doctype),
            "kanban": (["status"] if "status" in escolha else []) + [c for c in escolha if c != "status"], "calendario": datas, "pode": {
        "apagar": frappe.has_permission(doctype, "delete"), "escrever": frappe.has_permission(doctype, "write"),
        "submeter": bool(m.is_submittable and frappe.has_permission(doctype, "submit")),
        "cancelar": bool(m.is_submittable and frappe.has_permission(doctype, "cancel")),
        "exportar": frappe.has_permission(doctype, "export") or frappe.has_permission(doctype, "read"),
        "imprimir": frappe.has_permission(doctype, "print") or frappe.has_permission(doctype, "read")}}


# 27-11-2026 (N5 do plano dos funis): o funil do PROCESSO destes documentos — colunas do estado pela ordem do caminho
# (as de fim que já não interessam ficam de fora); o estado muda pelas acções do documento, não arrastando.
PROCESSO = {
    "Purchase Order": ["Draft", "On Hold", "To Receive and Bill", "To Receive", "To Bill", "Completed"],
    "Sales Order": ["Draft", "On Hold", "To Deliver and Bill", "To Deliver", "To Bill", "Completed"],
    "Supplier Quotation": ["Draft", "Submitted", "Ordered", "Expired"],
    "Request for Quotation": ["Draft", "Submitted"],
    "Quotation": ["Draft", "Open", "Replied", "Partially Ordered", "Ordered", "Lost", "Expired"],
    "Purchase Invoice": ["Draft", "Unpaid", "Overdue", "Partly Paid", "Paid", "Debit Note Issued", "Return"],
    "Sales Invoice": ["Draft", "Unpaid", "Overdue", "Partly Paid", "Paid", "Credit Note Issued", "Return"],
    "Purchase Receipt": ["Draft", "To Bill", "Completed"],
    "Delivery Note": ["Draft", "To Bill", "Completed"],
}


@frappe.whitelist()
def lista(doctype: str, q: str = None, filtros: str = None, pagina: int = 0, ordem: str = None, colunas: str = None,
          por: int = 50):
    """Como erp.lista, com colunas à escolha, todos os operadores e a contagem total."""
    m = _ler_dt(doctype)
    titulo = m.title_field if m.title_field and m.has_field(m.title_field) else None
    escolhidas = [c for c in (json.loads(colunas) if colunas else []) if isinstance(c, str) and (m.has_field(c) or c in ("owner", "creation", "modified", "_assign", "_user_tags"))]
    if not escolhidas:
        escolhidas = [f.fieldname for f in m.fields if f.in_list_view and f.fieldtype not in SEM_COLUNA and f.fieldname != titulo][:6]
    campos = ["name", "modified"] + ([titulo] if titulo else []) + escolhidas
    if m.is_submittable:
        campos.append("docstatus")
    if m.has_field("status") and "status" not in campos:
        campos.append("status")
    f = _filtros(m, filtros)
    ou = None
    if q and q.strip():
        alvo = f"%{q.strip()}%"
        ou = [[doctype, "name", "like", alvo]] + [[doctype, c, "like", alvo] for c in
                                                   ([titulo] if titulo else []) + [s.strip() for s in (m.search_fields or "").split(",") if s.strip() and m.has_field(s.strip())]]
    por = max(10, min(cint(por) or 50, 500))
    o = (ordem or "modified desc").split(" ")
    ordem = f"{o[0]} {o[-1]}" if (m.has_field(o[0]) or o[0] in ("name", "modified", "creation")) and o[-1] in ("asc", "desc") else "modified desc"
    linhas = frappe.get_list(doctype, fields=list(dict.fromkeys(campos)), filters=f, or_filters=ou, order_by=ordem,
                             start=cint(pagina) * por, page_length=por + 1)
    total = frappe.get_list(doctype, filters=f, or_filters=ou, fields=[{"COUNT": "name", "as": "n"}], limit=1)   # Frappe 16: funções em dict
    return {"linhas": linhas[:por], "mais": len(linhas) > por, "colunas": escolhidas, "titulo": titulo,
            "total": (total[0].n if total else 0)}


# ── vistas guardadas (as mesmas preferências do Frappe que as listas do CRM usam) ─────────────────────
def _chave(doctype, equipa=False):
    return f"orbit_vistas_{'eq_' if equipa else ''}erp_{frappe.scrub(doctype)}"


def _ler_v(chave, global_=False):
    v = frappe.defaults.get_global_default(chave) if global_ else frappe.defaults.get_user_default(chave)
    try:
        return json.loads(v) if v else []
    except ValueError:
        return []


@frappe.whitelist()
def vistas(doctype: str):
    _ler_dt(doctype)
    padrao = frappe.defaults.get_user_default(_chave(doctype) + "_padrao") or ""
    return {"vistas": [{**v, "equipa": False} for v in _ler_v(_chave(doctype))] + [{**v, "equipa": True} for v in _ler_v(_chave(doctype, True), True)],
            "padrao": padrao}


@frappe.whitelist(methods=["POST"])
def vista_gravar(doctype: str, nome: str, config: str, equipa: int = 0, antigo: str = None):
    _ler_dt(doctype)
    nome = (nome or "").strip()[:60]
    if not nome:
        frappe.throw(_("Dê um nome à vista."))
    c = json.loads(config or "{}")
    cfg = {"filtros": c.get("filtros") or [], "colunas": [x for x in (c.get("colunas") or []) if isinstance(x, str)][:15],
           "ordem": str(c.get("ordem") or "")[:80], "q": str(c.get("q") or "")[:80]}
    k = _chave(doctype, bool(cint(equipa)))
    if cint(equipa) and not frappe.has_permission(doctype, "write"):
        frappe.throw(_("Sem permissão para partilhar vistas com a equipa."), frappe.PermissionError)
    lst = [v for v in _ler_v(k, bool(cint(equipa))) if v.get("nome") not in (nome, antigo)]
    lst.append({"nome": nome, "config": cfg, "por": frappe.session.user})
    (frappe.defaults.set_global_default if cint(equipa) else frappe.defaults.set_user_default)(k, json.dumps(lst[-40:]))
    return vistas(doctype)


@frappe.whitelist(methods=["POST"])
def vista_apagar(doctype: str, nome: str, equipa: int = 0):
    _ler_dt(doctype)
    if cint(equipa) and not frappe.has_permission(doctype, "write"):
        frappe.throw(_("Sem permissão."), frappe.PermissionError)
    k = _chave(doctype, bool(cint(equipa)))
    (frappe.defaults.set_global_default if cint(equipa) else frappe.defaults.set_user_default)(
        k, json.dumps([v for v in _ler_v(k, bool(cint(equipa))) if v.get("nome") != nome]))
    return vistas(doctype)


@frappe.whitelist(methods=["POST"])
def vista_padrao(doctype: str, nome: str = ""):
    _ler_dt(doctype)
    frappe.defaults.set_user_default(_chave(doctype) + "_padrao", nome or "")
    return vistas(doctype)


# ── acções em massa ──────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist(methods=["POST"])
def em_massa(doctype: str, nomes: str, acao: str, campo: str = None, valor: str = None):
    m = _ler_dt(doctype)
    lista = [n for n in json.loads(nomes or "[]")][:500]
    feitos, falhas = 0, []
    if acao == "editar" and (not campo or not m.has_field(campo) or m.get_field(campo).fieldtype in SEM_COLUNA or m.get_field(campo).read_only):
        frappe.throw(_("Este campo não se pode editar em massa."))
    for i, n in enumerate(lista):
        sp = f"orbit_massa_{i}"
        frappe.db.savepoint(sp)
        try:
            if acao == "apagar":
                frappe.delete_doc(doctype, n)
            elif acao == "atribuir":
                from frappe.desk.form.assign_to import add
                add({"doctype": doctype, "name": n, "assign_to": [valor]})
            elif acao == "etiqueta":
                from frappe.desk.doctype.tag.tag import add_tag
                add_tag(valor, doctype, n)
            else:
                d = frappe.get_doc(doctype, n)
                if acao == "editar":
                    d.check_permission("write")
                    d.set(campo, valor if valor not in ("",) else None)
                    d.save()
                elif acao == "submeter":
                    if d.docstatus == 0:
                        d.submit()
                elif acao == "cancelar":
                    if d.docstatus == 1:
                        d.cancel()
                else:
                    frappe.throw(_("Ação desconhecida."))
            feitos += 1
        except Exception as e:  # noqa: BLE001 — continua com os outros e relata
            frappe.db.rollback(save_point=sp)   # só desfaz este registo; os anteriores ficam
            falhas.append({"name": n, "erro": str(e)[:200]})
    return {"feitos": feitos, "falhas": falhas}


@frappe.whitelist()
def exportar(doctype: str, q: str = None, filtros: str = None, ordem: str = None, colunas: str = None, nomes: str = None):
    """CSV («;», UTF-8 com BOM para o Excel) com as colunas da vista; até 10 000 linhas."""
    m = _ler_dt(doctype)
    if not (frappe.has_permission(doctype, "export") or frappe.has_permission(doctype, "read")):
        frappe.throw(_("Sem permissão."), frappe.PermissionError)
    f = _filtros(m, filtros)
    sel = json.loads(nomes) if nomes else []
    if sel:
        f.append([doctype, "name", "in", sel])
    r = lista(doctype, q=q, filtros=json.dumps([x[1:] for x in f]), ordem=ordem, colunas=colunas, por=500)
    cols = ["name"] + ([r["titulo"]] if r["titulo"] else []) + r["colunas"]
    linhas = r["linhas"]
    pagina = 1
    while r["mais"] and len(linhas) < 10000:
        r = lista(doctype, q=q, filtros=json.dumps([x[1:] for x in f]), ordem=ordem, colunas=colunas, por=500, pagina=pagina)
        linhas += r["linhas"]
        pagina += 1
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([_(m.get_field(c).label) if m.get_field(c) else c for c in cols])
    for ln in linhas:
        w.writerow([ln.get(c, "") if ln.get(c) is not None else "" for c in cols])
    frappe.response["filename"] = f"{frappe.scrub(doctype)}.csv"
    frappe.response["filecontent"] = "﻿" + buf.getvalue()
    frappe.response["type"] = "download"


# ── importar (o «Data Import» do Frappe, sem o ecrã antigo) ─────────────────────────────────────────
@frappe.whitelist()
def importar_modelo(doctype: str):
    """Os campos que o modelo de importação leva: obrigatórios e os da lista (como o «Download Template» sugere)."""
    m = _ler_dt(doctype)
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("Sem permissão para importar."), frappe.PermissionError)
    campos = [f.fieldname for f in m.fields if f.fieldtype not in SEM_COLUNA and not f.read_only and not f.hidden
              and (f.reqd or f.in_list_view or f.in_standard_filter or f.bold)]
    todos = [{"campo": f.fieldname, "rotulo": _(f.label or f.fieldname), "obrigatorio": cint(f.reqd)}
             for f in m.fields if f.fieldtype not in SEM_COLUNA and not f.read_only and not f.hidden]
    return {"campos": campos, "todos": todos}


@frappe.whitelist(methods=["POST"])
def importar_novo(doctype: str, ficheiro: str, tipo: str = "Insert New Records", submeter: int = 0):
    _ler_dt(doctype)
    if not frappe.has_permission(doctype, "create") or not frappe.has_permission("Data Import", "create"):
        frappe.throw(_("Sem permissão para importar."), frappe.PermissionError)
    if tipo not in ("Insert New Records", "Update Existing Records"):
        frappe.throw(_("Tipo de importação inválido."))
    d = frappe.get_doc({"doctype": "Data Import", "reference_doctype": doctype, "import_type": tipo, "import_file": ficheiro,
                        "submit_after_import": cint(submeter), "mute_emails": 1}).insert()
    return {"name": d.name}
