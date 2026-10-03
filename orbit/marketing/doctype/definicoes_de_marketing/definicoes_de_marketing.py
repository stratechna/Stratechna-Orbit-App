"""Definições de Marketing do tenant. A marca e o plano chegam do portal; a
conta de envio e o modo decidem-se aqui."""

import frappe
from frappe import _
from frappe.model.document import Document


class DefinicoesdeMarketing(Document):
    def validate(self):
        if self.modo == "Real":
            from orbit.marketing.envio import falta_para_enviar
            falta = falta_para_enviar(self)
            if falta:
                frappe.throw(_("Não se passa a «Real» sem {0}.").format("; ".join(falta)))
        if self.limite_hora is not None and int(self.limite_hora or 0) < 1:
            self.limite_hora = 1
