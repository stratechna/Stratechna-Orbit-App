# Stratechna Orbit — app da marca

App Frappe própria do Stratechna Orbit. Não acrescenta funcionalidade de negócio:
existe para segurar três coisas que não se conseguem fazer só por configuração.

1. **Rodapé do ecrã de apps** — o nome do produto, o que ele é, o logótipo da
   Stratechna e a atribuição ao Frappe e ao ERPNext. Entra pelos ganchos
   `app_include_js` e `app_include_css`, que exigem uma app instalada.

2. **Ícones dos módulos** — o frontend monta o caminho do ícone a partir do campo
   `app` do Desktop Icon. Dizemos que esses ícones pertencem à app `orbit` e os
   ficheiros passam a ser lidos daqui, em vez de dentro do ERPNext e do HR. Nada
   é escrito fora desta app: a marca sobrevive a qualquer actualização do
   upstream, e o cron que repunha os ficheiros deixa de ser preciso.

3. **Calendário em ICS** — o Frappe não fala CalDAV nem exporta ICS. Este
   endpoint publica as tarefas e eventos do utilizador num feed que o webmail
   subscreve.

Licença: AGPL-3.0, a mesma do Frappe.
