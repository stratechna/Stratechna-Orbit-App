# RH na interface nova (/orbit) — lote 6 do plano das opções dos originais (25-11-2026)
#
# O que o HRMS faz no ecrã antigo e o /orbit não tinha: «Por aprovar» (pedidos de ausência e despesas de quem
# me tem como aprovador, ou todos para o gestor de RH) com Aprovar/Recusar, e o calendário de ausências do mês.
# As aprovações passam pelas regras do próprio HRMS (submeter valida saldo, sobreposições e aprovador).
import calendar

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from orbit.interface.api import _guarda


def _gestor():
    return bool({"HR Manager", "HR User", "System Manager"} & set(frappe.get_roles()))


@frappe.whitelist()
def por_aprovar():
    _guarda()
    eu = frappe.session.user
    out = []
    if frappe.db.exists("DocType", "Leave Application") and frappe.has_permission("Leave Application", "read"):
        f = {"docstatus": 0, "status": "Open"}
        if not _gestor():
            f["leave_approver"] = eu
        for x in frappe.get_list("Leave Application", filters=f, fields=["name", "employee_name", "leave_type", "from_date", "to_date",
                                                                         "total_leave_days", "half_day", "description", "creation"], order_by="from_date asc", limit=200):
            out.append({"doctype": "Leave Application", "name": x.name, "tipo": "Ausência", "pessoa": x.employee_name,
                        "titulo": _(x.leave_type), "de": str(x.from_date), "ate": str(x.to_date), "dias": flt(x.total_leave_days),
                        "meio_dia": cint(x.half_day), "nota": x.description or "", "quando": str(x.creation)})
    if frappe.db.exists("DocType", "Expense Claim") and frappe.has_permission("Expense Claim", "read"):
        f = {"docstatus": 0, "approval_status": "Draft"}
        if not _gestor():
            f["expense_approver"] = eu
        for x in frappe.get_list("Expense Claim", filters=f, fields=["name", "employee_name", "posting_date", "total_claimed_amount",
                                                                     "remark", "creation"], order_by="posting_date asc", limit=200):
            out.append({"doctype": "Expense Claim", "name": x.name, "tipo": "Despesa", "pessoa": x.employee_name,
                        "titulo": _("Despesas"), "de": str(x.posting_date), "valor": flt(x.total_claimed_amount),
                        "nota": x.remark or "", "quando": str(x.creation)})
    return out


@frappe.whitelist(methods=["POST"])
def decidir(doctype: str, name: str, aprovar: int = 1, nota: str = None):
    _guarda()
    if doctype not in ("Leave Application", "Expense Claim"):
        frappe.throw(_("Tipo inválido."))
    d = frappe.get_doc(doctype, name)
    d.check_permission("write")
    if doctype == "Leave Application":
        d.status = "Approved" if cint(aprovar) else "Rejected"
    else:
        d.approval_status = "Approved" if cint(aprovar) else "Rejected"
    if nota:
        d.add_comment("Comment", nota)
    d.save()
    d.submit()   # o HRMS só fecha o pedido ao submeter (aprovado ou recusado)
    return {"ok": 1}


@frappe.whitelist()
def ausencias(ano: int, mes: int):
    _guarda()
    ano, mes = cint(ano), cint(mes)
    ini = getdate(f"{ano}-{mes:02d}-01")
    fim = getdate(f"{ano}-{mes:02d}-{calendar.monthrange(ano, mes)[1]}")
    out = []
    if frappe.db.exists("DocType", "Leave Application") and frappe.has_permission("Leave Application", "read"):
        for x in frappe.get_list("Leave Application", filters={"docstatus": ["!=", 2], "status": ["in", ["Approved", "Open"]],
                                                              "from_date": ["<=", fim], "to_date": [">=", ini]},
                                 fields=["name", "employee", "employee_name", "leave_type", "from_date", "to_date", "status", "half_day"], limit=500):
            out.append({"name": x.name, "pessoa": x.employee_name or x.employee, "tipo": _(x.leave_type), "de": str(x.from_date),
                        "ate": str(x.to_date), "aprovada": x.status == "Approved", "meio_dia": cint(x.half_day)})
    feriados = []
    lista = frappe.db.get_value("Company", frappe.defaults.get_user_default("Company"), "default_holiday_list") if frappe.db.exists("DocType", "Holiday List") else None
    if lista:
        feriados = [{"data": str(h.holiday_date), "nome": h.description}
                    for h in frappe.get_all("Holiday", filters={"parent": lista, "holiday_date": ["between", [ini, fim]], "weekly_off": 0},
                                            fields=["holiday_date", "description"])]
    return {"ausencias": out, "feriados": feriados, "inicio": str(ini), "fim": str(fim)}
