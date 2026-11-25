"""Desk (atendimento) dentro da interface /orbit — tickets, ficha, respostas e comentários (23-11-2026, pedido do Vítor).

Nada nosso por baixo: os mesmos `HD Ticket` do Helpdesk; responder usa `HD Ticket.reply_via_agent` e comentar
`HD Ticket.new_comment` (as mesmas funções que o ecrã do Helpdesk chama — SLA, avisos, emails e regras iguais);
a conversa vem de `helpdesk…hd_ticket.api.get_communications`; respostas-modelo = `HD Saved Reply`.
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, cint, flt, now_datetime

ESTADOS_PT = {"Open": "Aberto", "Replied": "Respondido (à espera do cliente)", "Paused": "Em pausa", "Resolved": "Resolvido",
              "Closed": "Fechado"}
PRIORIDADES_PT = {"Urgent": "Urgente", "High": "Alta", "Medium": "Média", "Low": "Baixa"}
TIPOS_PT = {"Unspecified": "Não indicado", "Question": "Pergunta", "Bug": "Erro", "Incident": "Incidente"}
SLA_PT = {"First Response Due": "À espera da 1.ª resposta", "Resolution Due": "À espera da resolução", "Failed": "Prazo falhado",
          "Fulfilled": "Cumprido", "Paused": "Em pausa"}
_CAMPOS = ["name", "subject", "status", "priority", "ticket_type", "agent_group", "_assign", "raised_by", "contact", "customer",
           "opening_date", "modified", "response_by", "resolution_by", "first_responded_on", "agreement_status", "_seen"]


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
            "atrasado": bool(t.agreement_status == "Failed"),
            # lote 3 (25-11): «por ler» a negrito, como no Helpdesk (quem já abriu fica em _seen)
            "por_ler": frappe.session.user not in (t.get("_seen") or ""), "tipo": t.ticket_type,
            "pausa": _categoria(t.status) == "Paused"}


@frappe.whitelist()
def tickets(vista: str = "abertos", q: str = "", equipa: str = "", estado: str = "", prioridade: str = "", marca: str = "",
            pagina: int = 0, responsavel: str = "", tipo: str = "", cliente: str = "", desde: str = "", ate: str = "",
            ordem: str = "atividade"):
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
    # lote 3 (25-11): filtros e ordem como na lista do Helpdesk
    if responsavel:
        f.append(["_assign", "like", f'%"{responsavel}"%'] if responsavel != "-" else ["_assign", "in", ["", "[]", None]])
    if tipo:
        f.append(["ticket_type", "=", tipo])
    if cliente:
        f.append(["customer", "=", cliente])
    if desde:
        f.append(["opening_date", ">=", desde])
    if ate:
        f.append(["opening_date", "<=", ate])
    from orbit.interface.desk_mais import ORDENS
    ordem_sql = ORDENS.get(ordem, "modified desc")
    q = (q or "").strip()
    ou = [["subject", "like", f"%{q}%"], ["raised_by", "like", f"%{q}%"], ["name", "like", f"%{q}%"]] if q else None
    pg = max(cint(pagina), 0)
    linhas = frappe.get_list("HD Ticket", filters=f, or_filters=ou, fields=campos, order_by=ordem_sql,
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
    return {"estados": [{"v": e, "r": ESTADOS_PT.get(e, e), "cat": _categoria(e)} for e in estados],
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
            "linha": linha, "pode_editar": bool(frappe.has_permission("HD Ticket", "write", t)),
            # 23-11-2026: resolução, inquérito e avaliação do cliente (plano do Desk)
            "categoria": _categoria(t.status), "resolucao": t.get("resolution_details") or "",
            "inquerito": t.get("orbit_inquerito") or "", "avaliacao": t.get("feedback_rating"),
            "avaliacao_texto": t.get("feedback_extra") or ""}


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


# ══ D1–D4 do plano do Desk (docs/PLANO-DESK-TICKETS.md, 23-11-2026) ════════════════════════════════════════════════
ORDEM = ["Open", "Replied", "Resolved", "Closed"]


def _categoria(estado: str) -> str:
    return frappe.db.get_value("HD Ticket Status", estado, "category") or ("Resolved" if estado in ("Resolved", "Closed") else "Open")


# ── K1: funil ─────────────────────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def funil(equipa: str = "", marca: str = "", prioridade: str = "", q: str = "", meus: int = 0):
    """Os tickets por estado. Resolvidos/fechados só os dos últimos 14 dias (o funil é do trabalho em curso)."""
    _guarda()
    from orbit.interface.api import _nome_user
    meta = frappe.get_meta("HD Ticket")
    campos = _CAMPOS + (["orbit_marca"] if meta.has_field("orbit_marca") else [])
    estados = frappe.get_all("HD Ticket Status", pluck="name") if frappe.db.exists("DocType", "HD Ticket Status") else ORDEM
    estados = sorted(estados, key=lambda e: ORDEM.index(e) if e in ORDEM else 2)
    f = [["status", "in", [e for e in estados if _categoria(e) != "Resolved"]]]
    f2 = [["status", "in", [e for e in estados if _categoria(e) == "Resolved"]], ["modified", ">", add_days(now_datetime(), -14)]]
    extra = []
    if equipa:
        extra.append(["agent_group", "=", equipa])
    if prioridade:
        extra.append(["priority", "=", prioridade])
    if marca and meta.has_field("orbit_marca"):
        extra.append(["orbit_marca", "=", marca])
    if cint(meus):
        extra.append(["_assign", "like", f'%"{frappe.session.user}"%'])
    q = (q or "").strip()
    ou = [["subject", "like", f"%{q}%"], ["raised_by", "like", f"%{q}%"], ["name", "like", f"%{q}%"]] if q else None
    linhas = []
    for filtros in (f, f2):
        linhas += frappe.get_list("HD Ticket", filters=filtros + extra, or_filters=ou, fields=campos, order_by="modified desc", limit=300)
    colunas = [{"v": e, "r": ESTADOS_PT.get(e, e), "cat": _categoria(e), "tickets": []} for e in estados]
    por = {c["v"]: c for c in colunas}
    for t in linhas:
        if t.status in por:
            por[t.status]["tickets"].append(_linha(t, _nome_user))
    return {"colunas": colunas}


# ── K5: mudança de estado com descrição (e o resto das propriedades) ──────────────────────────────────────────────
@frappe.whitelist(methods=["POST"])
def mudar_estado(nome: str, estado: str, nota: str = ""):
    """Muda o estado. Para Resolvido/Fechado é obrigatória a descrição da resolução (fica em `resolution_details`);
    cada mudança fica na conversa interna («Aberto → Resolvido: …»)."""
    _guarda()
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("write")
    antes = t.status
    if estado == antes:
        return {"ok": True}
    nota = (nota or "").strip()
    if _categoria(estado) == "Resolved" and not nota and not (t.get("resolution_details") or "").strip():
        frappe.throw("Descreva a resolução para fechar o ticket.")
    if _categoria(estado) == "Resolved" and nota:
        t.resolution_details = frappe.utils.escape_html(nota).replace("\n", "<br>")
    t.status = estado
    t.save()
    texto = f"Estado: {ESTADOS_PT.get(antes, antes)} → {ESTADOS_PT.get(estado, estado)}" + (f" — {nota}" if nota else "")
    frappe.get_doc({"doctype": "Comment", "comment_type": "Comment", "reference_doctype": "HD Ticket", "reference_name": nome,
                    "content": f"<p><b>{frappe.utils.escape_html(texto)}</b></p>"}).insert(ignore_permissions=True)
    return {"ok": True}


# ── K3: tempo (o mesmo livro de horas do Tempo do Orbit: Timesheet com custom_hd_ticket) ──────────────────────────
@frappe.whitelist()
def tempo(nome: str):
    _guarda()
    linhas = frappe.db.sql("""select d.from_time, d.hours, d.description, t.user, t.name ts from tabTimesheet t
        join `tabTimesheet Detail` d on d.parent=t.name where t.docstatus=1 and t.custom_hd_ticket=%s
        order by d.from_time desc limit 30""", (nome,), as_dict=1)
    from orbit.interface.api import _nome_user
    for l in linhas:
        l.quem = _nome_user(l.user)
    return {"total": sum(flt(l.hours) for l in linhas), "linhas": linhas}


@frappe.whitelist(methods=["POST"])
def registar_tempo(nome: str, horas: float, descricao: str = ""):
    _guarda()
    from orbit.interface.tempo import registar
    return registar(data=frappe.utils.nowdate(), horas=horas, descricao=descricao or f"Ticket #{nome}", ticket=nome)


# ── K4: checklist por ticket e modelos ────────────────────────────────────────────────────────────────────────────
CHAVE_MODELOS = "orbit_desk_checklists"


def _modelos() -> list:
    try:
        return json.loads(frappe.db.get_default(CHAVE_MODELOS) or "[]")
    except ValueError:
        return []


@frappe.whitelist()
def checklist(nome: str):
    _guarda()
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("read")
    try:
        itens = json.loads(t.get("orbit_checklist") or "[]")
    except ValueError:
        itens = []
    return {"itens": itens, "modelos": [{"nome": m.get("nome"), "tipo": m.get("tipo"), "n": len(m.get("itens") or [])} for m in _modelos()]}


@frappe.whitelist(methods=["POST"])
def gravar_checklist(nome: str, itens: str):
    _guarda()
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission("write")
    lst = []
    for i in json.loads(itens or "[]")[:100]:
        txt = str(i.get("t") or "").strip()[:300]
        if txt:
            lst.append({"t": txt, "feito": bool(i.get("feito")), "por": i.get("por") or "", "em": i.get("em") or ""})
    frappe.db.set_value("HD Ticket", nome, "orbit_checklist", json.dumps(lst, ensure_ascii=False), update_modified=False)
    return {"ok": True, "itens": lst}


@frappe.whitelist(methods=["POST"])
def aplicar_modelo(nome: str, modelo: str):
    _guarda()
    m = next((x for x in _modelos() if x.get("nome") == modelo), None)
    if not m:
        frappe.throw("Modelo inexistente.")
    atual = checklist(nome)["itens"]
    ja = {i["t"] for i in atual}
    atual += [{"t": t, "feito": False} for t in m.get("itens") or [] if t not in ja]
    return gravar_checklist(nome, json.dumps(atual))


@frappe.whitelist()
def modelos_checklist():
    _guarda()
    return {"modelos": _modelos(), "tipos": frappe.get_all("HD Ticket Type", pluck="name")}


@frappe.whitelist(methods=["POST"])
def gravar_modelos_checklist(modelos: str):
    _guarda()
    frappe.only_for("System Manager")
    lst = []
    for m in json.loads(modelos or "[]"):
        n = str(m.get("nome") or "").strip()[:80]
        itens = [str(x).strip()[:300] for x in (m.get("itens") or []) if str(x).strip()]
        if n and itens:
            lst.append({"nome": n, "tipo": m.get("tipo") or "", "itens": itens})
    frappe.db.set_default(CHAVE_MODELOS, json.dumps(lst, ensure_ascii=False))
    return {"ok": True}


def checklist_automatica(doc, method=None):
    """HD Ticket (insert e mudança de tipo): o modelo do tipo entra sozinho se a checklist estiver vazia."""
    if not doc.get("ticket_type") or (doc.get("orbit_checklist") or "").strip() not in ("", "[]"):
        return
    m = next((x for x in _modelos() if x.get("tipo") == doc.ticket_type), None)
    if m:
        doc.orbit_checklist = json.dumps([{"t": t, "feito": False} for t in m["itens"]], ensure_ascii=False)


# ── K6–K8: automatismos do ticket (inquérito, reaberto, sem resposta) ─────────────────────────────────────────────
JANELA_REABRIR = 14   # dias


def instalar():
    """after_migrate: campos do Orbit no HD Ticket."""
    if not frappe.db.exists("DocType", "HD Ticket"):
        return
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"HD Ticket": [
        {"fieldname": "orbit_checklist", "label": "Checklist (Orbit)", "fieldtype": "Long Text", "hidden": 1, "insert_after": "description"},
        {"fieldname": "orbit_inquerito", "label": "Inquérito (Orbit)", "fieldtype": "Data", "hidden": 1, "read_only": 1, "insert_after": "orbit_checklist"},
        {"fieldname": "orbit_aviso_sem_resposta", "label": "Aviso sem resposta (Orbit)", "fieldtype": "Check", "hidden": 1, "read_only": 1, "insert_after": "orbit_inquerito"},
    ]}, update=True)


def _avisar(user: str, assunto: str, nome: str, texto: str = ""):
    if not user:
        return
    frappe.get_doc({"doctype": "Notification Log", "for_user": user, "type": "Alert", "subject": assunto,
                    "email_content": texto, "document_type": "HD Ticket", "document_name": nome}).insert(ignore_permissions=True)


def _responsaveis(doc) -> list:
    try:
        return json.loads(doc.get("_assign") or "[]")
    except ValueError:
        return []


def ticket_gravado(doc, method=None):
    """HD Ticket on_update: resolvido → inquérito pendente (uma vez); reaberto → aviso ao responsável."""
    antes = doc.get_doc_before_save()
    if not antes or antes.status == doc.status:
        return
    if _categoria(doc.status) == "Resolved" and not doc.get("orbit_inquerito"):
        frappe.db.set_value("HD Ticket", doc.name, "orbit_inquerito", "pendente", update_modified=False)
    if _categoria(antes.status) == "Resolved" and _categoria(doc.status) != "Resolved":
        quem = doc.flags.get("reopened_by") or "o cliente"
        for u in _responsaveis(doc):
            _avisar(u, f"Ticket #{doc.name} reaberto por {quem}", doc.name, doc.subject or "")


def ticket_antes(doc, method=None):
    """HD Ticket validate: resposta do cliente a um ticket resolvido há mais de 14 dias não o reabre — nasce um novo,
    ligado (como no HubSpot)."""
    if doc.is_new() or not doc.flags.get("reopened_by"):
        return
    antes = doc.get_doc_before_save()
    if not antes or _categoria(antes.status) != "Resolved":
        return
    fim = antes.get("resolution_date") or antes.modified
    if fim and frappe.utils.date_diff(now_datetime(), fim) > JANELA_REABRIR:
        doc.status = antes.status
        frappe.enqueue("orbit.interface.desk._ticket_seguimento", queue="short", nome=doc.name, enqueue_after_commit=True)


def _ticket_seguimento(nome: str):
    t = frappe.get_doc("HD Ticket", nome)
    c = frappe.get_all("Communication", filters={"reference_doctype": "HD Ticket", "reference_name": nome, "sent_or_received": "Received"},
                       fields=["content", "subject"], order_by="creation desc", limit=1)
    novo = frappe.get_doc({"doctype": "HD Ticket", "subject": f"Seguimento de #{nome}: {t.subject}"[:140], "raised_by": t.raised_by,
                           "description": (c[0].content if c else "") + f"<p><i>Resposta ao ticket #{nome}, resolvido há mais de {JANELA_REABRIR} dias.</i></p>",
                           "agent_group": t.agent_group, "ticket_type": t.ticket_type})
    if t.meta.has_field("orbit_marca"):
        novo.orbit_marca = t.get("orbit_marca")
    novo.insert(ignore_permissions=True)
    frappe.db.commit()


def sem_resposta():
    """Scheduler (de hora a hora): ticket aberto há mais de 1 dia sem 1.ª resposta → aviso ao responsável (uma vez)."""
    if not frappe.db.exists("DocType", "HD Ticket") or not frappe.get_meta("HD Ticket").has_field("orbit_aviso_sem_resposta"):
        return
    for t in frappe.get_all("HD Ticket", filters={"first_responded_on": ["is", "not set"], "orbit_aviso_sem_resposta": 0,
                                                  "status": ["in", ["Open"]], "creation": ["<", add_days(now_datetime(), -1)]},
                            fields=["name", "subject", "_assign"], limit=200):
        for u in json.loads(t._assign or "[]"):
            _avisar(u, f"Ticket #{t.name} sem resposta há mais de 1 dia", t.name, t.subject or "")
        frappe.db.set_value("HD Ticket", t.name, "orbit_aviso_sem_resposta", 1, update_modified=False)
    frappe.db.commit()


# ── K7: inquérito de satisfação (email em dia útil 08–19, ligação de uso único) ───────────────────────────────────
NOTAS = {"bom": (1.0, "Bom"), "razoavel": (0.6, "Razoável"), "mau": (0.2, "Mau")}


def _token(nome: str) -> str:
    import hashlib
    import hmac
    chave = (frappe.local.conf.get("encryption_key") or frappe.local.site).encode()
    return hmac.new(chave, f"inquerito:{nome}".encode(), hashlib.sha256).hexdigest()[:32]


def _dia_util() -> bool:
    from zoneinfo import ZoneInfo
    from datetime import datetime
    agora = datetime.now(ZoneInfo("Europe/Lisbon"))
    return agora.weekday() < 5 and 8 <= agora.hour < 19


def enviar_inqueritos():
    """Scheduler (de 15 em 15 min): os inquéritos pendentes saem só em dia útil, das 08 às 19 (regra da casa)."""
    if not frappe.db.exists("DocType", "HD Ticket") or not frappe.get_meta("HD Ticket").has_field("orbit_inquerito") or not _dia_util():
        return
    base = frappe.utils.get_url().rstrip("/").replace("http://", "https://")
    for t in frappe.get_all("HD Ticket", filters={"orbit_inquerito": "pendente"}, fields=["name", "subject", "raised_by"], limit=50):
        if not t.raised_by or "noreply" in t.raised_by.lower() or "no-reply" in t.raised_by.lower():
            frappe.db.set_value("HD Ticket", t.name, "orbit_inquerito", "sem-destino", update_modified=False)
            continue
        url = f"{base}/satisfacao?t={t.name}&k={_token(t.name)}"
        botoes = "".join(f'<a href="{url}&n={k}" style="display:inline-block;margin:0 6px 8px 0;padding:10px 16px;border-radius:8px;'
                         f'background:#f1f3f5;color:#161a1d;text-decoration:none;font-weight:600">{v[1]}</a>' for k, v in NOTAS.items())
        corpo = (f"<p>Olá,</p><p>O seu pedido <b>#{t.name} — {frappe.utils.escape_html(t.subject or '')}</b> foi dado como resolvido. "
                 f"Como correu?</p><p>{botoes}</p><p>Se o problema não ficou resolvido, <a href=\"{url}&reabrir=1\">reabra o pedido aqui</a> "
                 f"— ou responda a este email.</p>")
        try:
            frappe.sendmail(recipients=[t.raised_by], subject=f"Como correu? Pedido #{t.name}", message=corpo,
                            reference_doctype="HD Ticket", reference_name=t.name, delayed=False)
            frappe.db.set_value("HD Ticket", t.name, "orbit_inquerito", "enviado", update_modified=False)
        except Exception:  # noqa: BLE001
            frappe.log_error(title=f"Orbit Desk: inquérito #{t.name}")
    frappe.db.commit()


@frappe.whitelist(allow_guest=True, methods=["POST"])
def responder_inquerito(t: str, k: str, nota: str = "", comentario: str = "", reabrir: int = 0):
    import hmac
    if not frappe.db.exists("HD Ticket", t) or not hmac.compare_digest(_token(t), k or ""):
        frappe.throw("Ligação inválida.", frappe.PermissionError)
    tk = frappe.get_doc("HD Ticket", t)
    comentario = (comentario or "").strip()[:2000]
    if nota in NOTAS and tk.get("orbit_inquerito") != "respondido":
        tk.db_set("feedback_rating", NOTAS[nota][0], update_modified=False)
        if comentario:
            tk.db_set("feedback_extra", comentario, update_modified=False)
        tk.db_set("orbit_inquerito", "respondido", update_modified=False)
        frappe.get_doc({"doctype": "Comment", "comment_type": "Comment", "reference_doctype": "HD Ticket", "reference_name": t,
                        "content": f"<p><b>Inquérito: {NOTAS[nota][1]}</b>{' — ' + frappe.utils.escape_html(comentario) if comentario else ''}</p>"}
                       ).insert(ignore_permissions=True)
    if cint(reabrir) or nota == "mau":
        fim = tk.get("resolution_date") or tk.modified
        if _categoria(tk.status) == "Resolved" and frappe.utils.date_diff(now_datetime(), fim) <= JANELA_REABRIR:
            tk.flags.ignore_permissions = True
            tk.flags.reopened_by = tk.raised_by
            tk.status = "Open"
            tk.save(ignore_permissions=True)
            frappe.get_doc({"doctype": "Comment", "comment_type": "Comment", "reference_doctype": "HD Ticket", "reference_name": t,
                            "content": f"<p><b>Reaberto pelo cliente</b>{' — ' + frappe.utils.escape_html(comentario) if comentario else ''}</p>"}
                           ).insert(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}
