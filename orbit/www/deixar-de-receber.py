"""A página de remoção. Aberta pela ligação no rodapé de cada email.

Diz o endereço, oferece sair do assunto daquela campanha ou de tudo, e regista.
Sem sessão: o token do envio é a credencial, e só serve para isto.
"""

import frappe

from orbit.marketing import mensagem, publico

no_cache = 1


def get_context(context):
    t = frappe.form_dict.get("t") or ""
    context.no_cache = 1
    context.marca = mensagem.definicoes().marca_nome or ""
    e = publico._envio(t)
    context.token, context.valido, context.feito = t, bool(e), None
    if not e:
        return context
    context.email = e.email
    context.assunto = (frappe.db.get_value("Automacao de Marketing", e.automacao, "assunto_marketing") if e.get("automacao")
                       else frappe.db.get_value("Campanha de Marketing", e.campanha, "assunto_marketing"))
    return context
