# Traduções do Orbit (18-10-2026)

Ver `docs/PLANO-I18N-ORBIT-APPS.md` na área de trabalho.

- O Frappe junta as traduções de todas as apps **pela ordem de instalação**. A `orbit` é a última nos tenants, por isso o que estes ficheiros trazem ganha às traduções do CRM, do Helpdesk e do Frappe. As linhas `Translation` da base de dados ganham a tudo: não as usar para o que é de todos os tenants.
- Formato CSV do Frappe: `origem,tradução[,contexto]`, com `\n` escrito como `\\n`.
- **pt** = pt-PT pelo Acordo Ortográfico de 1990, nunca pt-BR. Corrige o que falta ou está mal no `pt.po` do upstream (CRM, Helpdesk, Frappe) e os nomes dos módulos (`marca.NOMES`).
- **en/es/fr**: os nossos textos (campos personalizados, opções, doctypes, mensagens, JS, registos como estados e origens) e o que falta em es/fr no upstream.
- **Texto novo nosso** (rótulo, opção, `_()`/`__()`): acrescentar a linha nas quatro línguas. O `test_lingua.py` falha se faltar es ou fr a um texto que já está em en.
- Regra da marca em todas as línguas: «Helpdesk» → «Desk», «Frappe CRM» → «CRM».
