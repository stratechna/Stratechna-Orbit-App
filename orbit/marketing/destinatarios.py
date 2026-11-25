"""Quem pode receber, e quem está num segmento.

É a única função que decide a quem se escreve. Tudo passa por aqui: a
contagem que o ecrã mostra, a verificação antes de aprovar, e a lista fixada
no momento da saída.

Pode receber quem cumprir as quatro coisas, todas lidas do próprio CRM:
  1. está marcado «Pode receber», com base legal;
  2. o contacto não está `unsubscribed`;
  3. não pediu para sair de tudo (Email Unsubscribe global);
  4. não saiu do assunto desta campanha (Email Unsubscribe do assunto).

Um lead já convertido não conta: a pessoa vive agora no contacto, e contá-la
duas vezes era escrever-lhe duas vezes.
"""

from datetime import timedelta

import frappe
from frappe.utils import add_days, cint, flt, now_datetime, nowdate

from orbit.marketing.consentimento import NOMES


FORA = "Sem registo"


def _marcadores(v) -> set:
    return {t.strip().lower() for t in (v or "").split(",") if t.strip()}


def _tem(dt: str, campo: str) -> bool:
    return frappe.db.exists("DocType", dt) and frappe.get_meta(dt).has_field(campo)


def _registos(todos: bool = False) -> list[dict]:
    """Leads e contactos com email, com os campos de marketing e o que o CRM sabe deles (marca, marcadores,
    fase, responsável, origem, setor, território, empresa). Um endereço que esteja nos dois fica o contacto.
    `todos`: também quem não pode receber — para os marcadores automáticos e para a contagem de «fora»."""
    saida: dict[str, dict] = {}
    orgs = {}
    if frappe.db.exists("DocType", "CRM Organization"):
        cols = [c for c in ("name", "industry", "territory", "no_of_employees", "orbit_ciclo", "orbit_responsavel",
                            "nipc", "customer", "marca", "_user_tags") if c in ("name", "_user_tags") or _tem("CRM Organization", c)]
        orgs = {o.name: o for o in frappe.get_all("CRM Organization", fields=cols, limit_page_length=0)}
    if _tem("CRM Lead", "mkt_estado"):
        cols = ["name", "email", "first_name", "last_name", "organization", "status", "converted", "_user_tags"] + NOMES
        cols += [c for c in ("industry", "territory", "no_of_employees", "source", "lead_owner", "marca", "nipc",
                             "orbit_ultima_atividade", "distrito") if _tem("CRM Lead", c)]
        for l in frappe.get_all("CRM Lead", fields=cols, filters={"email": ("is", "set")}, limit_page_length=0):
            if cint(l.get("converted")):
                continue
            o = orgs.get(l.organization) or {}
            saida[l.email.strip().lower()] = {
                "doctype": "CRM Lead", "name": l.name, "email": l.email.strip().lower(),
                "nome": l.first_name, "apelido": l.last_name, "organizacao": l.organization,
                "estado_lead": l.status, "unsubscribed": 0, **{k: l.get(k) for k in NOMES},
                "marcas": {m for m in (l.get("marca"), o.get("marca")) if m},
                "marcadores": _marcadores(l.get("_user_tags")) | _marcadores(o.get("_user_tags")),
                "ciclo": "Lead", "responsavel": l.get("lead_owner"), "origem": l.get("source"),
                "setor": l.get("industry") or o.get("industry"), "territorio": l.get("territory") or o.get("territory"),
                "distrito": l.get("distrito"), "empregados": l.get("no_of_employees") or o.get("no_of_employees"),
                "ultima_atividade": l.get("orbit_ultima_atividade"), "nif": l.get("nipc") or o.get("nipc"),
                "cliente_erp": o.get("customer"), "org_crm": l.organization if l.organization in orgs else None}
    if _tem("Contact", "mkt_estado"):
        cols = ["name", "email_id", "first_name", "last_name", "company_name", "unsubscribed", "_user_tags"] + NOMES
        cols += [c for c in ("orbit_ciclo", "orbit_responsavel", "orbit_ultima_atividade") if _tem("Contact", c)]
        marcas: dict = {}
        if frappe.db.exists("DocType", "Marca do Contacto"):
            for r in frappe.get_all("Marca do Contacto", filters={"parenttype": "Contact"}, fields=["parent", "marca"],
                                    limit_page_length=0):
                marcas.setdefault(r.parent, set()).add(r.marca)
        clientes = {}
        for r in frappe.get_all("Dynamic Link", filters={"parenttype": "Contact", "link_doctype": "Customer"},
                                fields=["parent", "link_name"], limit_page_length=0):
            clientes.setdefault(r.parent, r.link_name)
        for c in frappe.get_all("Contact", fields=cols, filters={"email_id": ("is", "set")}, limit_page_length=0):
            o = orgs.get(c.company_name) or {}
            saida[c.email_id.strip().lower()] = {
                "doctype": "Contact", "name": c.name, "email": c.email_id.strip().lower(),
                "nome": c.first_name, "apelido": c.last_name, "organizacao": c.company_name,
                "estado_lead": None, "unsubscribed": cint(c.unsubscribed), **{k: c.get(k) for k in NOMES},
                "marcas": marcas.get(c.name, set()) | ({o["marca"]} if o.get("marca") else set()),
                "marcadores": _marcadores(c.get("_user_tags")) | _marcadores(o.get("_user_tags")),
                "ciclo": c.get("orbit_ciclo") or o.get("orbit_ciclo"),
                "responsavel": c.get("orbit_responsavel") or o.get("orbit_responsavel"), "origem": None,
                "setor": o.get("industry"), "territorio": o.get("territory"), "distrito": None,
                "empregados": o.get("no_of_employees"), "ultima_atividade": c.get("orbit_ultima_atividade"),
                "nif": o.get("nipc"), "cliente_erp": clientes.get(c.name) or o.get("customer"),
                "org_crm": c.company_name if c.company_name in orgs else None}
    return list(saida.values())


def _sairam(assunto: str | None) -> tuple[set, set]:
    globais = {(e or "").lower() for e in frappe.get_all(
        "Email Unsubscribe", filters={"global_unsubscribe": 1}, pluck="email", limit_page_length=0)}
    do_assunto = set()
    if assunto:
        do_assunto = {(e or "").lower() for e in frappe.get_all(
            "Email Unsubscribe", filters={"reference_doctype": "Assunto de Marketing",
                                          "reference_name": assunto}, pluck="email", limit_page_length=0)}
    return globais, do_assunto


def pode_receber(r: dict, globais: set, do_assunto: set, suprimidos: set) -> bool:
    return (r.get("mkt_estado") == "Pode receber" and bool(r.get("mkt_base_legal"))
            and not r["unsubscribed"] and r["email"] not in globais and r["email"] not in do_assunto
            and r["email"] not in suprimidos)


def _suprimidos() -> set:
    # Quem devolveu ou se queixou (Supressao de Marketing) fica de fora sempre.
    return {(e or "").lower() for e in frappe.get_all("Supressao de Marketing", pluck="email", limit_page_length=0)}


def marcas_da_conta() -> list:
    return frappe.get_all("Brand", pluck="name") if frappe.db.exists("DocType", "Brand") else []


def da_marca(r: dict, marca: str | None) -> bool:
    """S7 (25-11-2026): numa conta com várias marcas, a comunicação de uma marca só vai a quem é dessa marca.
    O soft opt-in («cliente») só vale para o que é análogo ao que comprou — por isso a marca manda também aqui."""
    if not marca:
        return True
    return marca in (r.get("marcas") or set())


def contactaveis(assunto: str | None = None, marca: str | None = None) -> list[dict]:
    globais, do_assunto = _sairam(assunto)
    suprimidos = _suprimidos()
    return [r for r in _registos() if pode_receber(r, globais, do_assunto, suprimidos) and da_marca(r, marca)]


def _comportamento(coluna: str, dias: int) -> set:
    desde = now_datetime() - timedelta(days=dias)
    return {(e or "").lower() for e in frappe.get_all(
        "Envio de Marketing", filters={coluna: (">=", desde)}, pluck="email", limit_page_length=0)}


# ── O que se sabe de cada pessoa fora da ficha (negócios e ERP), calculado uma vez por contagem ──

def _negocios(cache: dict) -> dict:
    """Por (doctype, nome) do registo: os negócios em que entra — {status, fase, ganho_em, motivo}."""
    if "negocios" in cache:
        return cache["negocios"]
    saida: dict = {}
    if frappe.db.exists("DocType", "CRM Deal"):
        meta = frappe.get_meta("CRM Deal")
        cols = ["name", "status", "modified", "lead"] + [c for c in ("lost_reason", "closed_date") if meta.has_field(c)]
        deals = {d.name: d for d in frappe.get_all("CRM Deal", fields=cols, limit_page_length=0)}
        tipos = {}
        if frappe.db.exists("DocType", "CRM Deal Status"):
            tipos = {x.name: x.get("type") for x in frappe.get_all("CRM Deal Status", fields=["name", "type"])}

        def _info(d):
            return {"fase": d.status, "tipo": tipos.get(d.status) or ("Won" if d.status == "Won" else
                                                                     "Lost" if d.status == "Lost" else "Open"),
                    "em": d.get("closed_date") or d.modified, "motivo": d.get("lost_reason")}
        for r in frappe.get_all("CRM Contacts", filters={"parenttype": "CRM Deal"}, fields=["parent", "contact"],
                                limit_page_length=0):
            if r.parent in deals and r.contact:
                saida.setdefault(("Contact", r.contact), []).append(_info(deals[r.parent]))
        for d in deals.values():
            if d.lead:
                saida.setdefault(("CRM Lead", d.lead), []).append(_info(d))
    cache["negocios"] = saida
    return saida


def _erp(cache: dict) -> dict:
    """Por cliente do ERP: grupo, faturado no último ano, faturas vencidas, marcas e artigos comprados."""
    if "erp" in cache:
        return cache["erp"]
    saida: dict = {}
    if frappe.db.exists("DocType", "Sales Invoice"):
        for c in frappe.get_all("Customer", fields=["name", "customer_group"], limit_page_length=0):
            saida[c.name] = {"grupo": c.customer_group, "ano": 0.0, "vencidas": 0, "marcas": set(), "artigos": set()}
        desde = add_days(nowdate(), -365)
        for r in frappe.db.sql("""SELECT customer, SUM(base_net_total) t FROM `tabSales Invoice`
                WHERE docstatus = 1 AND is_return = 0 AND posting_date >= %s GROUP BY customer""", desde, as_dict=True):
            saida.setdefault(r.customer, {"grupo": None, "ano": 0.0, "vencidas": 0, "marcas": set(), "artigos": set()})["ano"] = flt(r.t)
        for r in frappe.db.sql("""SELECT customer, COUNT(*) n FROM `tabSales Invoice`
                WHERE docstatus = 1 AND outstanding_amount > 0 AND due_date < CURDATE() GROUP BY customer""", as_dict=True):
            if r.customer in saida:
                saida[r.customer]["vencidas"] = r.n
        for tabela, pai in (("Sales Invoice Item", "Sales Invoice"), ("Sales Order Item", "Sales Order")):
            for r in frappe.db.sql(f"""SELECT DISTINCT p.customer, i.item_code, i.brand FROM `tab{tabela}` i
                    JOIN `tab{pai}` p ON p.name = i.parent WHERE p.docstatus = 1""", as_dict=True):
                if r.customer in saida:
                    saida[r.customer]["artigos"].add((r.item_code or "").lower())
                    if r.brand:
                        saida[r.customer]["marcas"].add(r.brand.lower())
    cache["erp"] = saida
    return saida


def _do_erp(r: dict, cache: dict) -> dict:
    return _erp(cache).get(r.get("cliente_erp") or "") or {}


def _campo(r: dict, valor: str, cache: dict) -> bool:
    """«campo=valor», «campo~texto» (contém) ou «campo=» (vazio), sobre o registo no CRM."""
    import re
    m = re.match(r"^\s*([a-z0-9_]+)\s*([=~])\s*(.*)$", valor or "", re.I)
    if not m:
        return False
    campo, op, alvo = m.group(1), m.group(2), m.group(3).strip().lower()
    if not _tem(r["doctype"], campo):
        return False
    chave = ("campo", r["doctype"], campo)
    if chave not in cache:
        cache[chave] = {x.name: x.get(campo) for x in frappe.get_all(r["doctype"], fields=["name", campo],
                                                                    limit_page_length=0)}
    v = str(cache[chave].get(r["name"]) or "").strip().lower()
    if op == "~":
        return bool(alvo) and alvo in v
    return v == alvo


def _cumpre(r: dict, regra: str, valor: str, cache: dict) -> bool:
    from frappe.utils import getdate
    v = (valor or "").strip()
    baixo = v.lower()
    if regra in ("Tem o marcador", "Segmento"):
        return baixo in (r.get("marcadores") or set()) or (r.get("mkt_segmento") or "").strip().lower() == baixo
    if regra == "Assunto de interesse":
        return baixo in {a.strip().lower() for a in (r.get("mkt_assuntos") or "").split(",")}
    if regra == "É da marca":
        return baixo in {m.lower() for m in (r.get("marcas") or set())}
    if regra == "Idioma":
        return (r.get("mkt_idioma") or "") == baixo
    if regra == "Base legal":
        return (r.get("mkt_base_legal") or "") == baixo
    if regra == "Tipo de registo":
        return {"lead": "CRM Lead", "contacto": "Contact"}.get(baixo) == r["doctype"]
    if regra == "Estado do lead":
        return (r.get("estado_lead") or "").lower() == baixo
    if regra == "Organização contém":
        return baixo in (r.get("organizacao") or "").lower()
    if regra == "Fase do ciclo":
        return (r.get("ciclo") or "").lower() == baixo
    if regra == "Responsável":
        return (r.get("responsavel") or "").lower() == baixo
    if regra == "Origem":
        return (r.get("origem") or r.get("mkt_origem") or "").lower() == baixo
    if regra == "Setor":
        return (r.get("setor") or "").lower() == baixo
    if regra == "Território ou distrito":
        return baixo in {(r.get("territorio") or "").lower(), (r.get("distrito") or "").lower()}
    if regra == "Empregados pelo menos":
        import re
        n = [int(x) for x in re.findall(r"\d+", str(r.get("empregados") or ""))]
        return bool(n) and max(n) >= cint(v)
    if regra == "Sem atividade há mais de N dias":
        u = r.get("ultima_atividade")
        return not u or getdate(u) < getdate(add_days(nowdate(), -cint(v)))
    if regra in ("Tem negócio aberto na fase", "Ganhou negócio nos últimos N dias", "Perdeu negócio (motivo)"):
        ns = _negocios(cache).get((r["doctype"], r["name"]), [])
        if regra == "Tem negócio aberto na fase":
            return any(n["tipo"] not in ("Won", "Lost") and (not baixo or (n["fase"] or "").lower() == baixo) for n in ns)
        if regra == "Ganhou negócio nos últimos N dias":
            return any(n["tipo"] == "Won" and getdate(n["em"]) >= getdate(add_days(nowdate(), -(cint(v) or 365)))
                       for n in ns)
        return any(n["tipo"] == "Lost" and (not baixo or (n["motivo"] or "").lower() == baixo) for n in ns)
    if regra == "Grupo de cliente":
        return (_do_erp(r, cache).get("grupo") or "").lower() == baixo
    if regra == "Comprou artigos da marca":
        return baixo in _do_erp(r, cache).get("marcas", set())
    if regra == "Comprou o artigo":
        return baixo in _do_erp(r, cache).get("artigos", set())
    if regra == "Faturado pelo menos (€, 12 meses)":
        return flt(_do_erp(r, cache).get("ano")) >= flt(v)
    if regra == "Tem faturas vencidas":
        return cint(_do_erp(r, cache).get("vencidas")) > 0
    if regra == "Campo do CRM":
        return _campo(r, v, cache)
    if regra in ("Comprou nos últimos N dias", "Não compra há mais de N dias", "Comprou no grupo de artigos",
                 "Tem pelo menos N encomendas"):
        from orbit.marketing import loja
        if "compras" not in cache:
            cache["compras"] = loja.ultima_compra()
        x = cache["compras"].get(r["email"])
        if not x:
            return False
        if regra == "Comprou nos últimos N dias":
            return getdate(x["ultima"]) >= getdate(add_days(nowdate(), -cint(v)))
        if regra == "Não compra há mais de N dias":
            return getdate(x["ultima"]) < getdate(add_days(nowdate(), -cint(v)))
        if regra == "Comprou no grupo de artigos":
            return baixo in {g.lower() for g in x["grupos"]}
        return x["n"] >= cint(v)
    if regra in ("Abriu nos últimos N dias", "Clicou nos últimos N dias"):
        coluna = "aberto_em" if regra.startswith("Abriu") else "clicado_em"
        chave = (coluna, cint(v))
        if chave not in cache:
            cache[chave] = _comportamento(coluna, cint(v) or 30)
        return r["email"] in cache[chave]
    return False


def filtrar(base: list[dict], regras: list, logica: str = "Todas", cache: dict | None = None) -> list[dict]:
    """Regras: [{regra, valor, negar}]. «Todas» = E, «Qualquer» = OU; «negar» = «não é». Sem regras = toda a base."""
    cache = {} if cache is None else cache
    if not regras:
        return list(base)

    def ok(r, x):
        return _cumpre(r, x.get("regra"), x.get("valor"), cache) != bool(cint(x.get("negar")))
    junta = any if (logica or "").startswith("Qualquer") else all
    return [r for r in base if junta(ok(r, x) for x in regras)]


def _regras(segmento: str) -> tuple[list, str]:
    regras = frappe.get_all("Regra de Segmento", filters={"parent": segmento, "parenttype": "Segmento de Marketing"},
                            fields=["regra", "valor", "negar"] if _tem("Regra de Segmento", "negar") else ["regra", "valor"],
                            order_by="idx")
    logica = frappe.db.get_value("Segmento de Marketing", segmento, "logica") if _tem("Segmento de Marketing", "logica") else None
    return regras, logica or "Todas"


def do_segmento(segmento: str, base: list[dict] | None = None) -> list[dict]:
    """Um segmento, sobre quem pode receber (ou sobre a base dada)."""
    regras, logica = _regras(segmento)
    base = contactaveis() if base is None else base
    return filtrar(base, regras, logica)


def da_campanha(campanha) -> list[dict]:
    """Os destinatários de uma campanha: os que podem receber o assunto dela, são da marca dela (S7) e estão
    em pelo menos um dos segmentos."""
    if not campanha.get("marca") and len(marcas_da_conta()) > 1:
        return []  # várias marcas e nenhuma escolhida: não sai para ninguém (S7)
    base = contactaveis(campanha.assunto_marketing, campanha.get("marca"))
    segmentos = [s.segmento for s in (campanha.segmentos or [])]
    if not segmentos:
        return []
    vistos, saida = set(), []
    for s in segmentos:
        for r in do_segmento(s, base):
            if r["email"] not in vistos:
                vistos.add(r["email"])
                saida.append(r)
    return saida


def contagem(regras: list, logica: str = "Todas", marca: str | None = None, assunto: str | None = None,
             amostra: int = 20) -> dict:
    """Para o ecrã do segmento: quantos cumprem as regras, quantos podem receber e porque ficam os outros de fora."""
    globais, do_assunto = _sairam(assunto)
    suprimidos = _suprimidos()
    todos = [r for r in _registos(True) if da_marca(r, marca)]
    dentro = filtrar(todos, regras, logica)
    podem, fora = [], {"sem_base": 0, "recusou": 0, "saiu": 0}
    for r in dentro:
        if pode_receber(r, globais, do_assunto, suprimidos):
            podem.append(r)
        elif r.get("mkt_estado") in ("Recusou", "Retirou"):
            fora["recusou"] += 1
        elif r["unsubscribed"] or r["email"] in globais or r["email"] in do_assunto or r["email"] in suprimidos:
            fora["saiu"] += 1
        else:
            fora["sem_base"] += 1

    def _linha(r):
        return {"doctype": r["doctype"], "name": r["name"], "email": r["email"],
                "nome": " ".join(x for x in (r.get("nome"), r.get("apelido")) if x), "organizacao": r.get("organizacao"),
                "estado": r.get("mkt_estado") or FORA, "base": r.get("mkt_base_legal"),
                "pode": r in podem, "marcadores": sorted(r.get("marcadores") or [])}
    return {"no_segmento": len(dentro), "podem_receber": len(podem), "fora": fora,
            "amostra": [_linha(r) for r in dentro[:amostra]]}
