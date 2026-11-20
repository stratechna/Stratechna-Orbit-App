"""Tarefas e projetos dentro da interface /orbit (A2 do plano da interface única, 20-11-2026).

Uma só lista de tarefas para a pessoa: as do CRM (`CRM Task`, ligadas a negócios/leads/contactos) e as dos projetos
(`Task` do ERPNext Projects, atribuídas pelo `_assign`). Os projetos são os do ERPNext (`Project`). Tudo pela API
do Frappe com as permissões da pessoa; nada das apps é alterado.
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

FEITAS_CRM = ("Done", "Canceled")
FEITAS_PROJ = ("Completed", "Cancelled", "Template")
ESTADOS_PROJ = [("Open", "Por fazer"), ("Working", "Em curso"), ("Pending Review", "Para rever"),
                ("Overdue", "Atrasada"), ("Completed", "Concluída")]
PRIOR = {"Low": "Baixa", "Medium": "Média", "High": "Alta", "Urgent": "Urgente"}


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _nome(u):
    from orbit.interface.api import _nome_user
    return _nome_user(u)


def _dono(assign):
    try:
        lst = json.loads(assign or "[]")
    except Exception:  # noqa: BLE001
        lst = []
    return lst[0] if lst else None


@frappe.whitelist()
def tarefas(vista: str = "minhas", projeto: str = "", q: str = ""):
    _guarda()
    u = frappe.session.user
    out = []
    q = (q or "").strip()
    if not projeto:
        f = {"status": ["not in", FEITAS_CRM]}
        if vista == "minhas":
            f["assigned_to"] = u
        for t in frappe.get_list("CRM Task", filters=f, fields=["name", "title", "status", "priority", "due_date", "assigned_to",
                                 "reference_doctype", "reference_docname"], or_filters=[["title", "like", f"%{q}%"]] if q else None,
                                 order_by="due_date asc", limit=300):
            from orbit.interface.api import _titulo
            out.append({"tipo": "crm", "id": t.name, "titulo": t.title, "estado": t.status, "prioridade": PRIOR.get(t.priority, t.priority),
                        "data": str(getdate(t.due_date)) if t.due_date else None, "dono": _nome(t.assigned_to),
                        "ref": [t.reference_doctype, t.reference_docname] if t.reference_docname else None,
                        "ref_titulo": _titulo(t.reference_doctype, t.reference_docname) if t.reference_docname else ""})
    f = {"status": ["not in", FEITAS_PROJ], "is_group": 0}
    if projeto:
        f["project"] = projeto
    elif vista == "minhas":
        f["_assign"] = ["like", f'%"{u}"%']
    for t in frappe.get_list("Task", filters=f, fields=["name", "subject", "status", "priority", "exp_end_date", "project", "_assign"],
                             or_filters=[["subject", "like", f"%{q}%"]] if q else None, order_by="exp_end_date asc", limit=500):
        out.append({"tipo": "projeto", "id": t.name, "titulo": t.subject, "estado": t.status, "prioridade": PRIOR.get(t.priority, t.priority),
                    "data": str(getdate(t.exp_end_date)) if t.exp_end_date else None, "dono": _nome(_dono(t._assign)),
                    "projeto": t.project, "projeto_nome": frappe.db.get_value("Project", t.project, "project_name") if t.project else ""})
    hoje = getdate(nowdate())
    fim_semana = add_days(hoje, 6 - hoje.weekday())
    for t in out:
        d = getdate(t["data"]) if t["data"] else None
        t["grupo"] = ("sem_data" if not d else "atrasadas" if d < hoje else "hoje" if d == hoje
                      else "semana" if d <= getdate(fim_semana) else "depois")
    return out


@frappe.whitelist(methods=["POST"])
def concluir(tipo: str, nome: str):
    _guarda()
    if tipo == "crm":
        d = frappe.get_doc("CRM Task", nome)
        d.status = "Done"
    else:
        d = frappe.get_doc("Task", nome)
        d.status = "Completed"
    d.save()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def criar(titulo: str, data: str = None, projeto: str = None, responsavel: str = None):
    _guarda()
    titulo = (titulo or "").strip()[:140]
    if not titulo:
        frappe.throw("Falta o título.")
    quem = responsavel or frappe.session.user
    if projeto:
        t = frappe.get_doc({"doctype": "Task", "subject": titulo, "project": projeto, "status": "Open",
                            "exp_end_date": data or None}).insert()
        from frappe.desk.form.assign_to import add as atribuir
        atribuir({"doctype": "Task", "name": t.name, "assign_to": [quem]})
        return {"ok": True, "id": t.name, "tipo": "projeto"}
    t = frappe.get_doc({"doctype": "CRM Task", "title": titulo, "status": "Todo", "priority": "Medium",
                        "due_date": data or None, "assigned_to": quem}).insert()
    return {"ok": True, "id": t.name, "tipo": "crm"}


@frappe.whitelist(methods=["POST"])
def mover(nome: str, estado: str):
    _guarda()
    if estado not in [e for e, _ in ESTADOS_PROJ]:
        frappe.throw("Estado desconhecido")
    t = frappe.get_doc("Task", nome)
    t.status = estado
    t.save()
    return {"ok": True}


@frappe.whitelist()
def projetos(estado: str = "Open", q: str = ""):
    _guarda()
    f = {"status": estado} if estado else {}
    q = (q or "").strip()
    linhas = frappe.get_list("Project", filters=f, fields=["name", "project_name", "status", "percent_complete", "expected_end_date",
                             "customer", "marca", "priority", "horas_orcamento", "actual_time", "modified"],
                             or_filters=[["project_name", "like", f"%{q}%"], ["customer", "like", f"%{q}%"]] if q else None,
                             order_by="modified desc", limit=300)
    if linhas:
        nomes = [p.name for p in linhas]
        cont = {}
        for r in frappe.db.sql("""select project, status, count(*) n from tabTask where project in %(p)s and is_group=0
                group by project, status""", {"p": tuple(nomes)}, as_dict=1):
            cont.setdefault(r.project, {})[r.status] = r.n
        for p in linhas:
            c = cont.get(p.name, {})
            p.abertas = sum(v for k, v in c.items() if k not in FEITAS_PROJ)
            p.atrasadas = c.get("Overdue", 0)
            p.concluidas = c.get("Completed", 0)
            p.total = sum(c.values())
            p.progresso = flt(p.percent_complete) or (round(100 * p.concluidas / p.total) if p.total else 0)
    return linhas


@frappe.whitelist()
def projeto(nome: str):
    _guarda()
    p = frappe.get_doc("Project", nome)
    p.check_permission("read")
    tarefas_ = frappe.get_list("Task", filters={"project": nome, "is_group": 0, "status": ["!=", "Template"]},
                               fields=["name", "subject", "status", "priority", "exp_end_date", "_assign", "completed_on", "ordem"],
                               order_by="ordem asc, exp_end_date asc", limit=1000)
    colunas = []
    for est, rot in ESTADOS_PROJ:
        cart = [{"id": t.name, "titulo": t.subject, "prioridade": PRIOR.get(t.priority, t.priority),
                 "data": str(getdate(t.exp_end_date)) if t.exp_end_date else None, "dono": _nome(_dono(t._assign))}
                for t in tarefas_ if t.status == est]
        if est == "Completed":
            cart = cart[-30:]
        colunas.append({"estado": est, "rotulo": rot, "cartoes": cart})
    horas = flt(frappe.db.sql("select sum(hours) from `tabTimesheet Detail` where project=%s and docstatus=1", nome)[0][0])
    return {"nome": p.name, "titulo": p.project_name, "estado": p.status, "cliente": p.customer, "marca": p.marca,
            "progresso": flt(p.percent_complete), "fim": str(p.expected_end_date) if p.expected_end_date else None,
            "inicio": str(p.expected_start_date) if p.expected_start_date else None, "horas": horas,
            "horas_orcamento": flt(p.get("horas_orcamento")), "notas": p.notes or "", "colunas": colunas,
            "pode_editar": frappe.has_permission("Task", "write"), "classico": f"/app/project/{p.name}"}


# ── Fila de tarefas e lembretes (H10, 20-11-2026) ──────────────────────────────────────────────────────
def _fim_do_dia():
    from frappe.utils import add_to_date, get_datetime
    return add_to_date(get_datetime(nowdate()), days=1)


@frappe.whitelist()
def fila():
    """As minhas tarefas de hoje e atrasadas (CRM e projetos), pela ordem: atrasadas primeiro, depois prioridade."""
    _guarda()
    u = frappe.session.user
    fim = _fim_do_dia()
    pr = {"Urgent": 0, "High": 1, "Medium": 2, "Low": 3}
    out = []
    for t in frappe.get_list("CRM Task", filters={"assigned_to": u, "status": ["not in", FEITAS_CRM], "due_date": ["<", fim]},
                             fields=["name", "due_date", "priority"], limit=200):
        out.append({"tipo": "crm", "id": t.name, "d": str(t.due_date), "p": pr.get(t.priority, 2)})
    for t in frappe.get_list("Task", filters={"_assign": ["like", f'%"{u}"%'], "status": ["not in", FEITAS_PROJ],
                                              "exp_end_date": ["<", fim], "is_group": 0},
                             fields=["name", "exp_end_date", "priority"], limit=200):
        out.append({"tipo": "projeto", "id": t.name, "d": str(t.exp_end_date), "p": pr.get(t.priority, 2)})
    out.sort(key=lambda x: (x["d"][:10], x["p"]))
    return out


@frappe.whitelist()
def detalhe(tipo: str, nome: str):
    """A tarefa e o resumo do registo a que pertence (para trabalhar sem sair da fila)."""
    _guarda()
    from orbit.interface.api import cronologia, ficha, _titulo
    if tipo == "crm":
        t = frappe.get_doc("CRM Task", nome)
        t.check_permission("read")
        out = {"tipo": tipo, "id": nome, "titulo": t.title, "descricao": t.description or "", "data": str(t.due_date or ""),
               "prioridade": PRIOR.get(t.priority, t.priority), "ref": [t.reference_doctype, t.reference_docname] if t.reference_docname else None}
    else:
        t = frappe.get_doc("Task", nome)
        t.check_permission("read")
        out = {"tipo": tipo, "id": nome, "titulo": t.subject, "descricao": t.description or "", "data": str(t.exp_end_date or ""),
               "prioridade": PRIOR.get(t.priority, t.priority), "projeto": t.project,
               "projeto_nome": frappe.db.get_value("Project", t.project, "project_name") if t.project else "", "ref": None}
    if out["ref"] and out["ref"][0] in ("Contact", "CRM Deal", "CRM Lead", "CRM Organization"):
        try:
            f = ficha(*out["ref"])
            c = cronologia(*out["ref"])
            out["registo"] = {"titulo": f["titulo"], "sub": f["sub"], "email": f["email_principal"], "telefone": f["telefone"],
                              "recentes": (c["passado"] or [])[:5]}
        except frappe.PermissionError:
            out["registo"] = None
    return out


@frappe.whitelist(methods=["POST"])
def adiar(tipo: str, nome: str, dias: int = 1):
    _guarda()
    from frappe.utils import add_days, get_datetime
    if tipo == "crm":
        d = frappe.get_doc("CRM Task", nome)
        base = get_datetime(d.due_date) if d.due_date else get_datetime(nowdate() + " 09:00:00")
        d.due_date = add_days(max(base, get_datetime(nowdate() + " 09:00:00")), cint(dias))
    else:
        d = frappe.get_doc("Task", nome)
        base = get_datetime(d.exp_end_date) if d.exp_end_date else get_datetime(nowdate())
        d.exp_end_date = add_days(max(base, get_datetime(nowdate())), cint(dias))
        if d.status == "Overdue":
            d.status = "Open"
    d.save()
    return {"ok": True}


def lembretes():
    """Cron de 15 em 15 min: aviso no sino a quem tem uma tarefa do CRM a chegar à hora marcada (uma vez por tarefa)."""
    from frappe.utils import add_to_date, now_datetime
    agora = now_datetime()
    for t in frappe.get_all("CRM Task", filters={"status": ["not in", FEITAS_CRM], "assigned_to": ["is", "set"],
                                                 "due_date": ["between", [add_to_date(agora, minutes=-15), add_to_date(agora, minutes=15)]]},
                            fields=["name", "title", "assigned_to", "due_date", "reference_doctype", "reference_docname"]):
        chave = f"orbit:lembrete:crm:{t.name}:{t.due_date}"
        if frappe.cache.get_value(chave):
            continue
        frappe.cache.set_value(chave, 1, expires_in_sec=3 * 86400)
        try:
            frappe.get_doc({"doctype": "Notification Log", "for_user": t.assigned_to, "type": "Alert",
                            "subject": f"Tarefa: {t.title}", "email_content": f"Para {frappe.utils.format_datetime(t.due_date, 'HH:mm')}",
                            "document_type": t.reference_doctype or "CRM Task",
                            "document_name": t.reference_docname or t.name}).insert(ignore_permissions=True)
        except Exception:  # noqa: BLE001
            frappe.log_error(title="orbit.interface.trabalho.lembretes")
    frappe.db.commit()


@frappe.whitelist()
def notificacoes():
    """O sino da interface: os avisos do Frappe da pessoa (tarefas, menções, atribuições)."""
    _guarda()
    ns = frappe.get_all("Notification Log", filters={"for_user": frappe.session.user}, fields=["name", "subject", "email_content",
                        "document_type", "document_name", "read", "creation", "type"], order_by="creation desc", limit=30)
    from frappe.utils import strip_html
    for n in ns:
        n.subject = strip_html(n.subject or "")
        n.email_content = strip_html(n.email_content or "")[:200]
    return {"por_ler": sum(1 for n in ns if not n.read), "itens": ns}


@frappe.whitelist(methods=["POST"])
def marcar_lidas():
    _guarda()
    frappe.db.set_value("Notification Log", {"for_user": frappe.session.user, "read": 0}, "read", 1, update_modified=False)
    return {"ok": True}
