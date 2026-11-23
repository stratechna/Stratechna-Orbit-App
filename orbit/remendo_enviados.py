"""Emails enviados no CRM (23-11-2026, pedido do Vítor: «a atividade só mostra os recebidos»).

O Frappe lê a pasta Enviados das caixas ligadas ao CRM, mas `InboundMail.process()` recusa tudo o que tem como
remetente a própria caixa (`SentEmailInInboxError`) — só deixa passar respostas a emails do próprio Orbit — e o que
deixa passar fica marcado como «Received» (`as_dict` tem «Received» fixo). Resultado no Orbit da Stratechna a 23-11:
1 237 recebidos e 3 enviados.

Este remendo (aplicado ao carregar a app, sem mudar o código do Frappe):
* um email cuja remetente é a própria caixa entra como **«Sent»** (enviado), seja resposta ou não;
* não é «novo» para efeitos de avisos: o Frappe não manda notificações nem respostas automáticas por ele
  (guardar um Communication nunca o volta a enviar — o envio só acontece por `make()`/fila de saída);
* os já existentes (enviados pelo próprio Orbit) reconhecem-se pelo Message-ID e não se repetem.

`emails_crm.filtrar` liga-os aos registos do CRM pelos destinatários; para enviados não cria leads novas.
"""
from __future__ import annotations

import frappe

_FEITO = False


def aplicar():
    global _FEITO
    if _FEITO:
        return
    try:
        from frappe.email import receive as R
    except Exception:
        return
    original_process = R.InboundMail.process
    original_as_dict = R.InboundMail.as_dict

    def _proprio(self) -> bool:
        try:
            return bool(self.from_email) and (self.from_email or "").lower() == (self.email_account.email_id or "").lower()
        except Exception:
            return False

    def process(self):
        if not _proprio(self):
            return original_process(self)
        existente = self.is_exist_in_system()
        if existente:
            existente.update_db(uid=self.uid)
            if existente.sent_or_received != "Sent":
                existente.update_db(sent_or_received="Sent")
            existente.reload()
            return existente
        self.flags.is_new_communication = False   # sem avisos nem respostas automáticas
        return self._build_communication_doc()

    def as_dict(self):
        d = original_as_dict(self)
        if _proprio(self):
            d["sent_or_received"] = "Sent"
        return d

    R.InboundMail.process = process
    R.InboundMail.as_dict = as_dict
    _FEITO = True


@frappe.whitelist()
def recuperar_enviados(dias: int = 365, simular: int = 1):
    """Volta a ler as pastas Enviados das caixas ligadas ao CRM (os que o Frappe deitou fora até 23-11).
    Só entram os trocados com quem já está no CRM (o `filtrar` não cria leads por emails enviados)."""
    frappe.only_for("System Manager")
    aplicar()
    import re
    from frappe.email.receive import InboundMail
    from orbit.emails_crm import NIVEIS, _imap_da_conta
    desde = frappe.utils.getdate(frappe.utils.add_days(frappe.utils.nowdate(), -int(dias))).strftime("%d-%b-%Y")
    res = {}
    for nome in frappe.get_all("Email Account", filters={"enable_incoming": 1, "orbit_registo_crm": ["in", list(NIVEIS)]}, pluck="name"):
        acc = frappe.get_doc("Email Account", nome)
        pastas = [p for p in acc.imap_folder if p.folder_name != "INBOX"]
        if not pastas:
            continue
        conta = {"encontrados": 0, "novos": 0, "ja_existiam": 0, "erros": 0}
        try:
            m = _imap_da_conta(acc)
        except Exception as ex:  # noqa: BLE001
            res[nome] = {"erro": str(ex)[:150]}
            continue
        try:
            for pasta in pastas:
                if m.select(f'"{pasta.folder_name}"', readonly=True)[0] != "OK":
                    continue
                _, r = m.uid("SEARCH", None, f"SINCE {desde}")
                uids = (r[0] or b"").split()[-3000:]
                conta["encontrados"] += len(uids)
                if int(simular):
                    continue
                for uid in uids:
                    try:
                        _, dados = m.uid("FETCH", uid, "(RFC822)")
                        bruto = next((p[1] for p in dados if isinstance(p, tuple)), None)
                        if not bruto:
                            continue
                        mail = InboundMail(bruto, acc, uid=None, seen_status=1, append_to=pasta.append_to)
                        if mail.message_id and frappe.db.exists("Communication", {"message_id": mail.message_id}):
                            conta["ja_existiam"] += 1
                            c = frappe.db.get_value("Communication", {"message_id": mail.message_id}, ["name", "sent_or_received"], as_dict=True)
                            if c.sent_or_received != "Sent" and (mail.from_email or "").lower() == (acc.email_id or "").lower():
                                frappe.db.set_value("Communication", c.name, "sent_or_received", "Sent", update_modified=False)
                        else:
                            mail.process()
                            conta["novos"] += 1
                        frappe.db.commit()
                    except Exception:  # noqa: BLE001
                        frappe.db.rollback()
                        conta["erros"] += 1
        finally:
            try:
                m.logout()
            except Exception:
                pass
        res[nome] = conta
    return res
