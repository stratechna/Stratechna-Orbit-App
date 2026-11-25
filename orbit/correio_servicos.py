"""Serviços de correio da Conta de e-mail (25-11-2026, pedido do Vítor: ligar comercial2@arnox.pt, que está no Zoho).

O Frappe só traz GMail, Outlook.com, Sendgrid, SparkPost, Yahoo, Yandex e «Frappe Mail», e preenche os servidores
por script no ecrã antigo (`frappe.email_defaults` em email_account.js). Aqui:

* `acertar` (after_migrate) acrescenta «Zoho Mail (UE)» e «Zoho Mail» às opções do campo `service` por Property Setter;
* `valores` devolve os servidores de um serviço — a interface /orbit chama-a ao escolher o serviço (o mesmo que o
  script do ecrã antigo faz), e os do Frappe vêm da mesma tabela do email_account.js;
* `validar` (validate) preenche os servidores do Zoho se ficarem vazios, para valer também pelo ecrã antigo e pela API.

«Frappe Mail» é um produto da Frappe Cloud, não o Orbit Mail: a interface esconde-o (só aparece se já estiver escolhido).
"""
import frappe

ZOHO = {
    "Zoho Mail (UE)": "zoho.eu",
    "Zoho Mail": "zoho.com",
}

# A mesma tabela do email_account.js do Frappe (IMAP), mais o Zoho.
_PREDEF = {
    "GMail": {"email_server": "imap.gmail.com", "incoming_port": 993, "use_ssl": 1, "enable_outgoing": 1,
              "smtp_server": "smtp.gmail.com", "smtp_port": 587, "use_tls": 1, "use_imap": 1},
    "Outlook.com": {"email_server": "imap-mail.outlook.com", "use_ssl": 1, "enable_outgoing": 1,
                    "smtp_server": "smtp-mail.outlook.com", "smtp_port": 587, "use_tls": 1, "use_imap": 1},
    "Sendgrid": {"enable_outgoing": 1, "smtp_server": "smtp.sendgrid.net", "smtp_port": 587, "use_tls": 1},
    "SparkPost": {"enable_incoming": 0, "enable_outgoing": 1, "smtp_server": "smtp.sparkpostmail.com",
                  "smtp_port": 587, "use_tls": 1},
    "Yahoo Mail": {"email_server": "imap.mail.yahoo.com", "use_ssl": 1, "enable_outgoing": 1,
                   "smtp_server": "smtp.mail.yahoo.com", "smtp_port": 587, "use_tls": 1, "use_imap": 1},
    "Yandex.Mail": {"email_server": "imap.yandex.com", "use_ssl": 1, "enable_outgoing": 1,
                    "smtp_server": "smtp.yandex.com", "smtp_port": 587, "use_tls": 1, "use_imap": 1},
}
for _s, _d in ZOHO.items():
    # Zoho: IMAP 993 SSL; SMTP 465 SSL (o 587 com STARTTLS também serve). Pastas: INBOX e Sent.
    _PREDEF[_s] = {"email_server": f"imap.{_d}", "incoming_port": 993, "use_ssl": 1, "use_imap": 1,
                   "enable_outgoing": 1, "smtp_server": f"smtp.{_d}", "smtp_port": 465,
                   "use_ssl_for_outgoing": 1, "use_tls": 0, "sent_folder_name": "Sent", "auth_method": "Basic"}

_POP = {"GMail": "pop.gmail.com", "Outlook.com": "pop3-mail.outlook.com", "Yahoo Mail": "pop.mail.yahoo.com",
        "Yandex.Mail": "pop.yandex.com"}


def acertar() -> None:
    """Acrescenta os serviços do Zoho às opções do campo `service` (idempotente)."""
    if not frappe.db.exists("DocType", "Email Account"):
        return
    df = frappe.get_meta("Email Account").get_field("service")
    if not df:
        return
    ops = [o for o in (df.options or "").split("\n")]
    novas = ops + [s for s in ZOHO if s not in ops]
    if novas == ops:
        return
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    make_property_setter("Email Account", "service", "options", "\n".join(novas), "Text", validate_fields_for_doctype=False)
    frappe.clear_cache(doctype="Email Account")


@frappe.whitelist()
def valores(service: str, use_imap: int = 1) -> dict:
    """Os servidores de um serviço, como o script do ecrã antigo preenche ao escolher o serviço."""
    d = dict(_PREDEF.get(service or "", {}))
    if d and not int(use_imap or 0) and service in _POP:
        d["email_server"] = _POP[service]
        d.pop("use_imap", None)
    return d


def validar(doc, method=None) -> None:
    """Conta do Zoho gravada sem servidores (ecrã antigo, API): preenche-os."""
    if doc.service not in ZOHO:
        return
    for k, v in _PREDEF[doc.service].items():
        if k in ("enable_outgoing", "auth_method"):
            continue
        if not doc.get(k):
            doc.set(k, v)


@frappe.whitelist()
def valores_dominio(domain: str) -> dict:
    """Os servidores de um Domínio de e-mail (o `get_domain_values` do ecrã antigo)."""
    if not domain or not frappe.db.exists("Email Domain", domain):
        return {}
    frappe.has_permission("Email Domain", "read", throw=True)
    d = frappe.get_doc("Email Domain", domain)
    conta = frappe.get_meta("Email Account")
    campos = ("email_server", "use_imap", "incoming_port", "use_ssl", "use_starttls", "validate_ssl_certificate",
              "attachment_limit", "smtp_server", "smtp_port", "use_tls", "use_ssl_for_outgoing",
              "append_emails_to_sent_folder", "sent_folder_name")
    return {c: d.get(c) for c in campos if d.meta.has_field(c) and conta.has_field(c)}
