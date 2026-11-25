# Desk na interface nova (/orbit) — lote 3 do plano das opções dos originais (25-11-2026)
#
# docs/PLANO-ORBIT-OPCOES-DOS-ORIGINAIS.md §3, lote 3: o que o agente faz no Helpdesk original e faltava no /orbit —
# resposta com «De», Para/Cc/Bcc, anexos e as acções da resposta-modelo; criar ticket em nome de um contacto;
# fundir e dividir; mudar o assunto, o cliente e os campos do modelo; apagar; lista com filtros, ordem e acções em
# massa. Tudo pelas funções do próprio Helpdesk, com as permissões de quem está a usar.
import json

import frappe
from frappe import _
from frappe.utils import cint, cstr, strip_html

from orbit.interface.api import _guarda

EDITAVEIS = {"subject", "customer", "status", "priority", "ticket_type", "agent_group", "orbit_marca", "contact", "raised_by"}
ORDENS = {"atividade": "modified desc", "abertura": "opening_date desc", "abertura_asc": "opening_date asc",
          "prazo": "resolution_by asc", "prioridade": "priority asc"}


def _t(nome, perm="write"):
    t = frappe.get_doc("HD Ticket", nome)
    t.check_permission(perm)
    return t


@frappe.whitelist()
def contas_envio():
    """As caixas de onde o agente pode responder («De», como no Helpdesk)."""
    _guarda()
    contas = frappe.get_all("Email Account", filters={"enable_outgoing": 1}, fields=["name", "email_id", "default_outgoing"],
                            order_by="default_outgoing desc, email_id asc")
    return [{"conta": c.name, "email": c.email_id, "padrao": cint(c.default_outgoing)} for c in contas if c.email_id]


@frappe.whitelist(methods=["POST"])
def responder(nome: str, html: str, para: str = None, cc: str = None, bcc: str = None, conta: str = None,
              anexos: str = None, acoes: str = None):
    """Resposta ao cliente com tudo o que o Helpdesk aceita; depois corre as acções da resposta-modelo, se houver."""
    _guarda()
    t = _t(nome)
    if not strip_html(html or "").strip():
        frappe.throw(_("Escreva a resposta."))
    de = None
    if conta:
        email = frappe.db.get_value("Email Account", conta, "email_id")
        if not email:
            frappe.throw(_("Caixa desconhecida."))
        de = {"email_account": conta, "email_id": email}
    t.reply_via_agent(message=html, from_email=de, to=(para or None), cc=cc or None, bcc=bcc or None,
                      attachments=json.loads(anexos) if anexos else [])
    feitas = None
    if acoes:
        try:
            from helpdesk.api.saved_replies import apply_saved_reply_actions
            feitas = apply_saved_reply_actions(nome, acoes)
        except Exception as e:  # noqa: BLE001 — o email já saiu; as acções que falham só se relatam
            feitas = {"erro": str(e)[:200]}
    return {"ok": 1, "acoes": feitas}


@frappe.whitelist()
def resposta_modelo(nome: str, ticket: str):
    """O texto da resposta-modelo em HTML (com formatação) e as acções dela."""
    _guarda()
    from helpdesk.api.saved_replies import get_rendered_saved_reply
    return get_rendered_saved_reply(ticket_id=ticket, saved_reply_id=nome)


@frappe.whitelist(methods=["POST"])
def mudar(nome: str, campo: str, valor: str = ""):
    """Também o assunto, o cliente, o contacto e os campos do modelo do ticket (que o Helpdesk mostra na barra)."""
    _guarda()
    t = _t(nome)
    permitidos = EDITAVEIS | {c["campo"] for c in _campos_modelo()}
    if campo not in permitidos or not t.meta.has_field(campo):
        frappe.throw(_("Campo não editável."))
    if campo == "subject" and not cstr(valor).strip():
        frappe.throw(_("O assunto não pode ficar vazio."))
    t.set(campo, valor if valor not in ("", None) else None)
    t.save()
    return {"ok": 1}


def _campos_modelo():
    """Campos que o «HD Ticket Template» (Default) acrescenta ao ticket — os mesmos que o Helpdesk pede."""
    if not frappe.db.exists("HD Ticket Template", "Default"):
        return []
    meta = frappe.get_meta("HD Ticket")
    base = {"subject", "description", "ticket_type", "priority", "agent_group", "customer", "contact", "raised_by", "status"}
    out = []
    for f in frappe.get_doc("HD Ticket Template", "Default").get("fields") or []:
        fn = f.get("fieldname")
        mf = meta.get_field(fn) if fn else None
        if not mf or fn in base:
            continue
        opcoes = None
        if mf.fieldtype == "Select":
            opcoes = [o for o in (mf.options or "").split("\n") if o]
        out.append({"campo": fn, "rotulo": _(mf.label or fn), "tipo": mf.fieldtype, "opcoes": opcoes, "liga": mf.options if mf.fieldtype == "Link" else None,
                    "obrigatorio": cint(f.get("required"))})
    return out


@frappe.whitelist()
def extra(nome: str):
    """O que a barra do ticket mostra além do básico: campos do modelo e valores, clientes, assuntos semelhantes."""
    _guarda()
    t = _t(nome, "read")
    campos = _campos_modelo()
    for c in campos:
        c["valor"] = t.get(c["campo"])
    recentes = []
    if t.raised_by:
        recentes = frappe.get_list("HD Ticket", filters={"raised_by": t.raised_by, "name": ["!=", t.name]},
                                   fields=["name", "subject", "status", "creation"], order_by="creation desc", limit=5)
    return {"campos": campos, "clientes": frappe.get_all("HD Customer", pluck="name", order_by="name asc", limit=500),
            "recentes": [{"name": r.name, "assunto": r.subject, "estado": r.status, "quando": str(r.creation)} for r in recentes],
            "fundido_em": t.get("merged_with") if cint(t.get("is_merged")) else None}


@frappe.whitelist(methods=["POST"])
def fundir(origem: str, destino: str):
    _guarda()
    from helpdesk.helpdesk.doctype.hd_ticket.api import merge_ticket
    merge_ticket(origem, destino)
    return {"ok": 1, "destino": destino}


@frappe.whitelist(methods=["POST"])
def dividir(comunicacao: str, assunto: str):
    _guarda()
    ticket = frappe.db.get_value("Communication", comunicacao, "reference_name")
    if not ticket:
        frappe.throw(_("Email desconhecido."))
    _t(ticket)
    from helpdesk.helpdesk.doctype.hd_ticket.api import split_ticket
    novo = split_ticket(assunto, comunicacao)
    return {"ok": 1, "novo": novo}


@frappe.whitelist(methods=["POST"])
def apagar(nome: str):
    _guarda()
    frappe.delete_doc("HD Ticket", nome)
    return {"ok": 1}


@frappe.whitelist(methods=["POST"])
def criar(dados: str):
    """Ticket aberto pelo agente em nome de um contacto (telefone, balcão, email reencaminhado)."""
    _guarda()
    d = json.loads(dados or "{}")
    if not frappe.has_permission("HD Ticket", "create"):
        frappe.throw(_("Sem permissão para criar tickets."), frappe.PermissionError)
    email = cstr(d.get("email")).strip()
    if not email or not cstr(d.get("assunto")).strip():
        frappe.throw(_("Indique o email do cliente e o assunto."))
    t = frappe.get_doc({"doctype": "HD Ticket", "subject": cstr(d["assunto"]).strip()[:140], "raised_by": email,
                        "description": d.get("descricao") or "", "priority": d.get("prioridade") or None,
                        "ticket_type": d.get("tipo") or None, "agent_group": d.get("equipa") or None,
                        "customer": d.get("cliente") or None})
    contacto = frappe.db.get_value("Contact Email", {"email_id": email, "parenttype": "Contact"}, "parent")
    if contacto:
        t.contact = contacto
    if d.get("marca") and t.meta.has_field("orbit_marca"):
        t.orbit_marca = d["marca"]
    t.insert()
    if d.get("responsavel"):
        t.assign_agent(d["responsavel"])
    return {"name": t.name}


@frappe.whitelist(methods=["POST"])
def em_massa(nomes: str, acao: str, valor: str = ""):
    """Atribuir, mudar estado/prioridade/equipa/tipo ou apagar vários tickets de uma vez (como a lista do Helpdesk)."""
    _guarda()
    lista = json.loads(nomes or "[]")
    campo = {"estado": "status", "prioridade": "priority", "equipa": "agent_group", "tipo": "ticket_type"}.get(acao)
    feitos, falhas = 0, []
    for n in lista[:500]:
        try:
            if acao == "apagar":
                frappe.delete_doc("HD Ticket", n)
            elif acao == "atribuir":
                t = _t(n)
                if valor:
                    t.assign_agent(valor)
            elif campo:
                t = _t(n)
                t.set(campo, valor or None)
                t.save()
            else:
                frappe.throw(_("Ação desconhecida."))
            feitos += 1
        except Exception as e:  # noqa: BLE001 — continua com os outros e relata
            falhas.append({"ticket": n, "erro": str(e)[:160]})
    return {"feitos": feitos, "falhas": falhas}


@frappe.whitelist()
def clientes_e_contactos(q: str = ""):
    """Para o «Novo ticket»: contactos com email que batem com o texto."""
    _guarda()
    q = cstr(q).strip()
    if len(q) < 2:
        return []
    out = []
    for c in frappe.get_list("Contact", or_filters=[["full_name", "like", f"%{q}%"], ["email_id", "like", f"%{q}%"]],
                             fields=["name", "full_name", "email_id", "company_name"], limit=10):
        if c.email_id:
            out.append({"nome": c.full_name or c.name, "email": c.email_id, "empresa": c.company_name})
    return out
