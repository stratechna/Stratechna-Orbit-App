"""Põe a grelha de módulos no estado em que a vendemos.

O desenho de cada módulo NÃO se decide aqui. O frontend monta o caminho a partir
da app dona do módulo — `assets/<app>/icons/desktop_icons/<estilo>/<nome>.svg`
(frappe/public/js/frappe/utils/utils.js, get_desktop_icon) — e só cai no
`logo_url` da base de dados quando esse ficheiro não existe. Como o Frappe, o
ERPNext e o HR trazem essas pastas cheias, os nossos símbolos entram por ficheiro,
na construção da imagem (Containerfile.marca), e não por definição.

Tentou-se o contrário: mudar o campo `app` dos Desktop Icon para `orbit`, para
o caminho apontar para cá. Lê bem no papel e parte a casa — `build_folder_map`
(sidebar_header.js) só mostra na barra lateral de cada app os ícones cujo `app`
é o dela, e os módulos do ERPNext desapareciam de lá. O campo `app` é a relação
de propriedade, não um apontador para ficheiros.

O que fica para a base de dados são as duas decisões de produto:

  sincronizar()  as fichas que as apps trazem em ficheiro voltam à tabela. O
                 `bench migrate` não as repõe — são um comando à parte
                 (`bench sync-desktop-icons`) — e já se viu a tabela cair de 49
                 para 13 linhas sem ninguém lhe tocar, deixando a grelha vazia.
  achatar()      cada módulo é uma app vendável, logo não há pastas: a
                 «Accounting» do ERPNext passa a módulo e os nove filhos sobem.

Corre no `after_migrate`, o último passo de qualquer actualização.
"""

import os

import frappe


def sincronizar():
    """Reimporta as fichas de Desktop Icon que cada app traz em ficheiro.

    É o mesmo que faz `bench sync-desktop-icons`, que não corre no migrate.
    """
    from frappe.modules.import_file import import_file_by_path
    from frappe.modules.utils import get_app_level_directory_path

    lidos, importados = 0, 0
    for app in frappe.get_installed_apps():
        pasta = get_app_level_directory_path("desktop_icon", app)
        if not os.path.isdir(pasta):
            continue
        for f in sorted(os.listdir(pasta)):
            if not f.endswith(".json"):
                continue
            lidos += 1
            if import_file_by_path(os.path.join(pasta, f), force=True, ignore_version=True):
                importados += 1

    frappe.db.commit()
    _limpar_cache()
    aviso = f"Orbit: fichas de ícones — {lidos} lidas, {importados} importadas"
    print(aviso)
    frappe.logger().info(aviso)


def achatar():
    """Desfaz as pastas da grelha: cada módulo é uma app, e vende-se sozinho."""
    achatadas = []
    for pasta in frappe.get_all("Desktop Icon", filters={"icon_type": "Folder"},
                                fields=["name", "label"]):
        filhos = frappe.get_all("Desktop Icon", filters={"parent_icon": pasta.label}, pluck="name")
        frappe.db.set_value("Desktop Icon", pasta.name, "icon_type", "Link", update_modified=False)
        for f in filhos:
            frappe.db.set_value("Desktop Icon", f, "parent_icon", "", update_modified=False)
        achatadas.append(f"{pasta.label} (+{len(filhos)})")

    frappe.db.commit()
    _limpar_cache()
    aviso = "Orbit: pastas achatadas — " + (", ".join(achatadas) or "nenhuma")
    print(aviso)
    frappe.logger().info(aviso)


def _limpar_cache():
    # a lista de ficheiros e os ícones são lidos no arranque e ficam no boot
    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
    frappe.clear_cache()


# ── Atalhos para os módulos que vivem fora do Frappe ────────────────────────
# O Mail, o Docs, o Sign, o Events e o Social são sistemas separados, cada um no
# seu domínio. Entram na grelha como Desk Icon com link externo — o mesmo
# mecanismo que o Frappe usa para o CRM e o Helpdesk, que também têm frontend
# próprio.
#
# Vivem aqui e não num script à parte por uma razão aprendida à força: instalar
# qualquer app corre «Creating Desktop Icons», que re-sincroniza a tabela e apaga
# o que não reconhece. Foi assim que estes cinco desapareceram. Recriá-los no
# after_install e no after_migrate fecha esse buraco de vez.

ATALHOS = [
    {"nome": "Mail", "url": "https://mail.orbit.{dominio}", "simbolo": "mail"},
    {"nome": "Docs", "url": "https://docs.{dominio}", "simbolo": "docs"},
    {"nome": "Sign", "url": "https://sign.{dominio}", "simbolo": "sign"},
    {"nome": "Events", "url": "https://events.{dominio}", "simbolo": "events"},
    {"nome": "Social", "url": "https://social.{dominio}", "simbolo": "social"},
]


# As apps com frontend próprio, que já vêm na grelha e só precisam do símbolo
# certo. O rótulo é o da base de dados, não o que se lê no ecrã.
MARCAS_APPS = {
    "Frappe CRM": "crm",
    "Helpdesk": "desk",
    "Wiki": "wiki",
    "Frappe HR": "rh",
}


def _dominio_do_tenant() -> str:
    """O domínio onde vivem os módulos de fora. Configurável por site em
    site_config.json (`orbit_dominio_apps`); por omissão, o nosso."""
    return frappe.conf.get("orbit_dominio_apps") or "stratechna.com"


def repor_atalhos():
    dominio = _dominio_do_tenant()
    criados, mantidos = [], 0
    for a in ATALHOS:
        url = a["url"].format(dominio=dominio)
        existente = frappe.db.get_value("Desktop Icon", {"label": a["nome"]}, "name")
        if existente:
            frappe.db.set_value("Desktop Icon", existente, {"link": url, "app": "orbit"},
                                update_modified=False)
            mantidos += 1
            continue
        frappe.get_doc({
            "doctype": "Desktop Icon",
            "label": a["nome"],
            "icon_type": "App",
            "link_type": "External",
            "link": url,
            "app": "orbit",
            "logo_url": f"/assets/orbit/icons/apps/{a['simbolo']}.svg",
            "bg_color": "gray",
            "standard": 1,
            "hidden": 0,
        }).insert(ignore_permissions=True)
        criados.append(a["nome"])

    # As apps que têm frontend próprio não passam pelos símbolos dos módulos: o
    # `get_desktop_icon` não encontra ficheiro para o rótulo delas e cai no
    # `logo_url`. Sem isto, o RH aparecia com o logótipo verde do Frappe HR no
    # meio dos nossos quadrados, e o CRM, o Desk e o Wiki dependiam de ficheiros
    # carregados à mão em /files — que não viajam com a app.
    for rotulo, simbolo in MARCAS_APPS.items():
        nome = frappe.db.get_value("Desktop Icon", {"label": rotulo}, "name")
        if nome:
            frappe.db.set_value("Desktop Icon", nome, "logo_url",
                                f"/assets/orbit/icons/apps/{simbolo}.svg",
                                update_modified=False)

    frappe.db.commit()
    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
    frappe.clear_cache()

    aviso = f"Orbit: atalhos — {len(criados)} criados, {mantidos} actualizados (domínio {dominio})"
    print(aviso)
    frappe.logger().info(aviso)


# ── Nomes dos módulos ───────────────────────────────────────────────────────
# Regra: marca não se traduz, função traduz-se.
#
# Os módulos que vendemos têm nome de produto — aparecem assim no catálogo, nos
# domínios (docs., sign., events.) e nas propostas. Traduzi-los na interface
# criaria duas designações para a mesma coisa. Os módulos do ERPNext e do RH
# descrevem uma função, e essa é em português.
#
# O Frappe passa os rótulos por `_()` (frappe/apps.py), por isso o doctype
# Translation é o ponto de extensão certo — e a tradução é por frase inteira, não
# por pedaço, portanto "Stock Entry" não é afectado por traduzirmos "Stock".

NOMES = {
    # função → português
    "Assets": "Ativos",
    "Buying": "Compras",
    "Selling": "Vendas",
    "Stock": "Inventário",
    "Manufacturing": "Produção",
    "Subcontracting": "Subcontratação",
    "Quality": "Qualidade",
    "Projects": "Projetos",
    "Payments": "Pagamentos",
    "Banking": "Bancos",
    "Taxes": "Impostos",
    "Budget": "Orçamentos",
    "Financial Reports": "Relatórios financeiros",
    "Accounts Setup": "Configuração de contas",
    "Account Setup": "Configuração de contas",
    "Share Management": "Participações",
    "Subscription": "Subscrições",
    "Accounting": "Contabilidade",
    "Invoicing": "Faturação",
    "Organization": "Organização",
    "ERPNext Settings": "Definições",
    "Support": "Suporte",
    # marca → fica como está; só se encurta o que vinha com o nome do fabricante
    "Frappe CRM": "CRM",
    "Helpdesk": "Desk",
    "ERPNext": "ERP",
    "Frappe HR": "RH",
    "HR": "RH",
}

# A página de construção do Frappe é ferramenta de quem programa, não um módulo
# do cliente. Fica escondida em vez de traduzida.
ESCONDER = ("Framework", "Frappe Framework", "Build")


def repor_nomes():
    idioma = frappe.db.get_single_value("System Settings", "language") or "pt"
    novas, actualizadas = 0, 0
    for origem, texto in NOMES.items():
        nome = frappe.db.get_value("Translation", {"language": idioma, "source_text": origem})
        if nome:
            if frappe.db.get_value("Translation", nome, "translated_text") != texto:
                frappe.db.set_value("Translation", nome, "translated_text", texto)
                actualizadas += 1
        else:
            frappe.get_doc({"doctype": "Translation", "language": idioma,
                            "source_text": origem, "translated_text": texto}).insert(
                ignore_permissions=True)
            novas += 1

    escondidos = 0
    for rotulo in ESCONDER:
        for nome in frappe.get_all("Desktop Icon", filters={"label": rotulo}, pluck="name"):
            frappe.db.set_value("Desktop Icon", nome, "hidden", 1, update_modified=False)
            escondidos += 1
        if frappe.db.exists("Workspace", rotulo):
            frappe.db.set_value("Workspace", rotulo, "is_hidden", 1, update_modified=False)

    frappe.db.commit()
    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")
    frappe.clear_cache()

    aviso = (f"Orbit: nomes — {novas} traduções novas, {actualizadas} actualizadas, "
             f"{escondidos} ícones escondidos (idioma {idioma})")
    print(aviso)
    frappe.logger().info(aviso)
