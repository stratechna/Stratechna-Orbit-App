"""Utilizadores contratados (16-10-2026).

O portal escreve no site_config do tenant `orbit_utilizadores_max` (a quantidade da subscrição Orbit)
e `orbit_contas_servico` (contas técnicas que não contam). Este gancho recusa criar, activar ou
promover a utilizador do sistema alguém que passe o limite. Sem a chave — tenants antigos, demos —
não faz nada. O Administrator e os guiões do portal (que correm como Administrator e já acertaram a
subscrição antes de criar a pessoa) passam sempre; quem esbarra é um administrador do cliente que
crie pessoas directamente no Orbit.
"""
import frappe
from frappe import _

SEMPRE = {"administrator", "guest", "suporte@stratechna.pt"}   # suporte@ = assistência (entrada_unica)


def _conta(user: str, servico: set) -> bool:
    return (user or "").lower() not in servico


def guarda(doc, method=None):
    maximo = frappe.conf.get("orbit_utilizadores_max")
    if not maximo or frappe.flags.in_migrate or frappe.flags.in_install or frappe.flags.in_patch:
        return
    if getattr(frappe.session, "user", None) == "Administrator":
        return
    servico = SEMPRE | {x.lower() for x in (frappe.conf.get("orbit_contas_servico") or [])}
    if doc.user_type != "System User" or not doc.enabled or not _conta(doc.name or doc.email, servico):
        return
    antes = doc.get_doc_before_save() if not doc.is_new() else None
    if antes and antes.enabled and antes.user_type == "System User":
        return   # já contava — gravar a ficha de quem já existe nunca é bloqueado
    activos = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["!=", doc.name or ""]},
                             pluck="name")
    usados = len([u for u in activos if _conta(u, servico)])
    if usados + 1 > int(maximo):
        frappe.throw(_("Atingiu os {0} utilizadores contratados do seu Orbit. Peça mais na área de cliente "
                       "do portal Stratechna (Stratechna Orbit → Pessoas).").format(maximo),
                     frappe.ValidationError, title=_("Utilizadores contratados"))
