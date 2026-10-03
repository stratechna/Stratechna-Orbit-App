"""Campanha de Marketing — o ciclo.

    Rascunho → Para aprovação → Aprovada → (hora) → A enviar → Enviada
         ↑______________|  rejeitar, com motivo

Quem aprova é quem tem «Sales Manager» (ou é System Manager) no tenant — o
cliente. Uma campanha que vem do portal (proposta pela IA, já revista pela
Stratechna) nasce em «Para aprovação».

O que foi a aprovar não se altera por baixo de quem aprovou: fora de rascunho
os campos da mensagem e dos destinatários ficam fechados.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime, now_datetime

from orbit.marketing import destinatarios, envio, mensagem

ABERTOS = ("titulo", "agendar_para")


def _pode_aprovar() -> bool:
    return bool({"Sales Manager", "System Manager"} & set(frappe.get_roles()))


class CampanhadeMarketing(Document):
    def validate(self):
        if self.is_new():
            # Uma campanha do portal já foi escrita pela IA e revista pela
            # Stratechna: chega à espera do cliente. Tudo o resto nasce em
            # rascunho, seja qual for o estado que venha no pedido.
            if self.flags.do_portal:
                self.estado, self.origem = "Para aprovação", "Portal"
            else:
                self.estado, self.origem = "Rascunho", "Orbit"
            return
        if self.estado != "Rascunho" and not self.flags.ciclo:
            antes = self.get_doc_before_save()
            if antes:
                for f in self.meta.fields:
                    if f.fieldname in ABERTOS or f.read_only or f.fieldtype in ("Section Break", "Column Break"):
                        continue
                    if str(antes.get(f.fieldname) or "") != str(self.get(f.fieldname) or "") and f.fieldtype not in ("Table", "Table MultiSelect"):
                        frappe.throw(_("Só se altera uma campanha em rascunho. Para mudar esta, rejeite-a com o motivo."))

    def _mudar(self, de: tuple, para: str, **extra):
        if self.estado not in de:
            frappe.throw(_("A campanha está «{0}» — este passo não se aplica.").format(self.estado))
        # A marca deixa o próprio ciclo gravar fora de rascunho. Tem de sair
        # logo a seguir: as flags vivem no objecto e sobrevivem ao reload(), e
        # esquecida aqui deixava passar qualquer edição feita depois.
        self.flags.ciclo = True
        try:
            self.estado = para
            self.update(extra)
            self.save()
        finally:
            self.flags.ciclo = False

    def _falta(self) -> list[str]:
        falta = []
        if not (self.linha_assunto or "").strip():
            falta.append(_("a linha de assunto"))
        if not ((self.texto or "").strip() or self.titulo_email):
            falta.append(_("o texto"))
        if not self.segmentos:
            falta.append(_("pelo menos um segmento"))
        return falta

    def _quota(self):
        d = mensagem.definicoes()
        if cint(d.plano_contactos):
            n = len(destinatarios.contactaveis())
            if n > cint(d.plano_contactos):
                frappe.throw(_("Há {0} contactos que podem receber e o plano inclui {1}.").format(n, d.plano_contactos))
        if cint(d.plano_campanhas_mes):
            inicio = now_datetime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            n = frappe.db.count("Campanha de Marketing", {"name": ("!=", self.name), "estado": ("not in", ["Rascunho", "Cancelada"]),
                                                          "creation": (">=", inicio)})
            if n >= cint(d.plano_campanhas_mes):
                frappe.throw(_("O plano inclui {0} campanhas por mês e este mês já foram {1}.").format(d.plano_campanhas_mes, n))

    @frappe.whitelist()
    def submeter(self):
        falta = self._falta()
        if falta:
            frappe.throw(_("Falta {0}.").format(", ".join(falta)))
        self._quota()
        self._mudar(("Rascunho",), "Para aprovação")

    @frappe.whitelist()
    def aprovar(self):
        if not _pode_aprovar():
            frappe.throw(_("Só quem gere o marketing da empresa pode aprovar."), frappe.PermissionError)
        self._mudar(("Para aprovação",), "Aprovada", aprovada_por=frappe.session.user, aprovada_em=now_datetime())

    @frappe.whitelist()
    def rejeitar(self, motivo: str):
        if not (motivo or "").strip():
            frappe.throw(_("Uma rejeição precisa do motivo — é dele que se refaz."))
        self._mudar(("Para aprovação", "Aprovada"), "Rascunho", aprovada_por=None, aprovada_em=None)
        self.add_comment("Comment", _("Rejeitada: {0}").format(motivo.strip()))

    @frappe.whitelist()
    def agendar(self, quando: str):
        if self.estado not in ("Rascunho", "Para aprovação", "Aprovada"):
            frappe.throw(_("Esta campanha já não se agenda."))
        self.db_set("agendar_para", get_datetime(quando))

    @frappe.whitelist()
    def retomar(self):
        """Depois de uma pausa automática. O travão volta a avaliar no
        minuto seguinte: retomar sem mudar nada à lista volta a parar."""
        if not _pode_aprovar():
            frappe.throw(_("Só quem gere o marketing da empresa pode retomar."), frappe.PermissionError)
        self._mudar(("Pausada",), "A enviar")

    @frappe.whitelist()
    def cancelar(self):
        self._mudar(("Rascunho", "Para aprovação", "Aprovada", "A enviar", "Pausada"), "Cancelada")
        for e in frappe.get_all("Envio de Marketing", filters={"campanha": self.name, "estado": "Na fila"}, pluck="name"):
            frappe.db.set_value("Envio de Marketing", e, "estado", "Cancelado")
        # O que já estava na fila do Frappe e ainda não saiu, não sai.
        for q in frappe.get_all("Envio de Marketing", filters={"campanha": self.name, "email_queue": ("is", "set")},
                                pluck="email_queue"):
            if frappe.db.get_value("Email Queue", q, "status") == "Not Sent":
                frappe.db.set_value("Email Queue", q, "status", "Cancelled")

    @frappe.whitelist()
    def contar(self) -> int:
        n = len(destinatarios.da_campanha(self))
        return n

    @frappe.whitelist()
    def previsualizar(self) -> dict:
        exemplo = {"nome": "Maria", "mkt_base_legal": "consentimento"}
        m = mensagem.compor(self, exemplo)
        return {"assunto": m["assunto"], "html": m["html"], "simula": envio.simula(),
                "falta": envio.falta_para_enviar()}

    @frappe.whitelist()
    def enviar_teste(self, para: str):
        """Uma mensagem a sério para um endereço escolhido. Não cria envio,
        não conta, e as ligações vão directas."""
        falta = envio.falta_para_enviar()
        if falta:
            frappe.throw(_("Falta configurar {0}.").format("; ".join(falta)))
        frappe.utils.validate_email_address(para, throw=True)
        d = mensagem.definicoes()
        m = mensagem.compor(self, {"nome": "Teste", "mkt_base_legal": "consentimento"})
        frappe.sendmail(recipients=[para], sender=frappe.db.get_value("Email Account", d.email_account, "email_id"),
                        subject="[TESTE] " + m["assunto"], message=m["html"], add_unsubscribe_link=0,
                        with_container=False, raw_html=True, add_css=False, now=True)
