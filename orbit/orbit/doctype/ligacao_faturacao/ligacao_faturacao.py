import frappe
from frappe.model.document import Document


class LigacaoFaturacao(Document):
    def validate(self):
        if self.modo == "Real" and self.activa and not self.ultimo_ensaio_ok:
            frappe.throw("Só se passa a modo Real depois de um ensaio bem-sucedido (botão «Ensaiar»).")
        if self.motivo_isencao:
            from orbit.faturacao.base import MOTIVOS_ISENCAO
            if self.motivo_isencao not in MOTIVOS_ISENCAO:
                frappe.throw(f"Motivo de isenção desconhecido: {self.motivo_isencao}")
