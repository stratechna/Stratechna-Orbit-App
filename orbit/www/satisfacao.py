# /satisfacao — o inquérito do fim do ticket (23-11-2026, docs/PLANO-DESK-TICKETS.md K7/K8). Sem conta: a ligação traz
# o n.º do ticket e uma chave (HMAC) que só o Orbit sabe gerar.
import hmac

import frappe

no_cache = 1


def get_context(context):
    from orbit.interface.desk import NOTAS, _token
    t = frappe.form_dict.get("t") or ""
    k = frappe.form_dict.get("k") or ""
    context.no_cache = 1
    context.valido = bool(t and frappe.db.exists("HD Ticket", t) and hmac.compare_digest(_token(t), k))
    if not context.valido:
        return context
    tk = frappe.db.get_value("HD Ticket", t, ["name", "subject", "orbit_inquerito"], as_dict=True)
    context.t, context.k = t, k
    context.assunto = tk.subject or ""
    context.respondido = tk.orbit_inquerito == "respondido"
    context.nota = frappe.form_dict.get("n") if frappe.form_dict.get("n") in NOTAS else ""
    context.reabrir = frappe.form_dict.get("reabrir") == "1"
    context.notas = [(k2, v[1]) for k2, v in NOTAS.items()]
    return context
