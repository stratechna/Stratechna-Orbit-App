# /orbit — a interface única do Orbit (20-11-2026; orbit/interface/api.py).
# Só abre nos tenants com `orbit_interface_nova: 1` no site_config; nos outros vai para o /crm de sempre.
import frappe

no_cache = 1


def get_context(context):
    from orbit.interface.api import ligada

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/orbit"
        raise frappe.Redirect
    if not ligada():
        frappe.local.flags.redirect_location = "/crm"
        raise frappe.Redirect
    context.no_cache = 1
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.versao = "1"
    return context
