#!/usr/bin/env python3
"""Marca das apps do Frappe que trazem frontend próprio: CRM, Desk e RH.

Porque é que isto existe e não bastam as definições
---------------------------------------------------
O CRM (`FCRM Settings`), o Helpdesk (`HD Settings`) e o Wiki têm campos de marca
na base de dados, e o `orbit_marca.py` preenche-os todos. Mas há três coisas que
esses campos nunca chegam a tocar, porque são servidas antes de haver sessão:

  * o **título do separador** do browser — `<title>Frappe CRM</title>`;
  * o **manifesto PWA** — o nome com que a app se instala no telemóvel, que
    continuava a dizer «Frappe CRM» com a descrição de marketing do Frappe;
  * os **ícones do manifesto e o favicon** — o quadrado do Frappe, não o nosso.

E há ainda dezoito símbolos de módulo que ficaram para trás: o ERPNext e o HR
guardam, além da pasta `icons/desktop_icons/<estilo>/` que o Containerfile já
troca, uma segunda cópia solta (`erpnext/public/desktop_icons/` e
`hrms/public/icons/desktop_icons/*.svg`) que é a que vai no campo `icon_image`
das fichas — e é essa que a barra lateral e o comutador de apps desenham.

Licença
-------
O CRM e o Helpdesk são AGPL v3. Alterá-los obriga (artigo 13) a oferecer o código
alterado a quem lhes acede pela rede. É por isso que este ficheiro vive num
repositório público e que a página `/licencas` do Orbit aponta para ele.

Regra da casa: uma substituição que não encontre o seu padrão **falha a
construção**. Uma marca que desaparece em silêncio na actualização seguinte é
pior do que uma construção vermelha.
"""

import json
import os
import shutil
import sys

APPS = "/home/frappe/frappe-bench/apps"
AQUI = os.path.dirname(os.path.abspath(__file__))
SIMBOLOS = os.path.join(os.path.dirname(AQUI), "simbolos", "modulos")

falhas: list[str] = []
feitos = 0


def trocar(caminho: str, pares: list[tuple[str, str]], obrigatorio: bool = True) -> None:
    """Troca texto por texto num ficheiro da app. Sem o padrão, é falha."""
    global feitos
    alvo = os.path.join(APPS, caminho)
    if not os.path.exists(alvo):
        (falhas if obrigatorio else []).append(f"ficheiro em falta: {caminho}")
        return
    with open(alvo, encoding="utf-8") as f:
        texto = original = f.read()
    for antes, depois in pares:
        if antes not in texto:
            # já trocado numa passagem anterior é aceitável; nunca visto não é
            if depois in texto:
                continue
            falhas.append(f"padrão não encontrado em {caminho}: {antes!r}")
            continue
        texto = texto.replace(antes, depois)
    if texto != original:
        with open(alvo, "w", encoding="utf-8") as f:
            f.write(texto)
        feitos += 1


def manifesto(caminho: str, campos: dict) -> None:
    """Reescreve os campos de marca de um manifesto PWA, deixando o resto igual."""
    global feitos
    alvo = os.path.join(APPS, caminho)
    if not os.path.exists(alvo):
        falhas.append(f"manifesto em falta: {caminho}")
        return
    with open(alvo, encoding="utf-8") as f:
        dados = json.load(f)
    for k, v in campos.items():
        dados[k] = v
    with open(alvo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))
    feitos += 1


def copiar(origem: str, destino: str) -> None:
    """Põe um ficheiro nosso por cima de um do upstream. O destino tem de existir
    — se o upstream lhe mudou o nome, queremos saber, não criar um órfão."""
    global feitos
    o = origem if os.path.isabs(origem) else os.path.join(AQUI, origem)
    d = os.path.join(APPS, destino)
    if not os.path.exists(o):
        falhas.append(f"ficheiro nosso em falta: {origem}")
        return
    if not os.path.exists(d):
        falhas.append(f"destino não existe (mudou de nome?): {destino}")
        return
    shutil.copyfile(o, d)
    feitos += 1


# ── CRM ─────────────────────────────────────────────────────────────────────
for pagina in ("crm/crm/www/crm.html",
               "crm/crm/public/frontend/index.html",
               "crm/frontend/index.html"):
    trocar(pagina, [("<title>Frappe CRM</title>", "<title>Stratechna CRM</title>"),
                    ('content="Frappe CRM"', 'content="Stratechna CRM"')])

trocar("crm/crm/www/crm.py",
       [('_("You do not have permission to access Frappe CRM")',
         '_("You do not have permission to access Stratechna CRM")')])

manifesto("crm/crm/public/frontend/manifest.webmanifest", {
    "name": "Stratechna CRM",
    "short_name": "Stratechna CRM",
    "description": "Clientes, contactos e oportunidades — Stratechna Orbit",
    "lang": "pt-PT",
    "theme_color": "#22303d",
})

for tamanho, destino in (("180", "crm/crm/public/manifest/apple-icon-180.png"),
                         ("192", "crm/crm/public/manifest/manifest-icon-192.maskable.png"),
                         ("512", "crm/crm/public/manifest/manifest-icon-512.maskable.png"),
                         ("256", "crm/crm/public/frontend/favicon.png")):
    copiar(f"pwa/crm-{tamanho}.png", destino)

# ── Desk (Helpdesk) ─────────────────────────────────────────────────────────
for pagina in ("helpdesk/helpdesk/www/helpdesk/index.html",
               "helpdesk/helpdesk/public/desk/index.html",
               "helpdesk/desk/index.html"):
    trocar(pagina, [("<title>Helpdesk</title>", "<title>Stratechna Desk</title>"),
                    ('content="Frappe Helpdesk"', 'content="Stratechna Desk"')])

manifesto("helpdesk/helpdesk/public/desk/manifest.webmanifest", {
    "name": "Stratechna Desk",
    "short_name": "Stratechna Desk",
    "description": "Pedidos de suporte e base de respostas — Stratechna Orbit",
    "lang": "pt-PT",
    "theme_color": "#22303d",
})

for tamanho, destino in (("180", "helpdesk/helpdesk/public/desk/manifest/apple-icon-180.png"),
                         ("192", "helpdesk/helpdesk/public/desk/manifest/manifest-icon-192.maskable.png"),
                         ("512", "helpdesk/helpdesk/public/desk/manifest/manifest-icon-512.maskable.png")):
    copiar(f"pwa/desk-{tamanho}.png", destino)

# O favicon do Desk é SVG, e o nosso símbolo já é SVG — vai o mesmo ficheiro que
# a grelha usa, para não haver duas versões do mesmo desenho.
for destino in ("helpdesk/helpdesk/public/desk/favicon.svg",
                "helpdesk/desk/public/favicon.svg"):
    copiar(os.path.join(os.path.dirname(AQUI), "orbit/public/icons/apps/desk.svg"), destino)

# ── RH (Frappe HR) ──────────────────────────────────────────────────────────
# O RH tem uma app de telemóvel própria (/hrms) com o seu manifesto.
for pagina in ("hrms/hrms/public/frontend/index.html", "hrms/frontend/index.html"):
    trocar(pagina, [("<title>Frappe HR</title>", "<title>Stratechna RH</title>"),
                    ('content="Frappe HR"', 'content="Stratechna RH"')])

manifesto("hrms/hrms/public/frontend/manifest.webmanifest", {
    "name": "Stratechna RH",
    "short_name": "Stratechna RH",
    "description": "Colaboradores, férias, assiduidade e salários — Stratechna Orbit",
    "lang": "pt-PT",
    "theme_color": "#22303d",
})

for tamanho, destino in (("180", "hrms/hrms/public/manifest/apple-icon-180.png"),
                         ("192", "hrms/hrms/public/manifest/manifest-icon-192.maskable.png"),
                         ("512", "hrms/hrms/public/manifest/manifest-icon-512.maskable.png"),
                         ("192", "hrms/hrms/public/manifest/favicon-196.png")):
    copiar(f"pwa/rh-{tamanho}.png", destino)

for destino in ("hrms/hrms/public/frontend/favicon.png", "hrms/hrms/public/roster/favicon.png"):
    copiar("pwa/rh-256.png", destino)

# ── Símbolos soltos: a segunda cópia que o `icon_image` das fichas usa ───────
#
# O Containerfile já troca `<app>/public/icons/desktop_icons/<estilo>/`, que é
# onde o ecrã de apps vai buscar o desenho. Mas o campo `icon_image` das fichas
# aponta para ficheiros noutra pasta, com outros nomes, e é ESSE que a barra
# lateral e o comutador de apps desenham. Ficavam dezoito símbolos do Frappe no
# meio dos nossos. O mapa é nome-do-upstream → nome do nosso símbolo.
SOLTOS = {
    "erpnext/erpnext/public/desktop_icons": ("erpnext", {
        "accounting.svg": "accounting", "asset.svg": "assets",
        "buying.svg": "buying", "crm.svg": "crm",
        "erpnext_settings.svg": "erpnext_settings",
        "financials_reports.svg": "financial_reports",
        "manufacturing.svg": "manufacturing", "projects.svg": "projects",
        "quality.svg": "quality", "selling.svg": "selling",
        "stock.svg": "stock", "subcontracting.svg": "subcontracting",
        "support.svg": "support",
    }),
    "hrms/hrms/public/icons/desktop_icons": ("hrms", {
        "employee_lifecycle.svg": "tenure", "expense_claim.svg": "expenses",
        "hr_setup.svg": "hr_setup", "leaves.svg": "leaves",
        "performance.svg": "performance", "recruitment.svg": "recruitment",
        "salary_payout.svg": "payroll",
        "shift-attendence.svg": "shift_&_attendance",
        "tax-benefits.svg": "tax_&_benefits",
    }),
}

for pasta, (app, mapa) in SOLTOS.items():
    for ficheiro, nosso in mapa.items():
        copiar(os.path.join(SIMBOLOS, app, "solid", f"{nosso}.svg"),
               os.path.join(pasta, ficheiro))

# ── Textos dentro dos pacotes compilados ────────────────────────────────────
#
# Os frontends do CRM, do Desk e do RH são Vue compilado, e o nome do fabricante
# não vive só no `index.html`: está dentro dos pacotes, em frases que o
# utilizador lê — «Welcome to Frappe CRM» no assistente de primeira utilização,
# «You do not have enough permissions to access Frappe CRM», «How did you hear
# about Frappe Helpdesk?», «Frappe Helpdesk Mobile» na ajuda.
#
# A troca é feita DENTRO do ficheiro, que mantém o nome com hash — a lição de
# 10-09-2026, quando se copiaram pacotes pelo nome com hash e o manifesto deixou
# de os referenciar, deixando cópias mortas no disco. Aqui não se substitui
# ficheiro nenhum: só o texto lá dentro.
#
# Só os nomes de duas palavras. «crm», «helpdesk» e «frappecrm» sozinhos são
# identificadores, rotas e nomes de propriedades — tocar-lhes parte a app.
NOMES_COMPOSTOS = [
    ("Frappe CRM", "Stratechna CRM"),
    ("Frappe Helpdesk", "Stratechna Desk"),
    ("Frappe HR", "Stratechna RH"),
]

PACOTES = {
    "crm/crm/public/frontend/assets": 3,
    "helpdesk/helpdesk/public/desk/assets": 2,
    "hrms/hrms/public/frontend/assets": 3,
}

for pasta, minimo in PACOTES.items():
    caminho = os.path.join(APPS, pasta)
    if not os.path.isdir(caminho):
        falhas.append(f"pasta de pacotes em falta: {pasta}")
        continue
    tocados = 0
    for ficheiro in sorted(os.listdir(caminho)):
        if not (ficheiro.endswith(".js") or ficheiro.endswith(".js.map")):
            continue
        alvo = os.path.join(caminho, ficheiro)
        with open(alvo, encoding="utf-8", errors="surrogateescape") as f:
            texto = original = f.read()
        for antes, depois in NOMES_COMPOSTOS:
            texto = texto.replace(antes, depois)
        if texto != original:
            with open(alvo, "w", encoding="utf-8", errors="surrogateescape") as f:
                f.write(texto)
            feitos += 1
        # conta-se o ficheiro se levava o nome do fabricante OU se já leva o
        # nosso: assim o guião pode correr duas vezes sem acusar falso alarme,
        # e continua a acusar quando o upstream deixa de ter lá o texto.
        if any(d in texto for _, d in NOMES_COMPOSTOS):
            tocados += 1
    if tocados < minimo:
        falhas.append(f"{pasta}: só {tocados} pacotes com o nome do fabricante "
                      f"(esperavam-se {minimo}) — o upstream mudou os textos?")

# ── Resultado ───────────────────────────────────────────────────────────────
print(f"marca das apps de frontend próprio: {feitos} ficheiros tratados")
if falhas:
    print("FALHAS:")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("sem falhas")
