"""Quem aparece como remetente dos avisos do Orbit (17-10-2026). Vale para todos os tenants.

**A conta de saída por omissão chama-se «Stratechna Orbit».** O Frappe põe o NOME da conta de email
como nome do remetente dos avisos automáticos («atribuiu-lhe uma tarefa», notificações…). Com nomes
técnicos («stratechna.pt - CRM») quem recebe não percebe de onde vem; com «—» chegava mesmo como
«utf8bc3Ry…» (o Frappe codifica o nome e depois limpa os =?…?=). Um tenant pode escolher outro nome com
`orbit_remetente_nome` no site_config.

**O «Administrator» mostra-se como «Stratechna Orbit (sistema)».** É a conta técnica do Frappe — as
cargas, as tarefas automáticas — e não uma pessoa; os avisos que ela gera («Administrator atribuiu-lhe…»)
passam a dizer de onde vêm. O login e as permissões não mudam: só o nome que se vê.

Corre no after_migrate (todos os sites, tenants novos incluídos) e sempre que uma conta de email é
gravada como saída por omissão.
"""
import frappe

NOME_SISTEMA = ("Stratechna Orbit", "(sistema)")
NOME_REMETENTE = "Stratechna Orbit"


def garantir() -> None:
    for f in (garantir_administrador, garantir_remetente):
        try:
            f()
        except Exception:
            frappe.log_error(title=f"orbit.remetentes.{f.__name__}")
    frappe.db.commit()


def garantir_administrador() -> None:
    primeiro, ultimo = NOME_SISTEMA
    atual = frappe.db.get_value("User", "Administrator", ["first_name", "last_name"], as_dict=True)
    if not atual or (atual.first_name == primeiro and atual.last_name == ultimo):
        return
    frappe.db.set_value("User", "Administrator", {"first_name": primeiro, "last_name": ultimo,
                                                  "full_name": f"{primeiro} {ultimo}"}, update_modified=False)
    frappe.clear_cache(user="Administrator")


def garantir_remetente() -> None:
    nome = (frappe.conf.get("orbit_remetente_nome") or NOME_REMETENTE).strip()
    conta = frappe.db.get_value("Email Account", {"default_outgoing": 1, "enable_outgoing": 1})
    if not conta or conta == nome:
        return
    if frappe.db.exists("Email Account", nome):
        # outra conta já tem este nome (ex.: a antiga de omissão): leva o nome técnico de volta
        email = frappe.db.get_value("Email Account", nome, "email_id") or nome
        tecnico = f"{email.split('@')[-1]} - {email.split('@')[0]}"
        frappe.rename_doc("Email Account", nome, tecnico, force=True)
        frappe.db.set_value("Email Account", tecnico, "email_account_name", tecnico, update_modified=False)
    frappe.rename_doc("Email Account", conta, nome, force=True)
    frappe.db.set_value("Email Account", nome, "email_account_name", nome, update_modified=False)


def conta_gravada(doc, method=None):
    """Email Account.on_update: quando esta passa a ser a de omissão, recebe o nome do remetente.
    Na fila e depois do commit — mudar o nome de um documento a meio da sua própria gravação parte-a."""
    if doc.get("default_outgoing") and doc.get("enable_outgoing"):
        nome = (frappe.conf.get("orbit_remetente_nome") or NOME_REMETENTE).strip()
        if doc.name != nome:
            frappe.enqueue("orbit.remetentes.garantir_remetente", queue="short", enqueue_after_commit=True)
