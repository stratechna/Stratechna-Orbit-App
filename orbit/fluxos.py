"""Fluxos do Orbit — gatilho → condições → ações, sem código (F1, 23-11-2026). Ver docs/PLANO-FLUXOS-ORBIT.md.

Gatilhos: `criado`, `campo_muda` (campo passa a valor), `sem_atividade` (N dias sem atividade), `data` (N dias depois
de um campo de data; negativo = antes), `email_recebido`. Os de tempo correm de hora a hora (`correr_tempo`).
Ações: `atribuir`, `tarefa`, `aviso`, `email` (modelo), `mudar`. Cada execução fica em `Execucao do Fluxo`; a chave
impede repetir o mesmo fluxo no mesmo registo pelo mesmo motivo.
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime, nowdate

OBJETOS = ("CRM Lead", "CRM Deal", "Contact", "CRM Organization", "HD Ticket")
DONO = {"CRM Lead": "lead_owner", "CRM Deal": "deal_owner", "Contact": "orbit_responsavel", "CRM Organization": "orbit_responsavel"}
EMAIL = {"CRM Lead": "email", "CRM Deal": "email", "Contact": "email_id", "CRM Organization": "email_geral", "HD Ticket": "raised_by"}
NAO_MARKETING = ("Recusou", "Retirou")


def _ha():
    return frappe.db.exists("DocType", "Fluxo")


def _fluxos(objeto: str, gatilho: str) -> list:
    if not _ha():
        return []
    chave = f"orbit:fluxos:{objeto}:{gatilho}"
    c = frappe.cache().get_value(chave)
    if c is None:
        c = frappe.get_all("Fluxo", filters={"ativo": 1, "objeto": objeto, "gatilho": gatilho},
                           fields=["name", "titulo", "campo", "valor", "dias", "condicoes", "acoes"])
        frappe.cache().set_value(chave, c, expires_in_sec=300)
    return [frappe._dict(x) for x in c]


def limpar_cache(doc=None, method=None):
    for o in OBJETOS:
        for g in ("criado", "campo_muda", "sem_atividade", "data", "email_recebido"):
            frappe.cache().delete_value(f"orbit:fluxos:{o}:{g}")


# ── Condições ───────────────────────────────────────────────────────────────────────────────────────────
def _valor(doc, campo):
    if doc.doctype == "Contact" and campo == "marca":
        from orbit.interface.marcas import marcas_do_contacto
        return marcas_do_contacto(doc.name)
    return doc.get(campo)


def _cumpre(doc, cond) -> bool:
    v = _valor(doc, cond.get("campo"))
    op, alvo = cond.get("op") or "igual", str(cond.get("valor") or "")
    lista = [x.strip() for x in alvo.split(",") if x.strip()]
    if isinstance(v, list):   # marcas do contacto
        return {"igual": alvo in v, "diferente": alvo not in v, "vazio": not v, "preenchido": bool(v),
                "em": any(x in v for x in lista), "nao_em": not any(x in v for x in lista)}.get(op, False)
    s = "" if v is None else str(v)
    try:
        if op in ("maior", "menor"):
            return (float(s or 0) > float(alvo or 0)) if op == "maior" else (float(s or 0) < float(alvo or 0))
    except ValueError:
        return False
    return {"igual": s == alvo, "diferente": s != alvo, "contem": alvo.lower() in s.lower(), "vazio": not s,
            "preenchido": bool(s), "em": s in lista, "nao_em": s not in lista}.get(op, False)


def _condicoes_ok(doc, f) -> bool:
    try:
        conds = json.loads(f.condicoes or "[]")
    except ValueError:
        return False
    return all(_cumpre(doc, c) for c in conds if c.get("campo"))


# ── Ações ───────────────────────────────────────────────────────────────────────────────────────────────
def _responsavel(doc):
    campo = DONO.get(doc.doctype)
    if campo and doc.get(campo):
        return doc.get(campo)
    try:
        a = json.loads(doc.get("_assign") or "[]")
        return a[0] if a else None
    except ValueError:
        return None


def _destino(doc, para):
    if not para or para == "responsavel":
        return _responsavel(doc)
    return para


def _atribuir(doc, a, fluxo):
    pessoas = [p for p in (a.get("pessoas") or []) if frappe.db.exists("User", p)]
    if not pessoas:
        return "sem pessoas para atribuir"
    if len(pessoas) > 1:
        k = f"orbit:fluxo:rotacao:{fluxo.name}"
        i = cint(frappe.cache().get_value(k))
        frappe.cache().set_value(k, i + 1)
        quem = pessoas[i % len(pessoas)]
    else:
        quem = pessoas[0]
    campo = DONO.get(doc.doctype)
    if campo and doc.meta.has_field(campo):
        frappe.db.set_value(doc.doctype, doc.name, campo, quem)
    from frappe.desk.form.assign_to import add as atribuir
    try:
        atribuir({"assign_to": [quem], "doctype": doc.doctype, "name": doc.name,
                  "description": f"Fluxo: {fluxo.titulo}"}, ignore_permissions=True)
    except Exception:
        pass   # já estava atribuído
    return f"atribuído a {quem}"


def _tarefa(doc, a, fluxo):
    quem = _destino(doc, a.get("para"))
    titulo = (a.get("titulo") or fluxo.titulo)[:140]
    prazo = add_days(nowdate(), cint(a.get("dias")))
    if doc.doctype in ("CRM Lead", "CRM Deal") and frappe.db.exists("DocType", "CRM Task"):
        t = frappe.get_doc({"doctype": "CRM Task", "title": titulo, "reference_doctype": doc.doctype,
                            "reference_docname": doc.name, "assigned_to": quem, "due_date": prazo,
                            "status": "Todo", "priority": a.get("prioridade") or "Medium",
                            "description": a.get("texto") or f"Criada pelo fluxo «{fluxo.titulo}»."})
    else:
        t = frappe.get_doc({"doctype": "ToDo", "description": titulo, "allocated_to": quem, "date": prazo,
                            "reference_type": doc.doctype, "reference_name": doc.name, "priority": "Medium"})
    t.insert(ignore_permissions=True)
    return f"tarefa «{titulo}» para {quem or 'ninguém'} até {prazo}"


def _aviso(doc, a, fluxo):
    quem = _destino(doc, a.get("para"))
    if not quem:
        return "sem destinatário para o aviso"
    texto = frappe.render_template(a.get("texto") or fluxo.titulo, {"doc": doc})
    frappe.get_doc({"doctype": "Notification Log", "for_user": quem, "subject": texto[:140], "type": "Alert",
                    "document_type": doc.doctype, "document_name": doc.name, "from_user": "Administrator"}).insert(ignore_permissions=True)
    return f"aviso a {quem}"


def _email(doc, a, fluxo):
    para = doc.get(EMAIL.get(doc.doctype) or "") or ""
    if not para or "@" not in para:
        return "sem email no registo"
    if doc.meta.has_field("mkt_estado") and doc.get("mkt_estado") in NAO_MARKETING:
        return "não enviado: pediu para não receber"
    modelo = a.get("modelo")
    if not modelo or not frappe.db.exists("Email Template", modelo):
        return "modelo de email inexistente"
    t = frappe.get_doc("Email Template", modelo)
    ctx = {"doc": doc, **doc.as_dict()}
    frappe.sendmail(recipients=[para], subject=frappe.render_template(t.subject or fluxo.titulo, ctx),
                    message=frappe.render_template(t.response_html or t.response or "", ctx),
                    reference_doctype=doc.doctype, reference_name=doc.name, now=False)
    return f"email «{modelo}» para {para}"


def _mudar(doc, a, fluxo):
    campo = a.get("campo")
    if not campo or not doc.meta.has_field(campo):
        return "campo inexistente"
    d = frappe.get_doc(doc.doctype, doc.name)
    d.set(campo, a.get("valor"))
    d.flags.orbit_fluxo = True
    d.save(ignore_permissions=True)
    return f"{campo} = {a.get('valor')}"


ACOES = {"atribuir": _atribuir, "tarefa": _tarefa, "aviso": _aviso, "email": _email, "mudar": _mudar}


def _executar(doc, f, chave: str):
    if frappe.db.exists("Execucao do Fluxo", {"fluxo": f.name, "chave": chave}):
        return
    if not _condicoes_ok(doc, f):
        return
    feitos, ok = [], True
    try:
        acoes = json.loads(f.acoes or "[]")
    except ValueError:
        acoes = []
    for a in acoes:
        fn = ACOES.get(a.get("tipo"))
        if not fn:
            continue
        try:
            feitos.append(fn(doc, a, f))
        except Exception as e:  # noqa: BLE001
            ok = False
            feitos.append(f"{a.get('tipo')}: erro — {str(e)[:120]}")
            frappe.log_error(title=f"Orbit: fluxo {f.titulo}")
    frappe.get_doc({"doctype": "Execucao do Fluxo", "fluxo": f.name, "ref_doctype": doc.doctype, "ref_name": doc.name,
                    "chave": chave[:140], "ok": 1 if ok else 0, "resultado": "; ".join(feitos)[:1000]}).insert(ignore_permissions=True)


# ── Ganchos ─────────────────────────────────────────────────────────────────────────────────────────────
def ao_criar(doc, method=None):
    if doc.flags.get("orbit_fluxo") or doc.doctype not in OBJETOS:
        return
    for f in _fluxos(doc.doctype, "criado"):
        _executar(doc, f, f"{f.name}:{doc.doctype}:{doc.name}:criado")


def ao_gravar(doc, method=None):
    if doc.flags.get("orbit_fluxo") or doc.doctype not in OBJETOS:
        return
    antes = doc.get_doc_before_save()
    if not antes:
        return
    for f in _fluxos(doc.doctype, "campo_muda"):
        if not f.campo:
            continue
        novo, velho = doc.get(f.campo), antes.get(f.campo)
        if novo == velho or (f.valor and str(novo) != str(f.valor)):
            continue
        _executar(doc, f, f"{f.name}:{doc.doctype}:{doc.name}:{f.campo}={novo}:{doc.modified}")


def email_recebido(doc, method=None):
    if doc.communication_medium != "Email" or doc.sent_or_received != "Received":
        return
    alvos = set()
    if doc.reference_doctype in OBJETOS and doc.reference_name:
        alvos.add((doc.reference_doctype, doc.reference_name))
    for l in doc.get("timeline_links") or []:
        if l.link_doctype in OBJETOS:
            alvos.add((l.link_doctype, l.link_name))
    # um email de um contacto também chega aos negócios abertos dele
    for dt, nome in list(alvos):
        if dt == "Contact":
            for d in frappe.get_all("CRM Contacts", filters={"contact": nome, "parenttype": "CRM Deal"}, pluck="parent"):
                alvos.add(("CRM Deal", d))
    for dt, nome in alvos:
        fl = _fluxos(dt, "email_recebido")
        if not fl or not frappe.db.exists(dt, nome):
            continue
        reg = frappe.get_doc(dt, nome)
        for f in fl:
            _executar(reg, f, f"{f.name}:{dt}:{nome}:email:{doc.name}")


def correr_tempo():
    """De hora a hora: «N dias sem atividade» e «N dias depois/antes de uma data»."""
    if not _ha():
        return
    for f in frappe.get_all("Fluxo", filters={"ativo": 1, "gatilho": ["in", ["sem_atividade", "data"]]},
                            fields=["name", "titulo", "objeto", "gatilho", "campo", "valor", "dias", "condicoes", "acoes"]):
        f = frappe._dict(f)
        meta = frappe.get_meta(f.objeto)
        try:
            if f.gatilho == "sem_atividade":
                campo = "orbit_ultima_atividade" if meta.has_field("orbit_ultima_atividade") else "modified"
                # só os que cruzam o limite nas últimas 24 h — ligar um fluxo não dispara para todos os registos antigos
                limite = add_days(now_datetime(), -cint(f.dias))
                nomes = frappe.get_all(f.objeto, filters=[[campo, "<", limite], [campo, ">=", add_days(limite, -1)]],
                                       fields=["name", campo], limit=500, order_by=f"{campo} desc")
                for r in nomes:
                    reg = frappe.get_doc(f.objeto, r.name)
                    _executar(reg, f, f"{f.name}:{f.objeto}:{r.name}:sem:{r.get(campo)}")
            else:
                campo = f.campo or "creation"
                if not (meta.has_field(campo) or campo in ("creation", "modified")):
                    continue
                alvo = getdate(add_days(nowdate(), -cint(f.dias)))
                nomes = frappe.get_all(f.objeto, filters={campo: ["between", [str(alvo) + " 00:00:00", str(alvo) + " 23:59:59"]]},
                                       pluck="name", limit=500)
                for n in nomes:
                    reg = frappe.get_doc(f.objeto, n)
                    _executar(reg, f, f"{f.name}:{f.objeto}:{n}:data:{alvo}")
            frappe.db.commit()
        except Exception:  # noqa: BLE001
            frappe.db.rollback()
            frappe.log_error(title=f"Orbit: fluxo de tempo {f.titulo}")


# ── Modelos (desligados à partida) ──────────────────────────────────────────────────────────────────────
MODELOS = [
    {"modelo": "lead-nova", "titulo": "Lead nova — responsável e tarefa", "objeto": "CRM Lead", "gatilho": "criado",
     "descricao": "Atribui a lead por rotação e cria a tarefa «Contactar em 24 h».",
     "acoes": [{"tipo": "atribuir", "pessoas": []}, {"tipo": "tarefa", "titulo": "Contactar a lead", "dias": 1, "para": "responsavel"}]},
    {"modelo": "lead-boas-vindas", "titulo": "Lead nova — email de boas-vindas", "objeto": "CRM Lead", "gatilho": "criado",
     "descricao": "Envia o email de modelo de boas-vindas (escolha o modelo e, se quiser, a marca).",
     "acoes": [{"tipo": "email", "modelo": ""}]},
    {"modelo": "lead-2-dias", "titulo": "Lead sem atividade há 2 dias — aviso", "objeto": "CRM Lead", "gatilho": "sem_atividade", "dias": 2,
     "descricao": "Avisa o responsável de uma lead em aberto sem atividade há 2 dias.",
     "condicoes": [{"campo": "status", "op": "nao_em", "valor": "Converted,Junk,Unqualified"}],
     "acoes": [{"tipo": "aviso", "para": "responsavel", "texto": "Lead sem atividade há 2 dias: {{ doc.lead_name or doc.name }}"}]},
    {"modelo": "lead-7-dias", "titulo": "Lead sem atividade há 7 dias — em acompanhamento", "objeto": "CRM Lead", "gatilho": "sem_atividade", "dias": 7,
     "descricao": "Passa a lead a «Em acompanhamento» (Nurture).",
     "condicoes": [{"campo": "status", "op": "em", "valor": "New,Contacted"}],
     "acoes": [{"tipo": "mudar", "campo": "status", "valor": "Nurture"}]},
    {"modelo": "negocio-proposta", "titulo": "Negócio em «Proposta» — seguimento a 3 dias", "objeto": "CRM Deal", "gatilho": "campo_muda",
     "campo": "status", "valor": "Proposal/Quotation", "descricao": "Cria a tarefa de seguimento da proposta para daqui a 3 dias.",
     "acoes": [{"tipo": "tarefa", "titulo": "Seguimento da proposta", "dias": 3, "para": "responsavel"}]},
    {"modelo": "negocio-parado", "titulo": "Negócio parado há 14 dias — aviso e tarefa", "objeto": "CRM Deal", "gatilho": "sem_atividade", "dias": 14,
     "descricao": "Avisa o responsável e cria uma tarefa num negócio em aberto sem atividade há 14 dias.",
     "condicoes": [{"campo": "status", "op": "nao_em", "valor": "Won,Lost"}],
     "acoes": [{"tipo": "aviso", "para": "responsavel", "texto": "Negócio parado há 14 dias: {{ doc.titulo or doc.name }}"},
               {"tipo": "tarefa", "titulo": "Retomar o negócio parado", "dias": 1, "para": "responsavel"}]},
    {"modelo": "negocio-ganho", "titulo": "Negócio ganho — arranque com o cliente", "objeto": "CRM Deal", "gatilho": "campo_muda",
     "campo": "status", "valor": "Won", "descricao": "Cria a tarefa de arranque (a fase «Cliente» já é posta pelo ciclo de vida).",
     "acoes": [{"tipo": "tarefa", "titulo": "Arranque com o cliente", "dias": 2, "para": "responsavel"}]},
    {"modelo": "negocio-perdido", "titulo": "Negócio perdido — voltar a contactar aos 90 dias", "objeto": "CRM Deal", "gatilho": "campo_muda",
     "campo": "status", "valor": "Lost", "descricao": "Cria a tarefa de voltar a contactar daqui a 90 dias.",
     "acoes": [{"tipo": "tarefa", "titulo": "Voltar a contactar (negócio perdido há 90 dias)", "dias": 90, "para": "responsavel"}]},
    {"modelo": "ticket-sem-resposta", "titulo": "Ticket aberto há 1 dia sem resposta — aviso", "objeto": "HD Ticket", "gatilho": "data",
     "campo": "creation", "dias": 1, "descricao": "Avisa o responsável (ou quem escolher) de um ticket com 1 dia sem 1.ª resposta.",
     "condicoes": [{"campo": "first_responded_on", "op": "vazio"}, {"campo": "status", "op": "em", "valor": "Open,Replied"}],
     "acoes": [{"tipo": "aviso", "para": "responsavel", "texto": "Ticket sem resposta há 1 dia: {{ doc.subject }}"}]},
    {"modelo": "email-negocio-aberto", "titulo": "Email de cliente com negócio aberto — aviso", "objeto": "CRM Deal", "gatilho": "email_recebido",
     "descricao": "Avisa o responsável do negócio quando o cliente escreve.",
     "condicoes": [{"campo": "status", "op": "nao_em", "valor": "Won,Lost"}],
     "acoes": [{"tipo": "aviso", "para": "responsavel", "texto": "O cliente escreveu: {{ doc.titulo or doc.name }}"}]},
]


def instalar():
    """after_migrate: os modelos que faltam, desligados (nunca se mexe num que já exista)."""
    if not _ha():
        return
    for m in MODELOS:
        if frappe.db.exists("DocType", m["objeto"]) is None or frappe.db.exists("Fluxo", {"modelo": m["modelo"]}):
            continue
        frappe.get_doc({"doctype": "Fluxo", "ativo": 0, "modelo": m["modelo"], "titulo": m["titulo"], "objeto": m["objeto"],
                        "gatilho": m["gatilho"], "campo": m.get("campo"), "valor": m.get("valor"), "dias": m.get("dias") or 0,
                        "descricao": m.get("descricao"), "condicoes": json.dumps(m.get("condicoes") or [], ensure_ascii=False),
                        "acoes": json.dumps(m.get("acoes") or [], ensure_ascii=False)}).insert(ignore_permissions=True)
