"""Tempo dentro da interface /orbit (A5 do plano da interface única, 20-11-2026).

O registo de horas é a Timesheet do ERPNext — a fonte do livro de horas do cliente no portal (ao submeter,
`orbit.portal.tempo_submetido` envia-a; ao anular, `tempo_cancelado` desfaz). Aqui regista-se com as permissões da
pessoa, uma linha por registo, e submete-se logo. Regra da casa: o tempo é uma estimativa do trabalho, não um
cronómetro (por isso horas escritas, não início/fim).
"""
from __future__ import annotations

import frappe
from frappe.utils import add_days, add_to_date, cint, flt, get_datetime, get_first_day, getdate, nowdate


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _meus(filtros_extra=None):
    u = frappe.session.user
    return [["Timesheet", "docstatus", "<", 2], ["Timesheet", "user", "=", u]] + (filtros_extra or [])


@frappe.whitelist()
def semana(inicio: str = None):
    _guarda()
    ini = getdate(inicio) if inicio else getdate(nowdate())
    ini = add_days(ini, -ini.weekday())
    fim = add_days(ini, 7)
    u = frappe.session.user
    linhas = frappe.db.sql("""select t.name ts, t.docstatus, t.customer, t.custom_hd_ticket, d.name, d.from_time, d.hours,
            d.activity_type, d.project, d.task, d.description, d.is_billable
        from tabTimesheet t join `tabTimesheet Detail` d on d.parent = t.name
        where t.docstatus < 2 and (t.user = %(u)s or (ifnull(t.user,'') = '' and t.owner = %(u)s))
          and d.from_time >= %(a)s and d.from_time < %(b)s
        order by d.from_time asc""", {"u": u, "a": ini, "b": fim}, as_dict=1)
    for l in linhas:
        l.dia = str(getdate(l.from_time))
        l.projeto_nome = frappe.db.get_value("Project", l.project, "project_name") if l.project else ""
        l.tarefa_nome = frappe.db.get_value("Task", l.task, "subject") if l.task else ""
        l.ticket_nome = frappe.db.get_value("HD Ticket", l.custom_hd_ticket, "subject") if l.custom_hd_ticket else ""
        l.estado = "Submetido" if l.docstatus == 1 else "Rascunho"
    dias = {}
    for l in linhas:
        dias[l.dia] = dias.get(l.dia, 0) + flt(l.hours)
    return {"inicio": str(ini), "linhas": linhas, "dias": dias, "total": sum(dias.values())}


@frappe.whitelist()
def opcoes(q: str = ""):
    _guarda()
    q = (q or "").strip()
    f = [["customer_name", "like", f"%{q}%"]] if q else None
    clientes = frappe.get_list("Customer", fields=["name", "customer_name"], or_filters=f, filters={"disabled": 0},
                               order_by="customer_name asc", limit=30)
    projetos = frappe.get_list("Project", filters={"status": "Open"}, fields=["name", "project_name", "customer"],
                               order_by="project_name asc", limit=300)
    atividades = frappe.get_all("Activity Type", filters={"disabled": 0} if frappe.db.has_column("Activity Type", "disabled") else {},
                                pluck="name")
    return {"clientes": clientes, "projetos": projetos, "atividades": atividades}


@frappe.whitelist()
def tarefas_do_projeto(projeto: str):
    _guarda()
    return frappe.get_list("Task", filters={"project": projeto, "status": ["not in", ["Completed", "Cancelled", "Template"]], "is_group": 0},
                           fields=["name", "subject"], order_by="subject asc", limit=300)


@frappe.whitelist(methods=["POST"])
def registar(data: str, horas: float, descricao: str = "", cliente: str = None, projeto: str = None, tarefa: str = None,
             ticket: str = None, atividade: str = None, faturavel: int = 1):
    _guarda()
    h = flt(horas)
    if h <= 0 or h > 16:
        frappe.throw("Indique as horas (entre 0 e 16).")
    descricao = (descricao or "").strip()[:1000]
    if not descricao:
        frappe.throw("Descreva o que foi feito.")
    if projeto and not cliente:
        cliente = frappe.db.get_value("Project", projeto, "customer")
    if ticket and not cliente:
        crm = frappe.db.get_value("HD Ticket", ticket, "crm_account_id")
        cliente = frappe.db.get_value("Customer", {"crm_account_id": crm}) if crm else None
    if not (cliente or projeto or ticket):
        frappe.throw("Escolha o cliente, o projeto ou o ticket.")
    atividade = atividade if atividade and frappe.db.exists("Activity Type", atividade) else ("Apoio ao cliente" if ticket else "Execution")
    inicio = get_datetime(f"{getdate(data)} 09:00:00")
    ja = frappe.db.sql("""select ifnull(sum(d.hours),0) from tabTimesheet t join `tabTimesheet Detail` d on d.parent=t.name
        where t.docstatus<2 and t.user=%s and date(d.from_time)=%s""", (frappe.session.user, getdate(data)))[0][0]
    inicio = add_to_date(inicio, seconds=int(flt(ja) * 3600))       # linhas seguidas no dia, sem sobreposições
    ts = frappe.get_doc({"doctype": "Timesheet", "company": frappe.defaults.get_user_default("Company") or frappe.get_all("Company", pluck="name")[0],
                         "customer": cliente, "parent_project": projeto, "custom_hd_ticket": ticket, "user": frappe.session.user,
                         "time_logs": [{"activity_type": atividade, "from_time": inicio, "hours": h,
                                        "to_time": add_to_date(inicio, seconds=int(h * 3600)), "project": projeto,
                                        "task": tarefa, "description": descricao, "is_billable": 1 if cint(faturavel) else 0}]})
    ts.insert()
    ts.submit()
    return {"ok": True, "timesheet": ts.name}


@frappe.whitelist(methods=["POST"])
def anular(timesheet: str):
    _guarda()
    ts = frappe.get_doc("Timesheet", timesheet)
    if ts.user != frappe.session.user and ts.owner != frappe.session.user:
        frappe.throw("Só quem registou pode anular.", frappe.PermissionError)
    if ts.docstatus == 1:
        ts.cancel()
    elif ts.docstatus == 0:
        ts.delete()
    return {"ok": True}


@frappe.whitelist()
def do_registo(doctype: str, name: str):
    """Horas do cliente (pelo Customer ligado à empresa do CRM): este mês, os 3 anteriores e os últimos registos."""
    _guarda()
    from orbit.interface.api import _relacionados
    frappe.get_doc(doctype, name).check_permission("read")
    rel, _e = _relacionados(doctype, name)
    clientes = {c for c in (frappe.db.get_value("CRM Organization", o, "customer") for o in rel["CRM Organization"]) if c}
    if not clientes:
        return {"cliente": None}
    hoje = getdate(nowdate())
    ini_mes = get_first_day(hoje)
    ini_3 = get_first_day(add_days(ini_mes, -85))
    r = frappe.db.sql("""select sum(case when d.from_time >= %(m)s then d.hours else 0 end) mes, sum(d.hours) tres
        from tabTimesheet t join `tabTimesheet Detail` d on d.parent=t.name
        where t.docstatus=1 and t.customer in %(c)s and d.from_time >= %(t)s""", {"c": tuple(clientes), "m": ini_mes, "t": ini_3}, as_dict=1)[0]
    ult = frappe.db.sql("""select d.from_time, d.hours, d.description, d.activity_type, t.user from tabTimesheet t
        join `tabTimesheet Detail` d on d.parent=t.name where t.docstatus=1 and t.customer in %(c)s
        order by d.from_time desc limit 5""", {"c": tuple(clientes)}, as_dict=1)
    from orbit.interface.api import _nome_user
    for u in ult:
        u.quem = _nome_user(u.user) if u.user else ""
    return {"cliente": sorted(clientes)[0], "mes": flt(r.mes), "tres_meses": flt(r.tres), "ultimos": ult}
