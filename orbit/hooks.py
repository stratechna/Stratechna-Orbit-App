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
app_include_js = "/assets/orbit/js/orbit.js?v=11"
app_include_css = "/assets/orbit/css/orbit.css?v=11"

# O ecrã precisa de saber, no arranque, que apps é que este tenant tem — para
# pintar a cinzento as que não tem em vez de as esconder. Vai no boot e não numa
# chamada à parte porque a grelha se desenha de uma vez: um pedido extra deixava
# os cartões a mudar de cor depois de já estarem no ecrã.
extend_bootinfo = "orbit.apps.acrescentar_ao_boot"

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
              "orbit.marca.repor_atalhos", "orbit.marca.repor_nomes"]
after_migrate = _POR_DE_PE
after_install = _POR_DE_PE

# Esta app não tem nada que valha a pena mostrar no ecrã de apps: é marca e
# extensões, não é um módulo de trabalho.
add_to_apps_screen = []
