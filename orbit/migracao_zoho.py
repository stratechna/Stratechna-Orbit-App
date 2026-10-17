"""Migração do Zoho (17-10-2026): campos de correspondência e conversão de leads.

Campos — os do levantamento `docs/levantamento-campos-zoho-orbit.md` §5. Todos os registos importados guardam
o `zoho_id` (único, só de leitura): é o que torna a importação repetível sem duplicar — correr duas vezes
actualiza. A conta do cliente guarda o `crm_account_id` (o id da Account no Zoho), que é a chave de cliente em
todo o portal e nunca muda.

Leads, contactos e contas (pedido do Vítor): no Orbit, como no Zoho, são coisas diferentes.
  * CRM Lead = alguém ainda por qualificar;
  * Contact + CRM Organization = quem já é contacto ou cliente (no Zoho: Contacts + Accounts);
  * CRM Deal = um negócio.
O CRM do Frappe já converte um lead em negócio (cria a organização e o contacto). O Zoho também converte
SEM negócio — em contacto e conta. Isso não existe no Frappe: `converter_sem_negocio` faz essa conversão.
"""
import frappe

UNICO = {"unique": 1, "read_only": 1, "no_copy": 1}

CAMPOS = {
    "CRM Organization": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        dict(fieldname="crm_account_id", label="Conta no portal", fieldtype="Data", unique=1, no_copy=1, in_standard_filter=1),
        dict(fieldname="customer", label="Cliente (ERP)", fieldtype="Link", options="Customer"),
        dict(fieldname="nipc", label="NIPC", fieldtype="Data"),
        dict(fieldname="telefone", label="Telefone", fieldtype="Data", options="Phone"),
        dict(fieldname="email_geral", label="Email geral", fieldtype="Data", options="Email"),
        dict(fieldname="email_contabilidade", label="Email da contabilidade", fieldtype="Data", options="Email"),
        dict(fieldname="id_cliente_moloni", label="ID cliente Moloni", fieldtype="Data"),
        dict(fieldname="estado_conta", label="Estado da conta", fieldtype="Select",
             options="\nActivo\nAdquirido\nEncerrar\nProjecto cancelado\nFalhou"),
        dict(fieldname="tipo_conta", label="Tipo de conta", fieldtype="Select",
             options="\nCliente\nParceiro\nFornecedor\nRevendedor\nConcorrente\nOutro"),
        dict(fieldname="webgate_cc", label="Conta-corrente Webgate", fieldtype="Data", options="URL"),
        dict(fieldname="mbontime_cc", label="Conta-corrente MBontime", fieldtype="Data", options="URL"),
        dict(fieldname="zoho_account_number", label="N.º de conta (Zoho)", fieldtype="Data", read_only=1),
    ],
    "Customer": [
        dict(fieldname="crm_account_id", label="Conta no portal", fieldtype="Data", unique=1, no_copy=1),
        dict(fieldname="id_cliente_moloni", label="ID cliente Moloni", fieldtype="Data"),
        dict(fieldname="faturar_moloni", label="Faturar no Moloni", fieldtype="Check"),
        dict(fieldname="email_contabilidade", label="Email da contabilidade", fieldtype="Data", options="Email"),
    ],
    "HD Customer": [
        dict(fieldname="crm_account_id", label="Conta no portal", fieldtype="Data", unique=1, no_copy=1),
    ],
    "Contact": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        dict(fieldname="zoho_desk_id", label="ID Zoho Desk", fieldtype="Data", read_only=1, no_copy=1),
        dict(fieldname="nif", label="NIF", fieldtype="Data"),
        dict(fieldname="aprova_redes_sociais", label="Aprova redes sociais", fieldtype="Check"),
        dict(fieldname="aprova_publicidade_digital", label="Aprova publicidade digital", fieldtype="Check"),
        dict(fieldname="origem", label="Origem", fieldtype="Link", options="CRM Lead Source"),
    ],
    "CRM Lead": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        dict(fieldname="nipc", label="NIPC", fieldtype="Data"),
        dict(fieldname="cidade", label="Cidade", fieldtype="Data"),
        dict(fieldname="distrito", label="Distrito", fieldtype="Data"),
        dict(fieldname="codigo_postal", label="Código postal", fieldtype="Data"),
        dict(fieldname="pais", label="País", fieldtype="Link", options="Country"),
    ],
    "CRM Deal": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        dict(fieldname="titulo", label="Título", fieldtype="Data", in_list_view=1),
        dict(fieldname="moloni_document_id", label="Documento Moloni", fieldtype="Data", read_only=1),
    ],
    "FCRM Note": [dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO)],
    "CRM Task": [dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO)],
    "CRM Call Log": [dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO)],
    "Event": [dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO)],
    "HD Ticket": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        dict(fieldname="zoho_ticket_number", label="N.º no Zoho", fieldtype="Int", read_only=1, no_copy=1),
        dict(fieldname="crm_account_id", label="Conta no portal", fieldtype="Data", no_copy=1),
        dict(fieldname="canal", label="Canal", fieldtype="Select",
             options="\nEmail\nChat\nWeb\nPhone\nFacebook\nInstagram\nTwitter\nForums\nFeedback Widget"),
        dict(fieldname="telefone", label="Telefone", fieldtype="Data", options="Phone"),
        dict(fieldname="data_limite", label="Data limite", fieldtype="Datetime"),
        dict(fieldname="tarefa_mbontime", label="Tarefa (MBontime)", fieldtype="Data",
             depends_on="eval:doc.agent_group=='MBontime'"),
    ],
    "Timesheet": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        # o tempo vindo do Zoho JÁ está no livro de horas do portal: importado=1 nunca volta a ser enviado
        dict(fieldname="importado_zoho", label="Importado do Zoho (já está no portal)", fieldtype="Check", read_only=1),
    ],
    "Project": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        dict(fieldname="crm_account_id", label="Conta no portal", fieldtype="Data", no_copy=1, in_standard_filter=1),
        dict(fieldname="subscricao_portal", label="Subscrição no portal", fieldtype="Data", no_copy=1),
        dict(fieldname="dominio", label="Domínio", fieldtype="Data"),
    ],
    "Task": [
        dict(fieldname="zoho_id", label="ID Zoho", fieldtype="Data", **UNICO),
        dict(fieldname="ordem", label="Ordem", fieldtype="Int"),
    ],
}


def garantir() -> None:
    """after_migrate: cria os campos que faltam (nunca mexe nos que existem). Nunca faz falhar a migração."""
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_field
        for dt, campos in CAMPOS.items():
            if not frappe.db.exists("DocType", dt):
                continue
            meta = frappe.get_meta(dt)
            for c in campos:
                if meta.has_field(c["fieldname"]) or frappe.db.exists("Custom Field", {"dt": dt, "fieldname": c["fieldname"]}):
                    continue
                create_custom_field(dt, {**c, "module": "Orbit"})
        _botao_converter()
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title="orbit.migracao_zoho.garantir")


@frappe.whitelist()
def converter_sem_negocio(lead: str) -> dict:
    """Converte um lead em contacto + organização, SEM criar negócio (como o «Converter» do Zoho sem
    oportunidade). O lead fica marcado como convertido e ligado aos dois."""
    doc = frappe.get_doc("CRM Lead", lead)
    doc.check_permission("write")
    if doc.converted:
        frappe.throw("Este lead já foi convertido.")
    contacto = doc.create_contact(throw=False)
    organizacao = doc.create_organization()
    if organizacao and contacto:
        c = frappe.get_doc("Contact", contacto)
        if not any(l.link_doctype == "CRM Organization" and l.link_name == organizacao for l in c.links):
            c.append("links", {"link_doctype": "CRM Organization", "link_name": organizacao})
            c.save(ignore_permissions=True)
    doc.db_set("converted", 1)
    return {"contacto": contacto, "organizacao": organizacao}


_SCRIPT = """function setupForm({ doc, call, toast, router }) {
  return {
    actions: doc.converted ? [] : [{
      label: 'Converter em contacto e organização',
      onClick: async () => {
        const r = await call('orbit.migracao_zoho.converter_sem_negocio', { lead: doc.name })
        toast.success('Convertido: ' + (r.contacto || '') + (r.organizacao ? ' · ' + r.organizacao : ''))
        if (r.organizacao) router.push({ name: 'Organization', params: { organizationId: r.organizacao } })
      },
    }],
  }
}"""


def _botao_converter() -> None:
    """No lead, ao lado do «Converter em negócio» do CRM: converter só em contacto e organização."""
    if not frappe.db.exists("DocType", "CRM Form Script"):
        return
    nome = "Orbit — converter sem negócio"
    if frappe.db.exists("CRM Form Script", nome):
        return
    frappe.get_doc({"doctype": "CRM Form Script", "name": nome, "dt": "CRM Lead", "view": "Form",
                    "enabled": 1, "script": _SCRIPT}).insert(ignore_permissions=True, set_name=nome)
