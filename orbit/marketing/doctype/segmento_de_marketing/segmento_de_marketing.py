"""Segmento de Marketing — um grupo de pessoas por regras, avaliado no dia.

As regras são uma lista fechada (`Regra de Segmento`), porque texto livre
acabaria em consultas montadas a partir de um formulário.
"""

import frappe
from frappe.model.document import Document


class SegmentodeMarketing(Document):
    @frappe.whitelist()
    def contar(self) -> int:
        from orbit.marketing import destinatarios
        n = len(destinatarios.do_segmento(self.name))
        self.db_set("contactaveis", n)
        return n
