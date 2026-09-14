app_name = "orbit"
app_title = "Orbit"
app_publisher = "Stratechna"
app_description = "A marca e as extensões do Stratechna Orbit"
app_email = "it@stratechna.pt"
app_license = "agpl-3.0"

# O rodapé do ecrã de apps só se consegue acrescentar por aqui: estes dois ganchos
# são a única forma de o Frappe deixar entrar CSS e JS próprios em todas as páginas
# do desk, e exigem uma app instalada.
app_include_js = "/assets/orbit/js/orbit.js"
app_include_css = "/assets/orbit/css/orbit.css"

# Os ícones dos módulos vivem dentro das pastas do ERPNext, do HR e do Frappe —
# é lá que o frontend os procura, antes de olhar para a base de dados. Uma
# reconstrução da imagem apaga-os. Repor no fim de cada migração é o que dispensa
# o cron que fazia isto de hora a hora.
after_migrate = ["orbit.marca.repor_icones", "orbit.marca.repor_atalhos",
                 "orbit.marca.repor_nomes"]
# A instalação de qualquer app corre «Creating Desktop Icons» e leva à frente os
# atalhos que não reconhece — foi o que apagou o Mail, o Docs, o Sign, o Events e
# o Social quando esta app foi instalada. Recriá-los no fim de cada migração
# fecha esse buraco.
after_install = ["orbit.marca.repor_icones", "orbit.marca.repor_atalhos",
                 "orbit.marca.repor_nomes"]

# Esta app não tem nada que valha a pena mostrar no ecrã de apps: é marca e
# extensões, não é um módulo de trabalho.
add_to_apps_screen = []
