"""A interface única do Orbit (20-11-2026; docs/PLANO-ORBIT-INTERFACE-UNICA.md na área de trabalho).

Tudo passa por aqui e só por documentos do Frappe CRM, do Helpdesk e do Frappe — nenhum ficheiro dessas apps é
alterado e nenhum código delas é copiado (CRM/Helpdesk são AGPL; isto fala com eles só pela API). As leituras usam
`frappe.get_list` (permissões da pessoa e o «só para mim» de orbit.emails_crm) e as escritas `doc.save()` sem
`ignore_permissions`. Se uma actualização do CRM mudar um campo, o erro aparece aqui e não nos dados.

Ligada por tenant: `orbit_interface_nova: 1` no site_config (só a Stratechna para já, decisão do Vítor a 20-11).
"""
from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, now_datetime, nowdate, strip_html

FECHADOS = ("Won", "Lost")


def ligada() -> bool:
    return bool(cint(frappe.conf.get("orbit_interface_nova")))


def _guarda():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    if not ligada():
        frappe.throw("A interface nova não está ligada neste Orbit.", frappe.PermissionError)


def _texto(html, n=280):
    import html as _h
    # algumas descrições (tickets vindos do Zoho) têm o HTML escapado («&lt;div…»): desfazer antes e depois
    t = strip_html(_h.unescape(strip_html(_h.unescape(html or ""))))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n] + ("…" if len(t) > n else "")


def _iniciais(nome):
    p = [x for x in re.split(r"\s+", (nome or "").strip()) if x]
    return ((p[0][0] if p else "?") + (p[-1][0] if len(p) > 1 else "")).upper()


def _nome_user(u, _cache={}):
    if not u:
        return ""
    if u not in _cache:
        _cache[u] = frappe.db.get_value("User", u, "full_name") or u
    return _cache[u]


_PT = {"Qualification": "Qualificação", "Demo/Making": "Demonstração", "Proposal/Quotation": "Proposta",
       "Negotiation": "Negociação", "Ready to Close": "Pronto a fechar", "Won": "Ganho", "Lost": "Perdido",
       "New": "Nova", "Contacted": "Contactada", "Nurture": "Em acompanhamento", "Qualified": "Qualificada",
       "Unqualified": "Não qualificada", "Junk": "Descartada", "Open": "Aberto", "Replied": "Respondido",
       "Paused": "Em pausa", "Resolved": "Resolvido", "Closed": "Fechado"}


def _rotulo_estado(s):
    if not s:
        return ""
    t = _(s)
    if t == s and (frappe.local.lang or "pt").startswith("pt"):
        return _PT.get(s, s)
    return t


# ── Contexto e pesquisa ─────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def contexto():
    _guarda()
    u = frappe.session.user
    nome = _nome_user(u)
    abertos = frappe.get_list("HD Ticket", filters={"status_category": ["!=", "Resolved"]}, pluck="name", limit=500) \
        if frappe.db.exists("DocType", "HD Ticket") else []
    return {
        "utilizador": u, "nome": nome, "iniciais": _iniciais(nome),
        "tenant": frappe.db.get_single_value("Website Settings", "app_name") or frappe.local.site,
        "contadores": {"tickets": len(abertos)},
        "apps": _apps(),
        "classico": {"crm": "/crm", "desk": "/helpdesk"},
        "modulos": _modulos(),
        "admin": "System Manager" in frappe.get_roles(),
    }


# Módulos do ERP e do RH (Frappe 16: «Desktop Icon» do tipo Workspace Sidebar → /desk/<espaço>), com nome em português.
_GESTAO = [("Accounting", "Contabilidade"), ("Invoicing", "Faturação"), ("Payments", "Pagamentos"), ("Banking", "Banca"),
           ("Financial Reports", "Relatórios financeiros"), ("Selling", "Vendas"), ("Buying", "Compras"), ("Stock", "Inventário"),
           ("Assets", "Ativos"), ("Projects", "Projetos (ERP)"), ("Quality", "Qualidade"), ("Manufacturing", "Produção"),
           ("Subcontracting", "Subcontratação"), ("Subscription", "Subscrições")]
# 22-11-2026: módulos de sistema para a app «Administração» (o Orbit passa a uma app por área).
_SISTEMA = [("ERPNext Settings", "Definições do ERP"), ("Users", "Utilizadores e permissões"), ("Website", "Site"),
            ("Integrations", "Integrações"), ("Automation", "Automação"), ("Data", "Dados e importação"),
            ("Email", "Email de envio"), ("Printing", "Impressão e PDF"), ("System", "Sistema")]
_RH = [("Frappe HR", "Pessoas"), ("Recruitment", "Recrutamento"), ("Leaves", "Férias e ausências"),
       ("Shift & Attendance", "Turnos e presenças"), ("Payroll", "Salários"), ("Expenses", "Despesas"),
       ("Performance", "Desempenho"), ("Tenure", "Ciclo do colaborador"), ("Tax & Benefits", "Impostos e benefícios")]


def _modulos():
    """Os módulos do ERP e do RH a que a pessoa tem acesso (ícones da secretária visíveis e com os papéis dela)."""
    if not frappe.db.exists("DocType", "Desktop Icon"):
        return []
    papeis = set(frappe.get_roles())
    icones = {d.name: d for d in frappe.get_all("Desktop Icon", filters={"hidden": 0},
                                                 fields=["name", "link_type", "link_to", "link"])}
    restritos = {}
    for r in frappe.get_all("Has Role", filters={"parenttype": "Desktop Icon"}, fields=["parent", "role"]):
        restritos.setdefault(r.parent, set()).add(r.role)
    out = []
    for grupo, lista in (("Gestão", _GESTAO), ("Recursos Humanos", _RH), ("Sistema", _SISTEMA)):
        for nome, pt in lista:
            d = icones.get(nome)
            if not d or (restritos.get(nome) and not (restritos[nome] & papeis)):
                continue
            # 22-11-2026: um módulo de barra lateral sem barra que exista (ex.: «Accounting», com link vazio) não abria
            # nada na interface — «Módulo desconhecido». Fica de fora.
            if d.link_type == "Workspace Sidebar" and not frappe.db.exists("Workspace Sidebar", d.link_to or nome):
                continue
            if d.link_type == "External" and d.link:
                url = d.link
            else:
                url = "/desk/" + (d.link_to or nome).lower().replace(" & ", "-").replace(" ", "-")
            # 21-11 (U1): a barra lateral do módulo no Frappe 16 — a interface desenha o menu a partir dela
            out.append({"nome": pt, "url": url, "grupo": grupo, "chave": nome,
                        "barra": (d.link_to or nome) if d.link_type == "Workspace Sidebar" else None})
    return out


def _apps():
    """As mesmas apps e endereços da grelha do Orbit (orbit/marca.py ATALHOS), sem repetir a regra dos endereços."""
    from orbit import marca
    try:
        valores = {"mail": marca._mail_do_tenant(), "docs": marca._docs_do_tenant(), "chat": marca._chat_do_tenant(),
                   "dominio": marca._dominio_do_tenant()}
    except Exception:  # noqa: BLE001
        return []
    icones = {"Mail": "mail", "Meet": "video", "Chat": "chat", "Docs": "livro", "Sign": "nota", "Booking": "cal",
              "Marketing": "negocio", "Propostas": "nota"}
    out = []
    for a in sorted(marca.ATALHOS, key=lambda x: x["ordem"]):
        if a.get("precisa") and not frappe.db.exists("DocType", a["precisa"]):
            continue
        try:
            url = a["url"].format(**valores)
        except (KeyError, IndexError):
            continue
        out.append({"nome": a["nome"], "url": url, "icone": icones.get(a["nome"], "grelha")})
    out.append({"nome": "Secretária", "url": "/app", "icone": "grelha"})
    return out


@frappe.whitelist()
def pesquisa(q: str):
    _guarda()
    q = (q or "").strip()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    out = []

    def junta(dt, campos, ou, titulo, sub, tipo):
        if not frappe.has_permission(dt, "read"):
            return
        for r in frappe.get_list(dt, fields=["name"] + campos, or_filters=[[c, "like", like] for c in ou], limit=5):
            out.append({"doctype": dt, "name": r.name, "titulo": titulo(r) or r.name, "sub": sub(r), "tipo": tipo})

    junta("Contact", ["full_name", "email_id", "company_name"], ["full_name", "email_id", "company_name", "mobile_no"],
          lambda r: r.full_name, lambda r: r.email_id or r.company_name or "", "Contacto")
    junta("CRM Organization", ["organization_name", "website"], ["organization_name", "website", "nipc"],
          lambda r: r.organization_name, lambda r: r.website or "", "Empresa")
    junta("CRM Deal", ["titulo", "organization", "lead_name", "status"], ["name", "titulo", "organization", "lead_name", "email"],
          lambda r: r.titulo or r.lead_name or r.organization, lambda r: f"{r.organization or ''} · {_rotulo_estado(r.status)}", "Negócio")
    junta("CRM Lead", ["lead_name", "email", "organization"], ["lead_name", "email", "organization"],
          lambda r: r.lead_name, lambda r: r.email or r.organization or "", "Lead")
    if frappe.db.exists("DocType", "HD Ticket"):
        junta("HD Ticket", ["subject", "raised_by"], ["subject", "raised_by", "name"],
              lambda r: f"#{r.name} {r.subject}", lambda r: r.raised_by or "", "Ticket")
    return out


# ── Início ──────────────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def inicio():
    _guarda()
    u = frappe.session.user
    hoje = getdate(nowdate())
    tarefas = frappe.get_list("CRM Task", filters={"assigned_to": u, "status": ["not in", ["Done", "Canceled"]]},
                              fields=["name", "title", "status", "priority", "due_date", "reference_doctype", "reference_docname"],
                              order_by="due_date asc", limit=12)
    for t in tarefas:
        t.atrasada = bool(t.due_date and getdate(t.due_date) < hoje)
        t.hoje = bool(t.due_date and getdate(t.due_date) == hoje)
        t.titulo_ref = _titulo(t.reference_doctype, t.reference_docname) if t.reference_docname else ""
    eventos = frappe.get_list("Event", filters={"starts_on": ["between", [f"{hoje} 00:00:00", f"{add_days(hoje, 1)} 23:59:59"]]},
                              fields=["name", "subject", "starts_on", "ends_on", "location", "reference_doctype",
                                      "reference_docname", "google_meet_link"], order_by="starts_on asc", limit=10)
    abertos = frappe.get_list("CRM Deal", filters={"status": ["not in", FECHADOS]}, fields=["name", "deal_value", "modified",
                              "titulo", "organization", "status", "lead_name"], limit=1000)
    ganhos = frappe.get_list("CRM Deal", filters={"status": "Won", "closed_date": ["between", [get_first_day(hoje), get_last_day(hoje)]]},
                             fields=["deal_value"], limit=1000)
    limite = add_days(now_datetime(), -14)
    parados = sorted([d for d in abertos if d.modified < limite], key=lambda d: d.modified)[:6]
    tickets = frappe.get_list("HD Ticket", filters={"status_category": ["!=", "Resolved"]}, fields=["name", "subject", "raised_by",
                              "modified", "status"], order_by="modified desc", limit=6) if frappe.db.exists("DocType", "HD Ticket") else []
    return {
        "tarefas": tarefas, "eventos": eventos, "tickets": tickets,
        "parados": [{"name": d.name, "titulo": d.titulo or d.lead_name or d.organization or d.name, "org": d.organization,
                     "estado": _rotulo_estado(d.status), "valor": flt(d.deal_value),
                     "dias": (now_datetime() - d.modified).days} for d in parados],
        "kpis": {"abertos": len(abertos), "abertos_valor": sum(flt(d.deal_value) for d in abertos),
                 "ganhos_valor": sum(flt(d.deal_value) for d in ganhos), "ganhos": len(ganhos),
                 "tarefas_atrasadas": sum(1 for t in tarefas if t.atrasada), "tickets": len(tickets)},
    }


# ── Listas ──────────────────────────────────────────────────────────────────────────────────────────────
_LISTAS = {
    "contactos": {"dt": "Contact", "campos": ["full_name", "email_id", "mobile_no", "company_name", "modified", "owner", "image",
                                               "orbit_responsavel", "orbit_ciclo", "orbit_ultima_atividade"],
                  "pesquisa": ["full_name", "email_id", "company_name", "mobile_no"], "dono": "orbit_responsavel"},
    "empresas": {"dt": "CRM Organization", "campos": ["organization_name", "website", "industry", "territory", "telefone",
                                                       "estado_conta", "modified", "organization_logo", "orbit_responsavel", "orbit_ciclo",
                                                       "orbit_ultima_atividade"],
                 "pesquisa": ["organization_name", "website", "nipc"], "dono": "orbit_responsavel"},
    "negocios": {"dt": "CRM Deal", "campos": ["titulo", "organization", "lead_name", "status", "deal_value", "currency",
                                               "expected_closure_date", "deal_owner", "modified", "email", "orbit_ultima_atividade"],
                 "pesquisa": ["titulo", "organization", "lead_name", "email", "name"], "dono": "deal_owner"},
    "leads": {"dt": "CRM Lead", "campos": ["lead_name", "email", "mobile_no", "organization", "status", "source",
                                            "lead_owner", "modified", "orbit_ultima_atividade"],
              "pesquisa": ["lead_name", "email", "organization"], "dono": "lead_owner",
              "base": {"converted": 0}},
}


@frappe.whitelist()
def lista(objeto: str, vista: str = "todos", q: str = "", pagina: int = 0, ordem: str = "modified desc", estado: str = "",
          filtros: str = "", colunas: str = "", marca: str = ""):
    _guarda()
    filtros_json = filtros
    cfg = _LISTAS.get(objeto)
    if not cfg:
        frappe.throw("Lista desconhecida")
    meta = frappe.get_meta(cfg["dt"])
    cfg = {**cfg, "campos": [c for c in cfg["campos"] if meta.has_field(c) or c in ("modified", "owner", "creation")]}
    if not meta.has_field(cfg["dono"]) and cfg["dono"] not in ("owner",):
        cfg["dono"] = "owner"
    filtros = dict(cfg.get("base") or {})
    if vista == "meus":
        filtros[cfg["dono"]] = frappe.session.user
    elif vista == "parados":
        campo_at = "orbit_ultima_atividade" if meta.has_field("orbit_ultima_atividade") else "modified"
        filtros[campo_at] = ["<", add_days(now_datetime(), -30)]
    elif vista == "abertos" and objeto == "negocios":
        filtros["status"] = ["not in", FECHADOS]
    if estado and objeto in ("negocios", "leads"):
        filtros["status"] = estado
    # H7: filtros à escolha e colunas da vista (lista branca em orbit/interface/vistas.py)
    from orbit.interface import vistas as _v
    extra = _v.traduzir(objeto, filtros_json) if filtros_json else []
    # 23-11-2026: separadores de marca no topo da lista (contactos: a tabela «Marcas»)
    if marca and frappe.db.exists("Brand", marca):
        if objeto == "contactos":
            if meta.has_field("marcas"):
                extra.append(["Marca do Contacto", "marca", "=", marca])
        elif meta.has_field("marca"):
            extra.append(["marca", "=", marca])
    if colunas:
        disp = {c for c, _r in _v.COLUNAS.get(objeto, [])} | {c["campo"] for c in _v.colunas_personalizadas(objeto)}
        pedidas = [c for c in json.loads(colunas) if c in disp and (meta.has_field(c) or c == "creation") and c != "marcas"]
        cfg = {**cfg, "campos": list(dict.fromkeys(cfg["campos"] + pedidas))}
    campo_ordem, sentido = (ordem.split() + ["desc"])[:2]
    if campo_ordem not in cfg["campos"] + ["creation", "modified"] or sentido not in ("asc", "desc"):
        campo_ordem, sentido = "modified", "desc"
    q = (q or "").strip()
    or_filtros = [[c, "like", f"%{q}%"] for c in cfg["pesquisa"]] if q else None
    pg = max(cint(pagina), 0)
    filtros_lista = [[k, *(v if isinstance(v, list) else ["=", v])] for k, v in filtros.items()] + extra
    linhas = frappe.get_list(cfg["dt"], filters=filtros_lista, or_filters=or_filtros, fields=["name"] + cfg["campos"],
                             order_by=f"{campo_ordem} {sentido}", limit_start=pg * 50, limit_page_length=51)
    total = len(frappe.get_list(cfg["dt"], filters=filtros_lista, or_filters=or_filtros, pluck="name", limit=5000))
    for r in linhas:
        for k in ("deal_owner", "lead_owner", "owner", "orbit_responsavel"):
            if r.get(k):
                r[k + "_nome"] = _nome_user(r[k])
        if r.get("status"):
            r.estado = _rotulo_estado(r.status)
    if objeto == "contactos":
        _ultima_actividade(linhas)
        if meta.has_field("marcas") and linhas:
            por = {}
            for r in frappe.get_all("Marca do Contacto", filters={"parenttype": "Contact", "parentfield": "marcas",
                                                                  "parent": ["in", [l.name for l in linhas]]},
                                    fields=["parent", "marca"], order_by="idx asc"):
                por.setdefault(r.parent, []).append(r.marca)
            for l in linhas:
                l.marcas = ", ".join(por.get(l.name, []))
    for l in linhas:
        for k, v in list(l.items()):
            if k.startswith("oc_") and isinstance(v, (int, float)) and meta.get_field(k) and meta.get_field(k).fieldtype == "Check":
                l[k] = "Sim" if v else "Não"
    return {"linhas": linhas[:50], "mais": len(linhas) > 50, "total": total, "doctype": cfg["dt"]}


def _ultima_actividade(contactos):
    emails = [c.email_id for c in contactos if c.email_id]
    if not emails:
        return
    ult = {}
    for r in frappe.db.sql("""select c.email_id, max(m.communication_date) d from `tabContact Email` c
            join tabCommunication m on (m.sender like concat('%%', c.email_id, '%%') or m.recipients like concat('%%', c.email_id, '%%'))
            where c.email_id in %(e)s and m.communication_medium='Email' group by c.email_id""", {"e": tuple(emails)}, as_dict=1):
        ult[r.email_id] = r.d
    for c in contactos:
        c.ultimo_email = ult.get(c.email_id)


# ── Ficha ───────────────────────────────────────────────────────────────────────────────────────────────
_PROPS = {
    "Contact": [("orbit_responsavel", "Responsável", "Link", 1), ("orbit_ciclo", "Fase do ciclo de vida", "Select", 1),
                ("orbit_ultima_atividade", "Última atividade", "Datetime", 0), ("email_id", "Email", "Data", 0), ("mobile_no", "Telemóvel", "Data", 0), ("phone", "Telefone", "Data", 0),
                ("designation", "Cargo", "Data", 1), ("company_name", "Empresa (texto)", "Data", 1),
                ("nif", "NIF", "Data", 1), ("origem", "Origem", "Link", 1), ("mkt_estado", "Marketing por email", "Select", 0),
                ("mkt_idioma", "Língua", "Select", 1), ("creation", "Criado", "Datetime", 0)],
    "CRM Deal": [("deal_owner", "Responsável", "Link", 1), ("orbit_ultima_atividade", "Última atividade", "Datetime", 0),
                 ("status", "Fase", "Link", 1), ("deal_value", "Valor", "Currency", 1), ("probability", "Probabilidade", "Percent", 1),
                 ("expected_closure_date", "Data prevista de fecho", "Date", 1),
                 ("next_step", "Próximo passo", "Data", 1), ("source", "Origem", "Link", 1), ("marca", "Marca", "Link", 1),
                 ("orbit_referencia_loja", "Encomenda na loja", "Data", 0), ("closed_date", "Data de fecho", "Date", 0),
                 ("creation", "Criado", "Datetime", 0)],
    "CRM Lead": [("lead_owner", "Responsável", "Link", 1), ("orbit_ultima_atividade", "Última atividade", "Datetime", 0),
                 ("status", "Estado", "Link", 1), ("email", "Email", "Data", 1), ("mobile_no", "Telemóvel", "Data", 1),
                 ("organization", "Empresa", "Data", 1), ("job_title", "Cargo", "Data", 1), ("source", "Origem", "Link", 1),
                 ("marca", "Marca", "Link", 1), ("nipc", "NIF / NIPC", "Data", 1), ("codigo_postal", "Código postal", "Data", 1),
                 ("cidade", "Localidade", "Data", 1), ("pais", "País", "Link", 1), ("mkt_estado", "Marketing por email", "Select", 0),
                 ("creation", "Criado", "Datetime", 0)],
    "CRM Organization": [("orbit_responsavel", "Responsável", "Link", 1), ("orbit_ciclo", "Fase do ciclo de vida", "Select", 1),
                         ("marca", "Marca", "Link", 1),
                         ("orbit_ultima_atividade", "Última atividade", "Datetime", 0), ("website", "Site", "Data", 1), ("telefone", "Telefone", "Data", 1), ("email_geral", "Email geral", "Data", 1),
                         ("nipc", "NIPC", "Data", 1), ("industry", "Setor", "Link", 1), ("territory", "Território", "Link", 1),
                         ("no_of_employees", "Pessoas", "Select", 1), ("tipo_conta", "Tipo de conta", "Select", 1),
                         ("estado_conta", "Estado da conta", "Select", 1), ("creation", "Criado", "Datetime", 0)],
}


def _titulo(dt, dn):
    if not dt or not dn:
        return ""
    campo = {"Contact": "full_name", "CRM Organization": "organization_name", "CRM Deal": "titulo", "CRM Lead": "lead_name",
             "HD Ticket": "subject"}.get(dt)
    v = frappe.db.get_value(dt, dn, campo) if campo else None
    if dt == "CRM Deal" and not v:
        v = frappe.db.get_value(dt, dn, "lead_name") or frappe.db.get_value(dt, dn, "organization")
    return v or dn


def _relacionados(dt, dn):
    """Os registos ligados a este (como as associações do HubSpot): contactos, empresas, negócios, leads e emails."""
    rel = {"Contact": set(), "CRM Organization": set(), "CRM Deal": set(), "CRM Lead": set()}
    rel[dt].add(dn)
    if dt == "Contact":
        rel["CRM Deal"] |= set(frappe.get_all("CRM Contacts", filters={"parenttype": "CRM Deal", "contact": dn}, pluck="parent"))
        rel["CRM Organization"] |= set(frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "parent": dn,
                                                                                "link_doctype": "CRM Organization"}, pluck="link_name"))
        emp = frappe.db.get_value("Contact", dn, "company_name")
        if emp and frappe.db.exists("CRM Organization", emp):
            rel["CRM Organization"].add(emp)
    elif dt == "CRM Deal":
        d = frappe.db.get_value("CRM Deal", dn, ["organization", "lead", "contact"], as_dict=1) or {}
        if d.get("organization"):
            rel["CRM Organization"].add(d["organization"])
        if d.get("lead"):
            rel["CRM Lead"].add(d["lead"])
        rel["Contact"] |= set(frappe.get_all("CRM Contacts", filters={"parenttype": "CRM Deal", "parent": dn}, pluck="contact"))
        if d.get("contact"):
            rel["Contact"].add(d["contact"])
    elif dt == "CRM Organization":
        rel["CRM Deal"] |= set(frappe.get_all("CRM Deal", filters={"organization": dn}, pluck="name"))
        rel["Contact"] |= set(frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "link_doctype": "CRM Organization",
                                                                       "link_name": dn}, pluck="parent"))
        rel["Contact"] |= set(frappe.get_all("Contact", filters={"company_name": dn}, pluck="name"))
    elif dt == "CRM Lead":
        rel["CRM Deal"] |= set(frappe.get_all("CRM Deal", filters={"lead": dn}, pluck="name"))
    if dt in ("Contact", "CRM Organization"):
        for n in list(rel["CRM Deal"]):
            l = frappe.db.get_value("CRM Deal", n, "lead")
            if l:
                rel["CRM Lead"].add(l)
    emails = set()
    for c in rel["Contact"]:
        emails |= set(frappe.get_all("Contact Email", filters={"parent": c, "parenttype": "Contact"}, pluck="email_id"))
    for l in rel["CRM Lead"]:
        e = frappe.db.get_value("CRM Lead", l, "email")
        if e:
            emails.add(e)
    if dt == "CRM Deal":
        e = frappe.db.get_value("CRM Deal", dn, "email")
        if e:
            emails.add(e)
    return rel, {e.lower() for e in emails if e}


@frappe.whitelist()
def ficha(doctype: str, name: str):
    _guarda()
    if doctype not in _PROPS:
        frappe.throw("Tipo de registo desconhecido")
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    pode_editar = frappe.has_permission(doctype, "write", doc)
    meta = frappe.get_meta(doctype)
    props = []
    # 23-11-2026: a ordem e os campos do resumo vêm do editor de formulários (CRM Fields Layout «Side Panel»)
    from orbit.interface.formularios import secoes as _secoes
    _base = {c[0]: c for c in _PROPS[doctype]}
    _ordem = [c for sec in _secoes(doctype, "resumo") for c in sec["campos"]]
    _extra = []
    _lista = []
    for c in _ordem:
        if c in _base:
            _lista.append(_base[c])
        elif c not in ("marcas",) and meta.has_field(c):
            _extra.append(c)
            _lista.append((c, None, None, None))
    for campo, rotulo, tipo, editavel in _lista:
        if rotulo is None:
            props.append(_prop_campo(doc, meta, meta.get_field(campo), pode_editar))
            continue
        if not meta.has_field(campo) and campo != "creation":
            continue
        v = doc.get(campo)
        f = meta.get_field(campo)
        opcoes = None
        if tipo == "Select" and f:
            opcoes = [o for o in (f.options or "").split("\n")]
        elif tipo == "Link" and f and f.options in ("CRM Deal Status", "CRM Lead Status", "CRM Lead Source", "CRM Industry",
                                                    "CRM Territory", "Brand"):
            opcoes = [""] + frappe.get_all(f.options, pluck="name", order_by="position asc" if f.options in
                                           ("CRM Deal Status", "CRM Lead Status") else "name asc", limit=200)
        elif tipo == "Link" and f and f.options == "User":
            opcoes = [""] + frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
                                           pluck="name", limit=200)
        mostra = v
        if tipo == "Link" and f and f.options == "User":
            mostra = _nome_user(v)
        elif tipo in ("Link", "Select") and campo in ("status",):
            mostra = _rotulo_estado(v)
        props.append({"campo": campo, "rotulo": rotulo, "tipo": tipo, "valor": v, "mostra": mostra,
                      "editavel": bool(editavel and pode_editar), "opcoes": opcoes,
                      "rotulos": {o: (_nome_user(o) if tipo == "Link" and f and f.options == "User" else _rotulo_estado(o)) for o in (opcoes or [])}})
    # 23-11-2026: NIF/NIPC verificados (fiscal.py), marcas do contacto, campos personalizados (campos.py), morada
    for p in props:
        if (doctype, p["campo"]) in (("Contact", "nif"), ("CRM Organization", "nipc")):
            p["tipo"] = "Fiscal"
    from orbit.interface import marcas as _M, campos as _C, fiscal as _F
    if doctype == "Contact" and meta.has_field("marcas") and "marcas" in _ordem:
        _antes = set(_ordem[:_ordem.index("marcas")])
        props.insert(sum(1 for p in props if p["campo"] in _antes), {"campo": "marcas", "rotulo": "Marcas", "tipo": "Marcas", "valor": _M.marcas_do_contacto(name),
                         "mostra": "", "editavel": bool(pode_editar), "opcoes": _M.lista(), "rotulos": {}})
    for cf in _C.personalizados(doctype):
        tipo = {"Data": "Data", "Small Text": "Text", "Float": "Number", "Int": "Number", "Currency": "Currency",
                "Date": "Date", "Check": "Check", "Select": "Select"}.get(cf.fieldtype, "Data")
        ops = [o for o in (cf.options or "").split("\n")] if cf.fieldtype == "Select" else None
        props.append({"campo": cf.fieldname, "rotulo": cf.label, "tipo": tipo, "valor": doc.get(cf.fieldname),
                      "mostra": doc.get(cf.fieldname), "editavel": bool(pode_editar), "opcoes": ops, "rotulos": {},
                      "personalizado": True})
    # Todos os campos, por secções e em colunas, estão no separador «Detalhes» (orbit/interface/detalhes.py).
    morada = None
    if doctype in ("Contact", "CRM Organization") and meta.has_field("address"):
        morada = {"valores": _F.morada_de(doctype, name), "campos": [{"campo": c, "rotulo": r} for c, r in _F.MORADA],
                  "paises": ["Portugal", "Spain", "France", "Italy", "Germany", "Belgium", "Netherlands", "Luxembourg",
                             "United Kingdom", "Switzerland", "Brazil", "Angola", "Mozambique", "Cape Verde"]}
    rel, emails = _relacionados(doctype, name)
    assoc = {}
    for dt, nomes in rel.items():
        nomes = [n for n in nomes if not (dt == doctype and n == name)]
        if not nomes:
            assoc[dt] = []
            continue
        if dt == "CRM Deal":
            campos = ["name", "titulo", "status", "deal_value", "expected_closure_date", "organization", "lead_name", "probability"]
        elif dt == "Contact":
            campos = ["name", "full_name", "email_id", "designation"]
        elif dt == "CRM Organization":
            campos = ["name", "organization_name", "website", "territory"]
        else:
            campos = ["name", "lead_name", "status", "email"]
        linhas = frappe.get_list(dt, filters={"name": ["in", nomes]}, fields=campos, limit=50)
        for r in linhas:
            if r.get("status"):
                r.estado = _rotulo_estado(r.status)
        if doctype == "CRM Deal" and dt == "Contact":
            # 23-11-2026: qual é o contacto principal do negócio (para «Tornar principal»)
            prim = {x.contact for x in doc.get("contacts") or [] if x.is_primary}
            for r in linhas:
                r.principal = r.name in prim
            linhas.sort(key=lambda r: not r.principal)
        assoc[dt] = linhas
    tickets = []
    if emails and frappe.db.exists("DocType", "HD Ticket"):
        tickets = frappe.get_list("HD Ticket", filters={"raised_by": ["in", list(emails)]},
                                  fields=["name", "subject", "status", "modified"], order_by="modified desc", limit=10)
    titulo = _titulo(doctype, name)
    sub = ""
    if doctype == "Contact":
        org = (assoc.get("CRM Organization") or [{}])[0].get("organization_name") if assoc.get("CRM Organization") else doc.company_name
        sub = " · ".join(x for x in [doc.designation, org] if x)
    elif doctype == "CRM Deal":
        sub = " · ".join(x for x in [doc.organization or doc.lead_name, _rotulo_estado(doc.status),
                                    f"{flt(doc.deal_value):,.2f} €".replace(",", " ") if doc.deal_value else ""] if x)
    elif doctype == "CRM Organization":
        sub = " · ".join(x for x in [doc.website, doc.territory] if x)
    elif doctype == "CRM Lead":
        sub = " · ".join(x for x in [doc.organization, _rotulo_estado(doc.status)] if x)
    estados = frappe.get_all("CRM Deal Status", fields=["name", "type", "color"], order_by="position asc") if doctype == "CRM Deal" else []
    for s in estados:
        s.rotulo = _rotulo_estado(s.name)
    return {"doctype": doctype, "name": name, "titulo": titulo, "sub": sub, "iniciais": _iniciais(titulo),
            "imagem": doc.get("image") or doc.get("organization_logo"), "props": props, "assoc": assoc, "tickets": tickets,
            "morada": morada,
            "emails": sorted(emails), "pode_editar": pode_editar, "estados": estados,
            "classico": _url_classico(doctype, name),
            "email_principal": (doc.get("email_id") or doc.get("email") or (sorted(emails)[0] if emails else "")),
            "telefone": doc.get("mobile_no") or doc.get("phone") or doc.get("telefone") or ""}


_TIPOS_FICHA = {"Data": "Data", "Small Text": "Text", "Text": "Text", "Long Text": "Text", "Text Editor": "Text",
                "Select": "Select", "Link": "Link", "Dynamic Link": "Data", "Date": "Date", "Datetime": "Datetime",
                "Check": "Check", "Int": "Number", "Float": "Number", "Currency": "Currency", "Percent": "Percent",
                "Phone": "Data", "Read Only": "Data", "Autocomplete": "Data", "Rating": "Number", "Duration": "Number"}
_NUNCA = {"naming_series", "amended_from", "_user_tags", "_comments", "_assign", "_liked_by", "_seen", "idx", "docstatus",
          "image", "organization_logo", "sync_with_google_contacts", "google_contacts", "google_contacts_id",
          "pulled_from_google_contacts", "unsubscribed", "is_primary_contact", "user"}


_PT_VALORES = {"Passive": "Passivo", "Open": "Aberto", "Replied": "Respondeu", "Male": "Masculino", "Female": "Feminino",
               "Other": "Outro", "Prefer not to say": "Prefiro não dizer", "Mr": "Sr.", "Ms": "Sr.ª", "Mrs": "Sr.ª",
               "Dr": "Dr.", "Prof": "Prof.", "Hot": "Quente", "Warm": "Morna", "Cold": "Fria", "Fulfilled": "Cumprido",
               "Failed": "Falhou", "First Response Due": "1.ª resposta em prazo", "Rolling Response Due": "Resposta em prazo"}


def _prop_campo(doc, meta, f, pode_editar: bool) -> dict:
    """Um campo do registo pronto para a ficha (tipo, valor, opções, se é editável)."""
    tipo = _TIPOS_FICHA.get(f.fieldtype, "Data")
    v = doc.get(f.fieldname)
    opcoes = None
    if f.fieldtype == "Select":
        opcoes = (f.options or "").split("\n")
    elif f.fieldtype == "Link" and f.options and f.options != "User":
        try:
            if frappe.db.count(f.options) <= 300:
                opcoes = [""] + frappe.get_all(f.options, pluck="name", order_by="name asc", limit=300)
        except Exception:
            opcoes = None
    elif f.fieldtype == "Link" and f.options == "User":
        opcoes = [""] + frappe.get_all("User", filters={"enabled": 1, "user_type": "System User",
                                                        "name": ["not in", ["Administrator", "Guest"]]}, pluck="name", limit=200)
    if f.fieldtype == "Text Editor" and v:
        v = _texto(v, 2000)
    rotulos = {}
    if f.fieldtype == "Link" and f.options == "User":
        rotulos = {o: _nome_user(o) for o in (opcoes or [])}
    elif f.fieldtype == "Link" and f.options in ("CRM Deal Status", "CRM Lead Status"):
        rotulos = {o: _rotulo_estado(o) for o in (opcoes or [])}
    elif f.fieldtype in ("Select", "Link") and opcoes:
        # valores de origem em inglês (Passive, Male, Mr…) mostrados pelas traduções do Orbit
        rotulos = {o: (_PT_VALORES.get(o) or _(o)) for o in opcoes if o}
    return {"campo": f.fieldname, "rotulo": _(f.label or f.fieldname),
            "tipo": "Data" if tipo == "Link" and not opcoes else tipo, "valor": v,
            "mostra": _nome_user(v) if f.fieldtype == "Link" and f.options == "User" else v,
            "editavel": bool(pode_editar and not f.read_only and f.fieldtype not in ("Read Only", "Text Editor")
                             and f.fieldname not in _NUNCA),
            "opcoes": opcoes, "rotulos": rotulos}


def _url_classico(dt, dn):
    return {"Contact": f"/crm/contacts/{dn}", "CRM Deal": f"/crm/deals/{dn}", "CRM Lead": f"/crm/leads/{dn}",
            "CRM Organization": f"/crm/organizations/{dn}"}.get(dt, "/crm")


_EDITAVEIS = {dt: {c for c, _r, _t, e in campos if e} for dt, campos in _PROPS.items()}


@frappe.whitelist(methods=["POST"])
def guardar(doctype: str, name: str, campo: str, valor=None):
    _guarda()
    # 23-11-2026: NIF/NIPC passam pela verificação (dígito de controlo, VIES) e o VIES preenche a morada da empresa
    if (doctype, campo) in (("Contact", "nif"), ("CRM Organization", "nipc")):
        from orbit.interface.fiscal import numero_fiscal
        return {"ok": True, **numero_fiscal(doctype, name, valor or "")}
    if doctype == "Contact" and campo == "marcas":
        from orbit.interface.marcas import definir_no_contacto
        return {"ok": True, "marcas": definir_no_contacto(name, json.loads(valor or "[]") if isinstance(valor, str) else (valor or []))}
    meta = frappe.get_meta(doctype)
    fm = meta.get_field(campo)
    # 23-11-2026: qualquer campo do registo que a ficha mostra como editável (todos os campos), com as permissões do doc
    outro = (doctype in _PROPS and fm is not None and fm.fieldtype in _TIPOS_FICHA and not fm.read_only and not fm.hidden
             and fm.fieldtype not in ("Read Only", "Text Editor") and campo not in _NUNCA)
    if campo not in _EDITAVEIS.get(doctype, set()) and not outro:
        frappe.throw("Campo não editável")
    doc = frappe.get_doc(doctype, name)
    f = meta.get_field(campo)
    if f and f.fieldtype == "Check":
        valor = 1 if str(valor) in ("1", "true", "True") else 0
    elif f and f.fieldtype in ("Float", "Int", "Currency"):
        valor = None if valor in (None, "") else (int(float(valor)) if f.fieldtype == "Int" else float(valor))
    doc.set(campo, valor if valor not in ("",) else None)
    # lead: o email/telemóvel/telefone da coluna lateral é o principal da tabela «Emails e telefones»
    _SINC = {("CRM Lead", "email"): "Email", ("CRM Lead", "mobile_no"): "Telemóvel", ("CRM Lead", "phone"): "Fixo",
             ("CRM Organization", "email_geral"): "Email", ("CRM Organization", "telefone"): "Fixo"}
    if (doctype, campo) in _SINC and doc.get("orbit_meios"):
        tipo = _SINC[(doctype, campo)]
        linha = next((r for r in doc.orbit_meios if (r.tipo == tipo or (tipo == "Fixo" and doctype == "CRM Organization" and r.tipo != "Email"))
                      and r.principal), None)
        if valor and linha:
            linha.valor = valor
        elif valor:
            doc.append("orbit_meios", {"tipo": tipo, "valor": valor, "principal": 1})
        elif linha:
            doc.remove(linha)
    doc.save()
    return {"ok": True}


# ── Cronologia ──────────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def cronologia(doctype: str, name: str, tipo: str = ""):
    _guarda()
    frappe.get_doc(doctype, name).check_permission("read")
    rel, emails = _relacionados(doctype, name)
    pares = [(dt, n) for dt, ns in rel.items() for n in ns]
    itens = []
    hoje = now_datetime()

    # Emails: pela referência e pelas ligações (Communication Link) — o mesmo que o separador «E-mails» do Frappe
    nomes = set()
    for dt, n in pares:
        nomes |= set(frappe.get_all("Communication", filters={"reference_doctype": dt, "reference_name": n,
                                                              "communication_type": "Communication"}, pluck="name"))
        nomes |= set(frappe.get_all("Communication Link", filters={"parenttype": "Communication", "link_doctype": dt,
                                                                   "link_name": n}, pluck="parent"))
    if nomes and tipo in ("", "emails"):
        for c in frappe.get_list("Communication", filters={"name": ["in", list(nomes)], "communication_medium": "Email"},
                                 fields=["name", "subject", "sender", "sender_full_name", "recipients", "communication_date",
                                         "sent_or_received", "content", "email_account", "orbit_privado_de",
                                         "reference_doctype", "reference_name", "read_by_recipient"], limit=300):
            itens.append({"tipo": "email", "id": c.name, "data": c.communication_date,
                          "titulo": c.subject or "(sem assunto)",
                          "quem": c.sender_full_name or c.sender, "sentido": c.sent_or_received,
                          "de": c.sender, "para": c.recipients, "conta": (c.email_account or "").replace("Orbit CRM · ", ""),
                          "texto": _texto(c.content, 400), "privado": bool(c.orbit_privado_de),
                          "lido": bool(c.read_by_recipient)})

    def por_ref(dt_alvo, campos, ref_dt="reference_doctype", ref_dn="reference_docname"):
        out = []
        for dt, n in pares:
            out += frappe.get_list(dt_alvo, filters={ref_dt: dt, ref_dn: n}, fields=campos, limit=200)
        return out

    if tipo in ("", "notas"):
        for nt in por_ref("FCRM Note", ["name", "title", "content", "creation", "owner"]):
            itens.append({"tipo": "nota", "id": nt.name, "data": nt.creation, "titulo": nt.title or "Nota",
                          "quem": _nome_user(nt.owner), "texto": _texto(nt.content, 600)})
    if tipo in ("", "conversa"):   # 23-11-2026: a conversa interna com @menções (orbit/interface/conversa.py)
        for c in por_ref("Comment", ["name", "content", "owner", "creation", "comment_type"], ref_dn="reference_name"):
            if c.comment_type == "Comment":
                itens.append({"tipo": "comentario", "id": c.name, "data": c.creation, "titulo": "Comentário",
                              "quem": _nome_user(c.owner), "texto": _texto(c.content, 600)})
    if tipo in ("", "tarefas"):
        for t in por_ref("CRM Task", ["name", "title", "status", "due_date", "assigned_to", "creation", "description"]):
            futura = t.status not in ("Done", "Canceled")
            itens.append({"tipo": "tarefa", "id": t.name, "data": t.due_date or t.creation, "titulo": t.title,
                          "quem": _nome_user(t.assigned_to), "estado": t.status, "texto": _texto(t.description, 300),
                          "proximo": futura, "atrasada": bool(futura and t.due_date and t.due_date < hoje)})
    if tipo in ("", "chamadas"):
        for cl in por_ref("CRM Call Log", ["name", "type", "status", "duration", "start_time", "creation", "caller",
                                           "receiver", "note", "telephony_medium"]):
            nota = frappe.db.get_value("FCRM Note", cl.note, "content") if cl.note else ""
            itens.append({"tipo": "chamada", "id": cl.name, "data": cl.start_time or cl.creation,
                          "titulo": ("Chamada efetuada" if cl.type == "Outgoing" else "Chamada recebida"),
                          "quem": _nome_user(cl.caller or cl.receiver), "duracao": cint(cl.duration),
                          "texto": _texto(nota, 600), "estado": cl.status})
    if tipo in ("", "reunioes"):
        for ev in por_ref("Event", ["name", "subject", "starts_on", "ends_on", "location", "google_meet_link", "description"]):
            itens.append({"tipo": "reuniao", "id": ev.name, "data": ev.starts_on, "titulo": ev.subject,
                          "texto": _texto(ev.description, 300), "local": ev.location,
                          "proximo": bool(ev.starts_on and ev.starts_on > hoje)})
    if emails and tipo in ("", "tickets") and frappe.db.exists("DocType", "HD Ticket"):
        for tk in frappe.get_list("HD Ticket", filters={"raised_by": ["in", list(emails)]},
                                  fields=["name", "subject", "status", "creation", "description", "status_category"], limit=50):
            itens.append({"tipo": "ticket", "id": tk.name, "data": tk.creation, "titulo": f"Ticket #{tk.name} · {tk.subject}",
                          "estado": _rotulo_estado(tk.status), "resolvido": tk.status_category == "Resolved", "texto": _texto(tk.description, 300)})
    itens.sort(key=lambda i: str(i.get("data") or ""), reverse=True)
    proximos = sorted([i for i in itens if i.get("proximo")], key=lambda i: str(i.get("data") or ""))
    passado = [i for i in itens if not i.get("proximo")]
    contagem = {}
    for i in itens:
        contagem[i["tipo"]] = contagem.get(i["tipo"], 0) + 1
    return {"proximos": proximos, "passado": passado[:200], "contagem": contagem}


@frappe.whitelist(methods=["POST"])
def email_completo(nome: str):
    _guarda()
    c = frappe.get_doc("Communication", nome)
    c.check_permission("read")
    return {"id": c.name, "assunto": c.subject, "de": c.sender, "para": c.recipients, "cc": c.cc, "data": c.communication_date,
            "html": c.content or ""}


# ── Criar a partir da ficha ─────────────────────────────────────────────────────────────────────────────
@frappe.whitelist(methods=["POST"])
def nota(doctype: str, name: str, conteudo: str):
    _guarda()
    frappe.get_doc(doctype, name).check_permission("read")
    n = frappe.get_doc({"doctype": "FCRM Note", "title": _texto(conteudo, 60), "content": frappe.utils.escape_html(conteudo).replace("\n", "<br>"),
                        "reference_doctype": doctype, "reference_docname": name}).insert()
    return {"ok": True, "id": n.name}


@frappe.whitelist(methods=["POST"])
def tarefa(doctype: str, name: str, titulo: str, data: str = None, responsavel: str = None):
    _guarda()
    frappe.get_doc(doctype, name).check_permission("read")
    t = frappe.get_doc({"doctype": "CRM Task", "title": titulo, "status": "Todo", "priority": "Medium",
                        "due_date": data or None, "assigned_to": responsavel or frappe.session.user,
                        "reference_doctype": doctype, "reference_docname": name}).insert()
    return {"ok": True, "id": t.name}


@frappe.whitelist(methods=["POST"])
def tarefa_feita(nome: str):
    _guarda()
    t = frappe.get_doc("CRM Task", nome)
    t.status = "Done" if t.status != "Done" else "Todo"
    t.save()
    return {"ok": True, "estado": t.status}


@frappe.whitelist(methods=["POST"])
def procurar_emails(doctype: str, name: str):
    """«Procurar emails antigos»: pede às caixas ligadas o que se trocou com os endereços deste registo."""
    _guarda()
    frappe.get_doc(doctype, name).check_permission("read")
    from orbit.emails_crm import recuperar_agora
    _rel, emails = _relacionados(doctype, name)
    for e in emails:
        recuperar_agora(e)
    return {"ok": True, "emails": sorted(emails)}


# ── Funil ───────────────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def funil(responsavel: str = "", marca: str = ""):
    _guarda()
    estados = frappe.get_all("CRM Deal Status", fields=["name", "type", "color", "position"], order_by="position asc")
    filtros = {"status": ["not in", ["Lost"]]}
    if responsavel == "eu":
        filtros["deal_owner"] = frappe.session.user
    # 23-11-2026: separadores de marca também no funil
    from orbit.interface.marcas import lista as _marcas
    tem_marca = frappe.get_meta("CRM Deal").has_field("marca")
    if marca and tem_marca and frappe.db.exists("Brand", marca):
        filtros["marca"] = marca
    negocios = frappe.get_list("CRM Deal", filters=filtros, fields=["name", "titulo", "organization", "lead_name", "status",
                               "deal_value", "deal_owner", "expected_closure_date", "modified", "closed_date"],
                               order_by="modified desc", limit=1000)
    limite = getdate(add_days(nowdate(), -30))
    proximas = {}
    for t in frappe.get_list("CRM Task", filters={"reference_doctype": "CRM Deal", "status": ["not in", ["Done", "Canceled"]]},
                             fields=["reference_docname", "title", "due_date"], order_by="due_date asc", limit=2000):
        proximas.setdefault(t.reference_docname, t)
    agora = now_datetime()
    colunas = []
    for s in estados:
        cartoes = []
        for d in negocios:
            if d.status != s.name:
                continue
            if s.type == "Won" and d.closed_date and getdate(d.closed_date) < limite:
                continue
            t = proximas.get(d.name)
            cartoes.append({"name": d.name, "titulo": d.titulo or d.lead_name or d.organization or d.name,
                            "org": d.organization or d.lead_name or "", "valor": flt(d.deal_value),
                            "dono": _iniciais(_nome_user(d.deal_owner)), "dono_nome": _nome_user(d.deal_owner),
                            "prox": (t.title if t else ""), "prox_data": (t.due_date if t else None),
                            "atraso": bool(t and t.due_date and t.due_date < agora),
                            "parado": (agora - d.modified).days if not t else 0})
        colunas.append({"estado": s.name, "rotulo": _rotulo_estado(s.name), "tipo": s.type, "cor": s.color,
                        "total": sum(c["valor"] for c in cartoes), "cartoes": cartoes})
    return {"colunas": colunas, "marcas": _marcas() if tem_marca else []}


@frappe.whitelist(methods=["POST"])
def mover(negocio: str, estado: str):
    _guarda()
    if not frappe.db.exists("CRM Deal Status", estado):
        frappe.throw("Fase desconhecida")
    d = frappe.get_doc("CRM Deal", negocio)
    d.status = estado
    d.save()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def contacto_principal(negocio: str, contacto: str):
    """«Tornar principal»: o contacto passa a principal do negócio (o CRM actualiza o email e o telemóvel do negócio)."""
    _guarda()
    d = frappe.get_doc("CRM Deal", negocio)
    d.check_permission("write")
    if not any(x.contact == contacto for x in d.get("contacts") or []):
        frappe.throw("Esse contacto não está associado a este negócio.")
    d.set_primary_contact(contacto)
    d.save()
    return {"ok": True}


# ── Funil das leads (23-11-2026): colunas pelos estados das leads, separadores de marca ─────────────────
@frappe.whitelist()
def funil_leads(responsavel: str = "", marca: str = ""):
    _guarda()
    from orbit.interface.marcas import lista as _marcas
    estados = frappe.get_all("CRM Lead Status", fields=["name", "type", "color", "position"], order_by="position asc")
    filtros = {"converted": 0}
    if responsavel == "eu":
        filtros["lead_owner"] = frappe.session.user
    tem_marca = frappe.get_meta("CRM Lead").has_field("marca")
    if marca and tem_marca and frappe.db.exists("Brand", marca):
        filtros["marca"] = marca
    leads = frappe.get_list("CRM Lead", filters=filtros, fields=["name", "lead_name", "organization", "status", "lead_owner",
                                                                 "email", "modified", "source"], order_by="modified desc", limit=1000)
    proximas = {}
    for t in frappe.get_list("CRM Task", filters={"reference_doctype": "CRM Lead", "status": ["not in", ["Done", "Canceled"]]},
                             fields=["reference_docname", "title", "due_date"], order_by="due_date asc", limit=2000):
        proximas.setdefault(t.reference_docname, t)
    agora = now_datetime()
    colunas = []
    for s in estados:
        cartoes = []
        for l in leads:
            if l.status != s.name:
                continue
            t = proximas.get(l.name)
            cartoes.append({"name": l.name, "titulo": l.lead_name or l.organization or l.email or l.name,
                            "org": l.organization or l.email or "", "origem": l.source or "",
                            "dono": _iniciais(_nome_user(l.lead_owner)), "dono_nome": _nome_user(l.lead_owner),
                            "prox": (t.title if t else ""), "prox_data": (t.due_date if t else None),
                            "atraso": bool(t and t.due_date and t.due_date < agora),
                            "parado": (agora - l.modified).days if not t else 0})
        colunas.append({"estado": s.name, "rotulo": _rotulo_estado(s.name), "tipo": s.type, "cor": s.color,
                        "total": len(cartoes), "cartoes": cartoes})
    return {"colunas": colunas, "marcas": _marcas() if tem_marca else []}


@frappe.whitelist(methods=["POST"])
def mover_lead(lead: str, estado: str):
    _guarda()
    if not frappe.db.exists("CRM Lead Status", estado):
        frappe.throw("Estado desconhecido")
    d = frappe.get_doc("CRM Lead", lead)
    d.status = estado
    d.save()
    return {"ok": True}


# ── Caixa de entrada (como a do HubSpot: conversas, não a caixa de correio inteira) ───────────────────────
# «Equipa» = caixas partilhadas ligadas ao CRM e tickets do Desk; «Privado» = as conversas da minha caixa pessoal
# com contactos do CRM («só para mim», orbit_privado_de = eu). O resto do correio fica no Orbit Mail (SOGo).
def _resp(a):
    """O 1.º utilizador de um campo _assign (JSON)."""
    try:
        l = json.loads(a or "[]")
        return l[0] if l else None
    except Exception:
        return None


@frappe.whitelist()
def caixa(grupo: str = "todos", conta: str = "", minhas: int = 0):
    _guarda()
    u = frappe.session.user
    out = []
    if conta == "minhas":
        conta, grupo, minhas = "", "todos", 1
    if conta == "tickets":
        grupo = "tickets"
    if grupo in ("todos", "equipa", "tickets") and not (conta and conta != "tickets") and frappe.db.exists("DocType", "HD Ticket"):
        for t in frappe.get_list("HD Ticket", filters={"status_category": ["!=", "Resolved"]},
                                 fields=["name", "subject", "raised_by", "status", "modified", "_assign"],
                                 order_by="modified desc", limit=50):
            out.append({"tipo": "ticket", "grupo": "equipa", "id": t.name, "titulo": t.subject, "quem": t.raised_by, "email": t.raised_by,
                        "data": t.modified, "estado": _rotulo_estado(t.status), "url": f"/helpdesk/tickets/{t.name}",
                        "atribuido": bool(t._assign and t._assign != "[]"), "responsavel": _resp(t._assign)})
    filtros = {"communication_medium": "Email", "communication_type": "Communication",
               "communication_date": [">", add_days(now_datetime(), -30)],
               "reference_doctype": ["in", ["Contact", "CRM Deal", "CRM Lead", "CRM Organization"]]}
    if grupo == "tickets":
        out.sort(key=lambda i: str(i["data"] or ""), reverse=True)
        return out
    if conta:
        filtros["email_account"] = conta
    if grupo == "privado":
        filtros["orbit_privado_de"] = u
    elif grupo == "equipa":
        filtros["orbit_privado_de"] = ["in", ["", None]]
    conversas = {}
    for e in frappe.get_list("Communication", filters=filtros,
                             fields=["name", "subject", "sender", "sender_full_name", "recipients", "communication_date",
                                     "sent_or_received", "reference_doctype", "reference_name", "email_account", "content",
                                     "orbit_privado_de", "_assign"], order_by="communication_date desc", limit=400):
        chave = (e.reference_doctype, e.reference_name, re.sub(r"^(re|fw|fwd|enc|res)\s*:\s*", "", (e.subject or "").strip(), flags=re.I).lower())
        if chave in conversas:
            conversas[chave]["n"] += 1
            if not conversas[chave].get("responsavel") and _resp(e.get("_assign")):
                conversas[chave]["responsavel"] = _resp(e.get("_assign"))
            continue
        conversas[chave] = {"tipo": "email", "grupo": "privado" if e.orbit_privado_de else "equipa", "id": e.name,
                            "titulo": e.subject or "(sem assunto)", "quem": e.sender_full_name or e.sender, "data": e.communication_date,
                            "email": (e.sender if e.sent_or_received == "Received" else (e.recipients or "").split(",")[0]).strip(),
                            "por_responder": e.sent_or_received == "Received", "n": 1,
                            "conta": (e.email_account or "").replace("Orbit CRM · ", ""),
                            "ref": [e.reference_doctype, e.reference_name], "ref_titulo": _titulo(e.reference_doctype, e.reference_name),
                            "texto": _texto(e.content, 160), "responsavel": _resp(e.get("_assign"))}
    out += list(conversas.values())
    if cint(minhas):
        out = [i for i in out if i.get("responsavel") == u]
    nomes = {}
    for i in out:
        r = i.get("responsavel")
        if r and r not in nomes:
            nomes[r] = frappe.db.get_value("User", r, "full_name") or r
        i["responsavel_nome"] = nomes.get(r) if r else None
    out.sort(key=lambda i: str(i["data"] or ""), reverse=True)
    return out


# ── Conversa e resposta dentro da caixa de entrada (20-11-2026) ─────────────────────────────────────────
def _assunto_base(s):
    return re.sub(r"^((re|fw|fwd|enc|res|rv)\s*:\s*)+", "", (s or "").strip(), flags=re.I).lower()


@frappe.whitelist()
def equipa_atribuir():
    """Quem pode ficar responsável por uma conversa: os utilizadores do Orbit activos."""
    _guarda()
    return [{"email": x.name, "nome": x.full_name or x.name} for x in frappe.get_all(
        "User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
        fields=["name", "full_name"], order_by="full_name asc")]


@frappe.whitelist(methods=["POST"])
def atribuir_conversa(nome: str, utilizador: str = ""):
    """Responsável por uma conversa da caixa de entrada (22-11-2026: a atribuição passa do webmail para aqui).
    Usa a atribuição do próprio Frappe: o responsável recebe o aviso (sino e email) e a conversa entra em
    «Atribuídas a mim». Uma conversa tem um só responsável: tira-se a atribuição de todas as mensagens dela."""
    _guarda()
    from frappe.desk.form import assign_to
    c = frappe.get_doc("Communication", nome)
    c.check_permission("read")
    base = _assunto_base(c.subject)
    filtros = {"communication_medium": "Email", "communication_type": "Communication"}
    if c.reference_doctype:
        filtros.update({"reference_doctype": c.reference_doctype, "reference_name": c.reference_name})
    else:
        filtros["name"] = c.name
    msgs = [m for m in frappe.get_all("Communication", filters=filtros, fields=["name", "subject", "_assign"], limit=200)
            if _assunto_base(m.subject) == base]
    utilizador = (utilizador or "").strip()
    if utilizador and not frappe.db.get_value("User", {"name": utilizador, "enabled": 1}):
        frappe.throw("Utilizador desconhecido.")
    for m in msgs:
        try:
            for quem in json.loads(m.get("_assign") or "[]"):
                if quem != utilizador or m.name != nome:
                    assign_to.remove("Communication", m.name, quem, ignore_permissions=True)
        except Exception:
            frappe.log_error(title="atribuir_conversa: tirar")
    if utilizador and utilizador not in json.loads(frappe.db.get_value("Communication", nome, "_assign") or "[]"):
        assign_to.add({"assign_to": [utilizador], "doctype": "Communication", "name": nome,
                       "description": c.subject or "Conversa da caixa de entrada"}, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "responsavel": utilizador or None,
            "responsavel_nome": frappe.db.get_value("User", utilizador, "full_name") if utilizador else None}


@frappe.whitelist()
def conversa(nome: str):
    """A conversa toda (mesmo registo e mesmo assunto), da mais antiga para a mais recente."""
    _guarda()
    c = frappe.get_doc("Communication", nome)
    c.check_permission("read")
    base = _assunto_base(c.subject)
    filtros = {"communication_medium": "Email", "communication_type": "Communication"}
    if c.reference_doctype:
        filtros.update({"reference_doctype": c.reference_doctype, "reference_name": c.reference_name})
    else:
        filtros["name"] = c.name
    msgs = [m for m in frappe.get_list("Communication", filters=filtros,
                                       fields=["name", "subject", "sender", "sender_full_name", "recipients", "cc",
                                               "communication_date", "sent_or_received", "content", "email_account",
                                               "orbit_privado_de"], order_by="communication_date asc", limit=200)
            if _assunto_base(m.subject) == base] or [c]
    from orbit.emails_crm import pode_responder
    conta = next((m.email_account for m in reversed(msgs) if m.email_account), c.email_account)
    ultima = msgs[-1]
    if ultima.sent_or_received == "Received":
        para = ultima.sender
    else:
        para = ultima.recipients
    resp = next((_resp(frappe.db.get_value("Communication", m.name, "_assign")) for m in reversed(msgs)
                 if _resp(frappe.db.get_value("Communication", m.name, "_assign"))), None)
    return {"assunto": c.subject, "ref": [c.reference_doctype, c.reference_name],
            "responsavel": resp, "responsavel_nome": frappe.db.get_value("User", resp, "full_name") if resp else None,
            "ref_titulo": _titulo(c.reference_doctype, c.reference_name),
            "conta": conta, "de": frappe.db.get_value("Email Account", conta, "email_id") if conta else None,
            "pode_responder": bool(conta and pode_responder(conta)), "para": para, "responder_a": ultima.name,
            "mensagens": [{"id": m.name, "de": m.sender_full_name or m.sender, "email_de": m.sender, "para": m.recipients,
                           "cc": m.cc, "data": m.communication_date, "enviado": m.sent_or_received == "Sent",
                           "html": m.content or ""} for m in msgs]}


@frappe.whitelist(methods=["POST"])
def responder(nome: str, html: str, para: str = None, cc: str = None):
    """Responde a partir da caixa onde a conversa chegou; a resposta fica nos Enviados da caixa e na cronologia."""
    _guarda()
    from frappe.core.doctype.communication.email import make
    from orbit.emails_crm import pode_responder, preparar_saida
    conv = conversa(nome)
    if not conv["pode_responder"]:
        frappe.throw("Não pode responder a partir desta caixa.", frappe.PermissionError)
    texto = (html or "").strip()
    if not strip_html(texto).strip():
        frappe.throw("A resposta está vazia.")
    acc = preparar_saida(conv["conta"])
    destino = (para or conv["para"] or "").strip()
    if not destino:
        frappe.throw("Falta o destinatário.")
    assunto = conv["assunto"] or ""
    if not re.match(r"^(re|res)\s*:", assunto, flags=re.I):
        assunto = f"Re: {assunto}"
    ref_dt, ref_dn = conv["ref"]
    if ref_dt:
        frappe.get_doc(ref_dt, ref_dn).check_permission("read")
    r = make(doctype=ref_dt, name=ref_dn, content=texto, subject=assunto, sender=acc.email_id,
             sender_full_name=frappe.db.get_value("User", frappe.session.user, "full_name"),
             recipients=destino, cc=cc or None, send_email=True, in_reply_to=conv["responder_a"],
             communication_medium="Email", now=True)
    nome_novo = (r or {}).get("name")
    if nome_novo:
        # O Frappe só grava a conta de saída depois do insert: o «só para mim» e as ligações vêm a seguir, à mão.
        if not frappe.db.get_value("Communication", nome_novo, "email_account"):
            frappe.db.set_value("Communication", nome_novo, "email_account", acc.name, update_modified=False)
        from orbit.emails_crm import filtrar
        filtrar(frappe.get_doc("Communication", nome_novo))
    return {"ok": True, "id": nome_novo}


# ── Canais da caixa de entrada (como o HubSpot: caixas de equipa e a minha caixa, bem separadas) ────────
@frappe.whitelist()
def canais():
    _guarda()
    u = frappe.session.user
    desde = add_days(now_datetime(), -30)
    contas = frappe.get_all("Email Account", filters={"enable_incoming": 1, "orbit_registo_crm": ["in", ["equipa", "so_eu"]]},
                            fields=["name", "email_id", "orbit_registo_crm", "orbit_dono"], order_by="email_id asc")
    def por_responder(nome, privado):
        f = {"email_account": nome, "communication_medium": "Email", "sent_or_received": "Received",
             "communication_date": [">", desde]}
        return len(frappe.get_list("Communication", filters=f, pluck="name", limit=500))
    equipa = [{"conta": c.name, "email": c.email_id, "n": por_responder(c.name, False)} for c in contas if c.orbit_registo_crm == "equipa"]
    minhas = [{"conta": c.name, "email": c.email_id, "n": por_responder(c.name, True)} for c in contas
              if c.orbit_registo_crm == "so_eu" and c.orbit_dono == u]
    tickets = len(frappe.get_list("HD Ticket", filters={"status_category": ["!=", "Resolved"]}, pluck="name", limit=1000)) \
        if frappe.db.exists("DocType", "HD Ticket") else 0
    return {"equipa": equipa, "privado": minhas, "tickets": tickets}


# ── Definições: tudo o que é configuração numa só roda dentada (como o HubSpot) ─────────────────────────
_DEFINICOES = [
    # 23-11-2026: tudo abre na interface nova (lista/ficha genéricas, #/erp/<doctype>); as listas simples que têm ecrã
    # próprio (fases, estados, origens…) vêm de definicoes.py e não se repetem aqui.
    ("Conta e utilizadores", [("Papéis e permissões", "Role"), ("Perfis de módulos", "Module Profile"),
                              ("Definições do sistema", "System Settings")]),
    ("Correio", [("Caixas de email", "Email Account"), ("Domínios de email", "Email Domain"),
                 ("Notificações automáticas", "Notification")]),
    ("CRM", [("Definições do CRM", "FCRM Settings"), ("Regras de atribuição", "Assignment Rule"),
             ("Acordos de nível de serviço (CRM)", "CRM Service Level Agreement"), ("Feriados (para os prazos)", "CRM Holiday List"),
             ("Hierarquia de vendas", "CRM Sales Hierarchy"), ("Sincronização de leads (Facebook)", "Lead Sync Source"),
             ("Enriquecimento de dados", "CRM Enrichment Settings"), ("Ligação ao ERPNext", "ERPNext CRM Settings"),
             ("Telefonia — agentes", "CRM Telephony Agent"), ("Telefonia — Twilio", "CRM Twilio Settings"),
             ("Telefonia — Exotel", "CRM Exotel Settings"),
             ("Motor dos fluxos", "Automation Settings")]),
    ("Atendimento (Desk)", [("Equipas", "HD Team"), ("Acordos de nível de serviço", "HD Service Level Agreement"),
                            ("Respostas-modelo", "HD Saved Reply"), ("Definições do Desk", "HD Settings")]),
    ("Marcas e empresa", [("Marcas", "Brand"), ("Empresas (ERP)", "Company"), ("Cabeçalhos de documentos", "Letter Head"),
                          ("Modelos de impressão", "Print Format")]),
    ("Vendas e faturação", [("Artigos", "Item"), ("Listas de preços", "Price List"),
                            ("Impostos de venda", "Sales Taxes and Charges Template"),
                            ("Termos e condições", "Terms and Conditions"), ("Ligação à faturação certificada", "Ligacao Faturacao")]),
    ("Pessoas e tempo", [("Funcionários", "Employee"), ("Departamentos", "Department"),
                         ("Tipos de atividade (tempo)", "Activity Type"), ("Projetos", "Project")]),
    ("Avançado", [("Campos personalizados (todos os registos)", "Custom Field"), ("Personalizar formulários", "Customize Form"),
                  ("Tarefas agendadas", "Scheduled Job Type"), ("Registo de erros", "Error Log")]),
]


@frappe.whitelist()
def definicoes():
    _guarda()
    out = []
    for grupo, itens in _DEFINICOES:
        ok = []
        for rotulo, dt in itens:
            if not frappe.db.exists("DocType", dt) or not frappe.has_permission(dt, "read"):
                continue
            ok.append({"rotulo": rotulo, "url": "#/erp/" + frappe.utils.quote(dt), "doctype": dt})
        if ok:
            out.append({"grupo": grupo, "itens": ok})
    return out


# ── Associações editáveis (H3, 20-11-2026) — os mesmos campos que o Frappe CRM usa ────────────────────
# Contacto↔Empresa: Contact.company_name (é assim que o CRM lista os contactos de uma organização)
# Contacto↔Negócio: tabela CRM Contacts do negócio · Negócio↔Empresa: CRM Deal.organization
ASSOCIAVEIS = {"Contact": ["CRM Organization", "CRM Deal"], "CRM Organization": ["Contact", "CRM Deal"],
               "CRM Deal": ["Contact", "CRM Organization"]}


@frappe.whitelist()
def candidatos(tipo: str, q: str = ""):
    _guarda()
    if tipo not in ("Contact", "CRM Organization", "CRM Deal"):
        frappe.throw("Tipo desconhecido")
    return [r for r in pesquisa(q) if r["doctype"] == tipo][:8] if len((q or "").strip()) >= 2 else []


def _par(a_dt, a_dn, b_dt, b_dn, ligar: bool):
    if b_dt not in ASSOCIAVEIS.get(a_dt, []):
        frappe.throw("Associação não suportada")
    par = {a_dt: a_dn, b_dt: b_dn}
    if "Contact" in par and "CRM Organization" in par:
        c = frappe.get_doc("Contact", par["Contact"])
        if ligar:
            c.company_name = par["CRM Organization"]
        elif c.company_name == par["CRM Organization"]:
            c.company_name = None
        c.save()
        if not ligar:
            frappe.db.delete("Dynamic Link", {"parenttype": "Contact", "parent": c.name, "link_doctype": "CRM Organization",
                                              "link_name": par["CRM Organization"]})
    elif "Contact" in par and "CRM Deal" in par:
        d = frappe.get_doc("CRM Deal", par["CRM Deal"])
        linhas = [x for x in d.get("contacts", []) if x.contact == par["Contact"]]
        if ligar and not linhas:
            d.append("contacts", {"contact": par["Contact"], "is_primary": 0 if d.get("contacts") else 1})
        elif not ligar:
            for x in linhas:
                d.remove(x)
            if d.get("contacts") and not any(x.is_primary for x in d.contacts):
                d.contacts[0].is_primary = 1
        d.save()
    else:   # Negócio ↔ Empresa
        d = frappe.get_doc("CRM Deal", par["CRM Deal"])
        if ligar:
            d.organization = par["CRM Organization"]
        elif d.organization == par["CRM Organization"]:
            d.organization = None
        d.save()


@frappe.whitelist(methods=["POST"])
def associar(doctype: str, name: str, outro_doctype: str, outro_name: str):
    _guarda()
    frappe.get_doc(outro_doctype, outro_name).check_permission("read")
    _par(doctype, name, outro_doctype, outro_name, True)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def desassociar(doctype: str, name: str, outro_doctype: str, outro_name: str):
    _guarda()
    _par(doctype, name, outro_doctype, outro_name, False)
    return {"ok": True}


# ── Converter lead em negócio (H5, 20-11-2026) — pela função do próprio Frappe CRM ───────────────────────
@frappe.whitelist()
def sugestao_conversao(lead: str):
    _guarda()
    l = frappe.get_doc("CRM Lead", lead)
    l.check_permission("read")
    contactos = []
    if l.email:
        for c in frappe.get_all("Contact Email", filters={"email_id": l.email.lower(), "parenttype": "Contact"}, pluck="parent", limit=5):
            contactos.append({"name": c, "titulo": _titulo("Contact", c)})
    empresas = []
    for f in ([["organization_name", "=", l.organization]] if l.organization else []) + \
             ([["website", "like", f"%{l.website}%"]] if l.website else []):
        for o in frappe.get_list("CRM Organization", filters=[f], pluck="name", limit=3):
            if o not in [e["name"] for e in empresas]:
                empresas.append({"name": o, "titulo": _titulo("CRM Organization", o)})
    fases = [{"name": s.name, "rotulo": _rotulo_estado(s.name)} for s in
             frappe.get_all("CRM Deal Status", filters={"type": ["not in", ["Won", "Lost"]]}, fields=["name"], order_by="position asc")]
    return {"convertida": bool(l.converted), "nome": l.lead_name, "empresa_texto": l.organization or "",
            "contactos": contactos, "empresas": empresas, "fases": fases,
            "negocios": frappe.get_all("CRM Deal", filters={"lead": lead}, pluck="name")}


@frappe.whitelist(methods=["POST"])
def converter(lead: str, valor: float = None, fase: str = None, contacto: str = None, empresa: str = None, titulo: str = None):
    """`contacto`/`empresa`: nome de um registo existente para reutilizar; vazio = o CRM cria a partir da lead."""
    _guarda()
    from crm.fcrm.doctype.crm_lead.crm_lead import convert_to_deal
    l = frappe.get_doc("CRM Lead", lead)
    l.check_permission("write")
    deal = {}
    if valor not in (None, ""):
        deal["deal_value"] = float(valor)
    if fase and frappe.db.exists("CRM Deal Status", fase):
        deal["status"] = fase
    if l.lead_owner:
        deal["deal_owner"] = l.lead_owner
    if titulo and frappe.get_meta("CRM Deal").has_field("titulo"):
        deal["titulo"] = titulo.strip()[:140]
    nome = convert_to_deal(lead=lead, deal=deal or None, existing_contact=contacto or None,
                           existing_organization=empresa or None)
    if isinstance(nome, dict):
        nome = nome.get("name") or nome.get("deal")
    # 23-11-2026: os emails e telefones extra da lead passam para o contacto do negócio
    try:
        from orbit.interface.detalhes import copiar_para_contacto
        for ct in frappe.get_all("CRM Contacts", filters={"parent": nome, "parenttype": "CRM Deal"}, pluck="contact"):
            copiar_para_contacto(lead, ct)
    except Exception:
        frappe.log_error(title="Orbit: meios da lead para o contacto")
    return {"ok": True, "negocio": nome}


# ── Compositor: modelos de email e email novo a partir da ficha (H9, 20-11-2026) ───────────────────────
@frappe.whitelist()
def modelos_email():
    _guarda()
    # todos (os modelos de origem do Frappe vêm «desligados» e o campo só serve às notificações automáticas)
    return frappe.get_list("Email Template", fields=["name", "subject"], order_by="name asc", limit=200)


def _contexto_modelo(doctype=None, name=None, para=None):
    eu = frappe.db.get_value("User", frappe.session.user, ["full_name", "first_name"], as_dict=True) or {}
    ctx = {"eu": eu.get("full_name") or frappe.session.user, "meu_nome": eu.get("full_name"), "data": frappe.utils.formatdate(frappe.utils.nowdate()),
           "nome": "", "nome_completo": "", "empresa": "", "negocio": "", "email": para or ""}
    doc = None
    if doctype and name and frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        doc.check_permission("read")
        if doctype == "Contact":
            ctx.update(nome=doc.first_name or "", nome_completo=doc.full_name or "", empresa=doc.company_name or "")
        elif doctype == "CRM Lead":
            ctx.update(nome=doc.first_name or "", nome_completo=doc.lead_name or "", empresa=doc.organization or "")
        elif doctype == "CRM Deal":
            ctx.update(negocio=doc.get("titulo") or doc.name, empresa=doc.organization or "",
                       nome=doc.first_name or "", nome_completo=" ".join(x for x in [doc.first_name, doc.last_name] if x))
            c = next((x.contact for x in doc.get("contacts") or [] if x.is_primary), None) or (doc.contacts[0].contact if doc.get("contacts") else None)
            if c:
                cd = frappe.db.get_value("Contact", c, ["first_name", "full_name"], as_dict=True) or {}
                ctx.update(nome=cd.get("first_name") or ctx["nome"], nome_completo=cd.get("full_name") or ctx["nome_completo"])
        elif doctype == "CRM Organization":
            ctx.update(empresa=doc.organization_name or "")
    ctx["doc"] = doc.as_dict() if doc else {}
    return ctx


@frappe.whitelist()
def aplicar_modelo(modelo: str, doctype: str = None, name: str = None, para: str = None):
    _guarda()
    t = frappe.get_doc("Email Template", modelo)
    t.check_permission("read")
    ctx = _contexto_modelo(doctype, name, para)
    corpo = t.response_html if t.get("use_html") and t.get("response_html") else (t.response or "")
    try:
        corpo = frappe.render_template(corpo, ctx)
        assunto = frappe.render_template(t.subject or "", ctx)
    except Exception:  # noqa: BLE001 — um modelo com variáveis erradas insere-se como está
        assunto = t.subject or ""
    import html as _h
    texto = re.sub(r"<br\s*/?>", "\n", corpo, flags=re.I)
    texto = re.sub(r"</p\s*>|</div\s*>|</li\s*>", "\n\n", texto, flags=re.I)
    texto = _h.unescape(strip_html(texto))
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return {"assunto": assunto, "texto": texto}


@frappe.whitelist()
def minhas_caixas():
    """As caixas de onde a pessoa pode escrever: as partilhadas ligadas ao CRM e a dela («só para mim»)."""
    _guarda()
    u = frappe.session.user
    out = []
    for a in frappe.get_all("Email Account", filters={"enable_incoming": 1, "orbit_registo_crm": ["in", ["equipa", "so_eu"]]},
                            fields=["name", "email_id", "orbit_registo_crm", "orbit_dono"], order_by="email_id asc"):
        if a.orbit_registo_crm == "so_eu" and a.orbit_dono != u:
            continue
        out.append({"conta": a.name, "email": a.email_id, "privada": a.orbit_registo_crm == "so_eu"})
    out.sort(key=lambda x: (not x["privada"], x["email"]))
    return out


@frappe.whitelist(methods=["POST"])
def enviar_email(doctype: str, name: str, conta: str, para: str, assunto: str, html: str, cc: str = None):
    """Email novo a partir da ficha, da caixa escolhida; fica nos Enviados dela e na cronologia do registo."""
    _guarda()
    from frappe.core.doctype.communication.email import make
    from orbit.emails_crm import filtrar, pode_responder, preparar_saida
    frappe.get_doc(doctype, name).check_permission("read")
    if not pode_responder(conta):
        frappe.throw("Não pode escrever a partir desta caixa.", frappe.PermissionError)
    if not strip_html(html or "").strip() or not (assunto or "").strip():
        frappe.throw("Falta o assunto ou o texto.")
    acc = preparar_saida(conta)
    r = make(doctype=doctype, name=name, content=html, subject=assunto.strip()[:200], sender=acc.email_id,
             sender_full_name=frappe.db.get_value("User", frappe.session.user, "full_name"), recipients=para, cc=cc or None,
             send_email=True, communication_medium="Email", now=True)
    nome = (r or {}).get("name")
    if nome:
        if not frappe.db.get_value("Communication", nome, "email_account"):
            frappe.db.set_value("Communication", nome, "email_account", acc.name, update_modified=False)
        filtrar(frappe.get_doc("Communication", nome))
    return {"ok": True, "id": nome}
