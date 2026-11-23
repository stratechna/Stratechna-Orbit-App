"""Conversa interna em cada registo, com @menções (23-11-2026, pedido do Vítor: «uma zona de conversas nas atividades,
escrevendo e mencionando @margot» — como os comentários do HubSpot/Pipedrive/Chatter).

Nada nosso por baixo: são os `Comment` do Frappe (comment_type «Comment») ligados ao registo, com as menções no formato
do Frappe (`<span class="mention" data-id="<email>">`). Ao gravar, o próprio Frappe cria o aviso «Mention» (Notification
Log) de cada pessoa mencionada — é o que o sino do Orbit mostra; a notificação no telemóvel sai desse aviso
(`orbit.interface.push`), e o email só no fim, se ficar por ver (`avisos_por_email`).

Registos: lead, contacto, empresa, negócio, ticket e email registado no CRM (Communication).
"""
from __future__ import annotations

import html
import json
import re

import frappe
from frappe.utils import add_to_date, now_datetime

DOCTYPES = ("CRM Lead", "Contact", "CRM Organization", "CRM Deal", "HD Ticket", "Communication")


def _guarda(doctype, nome, perm="read"):
    from orbit.interface.api import _guarda as g
    g()
    if doctype not in DOCTYPES:
        frappe.throw("Registo sem conversa.")
    frappe.get_doc(doctype, nome).check_permission(perm)


@frappe.whitelist()
def pessoas():
    """Quem se pode mencionar: as pessoas da equipa deste Orbit."""
    from orbit.interface.api import _guarda as g
    g()
    us = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "allowed_in_mentions": 1,
                                         "name": ["not in", ["Administrator", "Guest"]]},
                        fields=["name", "full_name", "user_image"], order_by="full_name asc")
    return [{"email": u.name, "nome": u.full_name or u.name} for u in us
            if "@" in u.name and not u.name.startswith(("portal@", "noreply@", "it@"))]


@frappe.whitelist()
def lista(doctype: str, nome: str):
    _guarda(doctype, nome)
    from orbit.interface.api import _nome_user
    cs = frappe.get_all("Comment", filters={"reference_doctype": doctype, "reference_name": nome, "comment_type": "Comment"},
                        fields=["name", "content", "owner", "creation", "modified"], order_by="creation asc", limit=500)
    eu = frappe.session.user
    return [{"id": c.name, "html": c.content or "", "quem": _nome_user(c.owner), "email": c.owner, "data": c.creation,
             "meu": c.owner == eu} for c in cs]


def _html(texto: str, mencoes: list) -> str:
    """Texto simples → HTML do Frappe, com cada «@Nome» escolhido transformado na menção que o Frappe reconhece."""
    t = html.escape((texto or "").strip())
    por_nome = {}
    for m in mencoes or []:
        if m.get("email") and m.get("nome"):
            por_nome[m["nome"]] = m["email"]
    for nome in sorted(por_nome, key=len, reverse=True):
        alvo = "@" + html.escape(nome)
        span = (f'<span class="mention" data-id="{html.escape(por_nome[nome])}" data-value="{html.escape(nome)}" '
                f'data-denotation-char="@">@{html.escape(nome)}</span>')
        t = t.replace(alvo, span)
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in re.split(r"\n{2,}", t) if p)


@frappe.whitelist(methods=["POST"])
def comentar(doctype: str, nome: str, texto: str, mencoes: str = "[]"):
    _guarda(doctype, nome)
    if not (texto or "").strip():
        frappe.throw("Escreva o comentário.")
    try:
        lst = json.loads(mencoes or "[]")
    except ValueError:
        lst = []
    validos = {p["email"] for p in pessoas()}
    lst = [m for m in lst if m.get("email") in validos]
    c = frappe.get_doc({"doctype": "Comment", "comment_type": "Comment", "reference_doctype": doctype,
                        "reference_name": nome, "content": _html(texto, lst),
                        "comment_email": frappe.session.user,
                        "comment_by": frappe.db.get_value("User", frappe.session.user, "full_name")})
    c.insert(ignore_permissions=True)   # o Frappe cria aqui os avisos «Mention» dos mencionados
    return {"ok": True, "id": c.name, "mencionados": [m["email"] for m in lst]}


@frappe.whitelist(methods=["POST"])
def apagar(id: str):
    from orbit.interface.api import _guarda as g
    g()
    c = frappe.get_doc("Comment", id)
    if c.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw("Só quem escreveu pode apagar.")
    c.delete(ignore_permissions=True)
    return {"ok": True}


# ── Avisos: email só no fim (23-11-2026: «email pode ser o último a disparar») ─────────────────────────────────────
# O Frappe mandava logo um email por menção; aqui desliga-se esse email (Notification Settings) e, de hora a hora,
# quem tiver uma menção por ver há mais de 3 h recebe-a por email — uma só vez por aviso.
HORAS_EMAIL = 3


def instalar():
    """after_migrate: campo de controlo no Notification Log e o email imediato das menções desligado."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    create_custom_field("Notification Log", {"fieldname": "orbit_email_enviado", "label": "Email enviado (Orbit)",
                                             "fieldtype": "Check", "read_only": 1, "hidden": 1, "insert_after": "read"})
    for u in frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, pluck="name"):
        try:
            if frappe.db.exists("Notification Settings", u):
                frappe.db.set_value("Notification Settings", u, "enable_email_mention", 0, update_modified=False)
            else:
                frappe.get_doc({"doctype": "Notification Settings", "name": u, "enable_email_mention": 0}).insert(ignore_permissions=True)
        except Exception:  # noqa: BLE001
            frappe.log_error(title=f"Orbit conversa: avisos de {u}")


def avisos_por_email():
    """Scheduler (de hora a hora)."""
    if not frappe.get_meta("Notification Log").has_field("orbit_email_enviado"):
        return
    limite = add_to_date(now_datetime(), hours=-HORAS_EMAIL)
    ns = frappe.get_all("Notification Log", filters={"type": "Mention", "read": 0, "orbit_email_enviado": 0,
                                                     "creation": ["between", [add_to_date(now_datetime(), days=-2), limite]]},
                        fields=["name", "for_user", "subject", "email_content", "document_type", "document_name"], limit=200)
    for n in ns:
        try:
            ligacao = ligacao_do_aviso(n.document_type, n.document_name)
            frappe.sendmail(recipients=[n.for_user], subject=frappe.utils.strip_html(n.subject or "Foi mencionado no Orbit"),
                            message=f"{n.subject}<br><br>{n.email_content or ''}<br><br><a href='{ligacao}'>Abrir no Orbit</a>",
                            delayed=False)
        except Exception:  # noqa: BLE001
            frappe.log_error(title="Orbit conversa: email do aviso")
        frappe.db.set_value("Notification Log", n.name, "orbit_email_enviado", 1, update_modified=False)
    frappe.db.commit()


ROTAS = {"CRM Lead": "lead", "Contact": "contacto", "CRM Organization": "empresa", "CRM Deal": "negocio",
         "HD Ticket": "ticket"}


def ligacao_do_aviso(doctype: str, nome: str) -> str:
    base = frappe.utils.get_url().rstrip("/").replace("http://", "https://")
    if doctype == "HD Ticket":
        return f"{base}/orbit?app=desk#/ticket/{nome}"
    if doctype == "Communication":
        ref = frappe.db.get_value("Communication", nome, ["reference_doctype", "reference_name"], as_dict=True) or {}
        if ref.get("reference_doctype") in ROTAS:
            return f"{base}/orbit#/{ROTAS[ref['reference_doctype']]}/{frappe.utils.quote(ref['reference_name'])}"
        return f"{base}/orbit#/caixa"
    if doctype in ROTAS:
        return f"{base}/orbit#/{ROTAS[doctype]}/{frappe.utils.quote(nome)}"
    return f"{base}/orbit"
