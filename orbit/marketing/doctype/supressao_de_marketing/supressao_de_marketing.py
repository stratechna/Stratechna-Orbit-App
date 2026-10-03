"""Quem nunca mais recebe marketing deste tenant, e porquê.

Não é a mesma coisa que pedir para sair (Email Unsubscribe): um endereço que
devolve não pediu nada — simplesmente não existe, e insistir é o que mais
depressa estraga a reputação de quem envia. Uma queixa de spam entra nas duas
listas: é saída E é aviso.
"""

from frappe.model.document import Document


class SupressaodeMarketing(Document):
    pass
