# /orbit — a interface única do Orbit (20-11-2026; orbit/interface/api.py).
# Só abre nos tenants com `orbit_interface_nova: 1` no site_config; nos outros vai para o /crm de sempre.
import frappe

no_cache = 1


def get_context(context):
    from orbit.interface.api import ligada

    if frappe.session.user == "Guest":
        from urllib.parse import quote
        app = frappe.form_dict.get("app")
        destino = f"/orbit?app={app}" if app and app.isalnum() else "/orbit"
        frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(destino, safe="/")
        raise frappe.Redirect
    if not ligada():
        frappe.local.flags.redirect_location = "/crm"
        raise frappe.Redirect
    context.no_cache = 1
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.versao = "104"
    # 23-11-2026: cada app com o seu ícone e nome — no separador e quando é gravada no telemóvel (orbit/interface/push.py)
    from orbit.interface.push import APPS
    app = frappe.form_dict.get("app") or "crm"
    context.app = app if app in APPS else "crm"
    context.app_nome = "Orbit " + APPS[context.app][0]
    context.app_cor = "#161a1d"
    return context
