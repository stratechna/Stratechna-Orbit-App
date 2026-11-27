app_name = "orbit"
app_title = "Orbit"
app_publisher = "Stratechna"
app_description = "A marca e as extensões do Stratechna Orbit"
app_email = "it@stratechna.pt"
app_license = "agpl-3.0"

# O rodapé do ecrã de apps só se consegue acrescentar por aqui: estes dois ganchos
# são a única forma de o Frappe deixar entrar CSS e JS próprios em todas as páginas
# do desk, e exigem uma app instalada.
# O `?v=` não é decoração: o Frappe entrega estes dois caminhos ao browser tal e
# qual (o `bundled_asset` só resolve nomes de bundle, e estes são caminhos
# completos), e o nginx serve /assets sem `Cache-Control`. Sem versão no URL, o
# browser fica agarrado à cópia que tem — e uma alteração publicada pode não
# chegar a ver-se, por mais vezes que se recarregue.
#
# SUBIR ESTE NÚMERO sempre que se mexer no CSS ou no JS.
# 20-11-2026: «Rever texto» (orbit-corrector.js; corrector.py) — também carregado por www/crm.html e www/helpdesk
app_include_js = ["/assets/orbit/js/orbit.js?v=40", "/assets/orbit/js/orbit-corrector.js?v=3", "/api/method/orbit.barra.barra_js?app=inicio"]
app_include_css = "/assets/orbit/css/orbit.css?v=39"
# As cores tambem nas paginas publicas — a entrada e a primeira coisa que
# alguem ve, e e servida pelo lado do site e nao pela secretaria.
web_include_css = "/assets/orbit/css/orbit.css?v=39"
# 17-10-2026: na página de entrada, seguir para o portal (entrada única) quando o tenant o tem ligado
web_include_js = ["/assets/orbit/js/entrada.js?v=10", "/api/method/orbit.barra.barra_js?app=wiki"]

# Sair do Orbit sai também do portal e do webmail (entrada_unica.ao_sair)
on_logout = "orbit.entrada_unica.ao_sair"
# Entrou pelo formulário do Orbit: também fica com sessão no portal (ponte, 18-10-2026)
on_session_creation = "orbit.entrada_unica.sessao_criada"
# 20-11-2026: a palavra-passe com que se entra (é a da caixa) serve o calendário da interface /orbit
on_login = "orbit.interface.calendario.ao_entrar"
# 03-11-2026: quem ainda não tem a palavra-passe da caixa no Orbit entra com ela (entrada_unica.antes_de_entrar)
before_login = "orbit.entrada_unica.antes_de_entrar"

# O ecrã precisa de saber, no arranque, que apps é que este tenant tem — para
# pintar a cinzento as que não tem em vez de as esconder. Vai no boot e não numa
# chamada à parte porque a grelha se desenha de uma vez: um pedido extra deixava
# os cartões a mudar de cor depois de já estarem no ecrã.
extend_bootinfo = ["orbit.apps.acrescentar_ao_boot", "orbit.entrada_unica.boot"]

# A grelha de módulos põe-se de pé por esta ordem, e a ordem importa: a
# sincronização traz de volta as fichas que as apps trazem em ficheiro (e que o
# migrate não repõe sozinho), e só depois se achatam as pastas, se recriam os
# atalhos e se escondem os módulos que não se vendem — senão a sincronização
# desfazia o que os outros três tinham feito.
#
# A instalação de qualquer app corre «Creating Desktop Icons» e leva à frente os
# atalhos que não reconhece — foi o que apagou o Mail, o Docs, o Sign, o Events e
# o Social quando esta app foi instalada. Correr isto no fim de cada migração e
# de cada instalação fecha esse buraco.
_POR_DE_PE = ["orbit.marca.sincronizar", "orbit.marca.achatar",
              "orbit.marca.calar_convites",
              "orbit.marca.repor_atalhos", "orbit.marca.repor_nomes"]
# O consentimento de marketing no CRM (campos, painel e histórico) entra em todos
# os tenants por aqui — é o que o torna transversal, e o que faz um tenant novo
# já nascer com ele.
_MARKETING = ["orbit.marketing.consentimento.garantir", "orbit.marketing.menu.garantir",
              "orbit.marketing.segmentos.converter_segmento_texto"]
# A marcação de reuniões precisa de dois campos próprios — a referência no
# `Event` e o segredo do feed no `User`. Pela mesma razão que o consentimento:
# um tenant novo tem de nascer com eles.
_MARCACAO = ["orbit.marcacao.garantir"]
_CAIXAS = ["orbit.caixas.garantir"]
# O botão «Actividade» nas fichas de organização e de contacto do CRM (actividade_crm.py, 19-11-2026);
# substitui o antigo botão «Notas» (notas_crm.py), cujos scripts o garantir() apaga.
_NOTAS = ["orbit.actividade_crm.garantir", "orbit.chamadas_crm.garantir"]
# 19-11-2026: «Ligar» e «Como correu a chamada?» (chamadas_crm.py + public/js/orbit-chamadas.js, carregado
# pela página www/crm.html; docs/PLANO-CHAMADAS-CRM.md, fase C1)
# 17-10-2026: perfis «Orbit · …», equipa Triagem do Desk e o departamento da pessoa (orbit/organizacao.py)
_ORGANIZACAO = ["orbit.organizacao.garantir"]
# 17-10-2026: campos de correspondência com o Zoho (zoho_id, crm_account_id…) e a conversão de leads sem negócio
_MIGRACAO = ["orbit.migracao_zoho.garantir", "orbit.portal.garantir", "orbit.remetentes.garantir"]

# 17-10-2026: entrada única — «Entrar com a Stratechna» (OpenID Connect do portal), ver entrada_unica.py
_ENTRADA = ["orbit.entrada_unica.garantir"]

# 18-10-2026: línguas pt/en/es/fr activas, campo «Língua» só de leitura (manda o portal), limpeza das
# traduções antigas dos módulos — as traduções em si vêm em orbit/translations/*.csv (ver lingua.py)
_LINGUA = ["orbit.lingua.garantir"]

# 05-11-2026: os emails no CRM (orbit/emails_crm.py; docs/PLANO-EMAILS-NO-CRM.md) — campos próprios
_EMAILS_CRM = ["orbit.emails_crm.instalar"]
# 20-11-2026: campos da interface /orbit (Responsável em contactos e empresas)
# 27-11-2026: vários funis no CRM (orbit/funis.py; docs/PLANO-FUNIS-CRM-ORBIT.md) — antes dos fluxos, que usam orbit_tipo_fase
_INTERFACE = ["orbit.funis.instalar", "orbit.interface.desk.instalar", "orbit.interface.definicoes.instalar", "orbit.interface.conversa.instalar", "orbit.interface.instalar.instalar", "orbit.interface.ciclo.instalar", "orbit.interface.marcas.instalar", "orbit.interface.detalhes.instalar", "orbit.fluxos_crm.instalar", "orbit.interface.formularios.instalar", "orbit.correio_servicos.acertar"]
_FATURACAO = ["orbit.faturacao.instalar.garantir"]   # DP8, 05-11-2026
_BOOKING = ["orbit.booking.garantir"]   # O1/I1, 06-11-2026: negócio do CRM ligado à marcação do Booking
# 10-11-2026: propostas comerciais por cima do Orçamento (orbit/propostas; docs/PLANO-PROPOSTAS-ORBIT.md)
_PROPOSTAS = ["orbit.propostas.instalar.garantir", "orbit.propostas.versoes.garantir_indices", "orbit.marcas_artigos.garantir", "orbit.inventario.campos.garantir", "orbit.inventario.encomendas.garantir", "orbit.inventario.armazens.instalar"]
after_migrate = _FATURACAO + _BOOKING + _PROPOSTAS + _POR_DE_PE + _MARKETING + _MARCACAO + _CAIXAS + _ORGANIZACAO + _MIGRACAO + _ENTRADA + _LINGUA + _EMAILS_CRM + _INTERFACE + _NOTAS + ["orbit.generos.acertar", "orbit.notificacoes_pt.acertar", "orbit.territorios.acertar", "orbit.listas_pt.acertar", "orbit.configuracao_pt.acertar", "orbit.compras.preparar.tudo", "orbit.compras.rascunho.garantir_campos", "orbit.snc.arrumar_novas", "orbit.empresas.garantir", "orbit.empresas.contabilidade_inicial", "orbit.interface.emitir.garantir", "orbit.interface.emitir.garantir_proforma", "orbit.faturacao.sincronizacao.garantir"]
after_install = _POR_DE_PE + _MARKETING + _MARCACAO + _ORGANIZACAO + ["orbit.remetentes.garantir"] + _LINGUA + _NOTAS + ["orbit.generos.acertar", "orbit.notificacoes_pt.acertar", "orbit.territorios.acertar", "orbit.listas_pt.acertar", "orbit.configuracao_pt.acertar"]

# Email marketing: a saída das campanhas corre ao minuto (o ritmo por hora
# reparte-se em sessenta lotes), as contagens de aberturas e cliques de hora a
# hora. Quem envia de facto é a fila do Frappe.
scheduler_events = {
    "cron": {
        "* * * * *": ["orbit.marketing.envio.processar"],
        # 27-11-2026: o Stratechna Chat no CRM — tópicos ligados e reacções :crm: (orbit/chat_crm.py)
        "*/2 * * * *": ["orbit.chat_crm.periodico"],
        # 05-11-2026 (DP8): faturação certificada — repetir o que ficou por emitir e ler anulações do programa
        "*/15 * * * *": ["orbit.faturacao.emissao.periodico", "orbit.faturacao.sincronizacao.periodico", "orbit.interface.trabalho.lembretes",
                         "orbit.interface.desk.enviar_inqueritos"],
    },
    # 23-11-2026: menções por ver há mais de 3 h seguem por email (orbit/interface/conversa.py)
    "hourly": ["orbit.marketing.envio.contagens_do_dia", "orbit.marketing.automacoes.correr",
               "orbit.marketing.segmentos.marcadores_automaticos",
               "orbit.interface.conversa.avisos_por_email", "orbit.interface.desk.sem_resposta"],
}

# Esta app não tem nada que valha a pena mostrar no ecrã de apps: é marca e
# extensões, não é um módulo de trabalho.
add_to_apps_screen = []


# Contas só de leitura (demonstrações): inerte sem `orbit_funcao_so_leitura` no site_config — ver so_leitura.py
doc_events = {
    # 27-11-2026 (docs/PLANO-WHATSAPP-ORBIT.md W3): a mensagem na ficha certa pelo número nacional, lead para números
    # novos e aviso no canal «WhatsApp» do Chat. Só existe nos tenants com o frappe_whatsapp.
    "WhatsApp Message": {"validate": "orbit.whatsapp.ligar_ficha", "after_insert": "orbit.whatsapp.mensagem_nova"},
    "*": {e: "orbit.so_leitura.guarda" for e in
          ("before_insert", "validate", "on_trash", "before_submit", "before_cancel", "before_update_after_submit")},
    # 16-10-2026: utilizadores contratados (orbit_utilizadores_max no site_config, escrito pelo portal)
    # 28-10-2026: a palavra-passe mudada pela própria pessoa (Definições) sobe ao portal (palavra_passe.py)
    "User": {"validate": ["orbit.utilizadores.guarda", "orbit.palavra_passe.validar"],
             "on_update": "orbit.palavra_passe.gravado"},
    # 17-10-2026: cada bilhete nasce na equipa da sua marca (formulário, destinatário) ou em Triagem
    # 23-11-2026 (plano do Desk): checklist do tipo, resposta fora da janela de 14 dias, inquérito e aviso de reaberto
    "HD Ticket": {"before_insert": ["orbit.organizacao.ticket_equipa", "orbit.interface.desk.checklist_automatica"],
                  "validate": ["orbit.interface.desk.checklist_automatica", "orbit.interface.desk.ticket_antes"],
                  "on_update": "orbit.interface.desk.ticket_gravado"},
    # 23-11-2026: a @menção também vai para o telemóvel (Orbit instalado como app; orbit/interface/push.py)
    "Notification Log": {"after_insert": "orbit.interface.push.aviso_criado"},
    "Communication": {"after_insert": ["orbit.organizacao.ticket_por_destinatario", "orbit.emails_crm.filtrar",
                                       "orbit.interface.ciclo.atividade", "orbit.interface.marcas.de_email"]},
    # 20-11-2026 (H4): fase do ciclo de vida e última actividade (orbit/interface/ciclo.py)
    "FCRM Note": {"after_insert": "orbit.interface.ciclo.atividade"},
    "CRM Task": {"after_insert": "orbit.interface.ciclo.atividade"},
    "CRM Call Log": {"after_insert": "orbit.interface.ciclo.atividade"},
    "Event": {"after_insert": "orbit.interface.ciclo.atividade"},
    "CRM Organization": {"after_insert": "orbit.interface.ciclo.empresa_gravada", "on_update": "orbit.interface.ciclo.empresa_gravada"},
    # 20-11-2026: um endereço novo no CRM vai buscar às caixas ligadas o que já se trocou com ele (emails_crm.py)
    "Contact": {"after_insert": ["orbit.emails_crm.ao_gravar_registo", "orbit.interface.ciclo.contacto_gravado",
                                 "orbit.marketing.base_legal.ao_criar"],
                "on_update": "orbit.emails_crm.ao_gravar_registo"},
    "CRM Lead": {"after_insert": ["orbit.emails_crm.ao_gravar_registo", "orbit.marketing.base_legal.ao_criar"], "on_trash": "orbit.emails_crm.lead_apagada"},
    # 23-11-2026: marca herdada da lead/empresa e passada à empresa e aos contactos (orbit/interface/marcas.py)
    # 27-11-2026: vários funis — a fase é sempre do funil do negócio (orbit/funis.py)
    "CRM Deal": {"before_insert": "orbit.interface.marcas.negocio_antes",
                 "before_validate": "orbit.funis.antes_de_validar",
                 "after_insert": ["orbit.emails_crm.ao_gravar_registo", "orbit.interface.ciclo.negocio_gravado",
                                  "orbit.interface.marcas.negocio_gravado"],
                 "on_update": ["orbit.emails_crm.ao_gravar_registo", "orbit.interface.ciclo.negocio_gravado",
                               "orbit.interface.marcas.negocio_gravado"]},
    # 17-10-2026 (corte do Zoho): o tempo registado no Orbit vai para o livro de horas do portal
    "Timesheet": {"on_submit": "orbit.portal.tempo_submetido", "on_cancel": "orbit.portal.tempo_cancelado"},
    # 17-10-2026: a conta de saída por omissão é o remetente dos avisos — chama-se «Stratechna Orbit»
    "Email Account": {"validate": "orbit.correio_servicos.validar", "on_update": "orbit.remetentes.conta_gravada"},
    # 05-11-2026 (DP8): o documento fiscal só nasce no programa certificado (Moloni, …) — inerte sem Ligacao activa
    # 25-11-2026: várias empresas — a marca fica escrita na venda e escolhe a série do programa certificado
    "Sales Invoice": {"before_validate": "orbit.empresas.antes_de_validar_venda",
                      "validate": "orbit.faturacao.emissao.validar_fatura",
                      "on_submit": ["orbit.faturacao.emissao.ao_submeter_fatura", "orbit.marketing.base_legal.fatura_submetida"],
                      "before_cancel": "orbit.faturacao.emissao.antes_de_cancelar_fatura"},
    "Payment Entry": {"on_submit": "orbit.faturacao.emissao.ao_submeter_pagamento"},
    # 24-11-2026 (fatura de compra F2): rascunho do Docs só se submete com todas as linhas ligadas
    "Purchase Invoice": {"before_submit": "orbit.compras.rascunho.antes_de_submeter",
                         "on_submit": "orbit.faturacao.sincronizacao.ao_submeter_compra"},
    # 25-11-2026: sincronização bidireccional com o programa certificado (opção na Ligação Faturação)
    "Purchase Order": {"on_submit": ["orbit.faturacao.sincronizacao.ao_submeter_compra", "orbit.funis.compra_submetida"]},
    "CRM Deal Status": {"validate": "orbit.funis.fase_antes_de_gravar", "on_update": "orbit.funis.fase_actualizada"},
    "Stock Entry": {"on_submit": "orbit.faturacao.sincronizacao.ao_mexer_stock",
                    "on_cancel": "orbit.faturacao.sincronizacao.ao_mexer_stock"},
    "Stock Reconciliation": {"on_submit": "orbit.faturacao.sincronizacao.ao_mexer_stock",
                             "on_cancel": "orbit.faturacao.sincronizacao.ao_mexer_stock"},
    "Purchase Receipt": {"on_submit": "orbit.faturacao.sincronizacao.ao_mexer_stock",
                         "on_cancel": "orbit.faturacao.sincronizacao.ao_mexer_stock"},
    "Supplier": {"on_update": "orbit.faturacao.sincronizacao.ao_gravar_fornecedor"},
    # 10-11-2026: marca → série/timbre/textos, linhas de transporte e montagem, IVA (orbit/propostas/regras.py)
    # 10-11-2026: a marca do artigo pelo prefixo da referência (A… JFusados, N… Arnox) → armazém da marca
    "Item": {"before_validate": ["orbit.marcas_artigos.antes_de_validar_artigo", "orbit.inventario.manuais.antes_de_validar"]},
    "Quotation": {"before_insert": ["orbit.propostas.regras.antes_de_inserir", "orbit.propostas.negocio.antes_de_inserir"],
                  "before_validate": "orbit.propostas.regras.antes_de_validar",
                  # 25-11-2026: o orçamento abre ou liga a um negócio do CRM e o negócio segue-o
                  "after_insert": "orbit.propostas.negocio.depois_de_inserir",
                  "on_submit": "orbit.propostas.negocio.ao_submeter",
                  "on_change": "orbit.propostas.negocio.ao_mudar",
                  "on_cancel": "orbit.propostas.negocio.ao_mudar"},
    # 25-11-2026: a guia de transporte segue para o programa certificado (código AT)
    "Delivery Note": {"before_validate": "orbit.empresas.antes_de_validar_venda",
                      "on_submit": "orbit.faturacao.emissao.ao_submeter_guia",
                      "before_cancel": "orbit.faturacao.emissao.antes_de_cancelar_guia"},
    "Sales Order": {"before_validate": "orbit.empresas.antes_de_validar_venda",
                    "on_submit": "orbit.propostas.negocio.encomenda_submetida"},
}

# 10-11-2026: «Adicionar por referência» e a marca no Orçamento; o modelo de impressão lê orbit_proposta(doc)
doctype_js = {"Quotation": "public/js/proposta.js"}
jinja = {"methods": ["orbit.propostas.impressao.orbit_proposta"]}

# 28-10-2026: palavra-passe universal — «Esqueci-me» e «Mudar palavra-passe» do Frappe avisam o portal, que a
# copia para a caixa, as lojas e os outros sítios (orbit/palavra_passe.py; plano das entradas independentes, passo 1)
override_whitelisted_methods = {
    "frappe.core.doctype.user.user.update_password": "orbit.palavra_passe.update_password",
    # 05-11-2026: «só para mim» — as actividades do CRM sem os emails e notas privados de outra pessoa
    "crm.api.activities.get_activities": "orbit.emails_crm.filtrar_actividades",
    # 27-11-2026 (docs/PLANO-WHATSAPP-ORBIT.md D3): o webhook do frappe_whatsapp não verifica a
    # assinatura da Meta; o mesmo endereço passa a exigir o X-Hub-Signature-256.
    "frappe_whatsapp.utils.webhook.webhook": "orbit.whatsapp.webhook",
}

# 05-11-2026: os emails e notas «só para mim» (orbit_privado_de) ficam fora das listas, da pesquisa e da
# abertura directa para quem não é o dono, administradores do tenant incluídos (06-11-2026).
permission_query_conditions = {
    "Communication": "orbit.emails_crm.condicao",
    "FCRM Note": "orbit.emails_crm.condicao_nota",
}
has_permission = {
    "Communication": "orbit.emails_crm.pode",
    "FCRM Note": "orbit.emails_crm.pode",
}

# 23-11-2026: os emails enviados pelas caixas ligadas ao CRM entram como «Enviado» (o Frappe deitava-os fora) —
# remendo aplicado em cada pedido e em cada trabalho de fundo (a recolha do correio corre no agendador).
before_request = ["orbit.remendo_enviados.aplicar"]
before_job = ["orbit.remendo_enviados.aplicar"]

# 23-11-2026: o service worker do Orbit (avisos no telemóvel) pode cuidar de /orbit (orbit/interface/push.py)
after_request = ["orbit.interface.push.cabecalhos"]
# 24-11-2026: entrada e página inicial do tenant gravam no telemóvel como «Orbit» com o ícone do Orbit
update_website_context = ["orbit.interface.push.contexto_web"]
