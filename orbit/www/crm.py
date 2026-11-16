# A página /crm do Orbit: a do CRM, tal e qual, com o tema Stratechna por cima.
#
# O Frappe procura as páginas www/ das apps instaladas da última para a primeira,
# e a orbit é instalada depois do CRM em todos os tenants — por isso esta página
# ganha à original. O contexto é o do CRM (mesma função, mesmas permissões); o
# modelo (crm.html, ao lado) inclui o do CRM e só lhe acrescenta a folha de estilo.
# Nenhum ficheiro do CRM é alterado (AGPL, art.º 13; actualizações sem conflitos).
from crm.www.crm import get_context, no_cache  # noqa: F401
