# Stratechna Orbit — app da marca

App Frappe própria do Stratechna Orbit. Não acrescenta funcionalidade de negócio:
existe para segurar três coisas que não se conseguem fazer só por configuração.

1. **Rodapé do ecrã de apps** — o nome do produto, o que ele é, o logótipo da
   Stratechna e a atribuição ao Frappe e ao ERPNext. Entra pelos ganchos
   `app_include_js` e `app_include_css`, que exigem uma app instalada.

2. **Ícones dos módulos** — o frontend procura primeiro
   `assets/<app>/icons/desktop_icons/<estilo>/<nome>.svg` e só depois olha para a
   base de dados. Como esses ficheiros vivem dentro do ERPNext, do HR e do
   Frappe, a marca deles não sobrevive a uma reconstrução da imagem. O gancho
   `after_migrate` repõe-nos sozinho, o que dispensa o cron que fazia isso antes.

3. **Calendário em ICS** — o Frappe não fala CalDAV nem exporta ICS. Este
   endpoint publica as tarefas e eventos do utilizador num feed que o webmail
   subscreve.

Licença: AGPL-3.0, a mesma do Frappe.
