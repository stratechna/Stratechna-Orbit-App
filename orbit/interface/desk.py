"""Desk (atendimento) dentro da interface /orbit — tickets, ficha, respostas e comentários (23-11-2026, pedido do Vítor).

Nada nosso por baixo: os mesmos `HD Ticket` do Helpdesk; responder usa `HD Ticket.reply_via_agent` e comentar
`HD Ticket.new_comment` (as mesmas funções que o ecrã do Helpdesk chama — SLA, avisos, emails e regras iguais);
a conversa vem de `helpdesk…hd_ticket.api.get_communications`; respostas-modelo = `HD Saved Reply`.
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, cint, now_datetime

ESTADOS_PT = {"Open": "Aberto", "Replied": "Respondido (à espera do cliente)", "Paused": "Em pausa", "Resolved": "Resolvido",
              "Closed": "Fechado"}
PRIORIDADES_PT = {"Urgent": "Urgente", "High": "Alta", "Medium": "Média", "Low": "Baixa"}
TIPOS_PT = {"Unspecified": "Não indicado", "Question": "Pergunta", "Bug": "Erro", "Incident": "Incidente"}
SLA_PT = {"First Response Due": "À espera da 1.ª resposta", "Resolution Due": "À espera da resolução", "Failed": "Prazo falhado",
          "Fulfilled": "Cumprido", "Paused": "Em pausa"}
_CAMPOS = ["name", "subject", "status", "priority", "ticket_type", "agent_group", "_assign", "raised_by", "contact", "customer",
           "opening_date", "modified", "response_by", "resolution_by", "first_responded_on", "agreement_status"]


def _guarda():
    from orbit.interface.api import _guarda as g
    g()
    if not frappe.db.exists("DocType", "HD Ticket"):
        frappe.throw("O Desk não está instalado neste Orbit.")


def _resolvidos():
    if frappe.db.exists("DocType", "HD Ticket Status"):
        return frappe.get_all("HD Ticket Status", filters={"category": "Resolved"}, pluck="name") or ["Resolved", "Closed"]
    return ["Resolved", "Closed"]


def _filtros(vista: str):
    u = frappe.session.user
    fechados = _resolvidos()
    f = []
    if vista == "abertos":
        f.append(["status", "not in", fechados])
    elif vista == "meus":
        f += [["status", "not in", fechados], ["_assign", "like", f'%"{u}"%']]
    elif vista == "sem_resposta":
        f += [["status", "not in", fechados], ["first_responded_on", "is", "not set"]]
    elif vista == "fora_prazo":
        f += [["status", "not in", fechados], ["agreement_status", "=", "Failed"]]
    elif vista == "resolvidos":
        f.append(["status", "in", fechados])
    return f


def _linha(t, nomes_user):
    try:
        resp = (json.loads(t.get("_assign") or "[]") or [None])[0]
    except ValueError:
        resp = None
    return {"name": t.name, "assunto": t.subject or "(sem assunto)", "estado": t.status, "estado_pt": ESTADOS_PT.get(t.status, t.status),
            "prioridade": t.priority, "prioridade_pt": PRIORIDADES_PT.get(t.priority, t.priority), "equipa": t.agent_group,
            "marca": t.get("orbit_marca"), "responsavel": resp, "responsavel_nome": nomes_user(resp) if resp else "",
            "cliente": t.contact or t.raised_by, "email": t.raised_by, "aberto": t.opening_date, "atividade": t.modified,
            "prazo": t.resolution_by if t.first_responded_on else t.response_by, "sla": SLA_PT.get(t.agreement_status, t.agreement_status),
            "atrasado": bool(t.agreement_status == "Failed")}


@frappe.whitelist()
def tickets(vista: str = "abertos", q: str = "", equipa: str = "", estado: str = "", prioridade: str = "", marca: str = "",
            pagina: int = 0):
    _guarda()
    from orbit.interface.api import _nome_user
    meta = frappe.get_meta("HD Ticket")
    campos = _CAMPOS + (["orbit_marca"] if meta.has_field("orbit_marca") else [])
    f = _filtros(vista)
    if equipa:
        f.append(["agent_group", "=", equipa])
    if estado:
        f.append(["status", "=", estado])
    if prioridade:
        f.append(["priority", "=", prioridade])
    if marca and meta.has_field("orbit_marca"):
        f.append(["orbit_marca", "=", marca])
    q = (q or "").strip()
    ou = [["subject", "like", f"%{q}%"], ["raised_by", "like", f"%{q}%"], ["name", "like", f"%{q}%"]] if q else None
    pg = max(cint(pagina), 0)
    linhas = frappe.get_list("HD Ticket", filters=f, or_filters=ou, fields=campos, order_by="modified desc",
                             limit_start=pg * 50, limit_page_length=51)
    contagens = {v: len(frappe.get_list("HD Ticket", filters=_filtros(v), pluck="name", limit=2000))
                 for v in ("abertos", "meus", "sem_resposta", "fora_prazo")}
    return {"linhas": [_linha(t, _nome_user) for t in linhas[:50]], "mais": len(linhas) > 50, "contagens": contagens}


@frappe.whitelist()
def metadados():
    _guarda()
    from orbit.interface.api import _nome_user
    meta = frappe.get_meta("HD Ticket")
    agentes = frappe.get_all("HD Agent", filters={"is_active": 1}, pluck="name") if frappe.db.exists("DocType", "HD Agent") else []
    marcas = [o for o in (meta.get_field("orbit_marca").options or "").split("\n") if o] if meta.has_field("orbit_marca") else []
    estados = frappe.get_all("HD Ticket Status", pluck="name") if frappe.db.exists("DocType", "HD Ticket Status") else list(ESTADOS_PT)
    return {"estados": [{"v": e, "r": ESTADOS_PT.get(e, e)} for e in estados],
            "prioridades": [{"v": p, "r": PRIORIDADES_PT.get(p, p)} for p in frappe.get_all("HD Ticket Priority", pluck="name")],
            "tipos": [{"v": t, "r": TIPOS_PT.get(t, t)} for t in frappe.get_all("HD Ticket Type", pluck="name")],
            "equipas": frappe.get_all("HD Team", pluck="name"), "marcas": marcas,
            "agentes": [{"v": a, "r": _nome_user(a)} for a in agentes],
            "respostas": frappe.get_all("HD Saved Reply", fields=["name", "title"], order_by="title asc", limit=200)
            if frappe.db.exists("DocType", "HD Saved Reply") else []}


@frappe.whitelist()
def ticket(nome: str):
    _guarda()
    from orbit.interface.api import _nome_user
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("read")
    from helpdesk.helpdesk.doctype.hd_ticket.api import get_communications
    linha = []
    for c in get_communications(nome):
        linha.append({"tipo": "email", "id": c.name, "quando": c.communication_date or c.creation, "de": c.sender,
                      "quem": (c.user or {}).get("name") if isinstance(c.user, dict) else c.sender,
                      "para": c.recipients, "cc": c.cc, "html": c.content or "", "enviado": c.sent_or_received == "Sent",
                      "anexos": [{"nome": a.get("file_name"), "url": a.get("file_url")} for a in (c.attachments or [])]})
    for c in frappe.get_all("Comment", filters={"reference_doctype": "HD Ticket", "reference_name": nome, "comment_type": "Comment"},
                            fields=["name", "content", "owner", "creation"], order_by="creation asc"):
        linha.append({"tipo": "comentario", "id": c.name, "quando": c.creation, "quem": _nome_user(c.owner), "html": c.content or ""})
    linha.sort(key=lambda x: str(x["quando"] or ""))
    try:
        atrib = json.loads(t.get("_assign") or "[]")
    except ValueError:
        atrib = []
    contacto = None
    if t.contact and frappe.db.exists("Contact", t.contact):
        c = frappe.db.get_value("Contact", t.contact, ["name", "full_name", "email_id", "mobile_no", "phone", "company_name"], as_dict=True)
        contacto = c
    return {"name": t.name, "assunto": t.subject, "estado": t.status, "prioridade": t.priority, "tipo": t.ticket_type,
            "equipa": t.agent_group, "marca": t.get("orbit_marca"), "responsaveis": [{"v": a, "r": _nome_user(a)} for a in atrib],
            "email": t.raised_by, "contacto": contacto, "cliente": t.customer, "aberto": t.opening_date,
            "resposta_ate": t.response_by, "resolucao_ate": t.resolution_by, "primeira_resposta": t.first_responded_on,
            "sla": SLA_PT.get(t.agreement_status, t.agreement_status), "atrasado": t.agreement_status == "Failed",
            "linha": linha, "pode_editar": bool(frappe.has_permission("HD Ticket", "write", t))}


@frappe.whitelist(methods=["POST"])
def responder(nome: str, html: str, cc: str = "", bcc: str = ""):
    _guarda()
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("write")
    t.reply_via_agent(message=html, cc=cc or None, bcc=bcc or None)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def comentar(nome: str, html: str):
    _guarda()
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("write")
    t.new_comment(html)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def mudar(nome: str, campo: str, valor: str = ""):
    _guarda()
    if campo not in ("status", "priority", "ticket_type", "agent_group", "orbit_marca"):
        frappe.throw("Campo não editável.")
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("write")
    t.set(campo, valor or None)
    t.save()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def atribuir(nome: str, agente: str = ""):
    _guarda()
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("write")
    from frappe.desk.form.assign_to import remove
    try:
        atuais = json.loads(t.get("_assign") or "[]")
    except ValueError:
        atuais = []
    for a in atuais:
        if a != agente:
            remove("HD Ticket", nome, a)
    if agente and agente not in atuais:
        t.assign_agent(agente)
    return {"ok": True}


@frappe.whitelist()
def resposta_modelo(nome: str, ticket: str):
    """O texto de uma resposta-modelo já preenchido para o ticket (a mesma função do Helpdesk)."""
    _guarda()
    from helpdesk.api.saved_replies import get_rendered_saved_reply
    return get_rendered_saved_reply(ticket_id=ticket, saved_reply_id=nome)
