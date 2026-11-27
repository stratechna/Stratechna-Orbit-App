# Actividades do CRM na interface nova (/orbit) — lote 2 do plano das opções dos originais (25-11-2026)
#
# docs/PLANO-ORBIT-OPCOES-DOS-ORIGINAIS.md §3, lote 2: tarefas completas (responsável, prioridade, estado,
# descrição, hora; abrir, editar, apagar), notas com título e formatação (editar, apagar, fixar), chamadas
# registadas à mão, email com Bcc, anexos, agendamento e resposta no registo, e o motivo de perda obrigatório.
# Sempre com as permissões de quem está a usar (o CRM confirma-as por dentro).
import json

import frappe
from frappe import _
from frappe.utils import cint, cstr, get_datetime, now_datetime, strip_html

from orbit.interface.api import _guarda

FICHAS = ("CRM Lead", "CRM Deal", "Contact", "CRM Organization")
ESTADOS_TAREFA = ["Backlog", "Todo", "In Progress", "Done", "Canceled"]
PRIORIDADES = ["Low", "Medium", "High"]


def _ler(doctype, name):
    if doctype not in FICHAS:
        frappe.throw(_("Ficha não suportada."))
    frappe.get_doc(doctype, name).check_permission("read")


def _nome(u):
    return (frappe.db.get_value("User", u, "full_name") or u) if u else ""


# ── tarefas ──────────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def tarefa_obter(id: str):
    _guarda()
    t = frappe.get_doc("CRM Task", id)
    t.check_permission("read")
    return {"id": t.name, "titulo": t.title, "descricao": t.description or "", "estado": t.status, "prioridade": t.priority,
            "data": str(t.due_date or ""), "inicio": str(t.get("start_date") or ""), "responsavel": t.assigned_to or "",
            "responsavel_nome": _nome(t.assigned_to), "doctype": t.reference_doctype, "name": t.reference_docname,
            "pode_escrever": frappe.has_permission("CRM Task", "write", t.name),
            "pode_apagar": frappe.has_permission("CRM Task", "delete", t.name)}


@frappe.whitelist(methods=["POST"])
def tarefa_gravar(dados: str):
    """Cria ou altera uma tarefa do CRM com todos os campos do ecrã original."""
    _guarda()
    d = json.loads(dados or "{}")
    if not cstr(d.get("titulo")).strip():
        frappe.throw(_("A tarefa precisa de um título."))
    if d.get("estado") and d["estado"] not in ESTADOS_TAREFA:
        frappe.throw(_("Estado inválido."))
    if d.get("prioridade") and d["prioridade"] not in PRIORIDADES:
        frappe.throw(_("Prioridade inválida."))
    if d.get("id"):
        t = frappe.get_doc("CRM Task", d["id"])
        t.check_permission("write")
    else:
        if d.get("doctype"):
            _ler(d["doctype"], d.get("name"))
        t = frappe.get_doc({"doctype": "CRM Task", "reference_doctype": d.get("doctype") or None,
                            "reference_docname": d.get("name") or None})
    t.title = cstr(d["titulo"]).strip()[:140]
    t.description = d.get("descricao") or ""
    t.status = d.get("estado") or t.status or "Todo"
    t.priority = d.get("prioridade") or t.priority or "Medium"
    t.due_date = d.get("data") or None
    if "inicio" in d and t.meta.has_field("start_date"):
        t.start_date = d.get("inicio") or None
    t.assigned_to = d.get("responsavel") or t.assigned_to or frappe.session.user
    t.save() if not t.is_new() else t.insert()
    return tarefa_obter(t.name)


@frappe.whitelist(methods=["POST"])
def tarefa_apagar(id: str):
    _guarda()
    frappe.delete_doc("CRM Task", id)   # o Frappe confirma a permissão de apagar
    return {"ok": 1}


# ── notas ────────────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def nota_obter(id: str):
    _guarda()
    n = frappe.get_doc("FCRM Note", id)
    n.check_permission("read")
    return {"id": n.name, "titulo": n.title or "", "html": n.content or "", "fixada": cint(n.get("pinned")),
            "pode_escrever": frappe.has_permission("FCRM Note", "write", n.name),
            "pode_apagar": frappe.has_permission("FCRM Note", "delete", n.name)}


@frappe.whitelist(methods=["POST"])
def nota_gravar(dados: str):
    _guarda()
    d = json.loads(dados or "{}")
    html = d.get("html") or ""
    if not strip_html(html).strip() and not cstr(d.get("titulo")).strip():
        frappe.throw(_("A nota está vazia."))
    if d.get("id"):
        n = frappe.get_doc("FCRM Note", d["id"])
        n.check_permission("write")
    else:
        _ler(d.get("doctype"), d.get("name"))
        n = frappe.get_doc({"doctype": "FCRM Note", "reference_doctype": d["doctype"], "reference_docname": d["name"]})
    n.title = cstr(d.get("titulo")).strip()[:140] or strip_html(html).strip()[:60] or _("Nota")
    n.content = html
    n.save() if not n.is_new() else n.insert()
    return nota_obter(n.name)


@frappe.whitelist(methods=["POST"])
def nota_fixar(id: str, fixar: int = 1):
    _guarda()
    n = frappe.get_doc("FCRM Note", id)
    n.check_permission("write")
    if n.meta.has_field("pinned"):
        n.pinned = cint(fixar)
        if n.meta.has_field("pinned_by"):
            n.pinned_by = frappe.session.user if cint(fixar) else None
        if n.meta.has_field("pinned_on"):
            n.pinned_on = now_datetime() if cint(fixar) else None
        n.save()
    return nota_obter(n.name)


@frappe.whitelist(methods=["POST"])
def nota_apagar(id: str):
    _guarda()
    frappe.delete_doc("FCRM Note", id)
    return {"ok": 1}


@frappe.whitelist()
def fixadas(doctype: str, name: str):
    """As notas fixadas no topo da ficha (como no CRM original)."""
    _guarda()
    _ler(doctype, name)
    if not frappe.get_meta("FCRM Note").has_field("pinned"):
        return []
    return [{"id": n.name, "titulo": n.title, "html": n.content, "quem": _nome(n.owner), "quando": str(n.creation)}
            for n in frappe.get_list("FCRM Note", filters={"reference_doctype": doctype, "reference_docname": name, "pinned": 1},
                                     fields=["name", "title", "content", "owner", "creation"], order_by="modified desc", limit=10)]


# ── chamadas registadas à mão ────────────────────────────────────────────────────────────────────────
def _meu(u):
    return frappe.db.get_value("User", u, "mobile_no") or frappe.db.get_value("User", u, "phone") or None


ESTADOS_CHAMADA = {"Completed": "Atendida", "No Answer": "Não atendida", "Busy": "Ocupado", "Failed": "Falhou", "Canceled": "Cancelada"}


@frappe.whitelist(methods=["POST"])
def chamada_registar(doctype: str, name: str, sentido: str = "Outgoing", estado: str = "Completed", inicio: str = None,
                     duracao_min: float = 0, numero: str = None, nota: str = None):
    """«Registar chamada» do CRM original: uma chamada feita ou recebida fora do Orbit, com a nota."""
    _guarda()
    _ler(doctype, name)
    if sentido not in ("Outgoing", "Incoming") or estado not in ESTADOS_CHAMADA:
        frappe.throw(_("Dados da chamada inválidos."))
    eu = frappe.session.user
    c = frappe.get_doc({"doctype": "CRM Call Log", "id": "orbit-man-" + frappe.generate_hash(length=10), "type": sentido,
                        "status": estado, "telephony_medium": "Manual", "start_time": get_datetime(inicio) if inicio else now_datetime(),
                        "duration": int(float(duracao_min or 0) * 60) if estado == "Completed" else 0,
                        "caller": eu if sentido == "Outgoing" else None, "receiver": eu if sentido == "Incoming" else None,
                        # «De» e «Para» são obrigatórios no CRM Call Log: o meu telemóvel (ou «Orbit») e o número do outro lado
                        "from": (numero or None) if sentido == "Incoming" else _meu(eu), "to": (numero or None) if sentido == "Outgoing" else _meu(eu),
                        "reference_doctype": doctype, "reference_docname": name})
    if c.meta.has_field("links"):
        c.append("links", {"link_doctype": doctype, "link_name": name})
    c.flags.ignore_mandatory = True   # registada à mão: pode não se saber o número de um dos lados
    c.insert()
    if cstr(nota).strip():
        n = frappe.get_doc({"doctype": "FCRM Note", "title": _("Nota da chamada"),
                            "content": "<p>" + frappe.utils.escape_html(nota).replace("\n", "<br>") + "</p>",
                            "reference_doctype": doctype, "reference_docname": name}).insert()
        c.db_set("note", n.name)
    return {"ok": 1, "id": c.name}


# ── motivo de perda ──────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def motivos_perda():
    """Os motivos de perda e quais as fases/estados que são «perdido» (para o ecrã pedir o motivo antes de gravar)."""
    _guarda()
    motivos = frappe.get_all("CRM Lost Reason", pluck="name", order_by="name asc") if frappe.db.exists("DocType", "CRM Lost Reason") else []
    return {"motivos": [{"v": m, "r": _(m)} for m in motivos],
            "negocio": frappe.get_all("CRM Deal Status", filters={"type": "Lost"}, pluck="name"),
            "lead": frappe.get_all("CRM Lead Status", filters={"type": "Lost"}, pluck="name") if frappe.get_meta("CRM Lead Status").has_field("type") else []}


def e_perdido(doctype, estado):
    st = "CRM Deal Status" if doctype == "CRM Deal" else "CRM Lead Status"
    return bool(estado and frappe.db.exists(st, estado) and frappe.db.get_value(st, estado, "type") == "Lost")


@frappe.whitelist(methods=["POST"])
def marcar_estado(doctype: str, name: str, estado: str, motivo: str = None, notas: str = None):
    """Muda a fase/estado; se for uma fase de perda, exige o motivo (como o CRM original)."""
    _guarda()
    if doctype not in ("CRM Deal", "CRM Lead"):
        frappe.throw(_("Só negócios e leads."))
    d = frappe.get_doc(doctype, name)
    d.check_permission("write")
    if e_perdido(doctype, estado):
        if not motivo:
            frappe.throw(_("Indique o motivo de perda."))
        if motivo in ("Other", "Outro") and not cstr(notas).strip():
            frappe.throw(_("Com «Outro», escreva o motivo."))
        d.lost_reason = motivo
        d.lost_notes = notas or ""
    d.status = estado
    d.save()
    return {"ok": 1}


# ── email: Bcc, anexos, agendar e responder no registo ───────────────────────────────────────────────
@frappe.whitelist(methods=["POST"])
def email_enviar(doctype: str, name: str, conta: str, para: str, assunto: str, html: str, cc: str = None, bcc: str = None,
                 anexos: str = None, agendar: str = None, responder_a: str = None):
    _guarda()
    from frappe.core.doctype.communication.email import make
    from orbit.emails_crm import filtrar, pode_responder, preparar_saida
    _ler(doctype, name)
    if not pode_responder(conta):
        frappe.throw(_("Não pode escrever a partir desta caixa."), frappe.PermissionError)
    if not strip_html(html or "").strip() or not cstr(assunto).strip():
        frappe.throw(_("Falta o assunto ou o texto."))
    quando = get_datetime(agendar) if agendar else None
    if quando and quando <= now_datetime():
        quando = None
    acc = preparar_saida(conta)
    origem = None
    if responder_a:
        c0 = frappe.get_doc("Communication", responder_a)
        c0.check_permission("read")
        origem = c0.message_id or c0.name
    r = make(doctype=doctype, name=name, content=html, subject=cstr(assunto).strip()[:200], sender=acc.email_id,
             sender_full_name=frappe.db.get_value("User", frappe.session.user, "full_name"), recipients=para, cc=cc or None,
             bcc=bcc or None, send_email=True, communication_medium="Email", attachments=json.loads(anexos) if anexos else None,
             send_after=quando, in_reply_to=responder_a or None, now=not quando)
    nome = (r or {}).get("name")
    if nome:
        if not frappe.db.get_value("Communication", nome, "email_account"):
            frappe.db.set_value("Communication", nome, "email_account", acc.name, update_modified=False)
        filtrar(frappe.get_doc("Communication", nome))
    return {"ok": 1, "id": nome, "agendado": str(quando) if quando else None, "em_resposta_a": origem}


@frappe.whitelist()
def agendados(doctype: str, name: str):
    """Emails agendados deste registo ainda por enviar (para «Enviar já» ou «Cancelar»)."""
    _guarda()
    _ler(doctype, name)
    out = []
    for q in frappe.get_all("Email Queue", filters={"reference_doctype": doctype, "reference_name": name, "status": "Not Sent",
                                                   "send_after": [">", now_datetime()]},
                            fields=["name", "send_after", "communication"], order_by="send_after asc"):
        assunto = frappe.db.get_value("Communication", q.communication, "subject") if q.communication else ""
        out.append({"id": q.name, "quando": str(q.send_after), "assunto": assunto or ""})
    return out


@frappe.whitelist(methods=["POST"])
def agendado_acao(id: str, acao: str):
    _guarda()
    q = frappe.get_doc("Email Queue", id)
    if q.reference_doctype:
        _ler(q.reference_doctype, q.reference_name)
    if q.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw(_("Só quem agendou o pode alterar."), frappe.PermissionError)
    if acao == "enviar":
        q.db_set("send_after", now_datetime())
        frappe.enqueue("frappe.email.queue.flush", queue="short")
    elif acao == "cancelar":
        q.db_set("status", "Cancelled")
        if q.communication:
            frappe.db.set_value("Communication", q.communication, "delivery_status", "Cancelled")
    else:
        frappe.throw(_("Ação desconhecida."))
    return {"ok": 1}


# ── criar a partir do contexto ───────────────────────────────────────────────────────────────────────
@frappe.whitelist(methods=["POST"])
def novo_negocio(doctype: str, name: str, titulo: str = None, valor: float = None):
    """«Novo negócio» numa empresa ou num contacto: nasce já ligado."""
    _guarda()
    _ler(doctype, name)
    from orbit import funis as F
    d = frappe.get_doc({"doctype": "CRM Deal", "status": F.primeira() or "Qualification", "orbit_funil": F.omissao(),
                        "deal_owner": frappe.session.user})
    if doctype == "CRM Organization":
        d.organization = name
    elif doctype == "Contact":
        org = frappe.db.get_value("Contact", name, "company_name")
        if org and frappe.db.exists("CRM Organization", org):
            d.organization = org
        d.append("contacts", {"contact": name, "is_primary": 1})
    if titulo and d.meta.has_field("titulo"):
        d.titulo = cstr(titulo)[:140]
    if valor and d.meta.has_field("deal_value"):
        d.deal_value = float(valor)
    d.insert()
    return {"name": d.name}


@frappe.whitelist(methods=["POST"])
def novo_contacto(negocio: str, nome: str, apelido: str = None, email: str = None, telemovel: str = None):
    """«Novo contacto» dentro do negócio: cria o contacto e associa-o."""
    _guarda()
    d = frappe.get_doc("CRM Deal", negocio)
    d.check_permission("write")
    c = frappe.get_doc({"doctype": "Contact", "first_name": cstr(nome).strip(), "last_name": cstr(apelido).strip() or None})
    if email:
        c.append("email_ids", {"email_id": email.strip(), "is_primary": 1})
    if telemovel:
        c.append("phone_nos", {"phone": telemovel.strip(), "is_primary_mobile_no": 1})
    if d.organization:
        c.company_name = d.organization
    c.insert()
    d.append("contacts", {"contact": c.name, "is_primary": 0 if d.contacts else 1})
    d.save()
    return {"name": c.name}


# ── fotografia / logótipo ────────────────────────────────────────────────────────────────────────────
CAMPO_IMAGEM = {"CRM Lead": "image", "Contact": "image", "CRM Organization": "organization_logo", "CRM Deal": None}


@frappe.whitelist(methods=["POST"])
def imagem(doctype: str, name: str, url: str = None):
    _guarda()
    campo = CAMPO_IMAGEM.get(doctype)
    if not campo:
        frappe.throw(_("Este registo não tem imagem."))
    d = frappe.get_doc(doctype, name)
    d.check_permission("write")
    d.set(campo, url or None)
    d.save()
    return {"ok": 1, "url": url}
