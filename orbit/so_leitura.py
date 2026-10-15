"""Contas só de leitura — para as demonstrações (15-10-2026, utilizador «Visitante» da VELA).

As apps abrem por funções que também escrevem (o CRM mostra tudo só a Sales Manager, o Desk só abre a
Agent, o Wiki a Wiki Approver). Uma função só de leitura não chega, e os Server Scripts só se ligam
para o bench inteiro — o que daria a qualquer System Manager de um cliente o poder de correr código.

Por isso este gancho: num site com `orbit_funcao_so_leitura` no site_config (ex.: "Visitante"), quem
tem essa função não cria, não grava, não submete, não cancela e não apaga NENHUM documento. Sem a chave
— todos os tenants de clientes — não faz nada. O Administrator e as tarefas de sistema passam sempre.
"""
import frappe
from frappe import _

# o que o próprio Frappe escreve à volta de uma sessão, e que não é dado da demonstração
LIVRES = {"Version", "Activity Log", "Access Log", "Route History", "Error Log", "Scheduled Job Log",
          "Session Default Settings", "Notification Log", "Energy Point Log", "View Log", "Deleted Document"}


def guarda(doc, method=None):
    funcao = frappe.conf.get("orbit_funcao_so_leitura")
    if not funcao or doc.doctype in LIVRES:
        return
    user = getattr(frappe.session, "user", None)
    if not user or user in ("Administrator", "Guest") or frappe.flags.in_migrate or frappe.flags.in_install:
        return
    if funcao in frappe.get_roles(user):
        frappe.throw(_("Esta é uma conta de demonstração só de leitura — nada é gravado."),
                     frappe.PermissionError, title=_("Demonstração"))
