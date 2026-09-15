"""As apps do Orbit: quais são, quem as tem, e o que o ecrã faz com isso.

Até aqui um tenant recebia só as apps Frappe que tinha comprado — `bench
install-app` do que foi pago e mais nada. Isso é isolamento a sério: o que não
está instalado não existe. Mas tinha dois buracos:

1. As apps que vivem fora do Frappe (Mail, Docs, Sign, Events, Social, Meet,
   Chat) não passam por `install-app`. Estavam sempre na grelha, comprasse-se
   ou não.
2. Uma app não comprada desaparecia. O cliente não fica a saber que existe, e
   nós perdemos a venda. A decisão (15-09-2026) é o contrário: mostra-se tudo,
   o que não está subscrito fica a cinzento e leva ao portal.

A lista do que está activo vem do `site_config.json` do próprio site, na chave
`orbit_apps`, escrita pelo aprovisionamento a partir das subscrições. Ausente ou
`"completo"` significa tudo activo — assim os sites que já existiam não mudam de
comportamento por esta alteração entrar.

ATENÇÃO à diferença entre o cinzento e o fechado. O cinzento é vista: quem
souber o endereço da app passa à mesma. O fechado é `install-app` para as apps
Frappe e aprovisionamento para as de fora. Esta lista serve a vista; não é, nem
pode passar a ser, o mecanismo de segurança.
"""

import frappe

# Nome no ecrã → como se identifica em cada sítio.
#
#   codigo    o código de faturação (billing_plan_map / SKU da loja)
#   frappe    a app Frappe que a serve, quando é o caso — é o que `install-app`
#             instala e o que determina se existe mesmo
#   rotulo    o rótulo do Desktop Icon, para casar com a grelha
APPS = {
    "crm":      {"codigo": "W1500010", "frappe": "crm",      "rotulo": "Frappe CRM", "nome": "CRM"},
    "desk":     {"codigo": "W1500011", "frappe": "helpdesk", "rotulo": "Helpdesk",   "nome": "Desk"},
    "projects": {"codigo": "W1500012", "frappe": "erpnext",  "rotulo": "Projects",   "nome": "Projects"},
    "rh":       {"codigo": "W1500013", "frappe": "hrms",     "rotulo": "Frappe HR",  "nome": "RH"},
    "wiki":     {"codigo": "W1500014", "frappe": "wiki",     "rotulo": "Wiki",       "nome": "Wiki"},
    "docs":     {"codigo": "W1500015", "frappe": None,       "rotulo": "Docs",       "nome": "Docs"},
    "sign":     {"codigo": "W1500016", "frappe": None,       "rotulo": "Sign",       "nome": "Sign"},
    "mail":     {"codigo": "W1500017", "frappe": None,       "rotulo": "Mail",       "nome": "Mail"},
    "meet":     {"codigo": "W1500018", "frappe": None,       "rotulo": "Meet",       "nome": "Meet"},
    "chat":     {"codigo": "W1500019", "frappe": None,       "rotulo": "Chat",       "nome": "Chat"},
    "events":   {"codigo": "W1500020", "frappe": None,       "rotulo": "Events",     "nome": "Events"},
    "erp":      {"codigo": "W1500021", "frappe": "erpnext",  "rotulo": "ERP",        "nome": "ERP"},
    "social":   {"codigo": "W1500022", "frappe": None,       "rotulo": "Social",     "nome": "Social"},
}

# Onde o cliente vai subscrever o que lhe falta.
PORTAL = "https://portal.stratechna.com/metodos-pagamento"
LOJA = "https://stratechna.com/produto"


def activas() -> set[str]:
    """As apps a que este tenant tem direito.

    `orbit_apps` no site_config: lista de nomes, ou "completo". Ausente também
    é tudo — um site criado antes disto existir não pode perder apps só porque
    passámos a saber contá-las.
    """
    valor = frappe.conf.get("orbit_apps")
    if not valor or valor == "completo":
        return set(APPS)
    if isinstance(valor, str):
        valor = [p.strip() for p in valor.split(",")]
    return {p for p in valor if p in APPS}


def _por_rotulo() -> dict:
    return {d["rotulo"]: nome for nome, d in APPS.items()}


def acrescentar_ao_boot(bootinfo) -> None:
    """Põe no arranque o que o ecrã precisa de saber para pintar a cinzento.

    Vai no boot e não numa chamada à parte porque a grelha desenha-se de uma
    vez: um pedido extra deixaria os cartões a saltar de cor depois de já
    estarem no ecrã.
    """
    act = activas()
    bootinfo.orbit_apps = {
        "activas": sorted(act),
        "inactivas": {
            d["rotulo"]: {"nome": d["nome"], "codigo": d["codigo"]}
            for nome, d in APPS.items() if nome not in act
        },
        "portal": PORTAL,
    }
