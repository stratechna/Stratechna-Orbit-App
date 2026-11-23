"""Ecrã Definições › CRM › Fluxos (23-11-2026) — sobre o motor de automações do Frappe (`Automation Flow`).

Nada nosso por baixo: lê e grava os mesmos `Automation Flow` que o CRM clássico edita. Mostra tudo em português,
deixa ligar/desligar, mudar o título e os parâmetros simples de cada passo (a quem atribuir, que modelo de email, o
texto e o prazo das tarefas, quantos dias esperar, pontos, temperatura, destinatários dos avisos), experimentar num
registo (ensaio do Frappe, sem efeitos) e ver as execuções. Só System Manager.
"""
from __future__ import annotations

import json
import re

import frappe
from frappe import _

DOCS = {"CRM Lead": "Leads", "CRM Deal": "Negócios", "Contact": "Contactos", "CRM Organization": "Empresas",
        "Communication": "Emails", "HD Ticket": "Tickets", "CRM Task": "Tarefas"}
GATILHOS = {"Doc Created": "Quando é criado", "Doc Updated": "Quando é alterado", "Field Value Changed": "Quando um campo muda",
            "Doc Deleted": "Quando é apagado", "Doc Submitted": "Quando é submetido", "Doc Cancelled": "Quando é cancelado",
            "Date Based": "Numa data do registo", "Scheduled": "Agendado", "Custom Event": "Quando acontece um evento",
            "Manual": "Só à mão"}
ACOES = {"SetFieldValue": "Mudar um campo", "CreateDocument": "Criar registo", "IncrementFieldValue": "Somar a um campo",
         "SendNotification": "Avisar", "AssignToUser": "Atribuir", "CallWebhook": "Chamar um webhook",
         "RunScript": "Correr um script", "AdjustLeadScore": "Pontuar a lead", "SetLeadTemperature": "Temperatura da lead",
         "ConvertLeadToDeal": "Converter a lead em negócio", "SendCRMEmail": "Enviar email ao registo",
         "SendCRMNotification": "Avisar no CRM"}
TEMPERATURA = {"Hot": "Quente", "Warm": "Morna", "Cold": "Fria"}
ESTADOS_RUN = {"Running": "A correr", "Waiting": "À espera", "Success": "Correu bem", "Partially Failed": "Falhou em parte",
               "Failed": "Falhou", "Skipped": "Não se aplicou"}
EVENTOS = {"crm.prospect_message_received": "o cliente responder", "crm.prospect_message_sent": "enviarmos um email"}
_DIAS = re.compile(r"add_days\(frappe\.utils\.nowdate\(\),\s*(-?\d+)\)")


def _guarda():
    from orbit.interface.api import _guarda as g
    g()
    frappe.only_for("System Manager")


def _rotulo_campo(dt, campo):
    try:
        f = frappe.get_meta(dt).get_field(campo)
        return _(f.label) if f else campo
    except Exception:
        return campo


def _quando(f) -> str:
    g = GATILHOS.get(f.trigger_type, f.trigger_type)
    if f.trigger_type == "Field Value Changed" and f.trigger_field:
        g = f"Quando «{_rotulo_campo(f.document_type, f.trigger_field)}» muda"
        if f.to_value:
            from orbit.interface.api import _rotulo_estado
            g += f" para «{_rotulo_estado(f.to_value)}»"
    elif f.trigger_type == "Date Based" and f.date_field:
        g = f"{f.date_offset or 0} dias {'antes' if f.date_direction == 'Before' else 'depois'} de «{_rotulo_campo(f.document_type, f.date_field)}»"
    elif f.trigger_type == "Custom Event" and f.custom_event:
        g = "Quando " + EVENTOS.get(f.custom_event, f.custom_event)
    return g


def _params(a) -> dict:
    try:
        return json.loads(a.params or "{}") or {}
    except ValueError:
        return {}


def _passo(a) -> dict:
    """Um passo em português e o que nele se pode mudar."""
    p = _params(a)
    tipo = a.step_type
    texto, campos = "", []
    rel = {}
    try:
        rel = json.loads(a.related_condition or "{}") or {}
    except (ValueError, TypeError):
        rel = {}
    if tipo == "If" and rel.get("relationship") == "communications":
        texto = "Se o cliente ainda não respondeu"
    elif tipo == "If":
        texto = "Se a condição se cumprir"
    elif tipo == "Wait":
        texto = f"Esperar {p.get('value')} {'dias' if (p.get('unit') or 'Days') == 'Days' else (p.get('unit') or '').lower()}"
        campos = [{"chave": "value", "rotulo": "Dias", "tipo": "numero", "valor": p.get("value")}]
    elif tipo == "WaitForEvent":
        texto = f"Esperar até {EVENTOS.get(p.get('event_name'), p.get('event_name'))} (no máximo {p.get('timeout_value')} dias)"
        campos = [{"chave": "timeout_value", "rotulo": "No máximo (dias)", "tipo": "numero", "valor": p.get("timeout_value")}]
    else:
        at = a.action_type
        nome = ACOES.get(at, at)
        if at == "AssignToUser":
            texto = f"{nome}: " + ", ".join(p.get("assign_to") or [])
            campos = [{"chave": "assign_to", "rotulo": "A quem", "tipo": "pessoas", "valor": p.get("assign_to") or []}]
        elif at == "SendCRMEmail":
            texto = f"{nome}: modelo «{p.get('email_template') or '—'}»"
            campos = [{"chave": "email_template", "rotulo": "Modelo de email", "tipo": "modelo", "valor": p.get("email_template")}]
        elif at in ("SendNotification", "SendCRMNotification"):
            assunto = p.get("subject") or p.get("notification_text") or ""
            texto = f"{nome}: {assunto}"
            chave_txt = "subject" if at == "SendNotification" else "notification_text"
            campos = [{"chave": "recipients", "rotulo": "Para", "tipo": "pessoas", "valor": p.get("recipients") or []},
                      {"chave": chave_txt, "rotulo": "Texto", "tipo": "texto", "valor": assunto}]
        elif at == "CreateDocument":
            v = p.get("values") or {}
            dt = p.get("doctype")
            dias = _DIAS.search(v.get("due_date") or "")
            texto = f"Criar {'tarefa' if dt == 'CRM Task' else DOCS.get(dt, dt)}: {v.get('title') or ''}"
            if dt == "CRM Task":
                campos = [{"chave": "values.title", "rotulo": "Título da tarefa", "tipo": "texto", "valor": v.get("title")}]
                if dias:
                    campos.append({"chave": "values.due_days", "rotulo": "Prazo (dias)", "tipo": "numero", "valor": int(dias.group(1))})
        elif at == "AdjustLeadScore":
            texto = f"{nome}: {p.get('amount'):+} pontos — {p.get('reason') or ''}" if isinstance(p.get("amount"), (int, float)) else nome
            campos = [{"chave": "amount", "rotulo": "Pontos", "tipo": "numero", "valor": p.get("amount")},
                      {"chave": "reason", "rotulo": "Razão", "tipo": "texto", "valor": p.get("reason")}]
        elif at == "SetLeadTemperature":
            texto = f"{nome}: {TEMPERATURA.get(p.get('temperature'), p.get('temperature'))}"
            campos = [{"chave": "temperature", "rotulo": "Temperatura", "tipo": "lista", "valor": p.get("temperature"),
                       "opcoes": [{"v": k, "r": v} for k, v in TEMPERATURA.items()]}]
        elif at == "IncrementFieldValue":
            texto = f"{nome}: {_rotulo_campo(a.parent and frappe.db.get_value('Automation Flow', a.parent, 'document_type'), p.get('field'))} {p.get('amount'):+}" if isinstance(p.get("amount"), (int, float)) else nome
            campos = [{"chave": "amount", "rotulo": "Quanto", "tipo": "numero", "valor": p.get("amount")}]
        else:
            texto = nome
    if rel.get("relationship") == "tasks" and tipo == "Action":
        texto += " (só se não houver tarefa aberta)"
    cond = "" if (a.step_condition or "").strip() == "True" else (a.step_condition or "")
    return {"chave": a.step_key, "idx": a.idx, "tipo": tipo, "texto": texto, "condicao": cond,
            "pai": a.parent_step or 0, "ramo": {"If": "Se sim", "Else": "Senão"}.get(a.branch or "", ""), "campos": campos,
            "alvo": a.target if a.target not in ("trigger", None, "") else ""}


@frappe.whitelist()
def listar():
    _guarda()
    fs = frappe.get_all("Automation Flow", fields=["name", "title", "enabled", "document_type", "trigger_type", "trigger_field",
                                                   "to_value", "date_field", "date_offset", "date_direction", "custom_event"],
                        order_by="document_type asc, title asc")
    runs = {r.automation: r for r in frappe.db.sql("""SELECT automation, COUNT(*) n, MAX(creation) ultima FROM `tabAutomation Run`
                                                       GROUP BY automation""", as_dict=True)}
    out = []
    for f in fs:
        f = frappe._dict(f)
        r = runs.get(f.name) or {}
        out.append({"name": f.name, "titulo": f.title, "ativo": bool(f.enabled), "registo": DOCS.get(f.document_type, f.document_type),
                    "quando": _quando(f), "passos": frappe.db.count("Automation Action", {"parent": f.name}),
                    "execucoes": r.get("n") or 0, "ultima": r.get("ultima")})
    return out


@frappe.whitelist()
def obter(nome: str):
    _guarda()
    f = frappe.get_doc("Automation Flow", nome)
    return {"name": f.name, "titulo": f.title, "ativo": bool(f.enabled), "registo": DOCS.get(f.document_type, f.document_type),
            "document_type": f.document_type, "quando": _quando(f), "condicao": f.condition or "",
            "passos": [_passo(a) for a in f.actions], "motivo_desligado": f.disabled_reason or ""}


@frappe.whitelist()
def metadados():
    _guarda()
    pessoas = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
                             fields=["name", "full_name"], order_by="full_name asc")
    return {"pessoas": [{"v": "@owner", "r": "Quem criou o registo"}, {"v": "@assignees", "r": "Os responsáveis do registo"}]
            + [{"v": p.name, "r": p.full_name or p.name} for p in pessoas],
            "modelos_email": frappe.get_all("Email Template", pluck="name", order_by="name asc", limit=200)}


@frappe.whitelist(methods=["POST"])
def gravar(nome: str, dados: str):
    """`dados` = {titulo, ativo, passos: {chave_do_passo: {chave_do_parametro: valor}}}."""
    _guarda()
    d = json.loads(dados or "{}")
    f = frappe.get_doc("Automation Flow", nome)
    if (d.get("titulo") or "").strip():
        f.title = d["titulo"].strip()[:140]
    if "ativo" in d:
        f.enabled = 1 if d["ativo"] else 0
    mudancas = d.get("passos") or {}
    for a in f.actions:
        m = mudancas.get(a.step_key)
        if not m:
            continue
        p = _params(a)
        for k, v in m.items():
            if k == "values.title":
                p.setdefault("values", {})["title"] = v
            elif k == "values.due_days":
                p.setdefault("values", {})["due_date"] = f"{{{{ frappe.utils.add_days(frappe.utils.nowdate(), {int(v or 0)}) }}}}"
            elif k in ("value", "timeout_value", "amount"):
                p[k] = int(v or 0)
            else:
                p[k] = v
        a.params = frappe.as_json(p)
    f.save(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def ligar(nome: str, ativo: int):
    _guarda()
    f = frappe.get_doc("Automation Flow", nome)
    f.enabled = 1 if int(ativo) else 0
    f.save(ignore_permissions=True)   # o Frappe valida os passos: se faltar um parâmetro, recusa e diz qual
    return {"ok": True}


@frappe.whitelist()
def execucoes(nome: str = ""):
    _guarda()
    filtros = {"automation": nome} if nome else {}
    linhas = frappe.get_all("Automation Run", filters=filtros, fields=["name", "automation_title", "status", "reference_doctype",
                                                                      "reference_name", "started_at", "ended_at", "error_summary"],
                            order_by="creation desc", limit=100)
    for l in linhas:
        l.estado = ESTADOS_RUN.get(l.status, l.status)
        l.passos = frappe.get_all("Automation Run Step", filters={"parent": l.name},
                                  fields=["step_key", "status", "message", "exception"], order_by="idx asc", limit=40) \
            if frappe.db.exists("DocType", "Automation Run Step") else []
    return linhas


@frappe.whitelist(methods=["POST"])
def experimentar(nome: str, registo: str):
    """Ensaio do Frappe num registo concreto: mostra o que o fluxo faria, sem gravar efeitos."""
    _guarda()
    from frappe.automation_engine.api import trial_run
    return trial_run(automation=nome, docname=registo)
