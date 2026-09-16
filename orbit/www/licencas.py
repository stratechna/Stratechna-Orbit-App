"""Os componentes que o Stratechna Orbit usa, e ao abrigo de quê.

A lista vive em código e não na base de dados de propósito: é uma declaração
legal, tem de ser igual em todos os tenants, e tem de andar junto com a versão
do software a que se refere. Uma tabela editável por tenant divergia do que
está instalado — e uma declaração de licenças errada é pior do que não existir.

**Ao acrescentar uma app ao Orbit, acrescentar aqui.** As licenças abaixo foram
verificadas nos ficheiros `LICENSE` das próprias apps instaladas, não na
documentação dos projectos.
"""

no_cache = 1

# nome, o que faz, licença, repositório original, o nosso (quando há alterações)
COMPONENTES = [
    ("Frappe Framework", "A plataforma onde as apps correm", "MIT",
     "https://github.com/frappe/frappe", None),
    ("ERPNext", "Faturação, vendas, compras, inventário", "GNU GPL v3",
     "https://github.com/frappe/erpnext", None),
    ("Frappe HR", "Colaboradores, férias, assiduidade, salários", "GNU GPL v3",
     "https://github.com/frappe/hrms", None),
    ("Frappe CRM", "Clientes, contactos e oportunidades", "GNU AGPL v3",
     "https://github.com/frappe/crm", None),
    ("Frappe Helpdesk", "Pedidos de suporte e base de respostas", "GNU AGPL v3",
     "https://github.com/frappe/helpdesk", None),
    ("Frappe Wiki", "Base de conhecimento", "MIT",
     "https://github.com/frappe/wiki", None),
    ("Jitsi Meet", "Reuniões por vídeo (Stratechna Meet)", "Apache 2.0",
     "https://github.com/jitsi/jitsi-meet",
     "https://github.com/stratechna/Stratechna-Meet"),
    ("Zulip", "Conversas internas da equipa (Stratechna Chat)", "Apache 2.0",
     "https://github.com/zulip/zulip",
     "https://github.com/stratechna/Stratechna-Chat"),
    ("SOGo", "Correio, calendário e contactos (Stratechna Mail)", "GNU GPL v2",
     "https://github.com/Alinto/sogo", None),
    ("Postiz", "Publicação nas redes sociais (Stratechna Social)", "GNU AGPL v3",
     "https://github.com/gitroomhq/postiz-app",
     "https://github.com/stratechna/Stratechna-Social"),
    ("Zammad", "Suporte a clientes (Stratechna Desk)", "GNU AGPL v3",
     "https://github.com/zammad/zammad",
     "https://github.com/stratechna/Stratechna-Desk"),
    ("Docuseal", "Assinatura digital (Stratechna Sign)", "GNU AGPL v3",
     "https://github.com/docusealco/docuseal",
     "https://github.com/stratechna/Stratechna-Sign"),
    ("Orbit", "A marca e as extensões do Stratechna Orbit", "GNU AGPL v3",
     "https://github.com/stratechna/Stratechna-Orbit-App", None),
]


def get_context(context):
    context.no_cache = 1
    context.componentes = [
        {"nome": n, "papel": p, "licenca": l, "origem": o, "nosso": s}
        for n, p, l, o, s in COMPONENTES
    ]
    return context
