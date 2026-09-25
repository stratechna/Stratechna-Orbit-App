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


# ── A assinatura do fabricante em todas as páginas web ──────────────────────
# `base.html` do Frappe abre com um comentário «Built on Frappe» e uma
# meta-etiqueta `generator`. Não se veem no ecrã, mas vão em TODAS as páginas
# públicas de todos os tenants: é o que um cliente encontra no código-fonte e o
# que as ferramentas de impressão digital usam para dizer que software corremos.
# O Frappe é MIT — não exige atribuição nenhuma —, e a declaração honesta está
# na página /licencas, que é onde se lê e não onde se esconde.
trocar("frappe/frappe/templates/base.html",
       [("<!-- Built on Frappe. https://frappeframework.com/ -->",
         "<!-- Stratechna Orbit. https://stratechna.com/orbit/ -->"),
        ('<meta name="generator" content="frappe">',
         '<meta name="generator" content="Stratechna Orbit">')])

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

# ── Os logótipos do fabricante desenhados DENTRO dos pacotes ────────────────
#
# O painel «Getting started» do CRM e do Desk abre-se na primeira utilização com
# um quadrado grande — magenta no CRM, violeta no Desk. Não é um ficheiro: é SVG
# compilado para dentro do pacote Vue, como chamadas de render. Por isso
# sobreviveu a todas as trocas de ficheiros de imagem, e era a primeira coisa
# que um cliente via ao abrir a app.
#
# A troca é feita sobre o texto do pacote, sem lhe mudar o nome (mantém o hash).
# A âncora é o `d` do primeiro caminho do logótipo, que é único e estável: se o
# upstream redesenhar o símbolo, o padrão deixa de aparecer e a construção falha
# — que é o que queremos saber.
#
# Os dois pacotes vêm de minificadores com aspas diferentes (" no Desk, ` no
# CRM), por isso a aspa é capturada e reutilizada, em vez de assumida.
LOGOS = {
    "helpdesk/helpdesk/public/desk/assets": {
        "ancora": "M93.9278 0H23.1013",
        # A aspa é um grupo COM NOME: `\1` seguido de dígitos («\1118») é lido
        # como a referência 11, e o padrão nunca casava — sem erro nenhum.
        "caixa": r'width:(?P<q>["`])118(?P=q),height:(?P=q)118(?P=q),viewBox:(?P=q)0 0 118 118(?P=q)',
        "simbolo": "desk",
    },
    "crm/crm/public/frontend/assets": {
        "ancora": "M214.286 0H85.7143",
        "caixa": r'width:(?P<q>["`])300(?P=q),height:(?P=q)300(?P=q),viewBox:(?P=q)0 0 300 300(?P=q)',
        "simbolo": "crm",
    },
}

# Os nossos símbolos, em chamadas de render. `{a}` é o nome que o minificador deu
# ao createElementVNode e `{q}` a aspa que usa — ambos vêm do pacote.
#
# As chaves com hífen levam aspas DUPLAS fixas e não `{q}`: quando o pacote usa
# crases, uma chave em crase (`stroke-width`:) não é JavaScript válido e o
# ficheiro deixa de carregar. A crase serve para valores, não para nomes.
FORMAS = {
    "desk": (
        '{a}({q}rect{q},{{width:{q}512{q},height:{q}512{q},rx:{q}72{q},fill:{q}#22303d{q}}},null,-1),'
        '{a}({q}path{q},{{d:{q}M 128 288 a 128 128 0 0 1 256 0{q},transform:{q}translate(60 60) scale(0.7656){q},'
        'stroke:{q}#8a9bab{q},\"stroke-width\":{q}32{q},\"stroke-linecap\":{q}round{q}}},null,-1),'
        '{a}({q}path{q},{{d:{q}M 128 284 v 48{q},transform:{q}translate(60 60) scale(0.7656){q},'
        'stroke:{q}#8a9bab{q},\"stroke-width\":{q}32{q},\"stroke-linecap\":{q}round{q}}},null,-1),'
        '{a}({q}path{q},{{d:{q}M 384 284 v 48{q},transform:{q}translate(60 60) scale(0.7656){q},'
        'stroke:{q}#ea5c55{q},\"stroke-width\":{q}32{q},\"stroke-linecap\":{q}round{q}}},null,-1)'
    ),
    "crm": (
        '{a}({q}rect{q},{{width:{q}512{q},height:{q}512{q},rx:{q}72{q},fill:{q}#22303d{q}}},null,-1),'
        '{a}({q}circle{q},{{cx:{q}256{q},cy:{q}190{q},r:{q}54{q},transform:{q}translate(60 60) scale(0.7656){q},'
        'stroke:{q}#8a9bab{q},\"stroke-width\":{q}32{q},fill:{q}none{q}}},null,-1),'
        '{a}({q}path{q},{{d:{q}M 146 388 a 110 110 0 0 1 220 0{q},transform:{q}translate(60 60) scale(0.7656){q},'
        'stroke:{q}#8a9bab{q},\"stroke-width\":{q}32{q},\"stroke-linecap\":{q}round{q},fill:{q}none{q}}},null,-1),'
        '{a}({q}circle{q},{{cx:{q}360{q},cy:{q}150{q},r:{q}34{q},transform:{q}translate(60 60) scale(0.7656){q},'
        'fill:{q}#ea5c55{q}}},null,-1)'
    ),
}


# A assinatura do nosso quadrado dentro de um pacote: a caixa escura, do tamanho
# a que os desenhamos. É o que distingue «ainda por trocar» de «já trocado».
# Duas formas porque os dois pacotes vêm de minificadores com aspas diferentes.
MARCAS_NOSSAS = ('width:`512`,height:`512`,rx:`72`,fill:`#22303d`',
                 'width:"512",height:"512",rx:"72",fill:"#22303d"')


def trocar_logotipos() -> None:
    import re
    global feitos
    for pasta, d in LOGOS.items():
        caminho = os.path.join(APPS, pasta)
        if not os.path.isdir(caminho):
            falhas.append(f"pasta de pacotes em falta: {pasta}")
            continue
        trocados = 0
        alvo = re.compile(
            r'(\w+)\((["`])path\2,\{d:\2' + re.escape(d["ancora"]) + r'.*?\},null,-1\)\]',
            re.DOTALL)
        caixa = re.compile(d["caixa"])
        for ficheiro in sorted(os.listdir(caminho)):
            if not ficheiro.endswith(".js"):
                continue
            f = os.path.join(caminho, ficheiro)
            with open(f, encoding="utf-8", errors="surrogateescape") as fh:
                texto = fh.read()
            # Já trocado numa passagem anterior conta como feito: sem isto, correr
            # o guião duas vezes (ou construir sobre uma base em cache) acusava
            # «o upstream mudou o símbolo» sobre um símbolo que já era nosso.
            if any(m in texto for m in MARCAS_NOSSAS):
                trocados += 1
                continue
            if d["ancora"] not in texto:
                continue
            m = alvo.search(texto)
            if not m:
                falhas.append(f"{pasta}/{ficheiro}: o logótipo está lá mas não na forma esperada")
                continue
            a, q = m.group(1), m.group(2)
            novo = FORMAS[d["simbolo"]].format(a=a, q=q) + "]"
            texto = texto[:m.start()] + novo + texto[m.end():]
            texto, n = caixa.subn(lambda mm: f'viewBox:{mm.group("q")}0 0 512 512{mm.group("q")}', texto)
            if not n:
                falhas.append(f"{pasta}/{ficheiro}: a caixa do logótipo não mudou de tamanho")
            with open(f, "w", encoding="utf-8", errors="surrogateescape") as fh:
                fh.write(texto)
            trocados += 1
            feitos += 1
        if not trocados:
            falhas.append(f"{pasta}: nenhum pacote com o logótipo do fabricante "
                          f"(âncora {d['ancora']}) — o upstream mudou o símbolo?")


trocar_logotipos()

# ── O comutador de apps ─────────────────────────────────────────────────────
#
# O menu «Apps» dentro do CRM e do Desk NÃO lê a tabela `Desktop Icon`: lê o
# gancho `add_to_apps_screen` do `hooks.py` de cada app, e cada uma aponta para
# o seu próprio logótipo. Era por isso que o ERP aparecia com o «E» verde do
# ERPNext, o RH com o logótipo do Frappe HR e o Wiki com o do Frappe Wiki —
# depois de todo o resto já estar marcado.
#
# E havia um «Desk» a mais: o frontend do CRM acrescenta à mão uma entrada para
# a área de trabalho do Frappe, com o título «Desk», que colide com o nome que
# damos ao Helpdesk. Essa entrada leva ao ecrã de apps do Orbit, por isso
# chama-se «Orbit» — que é o que é.
LOGOS_APPS = {
    "frappe/frappe/hooks.py": ("/assets/frappe/images/frappe-framework-logo.svg", "orbit"),
    "erpnext/erpnext/hooks.py": ("/assets/erpnext/images/erpnext-logo.svg", "erp"),
    "hrms/hrms/hooks.py": ("/assets/hrms/images/frappe-hr-logo.svg", "rh"),
    "crm/crm/hooks.py": ("/assets/crm/images/logo.svg", "crm"),
    "helpdesk/helpdesk/hooks.py": ("/assets/helpdesk/desk/favicon.svg", "desk"),
    "wiki/wiki/hooks.py": ("/assets/wiki/images/wiki-logo.png", "wiki"),
}

for ficheiro, (antigo, simbolo) in LOGOS_APPS.items():
    trocar(ficheiro, [(antigo, f"/assets/orbit/icons/apps/{simbolo}.svg")])

# A entrada «Desk» que o CRM acrescenta à mão, dentro do pacote compilado.
trocar_no_pacote = [
    ("crm/crm/public/frontend/assets", [
        ("logo:`/assets/frappe/images/framework.png`,title:__(`Desk`)",
         "logo:`/assets/orbit/icons/apps/orbit.svg`,title:__(`Orbit`)"),
        ('logo:"/assets/frappe/images/framework.png",title:__("Desk")',
         'logo:"/assets/orbit/icons/apps/orbit.svg",title:__("Orbit")'),
    ]),
]

for pasta, pares in trocar_no_pacote:
    caminho = os.path.join(APPS, pasta)
    if not os.path.isdir(caminho):
        falhas.append(f"pasta de pacotes em falta: {pasta}")
        continue
    tocados = 0
    for ficheiro in sorted(os.listdir(caminho)):
        if not ficheiro.endswith(".js"):
            continue
        alvo = os.path.join(caminho, ficheiro)
        with open(alvo, encoding="utf-8", errors="surrogateescape") as fh:
            texto = original = fh.read()
        for antes, depois in pares:
            if antes in texto:
                texto = texto.replace(antes, depois)
            if depois in texto:
                tocados += 1
        if texto != original:
            with open(alvo, "w", encoding="utf-8", errors="surrogateescape") as fh:
                fh.write(texto)
            feitos += 1
    if not tocados:
        falhas.append(f"{pasta}: não encontrei a entrada «Desk» que o CRM acrescenta "
                      "ao comutador de apps — o upstream mudou-a?")

# ── O rodapé de TODOS os emails que o Orbit envia ───────────────────────────
#
# O ERPNext acrescenta a cada email um «Sent via ERPNext» com ligação para
# frappe.io. Não é uma atribuição de licença — a GPL v3 não exige nada na
# interface — é uma ligação de marketing do fabricante dentro do correio que os
# NOSSOS clientes recebem dos seus clientes. Passa a ser nossa.
#
# O gancho é `default_mail_footer` no hooks.py do ERPNext, lido pelo
# frappe/email/email_body.py em cada mensagem.
RODAPE_ERPNEXT = '''default_mail_footer = """
\t<span>
\t\tSent via
\t\t<a class="text-muted" href="https://frappe.io/erpnext?source=via_email_footer" target="_blank">
\t\t\tERPNext
\t\t</a>
\t</span>
"""'''

RODAPE_NOSSO = '''default_mail_footer = """
\t<span>
\t\tEnviado pelo
\t\t<a class="text-muted" href="https://stratechna.com/orbit/" target="_blank">
\t\t\tStratechna Orbit
\t\t</a>
\t</span>
"""'''

trocar("erpnext/erpnext/hooks.py", [(RODAPE_ERPNEXT, RODAPE_NOSSO)])

# ── Resultado ───────────────────────────────────────────────────────────────
print(f"marca das apps de frontend próprio: {feitos} ficheiros tratados")
if falhas:
    print("FALHAS:")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("sem falhas")
