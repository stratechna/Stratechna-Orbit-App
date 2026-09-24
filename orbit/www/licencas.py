"""Os componentes que o Stratechna Orbit usa, e ao abrigo de quê.

A lista vive em código e não na base de dados de propósito: é uma declaração
legal, tem de ser igual em todos os tenants, e tem de andar junto com a versão
do software a que se refere. Uma tabela editável por tenant divergia do que
está instalado — e uma declaração de licenças errada é pior do que não existir.

O Zammad esteve aqui enquanto foi o Stratechna Desk. Deixou de estar instalado
quando o Desk passou para o Frappe Helpdesk, em Setembro de 2026, e uma
declaração que anuncia software que não corre é tão errada como uma que omite o
que corre.

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
     "https://github.com/frappe/erpnext",
     "https://github.com/stratechna/Stratechna-Orbit-App"),
    ("Frappe HR", "Colaboradores, férias, assiduidade, salários", "GNU GPL v3",
     "https://github.com/frappe/hrms",
     "https://github.com/stratechna/Stratechna-Orbit-App"),
    ("Frappe CRM", "Clientes, contactos e oportunidades", "GNU AGPL v3",
     "https://github.com/frappe/crm",
     "https://github.com/stratechna/Stratechna-Orbit-App"),
    ("Frappe Helpdesk", "Pedidos de suporte e base de respostas", "GNU AGPL v3",
     "https://github.com/frappe/helpdesk",
     "https://github.com/stratechna/Stratechna-Orbit-App"),
    ("Frappe Wiki", "Base de conhecimento", "MIT",
     "https://github.com/frappe/wiki", None),
    ("Frappe Telephony", "Ligações telefónicas dentro do CRM", "MIT",
     "https://github.com/frappe/telephony", None),
    ("Jitsi Meet", "Reuniões por vídeo (Stratechna Meet)", "Apache 2.0",
     "https://github.com/jitsi/jitsi-meet",
     "https://github.com/stratechna/Stratechna-Meet"),
    ("Zulip", "Conversas internas da equipa (Stratechna Chat)", "Apache 2.0",
     "https://github.com/zulip/zulip",
     "https://github.com/stratechna/Stratechna-Chat"),
    ("SOGo", "Correio, calendário e contactos (Stratechna Mail)", "GNU GPL v2",
     "https://github.com/Alinto/sogo", None),
    ("Paperless-ngx", "Arquivo de documentos (Stratechna Docs)", "GNU GPL v3",
     "https://github.com/paperless-ngx/paperless-ngx",
     "https://github.com/stratechna/Stratechna-Docs"),
    ("Postiz", "Publicação nas redes sociais (Stratechna Social)", "GNU AGPL v3",
     "https://github.com/gitroomhq/postiz-app",
     "https://github.com/stratechna/Stratechna-Social"),
    ("Docuseal", "Assinatura digital (Stratechna Sign)", "GNU AGPL v3",
     "https://github.com/docusealco/docuseal",
     "https://github.com/stratechna/Stratechna-Sign"),
    ("Hi.Events", "Bilhetes e inscrições (Stratechna Events)", "GNU AGPL v3",
     "https://github.com/HiEventsDev/hi.events",
     "https://github.com/stratechna/Stratechna-Events"),
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
