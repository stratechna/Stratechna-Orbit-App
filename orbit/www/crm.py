# A página /crm do Orbit: a do CRM, tal e qual, com o tema Stratechna por cima.
#
# O Frappe procura as páginas www/ das apps instaladas da última para a primeira,
# e a orbit é instalada depois do CRM em todos os tenants — por isso esta página
# ganha à original. O contexto é o do CRM (mesma função, mesmas permissões); o
# modelo (crm.html, ao lado) inclui o do CRM e só lhe acrescenta a folha de estilo.
# Nenhum ficheiro do CRM é alterado (AGPL, art.º 13; actualizações sem conflitos).
#
# 23-11-2026 (Vítor: «acabar com o CRM clássico»): com a interface nova ligada, qualquer endereço do CRM clássico
# (/crm, /crm/deals/X, /crm/leads, …) abre o ecrã equivalente em /orbit — ligações antigas, emails, avisos e favoritos
# deixam de ir parar ao ecrã antigo. `?classico=1` ainda o abre (só para assistência; não há ligação para ele).
import frappe
from crm.www.crm import get_context as _get_context_crm, no_cache  # noqa: F401
from urllib.parse import quote, unquote

_LISTAS = {"deals": "negocios", "leads": "leads", "contacts": "contactos", "organizations": "empresas",
           "tasks": "tarefas", "notes": "erp/FCRM%20Note", "call-logs": "erp/CRM%20Call%20Log", "dashboard": "inicio",
           "data-import": "contactos", "data-imports": "contactos"}
_FICHAS = {"deals": "negocio", "leads": "lead", "contacts": "contacto", "organizations": "empresa"}


def _destino(caminho: str) -> str:
    partes = [p for p in (caminho or "").split("/") if p][1:]   # tira o «crm»
    if not partes:
        return "/orbit#/inicio"
    lista = partes[0]
    if len(partes) > 1 and lista in _FICHAS:
        return f"/orbit#/{_FICHAS[lista]}/{quote(unquote(partes[1]), safe='')}"
    return "/orbit#/" + _LISTAS.get(lista, "inicio")


def get_context(context):
    try:
        from orbit.interface.api import ligada
        if ligada() and not frappe.form_dict.get("classico") and frappe.session.user != "Guest":
            frappe.local.flags.redirect_location = _destino(frappe.request.path)
            raise frappe.Redirect
    except frappe.Redirect:
        raise
    except Exception:
        pass
    return _get_context_crm()
