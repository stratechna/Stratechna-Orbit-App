# Lote 7 (e a árvore do lote 6) do plano das opções dos originais — 25-11-2026
#
# docs/PLANO-ORBIT-OPCOES-DOS-ORIGINAIS.md §3: o painel do CRM com período e vendedor (o «Dashboard» do Frappe CRM),
# o Início/painel do Desk (o «Dashboard» do Helpdesk), a base de conhecimento em ecrã próprio e a vista em árvore
# das tabelas hierárquicas do ERP (plano de contas, centros de custo, grupos de artigos, armazéns, territórios…).
# Só leituras e gravações pelas permissões de quem está a usar.
import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from orbit.interface.api import _guarda

PERIODOS = {"7": 7, "30": 30, "90": 90, "365": 365}


def _desde(periodo):
    return add_days(nowdate(), -PERIODOS.get(str(periodo), 30))


# ── painel do CRM ────────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def crm(periodo: str = "30", responsavel: str = "", funil: str = ""):
    _guarda()
    if not frappe.has_permission("CRM Deal", "read"):
        frappe.throw(_("Sem acesso ao CRM."), frappe.PermissionError)
    desde = _desde(periodo)
    fd = {"creation": [">=", desde]}
    fl = {"creation": [">=", desde]}
    if responsavel:
        fd["deal_owner"] = responsavel
        fl["lead_owner"] = responsavel
    # 27-11-2026: vários funis — os números são de um funil (vazio = o por omissão)
    from orbit import funis as F
    funil = funil if funil and frappe.db.exists("Funil", funil) else F.omissao()
    tipos = {s.name: s.type for s in F.fases(funil)}
    from orbit.interface.api import _rotulo_estado as _rotulo
    fd["status"] = ["in", list(tipos) or ["-"]]
    negocios = frappe.get_list("CRM Deal", filters=fd, fields=["name", "status", "deal_value", "lost_reason", "creation", "closed_date", "source"], limit=5000)
    abertos = frappe.get_list("CRM Deal", filters={**({"deal_owner": responsavel} if responsavel else {}),
                                                  "status": ["in", [k for k, t in tipos.items() if t not in ("Won", "Lost")]]},
                              fields=["status", "deal_value", "probability", "expected_closure_date"], limit=5000)
    leads = frappe.get_list("CRM Lead", filters=fl, fields=["name", "status", "source", "converted", "creation"], limit=5000)
    por_fase = []
    for fase, tipo in tipos.items():
        if tipo in ("Won", "Lost"):
            continue
        xs = [n for n in abertos if n.status == fase]
        por_fase.append({"fase": _rotulo(fase), "n": len(xs), "valor": round(sum(flt(n.deal_value) for n in xs), 2)})
    ganhos = [n for n in negocios if tipos.get(n.status) == "Won"]
    perdidos = [n for n in negocios if tipos.get(n.status) == "Lost"]
    motivos = {}
    for n in perdidos:
        motivos[n.lost_reason or _("Sem motivo")] = motivos.get(n.lost_reason or _("Sem motivo"), 0) + 1
    origens = {}
    for x in leads:
        origens[x.source or _("Sem origem")] = origens.get(x.source or _("Sem origem"), 0) + 1
    # por semana (ou por mês, no ano): criados e ganhos
    passo = 30 if str(periodo) == "365" else 7 if str(periodo) in ("30", "90") else 1
    serie = {}
    for n in negocios:
        d = getdate(n.creation)
        chave = d.strftime("%Y-%m") if passo == 30 else str(add_days(d, -d.weekday())) if passo == 7 else str(d)
        serie.setdefault(chave, {"criados": 0, "ganhos": 0})["criados"] += 1
        if tipos.get(n.status) == "Won":
            serie[chave]["ganhos"] += 1
    rotulos = sorted(serie)
    previsto = sum(flt(n.deal_value) * flt(n.probability or 0) / 100 for n in abertos)
    return {
        "kpis": {"leads": len(leads), "convertidos": sum(1 for x in leads if cint(x.converted)),
                 "negocios": len(negocios), "ganhos": len(ganhos), "perdidos": len(perdidos),
                 "valor_ganho": round(sum(flt(n.deal_value) for n in ganhos), 2),
                 "em_aberto": round(sum(flt(n.deal_value) for n in abertos), 2), "previsto": round(previsto, 2),
                 "taxa_ganho": round(100 * len(ganhos) / max(1, len(ganhos) + len(perdidos)), 1),
                 "conversao_leads": round(100 * sum(1 for x in leads if cint(x.converted)) / max(1, len(leads)), 1)},
        "por_fase": por_fase,
        "motivos": sorted([{"r": k, "n": v} for k, v in motivos.items()], key=lambda x: -x["n"]),
        "origens": sorted([{"r": k, "n": v} for k, v in origens.items()], key=lambda x: -x["n"])[:10],
        "serie": {"labels": rotulos, "series": [{"name": _("Criados"), "values": [serie[k]["criados"] for k in rotulos]},
                                                {"name": _("Ganhos"), "values": [serie[k]["ganhos"] for k in rotulos]}]},
        "funil": funil, "funis": [{"name": v.name} for v in F.visiveis()],
        "responsaveis": [{"v": u, "r": frappe.db.get_value("User", u, "full_name") or u}
                         for u in sorted({x for x in frappe.get_all("CRM Deal", pluck="deal_owner", distinct=True) if x})],
    }


# ── painel do Desk ───────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def desk(periodo: str = "30", equipa: str = ""):
    _guarda()
    if not frappe.db.exists("DocType", "HD Ticket") or not frappe.has_permission("HD Ticket", "read"):
        frappe.throw(_("Sem acesso ao Desk."), frappe.PermissionError)
    desde = _desde(periodo)
    f = {"opening_date": [">=", desde]}
    if equipa:
        f["agent_group"] = equipa
    ts = frappe.get_list("HD Ticket", filters=f, fields=["name", "status", "priority", "agent_group", "_assign", "opening_date",
                                                         "first_responded_on", "resolution_date", "creation", "agreement_status",
                                                         "feedback_rating"], limit=10000)
    import json
    from orbit.interface.desk import _categoria
    estados, agentes, por_dia = {}, {}, {}
    resp, resol, notas = [], [], []
    for t in ts:
        estados[t.status] = estados.get(t.status, 0) + 1
        try:
            a = (json.loads(t._assign or "[]") or [None])[0]
        except ValueError:
            a = None
        k = frappe.db.get_value("User", a, "full_name") if a else _("Sem responsável")
        ag = agentes.setdefault(k or a, {"r": k or a, "n": 0, "resolvidos": 0})
        ag["n"] += 1
        if _categoria(t.status) == "Resolved":
            ag["resolvidos"] += 1
        d = str(getdate(t.creation))
        por_dia[d] = por_dia.get(d, 0) + 1
        if t.first_responded_on and t.creation:
            resp.append((frappe.utils.get_datetime(t.first_responded_on) - frappe.utils.get_datetime(t.creation)).total_seconds() / 3600)
        if t.resolution_date and t.creation:
            resol.append((frappe.utils.get_datetime(t.resolution_date) - frappe.utils.get_datetime(t.creation)).total_seconds() / 3600)
        if t.feedback_rating:
            notas.append(flt(t.feedback_rating))
    abertos = frappe.get_list("HD Ticket", filters={"status": ["not in", [s for s in estados if _categoria(s) == "Resolved"] or ["Resolved", "Closed"]]},
                              fields=["name", "agreement_status", "first_responded_on"], limit=10000)
    dias = sorted(por_dia)
    return {"kpis": {"criados": len(ts), "abertos": len(abertos), "sem_resposta": sum(1 for x in abertos if not x.first_responded_on),
                     "fora_prazo": sum(1 for x in abertos if x.agreement_status == "Failed"),
                     "resp_media_h": round(sum(resp) / len(resp), 1) if resp else None,
                     "resol_media_h": round(sum(resol) / len(resol), 1) if resol else None,
                     "avaliacao": round(100 * sum(notas) / len(notas)) if notas else None,
                     "cumpridos": sum(1 for t in ts if t.agreement_status == "Fulfilled"), "falhados": sum(1 for t in ts if t.agreement_status == "Failed")},
            "estados": sorted([{"r": _(k), "n": v} for k, v in estados.items()], key=lambda x: -x["n"]),
            "agentes": sorted(agentes.values(), key=lambda x: -x["n"]),
            "serie": {"labels": dias, "series": [{"name": _("Tickets"), "values": [por_dia[d] for d in dias]}]},
            "equipas": frappe.get_all("HD Team", pluck="name") if frappe.db.exists("DocType", "HD Team") else []}


# ── base de conhecimento ─────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def kb(categoria: str = "", estado: str = "", q: str = ""):
    _guarda()
    if not frappe.db.exists("DocType", "HD Article"):
        return {"categorias": [], "artigos": []}
    cats = frappe.get_list("HD Article Category", fields=["name", "category_name", "description"], order_by="category_name asc", limit=500)
    f = {}
    if categoria:
        f["category"] = categoria
    if estado:
        f["status"] = estado
    ou = [["title", "like", f"%{q}%"], ["content", "like", f"%{q}%"]] if q else None
    arts = frappe.get_list("HD Article", filters=f, or_filters=ou, fields=["name", "title", "status", "category", "modified", "author"],
                           order_by="modified desc", limit=500)
    contagem = {}
    for a in frappe.get_list("HD Article", fields=["category"], limit=5000):
        contagem[a.category] = contagem.get(a.category, 0) + 1
    return {"categorias": [{"name": c.name, "nome": c.category_name or c.name, "n": contagem.get(c.name, 0)} for c in cats],
            "artigos": [{"name": a.name, "titulo": a.title, "estado": a.status, "categoria": a.category, "quando": str(a.modified),
                         "autor": frappe.db.get_value("User", a.author, "full_name") if a.author else ""} for a in arts],
            "pode": {"criar": frappe.has_permission("HD Article", "create"), "categorias": frappe.has_permission("HD Article Category", "create")}}


@frappe.whitelist()
def kb_artigo(name: str):
    _guarda()
    a = frappe.get_doc("HD Article", name)
    a.check_permission("read")
    return {"name": a.name, "titulo": a.title, "html": a.content or "", "estado": a.status, "categoria": a.category,
            "pode": {"escrever": frappe.has_permission("HD Article", "write", name), "apagar": frappe.has_permission("HD Article", "delete", name)},
            "publico": frappe.utils.get_url(f"/helpdesk/kb-public/articles/{a.name}")}


@frappe.whitelist(methods=["POST"])
def kb_gravar(titulo: str, html: str = "", categoria: str = None, estado: str = "Draft", name: str = None):
    _guarda()
    if estado not in ("Draft", "Published", "Archived"):
        frappe.throw(_("Estado inválido."))
    a = frappe.get_doc("HD Article", name) if name else frappe.new_doc("HD Article")
    a.title = (titulo or "").strip()[:140] or _("Sem título")
    a.content = html or ""
    a.category = categoria or a.get("category")
    a.status = estado
    a.save() if name else a.insert()
    return kb_artigo(a.name)


@frappe.whitelist(methods=["POST"])
def kb_apagar(name: str):
    _guarda()
    frappe.delete_doc("HD Article", name)
    return {"ok": 1}


@frappe.whitelist(methods=["POST"])
def kb_categoria(nome: str, name: str = None, apagar: int = 0):
    _guarda()
    if cint(apagar):
        if frappe.db.count("HD Article", {"category": name}):
            frappe.throw(_("A categoria tem artigos: mova-os primeiro."))
        frappe.delete_doc("HD Article Category", name)
        return {"ok": 1}
    c = frappe.get_doc("HD Article Category", name) if name else frappe.new_doc("HD Article Category")
    c.category_name = (nome or "").strip()[:140]
    c.save() if name else c.insert()
    return {"name": c.name}


@frappe.whitelist(methods=["POST"])
def kb_mover(nomes: str, categoria: str = None, estado: str = None):
    """Mover vários artigos de categoria, ou publicar/arquivar em massa."""
    _guarda()
    import json
    n = 0
    for x in json.loads(nomes or "[]")[:500]:
        a = frappe.get_doc("HD Article", x)
        a.check_permission("write")
        if categoria:
            a.category = categoria
        if estado in ("Draft", "Published", "Archived"):
            a.status = estado
        a.save()
        n += 1
    return {"feitos": n}


# ── árvore (lote 6) ──────────────────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def arvore(doctype: str, pai: str = ""):
    """Os filhos de um ramo de uma tabela em árvore (nested set), como a «Tree View» do desk."""
    _guarda()
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(_("Sem acesso."), frappe.PermissionError)
    m = frappe.get_meta(doctype)
    if not m.is_tree:
        frappe.throw(_("Esta lista não é uma árvore."))
    campo = m.nsm_parent_field or ("parent_" + frappe.scrub(doctype))
    titulo = m.title_field if m.title_field and m.has_field(m.title_field) else None
    campos = ["name", "is_group"] + ([titulo] if titulo else [])
    for extra in ("account_type", "root_type", "account_number", "company", "disabled"):
        if m.has_field(extra):
            campos.append(extra)
    f = {campo: pai} if pai else {campo: ["is", "not set"]}
    filhos = frappe.get_list(doctype, filters=f, fields=campos, order_by="lft asc" if m.has_field("lft") else "name asc", limit=1000)
    return [{"name": x.name, "titulo": x.get(titulo) or x.name, "grupo": cint(x.is_group),
             "extra": " · ".join(str(x.get(c)) for c in ("account_number", "root_type", "account_type", "company") if x.get(c))}
            for x in filhos]
