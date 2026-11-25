# O que qualquer registo tem no ecrã antigo, na interface nova (/orbit) — lote 1 do plano das opções dos originais (25-11-2026)
#
# docs/PLANO-ORBIT-OPCOES-DOS-ORIGINAIS.md §3, lote 1: anexos, histórico de alterações, atribuir a várias pessoas,
# etiquetas, partilhar, seguir, ligações do documento, duplicar, corrigir (amend), mudar o nome, anterior/seguinte,
# imprimir com formato/papel timbrado/língua e enviar por email com o PDF. Tudo pelas funções do Frappe, com as
# permissões do próprio utilizador — nada é feito como Administrator.
import json

import frappe
from frappe import _
from frappe.utils import cint, get_url, strip_html

from orbit.interface.api import _guarda as _guarda_sessao

LINGUAS = [("pt", "Português"), ("en", "English"), ("es", "Español"), ("fr", "Français")]
SEM_LIGACOES = {"Version", "Comment", "Communication", "File", "ToDo", "DocShare", "Activity Log", "Access Log",
                "View Log", "Document Follow", "Notification Log", "Email Queue", "Tag Link", "Communication Link",
                "Dynamic Link", "Error Log", "Deleted Document", "Payment Ledger Entry", "GL Entry", "Stock Ledger Entry",
                "Serial and Batch Bundle", "Repost Item Valuation", "Repost Payment Ledger", "Repost Accounting Ledger"}
# o «de onde veio» só mostra documentos e partes, não tabelas de configuração
NAO_ORIGEM = {"User", "Territory", "Customer Group", "Supplier Group", "Item Group", "Mode of Payment", "Payment Terms Template",
              "Tax Category", "Sales Taxes and Charges Template", "Purchase Taxes and Charges Template", "Shipping Rule",
              "Incoterm", "Print Heading", "Letter Head", "Terms and Conditions", "Role", "Module Def", "DocType", "Department",
              "Designation", "Holiday List", "Market Segment", "Industry Type", "Lead Source", "Opportunity Type"}


def _guarda(doctype, name, perm="read"):
    _guarda_sessao()
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("Registo não encontrado."), frappe.DoesNotExistError)
    if not frappe.has_permission(doctype, perm, name):
        frappe.throw(_("Sem permissão."), frappe.PermissionError)
    return frappe.get_doc(doctype, name)


def _nome(u):
    if not u:
        return ""
    return frappe.db.get_value("User", u, "full_name") or u


def _anexos(doctype, name):
    out = []
    for f in frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": name, "is_folder": 0},
                            fields=["name", "file_name", "file_url", "is_private", "file_size", "creation", "owner",
                                    "attached_to_field"], order_by="creation desc"):
        out.append({"id": f.name, "nome": f.file_name, "url": f.file_url, "privado": cint(f.is_private),
                    "tamanho": f.file_size or 0, "quando": str(f.creation), "quem": _nome(f.owner), "campo": f.attached_to_field})
    return out


@frappe.whitelist()
def extras(doctype: str, name: str):
    """Tudo o que a barra lateral do registo mostra, numa chamada."""
    doc = _guarda(doctype, name)
    meta = frappe.get_meta(doctype)
    from frappe.desk.form.assign_to import get as atribuidos
    from frappe.desk.form.document_follow import is_document_followed
    from frappe.share import get_users
    atr = [{"utilizador": a.get("owner"), "nome": _nome(a.get("owner"))} for a in (atribuidos({"doctype": doctype, "name": name}) or [])]
    tags = [t for t in (doc.get("_user_tags") or "").split(",") if t]
    partilhas = [{"utilizador": s.user, "nome": _nome(s.user) if s.user else _("Todos"), "ler": cint(s.read),
                  "escrever": cint(s.write), "partilhar": cint(s.share), "todos": cint(s.everyone)} for s in get_users(doctype, name)]
    formatos = frappe.get_all("Print Format", filters={"doc_type": doctype, "disabled": 0}, pluck="name", order_by="name asc")
    padrao = meta.default_print_format or (formatos[0] if formatos else "Standard")
    if "Standard" not in formatos:
        formatos = ["Standard"] + formatos
    cabecalhos = frappe.get_all("Letter Head", filters={"disabled": 0}, fields=["name", "is_default"], order_by="is_default desc, name asc")
    ds = cint(doc.get("docstatus")) if meta.is_submittable else 0
    return {
        "anexos": _anexos(doctype, name),
        "atribuidos": atr, "etiquetas": tags, "partilhas": partilhas,
        "seguir": bool(is_document_followed(doctype, name, frappe.session.user)),
        "impressao": {"formatos": formatos, "padrao": padrao, "cabecalhos": [c.name for c in cabecalhos],
                      "cabecalho": (cabecalhos[0].name if cabecalhos and cabecalhos[0].is_default else ""),
                      "linguas": [{"v": v, "r": r} for v, r in LINGUAS], "lingua": frappe.local.lang or "pt"},
        "pode": {"escrever": frappe.has_permission(doctype, "write", name), "apagar": frappe.has_permission(doctype, "delete", name),
                 "partilhar": frappe.has_permission(doctype, "share", name), "criar": frappe.has_permission(doctype, "create"),
                 "email": frappe.has_permission(doctype, "email", name) or frappe.has_permission(doctype, "read", name),
                 "imprimir": frappe.has_permission(doctype, "print", name) or frappe.has_permission(doctype, "read", name),
                 "corrigir": bool(meta.is_submittable and ds == 2 and frappe.has_permission(doctype, "amend", name)),
                 "renomear": bool(meta.allow_rename and frappe.has_permission(doctype, "write", name))},
        "url": get_url(f"/orbit#/erp/{doctype}/{name}"),
    }


# ── histórico ────────────────────────────────────────────────────────────────────────────────────────
_VAZIOS = (None, "", 0, 0.0, "0", "0.0", "0.000", "[]", "{}")


def _txt(v):
    if v in (None, ""):
        return "—"
    s = strip_html(str(v)) if isinstance(v, str) else str(v)
    return s if len(s) <= 140 else s[:137] + "…"


@frappe.whitelist()
def historico(doctype: str, name: str, limite: int = 60):
    """As alterações gravadas (Version) e a criação: quem, quando, que campo, de quê para quê."""
    doc = _guarda(doctype, name)
    meta = frappe.get_meta(doctype)

    def rot(campo, m=meta):
        f = m.get_field(campo)
        return _(f.label) if f and f.label else campo

    out = []
    for v in frappe.get_all("Version", filters={"ref_doctype": doctype, "docname": name}, fields=["owner", "creation", "data"],
                            order_by="creation desc", limit=cint(limite) or 60):
        try:
            d = json.loads(v.data or "{}")
        except Exception:  # noqa: BLE001
            continue
        alt = []
        for c in d.get("changed") or []:
            # «0 → vazio» e semelhantes não são alterações que alguém tenha feito (o ERPNext grava-as ao submeter)
            if len(c) >= 3 and c[0] not in ("modified", "modified_by") and not (c[1] in _VAZIOS and c[2] in _VAZIOS):
                if c[0] == "docstatus":
                    alt.append({"campo": _("Estado"), "de": {0: _("Rascunho"), 1: _("Submetido"), 2: _("Cancelado")}.get(cint(c[1]), c[1]),
                                "para": {0: _("Rascunho"), 1: _("Submetido"), 2: _("Cancelado")}.get(cint(c[2]), c[2])})
                else:
                    alt.append({"campo": rot(c[0]), "de": _txt(c[1]), "para": _txt(c[2])})
        for chave, verbo in (("added", _("Linha acrescentada")), ("removed", _("Linha retirada"))):
            for r in d.get(chave) or []:
                if len(r) >= 2:
                    alt.append({"campo": rot(r[0]), "acao": verbo})
        for r in d.get("row_changed") or []:
            if len(r) >= 4:
                tab = meta.get_field(r[0])
                fm = frappe.get_meta(tab.options) if tab and tab.options else meta
                for c in r[3] or []:
                    if len(c) >= 3 and not (c[1] in _VAZIOS and c[2] in _VAZIOS):
                        alt.append({"campo": f"{rot(r[0])} · {_('linha')} {r[1]} · {rot(c[0], fm)}", "de": _txt(c[1]), "para": _txt(c[2])})
        if alt:
            out.append({"quem": _nome(v.owner), "quando": str(v.creation), "alteracoes": alt[:30]})
    out.append({"quem": _nome(doc.owner), "quando": str(doc.creation), "criado": True, "alteracoes": []})
    return out


# ── anexos ───────────────────────────────────────────────────────────────────────────────────────────
def _guarda_anexo(fid, perm="write"):
    f = frappe.get_doc("File", fid)
    if not f.attached_to_doctype:
        frappe.throw(_("Este ficheiro não está ligado a um registo."))
    _guarda(f.attached_to_doctype, f.attached_to_name, perm)
    return f


@frappe.whitelist(methods=["POST"])
def anexo_privado(id: str, privado: int):
    f = _guarda_anexo(id)
    f.is_private = cint(privado)
    f.save()
    return _anexos(f.attached_to_doctype, f.attached_to_name)


@frappe.whitelist(methods=["POST"])
def anexo_apagar(id: str):
    f = _guarda_anexo(id)
    dt, dn = f.attached_to_doctype, f.attached_to_name
    if f.attached_to_field:
        # anexo de um campo: esvazia o campo também (como o ecrã antigo)
        frappe.db.set_value(dt, dn, f.attached_to_field, None)
    frappe.delete_doc("File", f.name)
    return _anexos(dt, dn)


# ── atribuir, etiquetas, partilhar, seguir ───────────────────────────────────────────────────────────
@frappe.whitelist(methods=["POST"])
def atribuir(doctype: str, name: str, utilizadores: str, nota: str = None):
    _guarda(doctype, name)
    from frappe.desk.form.assign_to import add
    lista = [u for u in json.loads(utilizadores or "[]") if u]
    if lista:
        add({"doctype": doctype, "name": name, "assign_to": lista, "description": nota or ""})
    return extras(doctype, name)


@frappe.whitelist(methods=["POST"])
def desatribuir(doctype: str, name: str, utilizador: str):
    _guarda(doctype, name)
    from frappe.desk.form.assign_to import remove
    remove(doctype, name, utilizador)
    return extras(doctype, name)


@frappe.whitelist(methods=["POST"])
def etiqueta(doctype: str, name: str, etiqueta: str, tirar: int = 0):
    _guarda(doctype, name)
    from frappe.desk.doctype.tag.tag import add_tag, remove_tag
    t = (etiqueta or "").strip()
    if t:
        (remove_tag if cint(tirar) else add_tag)(t, doctype, name)
    return extras(doctype, name)


@frappe.whitelist()
def etiquetas_sugeridas(doctype: str, q: str = ""):
    _guarda_sessao()
    from frappe.desk.doctype.tag.tag import get_tags
    return get_tags(doctype, q or "")[:20]


@frappe.whitelist(methods=["POST"])
def partilhar(doctype: str, name: str, utilizador: str = None, ler: int = 1, escrever: int = 0, partilhar: int = 0,
              todos: int = 0, tirar: int = 0):
    _guarda(doctype, name, "share")
    from frappe import share
    if cint(tirar):
        share.remove(doctype, name, utilizador) if utilizador else share.set_permission(doctype, name, None, "read", 0, everyone=1)
    else:
        share.add(doctype, name, user=None if cint(todos) else utilizador, read=cint(ler), write=cint(escrever),
                  share=cint(partilhar), everyone=cint(todos), notify=1)
    return extras(doctype, name)


@frappe.whitelist(methods=["POST"])
def seguir(doctype: str, name: str, seguir: int = 1):
    _guarda(doctype, name)
    from frappe.desk.form.document_follow import follow_document, unfollow_document
    (follow_document if cint(seguir) else unfollow_document)(doctype, name)
    return {"seguir": bool(cint(seguir))}


# ── ligações do documento ────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def ligacoes(doctype: str, name: str):
    """O que aponta para este registo (as «Connections» do ecrã antigo), por tipo, só o que o utilizador pode ler."""
    doc = _guarda(doctype, name)
    from frappe.desk.form.linked_with import get as ligados
    out = []
    try:
        res = ligados(doctype, name) or {}
    except Exception:  # noqa: BLE001
        res = {}
    for dt, bloco in res.items():
        linhas = (bloco.get("docs") if isinstance(bloco, dict) else bloco) or []   # Frappe 16: {"docs": [...], "hidden_count": n}
        if dt in SEM_LIGACOES or not linhas or not frappe.has_permission(dt, "read"):
            continue
        m = frappe.get_meta(dt)
        itens = []
        for r in linhas[:30]:
            titulo = r.get(m.title_field) if m.title_field else None
            itens.append({"name": r.get("name"), "titulo": titulo or r.get("name"),
                          "estado": r.get("status") or {0: _("Rascunho"), 1: _("Submetido"), 2: _("Cancelado")}.get(cint(r.get("docstatus")), ""),
                          "data": str(r.get("modified") or "")})
        if itens:
            out.append({"doctype": dt, "rotulo": _(dt), "n": len(linhas), "itens": itens})
    # de onde veio: campos de ligação preenchidos na cabeça (cliente, encomenda, orçamento…) e as origens das linhas
    origem = []
    vistos = set()
    meta = frappe.get_meta(doctype)
    for f in meta.fields:
        if f.fieldtype == "Link" and f.options and doc.get(f.fieldname) and f.options not in SEM_LIGACOES \
                and f.options not in ("Company", "Currency", "Price List", "Account", "Cost Center", "Warehouse", "UOM",
                                      "Print Heading", "Letter Head", "Naming Series", "Language", "Country", "Fiscal Year"):
            chave = (f.options, doc.get(f.fieldname))
            if f.options in NAO_ORIGEM or f.options.endswith((" Status", " Type", " Group", " Template")) or frappe.get_meta(f.options).issingle:
                continue
            if chave not in vistos and frappe.has_permission(f.options, "read"):
                vistos.add(chave)
                origem.append({"doctype": f.options, "rotulo": _(f.label or f.options), "name": doc.get(f.fieldname)})
    for t in meta.get_table_fields():
        fm = frappe.get_meta(t.options)
        for lf in fm.fields:
            if lf.fieldtype == "Link" and lf.options in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice", "Purchase Order",
                                                       "Purchase Receipt", "Purchase Invoice", "Material Request"):
                for linha in doc.get(t.fieldname) or []:
                    v = linha.get(lf.fieldname)
                    if v and (lf.options, v) not in vistos and frappe.has_permission(lf.options, "read"):
                        vistos.add((lf.options, v))
                        origem.append({"doctype": lf.options, "rotulo": _(lf.options), "name": v})
    return {"ligados": out, "origem": origem[:40]}


# ── duplicar, corrigir, mudar o nome, anterior/seguinte ──────────────────────────────────────────────
_LIMPAR = ("name", "docstatus", "amended_from", "creation", "modified", "owner", "modified_by", "_user_tags", "_comments",
           "_assign", "_liked_by", "_seen", "status", "outstanding_amount", "per_billed", "per_delivered", "per_received")


def _copia(doc):
    novo = frappe.copy_doc(doc).as_dict()
    for k in _LIMPAR:
        novo.pop(k, None)
    for t in frappe.get_meta(doc.doctype).get_table_fields():
        for linha in novo.get(t.fieldname) or []:
            for k in ("name", "parent", "creation", "modified", "owner", "modified_by", "docstatus"):
                linha.pop(k, None)
    novo["doctype"] = doc.doctype
    novo["__islocal"] = 1
    return novo


@frappe.whitelist(methods=["POST"])
def duplicar(doctype: str, name: str):
    """Uma cópia por gravar (o ecrã abre-a como «novo»), como «Duplicar» do ecrã antigo."""
    doc = _guarda(doctype, name)
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("Sem permissão para criar."), frappe.PermissionError)
    return {"doc": _copia(doc)}


@frappe.whitelist(methods=["POST"])
def corrigir(doctype: str, name: str):
    """«Corrigir» (Amend) um documento cancelado: cópia por gravar com amended_from."""
    doc = _guarda(doctype, name)
    if cint(doc.docstatus) != 2 or not frappe.has_permission(doctype, "amend", name):
        frappe.throw(_("Só se corrige um documento cancelado."))
    novo = _copia(doc)
    novo["amended_from"] = doc.name
    return {"doc": novo}


@frappe.whitelist(methods=["POST"])
def renomear(doctype: str, name: str, novo: str, juntar: int = 0):
    _guarda(doctype, name, "write")
    if not frappe.get_meta(doctype).allow_rename:
        frappe.throw(_("Este tipo de registo não permite mudar o nome."))
    novo = (novo or "").strip()
    if not novo or novo == name:
        return {"name": name}
    return {"name": frappe.rename_doc(doctype, name, novo, merge=cint(juntar))}


@frappe.whitelist()
def vizinhos(doctype: str, name: str):
    """Anterior e seguinte pela ordem da lista (última alteração primeiro)."""
    _guarda(doctype, name)
    mod = frappe.db.get_value(doctype, name, "modified")
    ant = frappe.get_list(doctype, filters={"modified": [">", mod]}, order_by="modified asc", limit=1, pluck="name")
    seg = frappe.get_list(doctype, filters={"modified": ["<", mod]}, order_by="modified desc", limit=1, pluck="name")
    return {"anterior": ant[0] if ant else None, "seguinte": seg[0] if seg else None}


# ── email com o PDF ──────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def email_sugestao(doctype: str, name: str):
    doc = _guarda(doctype, name)
    para = ""
    for c in ("contact_email", "email_id", "email", "supplier_email", "customer_email"):
        if doc.get(c):
            para = doc.get(c)
            break
    titulo = doc.get(frappe.get_meta(doctype).title_field or "name") or name
    return {"para": para, "assunto": f"{_(doctype)}: {titulo}" if titulo == name else f"{_(doctype)} {name} — {titulo}",
            "modelos": frappe.get_all("Email Template", pluck="name", order_by="name asc", limit=50)}


@frappe.whitelist(methods=["POST"])
def enviar_email(doctype: str, name: str, para: str, assunto: str, mensagem: str, cc: str = None, bcc: str = None,
                 formato: str = None, anexar_pdf: int = 1, cabecalho: str = None, lingua: str = None, anexos: str = None):
    _guarda(doctype, name)
    if not frappe.has_permission(doctype, "email", name) and not frappe.has_permission(doctype, "read", name):
        frappe.throw(_("Sem permissão."), frappe.PermissionError)
    if not (para or "").strip():
        frappe.throw(_("Indique pelo menos um destinatário."))
    from frappe.core.doctype.communication.email import make
    r = make(doctype=doctype, name=name, content=mensagem or "", subject=assunto or name, recipients=para, cc=cc or None,
             bcc=bcc or None, send_email=1, print_format=(formato or "Standard") if cint(anexar_pdf) else None,
             print_letterhead=bool(cabecalho), letterhead=cabecalho or None, print_language=lingua or None,
             attachments=json.loads(anexos) if anexos else None)
    return {"ok": 1, "comunicacao": (r or {}).get("name")}


@frappe.whitelist(methods=["POST"])
def apagar(doctype: str, name: str):
    """Apagar o registo (o ecrã antigo: «⋯ › Apagar»); o Frappe recusa se houver documentos ligados que o impeçam."""
    _guarda(doctype, name, "delete")
    frappe.delete_doc(doctype, name)
    return {"ok": 1}
