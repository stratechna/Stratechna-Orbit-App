"""Automação de Marketing — uma por tipo, por tenant.

    Rascunho → Para aprovação → Activa ⇄ Pausada
       ↑_____________|  rejeitar (com motivo)

O cliente aprova o modelo uma vez. Para mudar o texto de uma automação activa,
pausa-se e devolve-se a rascunho: o que foi aprovado foi o que lá estava.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


def _pode_aprovar() -> bool:
    return bool({"Sales Manager", "System Manager"} & set(frappe.get_roles()))


class AutomacaodeMarketing(Document):
    def validate(self):
        from orbit.marketing.automacoes import permitidas
        if self.is_new():
            self.estado = "Rascunho"
            if self.tipo not in permitidas():
                frappe.throw(_("O plano não inclui esta automação."))
            return
        if self.estado != "Rascunho" and not self.flags.ciclo:
            antes = self.get_doc_before_save()
            for f in ("linha_assunto", "texto", "titulo_email", "cta_url", "modelo", "assunto_marketing"):
                if antes and str(antes.get(f) or "") != str(self.get(f) or ""):
                    frappe.throw(_("Só se altera uma automação em rascunho. Pause-a e devolva-a a rascunho primeiro."))

    def _mudar(self, de, para, **extra):
        if self.estado not in de:
            frappe.throw(_("A automação está «{0}» — este passo não se aplica.").format(self.estado))
        self.flags.ciclo = True
        try:
            self.estado = para
            self.update(extra)
            self.save()
        finally:
            self.flags.ciclo = False

    @frappe.whitelist()
    def submeter(self):
        if not ((self.linha_assunto or "").strip() and ((self.texto or "").strip() or self.titulo_email)):
            frappe.throw(_("Falta a linha de assunto ou o texto."))
        self._mudar(("Rascunho",), "Para aprovação")

    @frappe.whitelist()
    def aprovar(self):
        if not _pode_aprovar():
            frappe.throw(_("Só quem gere o marketing da empresa pode aprovar."), frappe.PermissionError)
        # Só conta o que acontecer a partir de agora.
        self._mudar(("Para aprovação",), "Activa", activa_desde=now_datetime(), aprovada_por=frappe.session.user)

    @frappe.whitelist()
    def rejeitar(self, motivo: str):
        if not (motivo or "").strip():
            frappe.throw(_("Uma rejeição precisa do motivo."))
        self._mudar(("Para aprovação",), "Rascunho")
        self.add_comment("Comment", _("Rejeitada: {0}").format(motivo.strip()))

    @frappe.whitelist()
    def pausar(self):
        self._mudar(("Activa",), "Pausada")
        # O que estava na fila não sai: pausar é parar agora.
        for e in frappe.get_all("Envio de Marketing", filters={"automacao": self.name, "estado": "Na fila"}, pluck="name"):
            frappe.db.set_value("Envio de Marketing", e, "estado", "Cancelado")

    @frappe.whitelist()
    def retomar(self):
        if not _pode_aprovar():
            frappe.throw(_("Só quem gere o marketing da empresa pode retomar."), frappe.PermissionError)
        # Retoma-se a contar de agora: o que aconteceu na pausa não gera correio atrasado.
        self._mudar(("Pausada",), "Activa", activa_desde=now_datetime())

    @frappe.whitelist()
    def editar(self):
        self._mudar(("Pausada", "Para aprovação"), "Rascunho")

    @frappe.whitelist()
    def previsualizar(self) -> dict:
        from orbit.marketing import loja, mensagem
        dados = {"produtos": loja.mais_vendidos(quantos=3)} if self.tipo != "Boas-vindas" else {}
        m = mensagem.compor(self, {"nome": "Maria", "mkt_base_legal": "cliente"}, dados=dados)
        return {"assunto": m["assunto"], "html": m["html"]}
