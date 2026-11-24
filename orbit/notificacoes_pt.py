"""Notificações automáticas do ERP em português (24-11-2026, pedido do Vítor: «todas estas notificações estão em inglês»).

As regras de aviso que vêm com o ERPNext/HRMS (Notification, `is_standard`) têm o assunto e o corpo em inglês e,
na lista das Definições, aparecia o modelo Jinja cru como título. Aqui:
- cada regra ganha uma descrição em PT-PT (`orbit_descricao`, título da lista) e o assunto e o corpo em PT-PT;
- corre em `after_migrate`, depois de o Frappe repor as regras-padrão a partir dos ficheiros das apps, por isso uma
  actualização do ERPNext/HRMS não as volta a pôr em inglês.
Regras novas que alguém crie no Orbit ficam como foram escritas.
"""
import frappe

_MOTIVO = "{% if doc.status == 'Rejected' and doc.rejection_reason %}<p>Motivo: {{ doc.rejection_reason | e }}</p>{% endif %}"

_ERRO_EN_PT = [
    ("Error Log\n", "Registo de erro\n"), ("Integration Request\n", "Pedido de integração\n"),
    (">Site<", ">Site<"), (">Error ID<", ">N.º do erro<"), (">Title<", ">Título<"), (">Logged At<", ">Registado em<"),
    (">Reference<", ">Referência<"), (">Request ID<", ">N.º do pedido<"), (">Service<", ">Serviço<"),
    (">Status<", ">Estado<"), (">Description<", ">Descrição<"), (">Endpoint URL<", ">Endereço chamado<"),
    ("Error Details", "Detalhes do erro"), ("Response Output", "Resposta recebida"),
    (" of {{", " de {{"), ("lines)", "linhas)"), ("lines omitted", "linhas omitidas"),
    ("View Error Log", "Ver o registo de erro"), ("View Integration Request", "Ver o pedido de integração"),
    ("This is an automated notification from", "Aviso automático de"), ('"N/A"', '"—"'),
]

REGRAS = {
    "Asset Request Decided": (
        "RH — pedido de equipamento aprovado ou recusado",
        "{{ ('O seu pedido de equipamento {0} foi aprovado' if doc.status == 'Approved' else "
        "'O seu pedido de equipamento {0} foi recusado').format(doc.name) }}",
        _MOTIVO),
    "Bank Details Change Request Decided": (
        "RH — alteração dos dados bancários aprovada ou recusada",
        "{{ 'O seu pedido de alteração dos dados bancários foi aprovado' if doc.status == 'Approved' else "
        "'O seu pedido de alteração dos dados bancários foi recusado' }}",
        _MOTIVO),
    "Error Log": ("Sistema — erro registado (email, desligado)", "[Erro] {{ doc.method }}", None),
    "Integration Request": ("Sistema — erro numa integração (email, desligado)",
                            "[Erro] {{ doc.integration_request_service }}", None),
    "Exit Interview Scheduled": (
        "RH — entrevista de saída marcada",
        "Entrevista de saída marcada: {{ doc.employee_name or doc.name }}",
        """<p><b>Entrevista de saída marcada</b></p>
<ul style="line-height: 1.7">
<li>Colaborador: <b>{{ doc.employee }} — {{ doc.employee_name }}</b></li>
<li>Data: <b>{{ frappe.utils.formatdate(doc.date) }}</b></li>
<li>Entrevistadores: {% for e in doc.interviewers %}{{ e.user }}{% if not loop.last %}, {% endif %}{% endfor %}</li>
<li>Documento: {{ frappe.utils.get_link_to_form(doc.doctype, doc.name) }}</li>
</ul>"""),
    "Material Request Receipt Notification": (
        "Operações — requisição de material recebida",
        "A requisição de material {{ doc.name }} foi recebida",
        """<p><b>Tipo de requisição:</b> {{ doc.material_request_type }}<br><b>Empresa:</b> {{ doc.company }}</p>
<p><b>Recebido</b></p>
<table border="1" cellpadding="6" style="border-collapse: collapse">
<tr><th>Artigo</th><th>Quantidade recebida</th></tr>
{% for item in doc.items %}{% if frappe.utils.flt(item.received_qty, 2) > 0.0 %}
<tr><td>{{ item.item_code }} — {{ item.item_name }}</td><td align="right">{{ frappe.utils.flt(item.received_qty, 2) }}</td></tr>
{% endif %}{% endfor %}
</table>"""),
    "Notification for new fiscal year": (
        "Contabilidade — novo ano fiscal criado",
        "Novo ano fiscal {{ doc.name }} — rever a configuração",
        """<p>Foi criado automaticamente o ano fiscal <b>{{ doc.name }}</b>
({{ frappe.format_value(doc.year_start_date) }} a {{ frappe.format_value(doc.year_end_date) }}){% if doc.companies %}
para {% for c in doc.companies %}{{ c.company }}{% if not loop.last %}, {% endif %}{% endfor %}{% endif %}.</p>
{% if doc.disabled %}<p>Ficou desactivado, como o ano anterior.</p>{% endif %}
<p>Reveja a configuração em {{ frappe.utils.get_link_to_form("Fiscal Year", doc.name, "Ano fiscal") }}.</p>"""),
    "Retention Bonus": (
        "RH — prémio de permanência a pagar",
        "Prémio de permanência de {{ doc.employee_name }}",
        "<p>O prémio de permanência de <b>{{ doc.employee_name }}</b> vence a "
        "{{ frappe.utils.formatdate(doc.bonus_payment_date) }}.</p>"),
    "Training Feedback": (
        "RH — pedido de opinião sobre uma formação",
        "Partilhe a sua opinião sobre a formação {{ doc.training_event }}",
        """<p><b>Formação</b></p>
<p>{{ message }}</p>
<p>Nome: <a href="{{ event_link }}">{{ name }}</a><br>Local: {{ location }}<br>Início: {{ start_time }}<br>
Fim: {{ end_time }}<br>Presença: {{ attendance }}</p>"""),
    "Training Scheduled": (
        "RH — formação marcada",
        "Formação marcada: {{ doc.event_name or doc.name }}",
        """<p><b>Formação: {{ doc.event_name }}</b></p>
{{ doc.introduction or "" }}
<ul style="line-height: 1.7">
<li>Local: <b>{{ doc.location }}</b></li>
<li>Início: <b>{{ frappe.utils.format_datetime(doc.start_time, "dd-MM-yyyy HH:mm") }}</b></li>
<li>Fim: <b>{{ frappe.utils.format_datetime(doc.end_time, "dd-MM-yyyy HH:mm") }}</b></li>
<li>Ligação: {{ frappe.utils.get_link_to_form(doc.doctype, doc.name) }}</li>
{% if doc.is_mandatory %}<li>Esta formação é obrigatória.</li>{% endif %}
</ul>"""),
}


def _campo():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    if not frappe.get_meta("Notification").has_field("orbit_descricao"):
        create_custom_field("Notification", {"fieldname": "orbit_descricao", "label": "Descrição",
                                             "fieldtype": "Data", "insert_after": "name", "bold": 1})
    if frappe.get_meta("Notification").title_field != "orbit_descricao":
        make_property_setter("Notification", None, "title_field", "orbit_descricao", "Data",
                             validate_fields_for_doctype=False)
    frappe.clear_cache(doctype="Notification")


def acertar():
    try:
        _campo()
        for nome, (descricao, assunto, corpo) in REGRAS.items():
            if not frappe.db.exists("Notification", nome):
                continue
            valores = {"orbit_descricao": descricao, "subject": assunto}
            if corpo is not None:
                valores["message"] = corpo
                valores["message_type"] = "HTML"
            else:
                texto = frappe.db.get_value("Notification", nome, "message") or ""
                for en, pt in _ERRO_EN_PT:
                    texto = texto.replace(en, pt)
                valores["message"] = texto
            frappe.db.set_value("Notification", nome, valores, update_modified=False)
        # as que alguém criou sem descrição mostram o próprio nome
        frappe.db.sql("update tabNotification set orbit_descricao=name where ifnull(orbit_descricao,'')=''")
        frappe.db.commit()
    except Exception as e:  # noqa: BLE001 — nunca deita abaixo uma migração
        frappe.db.rollback()
        frappe.log_error(f"notificacoes_pt: {e}", "orbit notificações PT")
