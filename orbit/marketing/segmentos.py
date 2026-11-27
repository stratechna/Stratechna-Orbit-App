"""Marcadores e segmentos para o ecrã do Marketing no /orbit (plano da segmentação, 25-11-2026).

* **Marcadores** = etiquetas nativas do Frappe (`_user_tags`, doctype «Tag») em contactos, leads e organizações.
  Uma «lista» é um marcador: «Feira 2026» + um segmento «Tem o marcador Feira 2026». O marcador de uma
  organização vale para os contactos dela.
* **Segmentos** dinâmicos: regras com «é / não é», juntas por «Todas» ou «Qualquer», avaliadas no momento.
* **Marcadores automáticos**: um segmento pode pôr um marcador em quem entrar (de hora a hora); nunca o tira.

Quem pode receber decide-o sempre `destinatarios` — nada aqui contorna a base legal nem a saída.
"""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint

from orbit.marketing import destinatarios

DOCTYPES = ("Contact", "CRM Lead", "CRM Organization")

# Regra → como se escreve o valor: «lista» (escolher de `valores`), «numero», «texto», «nenhum»
TIPOS = {
    "Tem o marcador": "lista", "É da marca": "lista", "Assunto de interesse": "lista", "Fase do ciclo": "lista",
    "Responsável": "lista", "Origem": "lista", "Setor": "lista", "Território ou distrito": "lista",
    "Empregados pelo menos": "numero", "Organização contém": "texto", "Sem atividade há mais de N dias": "numero",
    "Tem negócio aberto na fase": "lista", "Tem negócio aberto no funil": "lista", "Ganhou negócio nos últimos N dias": "numero",
    "Perdeu negócio (motivo)": "lista", "Comprou nos últimos N dias": "numero", "Não compra há mais de N dias": "numero",
    "Comprou no grupo de artigos": "lista", "Comprou artigos da marca": "lista", "Comprou o artigo": "texto",
    "Tem pelo menos N encomendas": "numero", "Faturado pelo menos (€, 12 meses)": "numero",
    "Tem faturas vencidas": "nenhum", "Grupo de cliente": "lista", "Abriu nos últimos N dias": "numero",
    "Clicou nos últimos N dias": "numero", "Idioma": "lista", "Base legal": "lista", "Tipo de registo": "lista",
    "Estado do lead": "lista", "Campo do CRM": "texto",
}
GRUPOS = [
    ("Marcadores e marca", ["Tem o marcador", "É da marca", "Assunto de interesse"]),
    ("CRM", ["Fase do ciclo", "Responsável", "Origem", "Setor", "Território ou distrito", "Empregados pelo menos",
             "Organização contém", "Sem atividade há mais de N dias", "Estado do lead", "Tipo de registo"]),
    ("Negócios", ["Tem negócio aberto na fase", "Tem negócio aberto no funil", "Ganhou negócio nos últimos N dias", "Perdeu negócio (motivo)"]),
    ("Compras e faturação", ["Comprou nos últimos N dias", "Não compra há mais de N dias", "Comprou no grupo de artigos",
                             "Comprou artigos da marca", "Comprou o artigo", "Tem pelo menos N encomendas",
                             "Faturado pelo menos (€, 12 meses)", "Tem faturas vencidas", "Grupo de cliente"]),
    ("Correio", ["Abriu nos últimos N dias", "Clicou nos últimos N dias", "Idioma", "Base legal"]),
    ("Avançado", ["Campo do CRM"]),
]


def _pode():
    if not frappe.has_permission("Segmento de Marketing", "read"):
        frappe.throw(_("Sem acesso ao marketing."), frappe.PermissionError)


def _todos(dt, campo, **f):
    if not (frappe.db.exists("DocType", dt) and (campo == "name" or frappe.get_meta(dt).has_field(campo))):
        return []
    return sorted({v for v in frappe.get_all(dt, pluck=campo, filters=f, limit_page_length=0, distinct=True) if v})


def _valores() -> dict:
    regs = destinatarios._registos(True)
    juntar = lambda k: sorted({r.get(k) for r in regs if r.get(k)})  # noqa: E731
    fases_neg = _todos("CRM Deal Status", "name")
    return {
        "Tem o marcador": [m["marcador"] for m in marcadores()["marcadores"]],
        "É da marca": destinatarios.marcas_da_conta(),
        "Assunto de interesse": _todos("Assunto de Marketing", "name"),
        "Fase do ciclo": ["Subscritor", "Lead", "Oportunidade", "Cliente"],
        "Responsável": juntar("responsavel"),
        "Origem": sorted(set(_todos("CRM Lead Source", "name")) | set(juntar("origem"))),
        "Setor": sorted(set(_todos("CRM Industry", "name")) | set(juntar("setor"))),
        "Território ou distrito": sorted(set(juntar("territorio")) | set(juntar("distrito"))),
        "Tem negócio aberto na fase": fases_neg,
        "Tem negócio aberto no funil": _todos("Funil", "name", desligado=0),   # 27-11-2026
        "Perdeu negócio (motivo)": _todos("CRM Lost Reason", "name"),
        "Comprou no grupo de artigos": _todos("Item Group", "name", is_group=0),
        "Comprou artigos da marca": _todos("Brand", "name"),
        "Grupo de cliente": _todos("Customer Group", "name", is_group=0),
        "Idioma": ["pt", "en", "es", "fr"],
        "Base legal": ["consentimento", "cliente", "b2b"],
        "Tipo de registo": ["lead", "contacto"],
        "Estado do lead": _todos("CRM Lead Status", "name"),
    }


@frappe.whitelist()
def opcoes() -> dict:
    """As regras (agrupadas), como se escreve o valor de cada uma e os valores possíveis."""
    _pode()
    return {"grupos": [{"titulo": t, "regras": [{"regra": r, "tipo": TIPOS[r]} for r in rs]} for t, rs in GRUPOS],
            "valores": _valores(), "marcas": destinatarios.marcas_da_conta(),
            "marca_obrigatoria": len(destinatarios.marcas_da_conta()) > 1,
            "assuntos": _todos("Assunto de Marketing", "name")}


def _regras_de(regras) -> list:
    regras = json.loads(regras) if isinstance(regras, str) else (regras or [])
    saida = []
    for x in regras:
        if x.get("regra") in TIPOS:
            saida.append({"regra": x["regra"], "valor": str(x.get("valor") or "")[:140], "negar": cint(x.get("negar"))})
    return saida


@frappe.whitelist()
def contar(regras="[]", logica="Todas", marca=None, assunto=None) -> dict:
    """Contagem ao vivo: no segmento, podem receber, fora (sem base / recusou / saiu) e as primeiras 20 pessoas."""
    _pode()
    return destinatarios.contagem(_regras_de(regras), logica if logica in ("Todas", "Qualquer") else "Todas",
                                  marca or None, assunto or None)


@frappe.whitelist()
def lista() -> list:
    _pode()
    base = destinatarios.contactaveis()
    saida = []
    for s in frappe.get_all("Segmento de Marketing", fields=["name", "descricao", "logica", "marcador_auto", "modified"],
                            order_by="modified desc"):
        regras, logica = destinatarios._regras(s.name)
        saida.append({**s, "regras": regras, "podem_receber": len(destinatarios.filtrar(base, regras, logica))})
    return saida


@frappe.whitelist()
def obter(nome: str) -> dict:
    _pode()
    d = frappe.get_doc("Segmento de Marketing", nome)
    return {"nome": d.name, "descricao": d.descricao, "logica": d.get("logica") or "Todas",
            "marcador_auto": d.get("marcador_auto"),
            "regras": [{"regra": r.regra, "valor": r.valor, "negar": cint(r.get("negar"))} for r in d.regras]}


@frappe.whitelist()
def guardar(nome: str, regras="[]", logica="Todas", descricao=None, marcador_auto=None, antigo=None) -> dict:
    """Cria ou actualiza um segmento (`antigo` = nome actual, para mudar o nome)."""
    if not frappe.has_permission("Segmento de Marketing", "write"):
        frappe.throw(_("Sem permissão para gravar segmentos."), frappe.PermissionError)
    nome = (nome or "").strip()[:140]
    if not nome:
        frappe.throw(_("Falta o nome do segmento."))
    if antigo and antigo != nome and frappe.db.exists("Segmento de Marketing", antigo):
        frappe.rename_doc("Segmento de Marketing", antigo, nome)
    d = frappe.get_doc("Segmento de Marketing", nome) if frappe.db.exists("Segmento de Marketing", nome) else \
        frappe.new_doc("Segmento de Marketing")
    d.nome = nome
    d.descricao = descricao
    d.logica = logica if logica in ("Todas", "Qualquer") else "Todas"
    d.marcador_auto = (marcador_auto or "").strip()[:140] or None
    d.set("regras", _regras_de(regras))
    d.save()
    if d.marcador_auto:
        frappe.enqueue("orbit.marketing.segmentos.marcadores_automaticos", queue="short", enqueue_after_commit=True)
    return obter(d.name)


@frappe.whitelist()
def apagar(nome: str) -> dict:
    if not frappe.has_permission("Segmento de Marketing", "delete"):
        frappe.throw(_("Sem permissão."), frappe.PermissionError)
    usado = frappe.get_all("Segmento da Campanha", filters={"segmento": nome}, pluck="parent", limit=3)
    if usado:
        frappe.throw(_("Está em uso nas campanhas {0}.").format(", ".join(usado)))
    frappe.delete_doc("Segmento de Marketing", nome)
    return {"ok": True}


# ── Marcadores ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def marcadores() -> dict:
    """Os marcadores em uso, com quantos contactos/leads/organizações têm cada um."""
    conta: dict = {}
    for dt in DOCTYPES:
        if not frappe.db.exists("DocType", dt):
            continue
        for t in frappe.db.sql_list(f"SELECT _user_tags FROM `tab{dt}` WHERE COALESCE(_user_tags, '') <> ''"):
            for m in {x.strip() for x in (t or "").split(",") if x.strip()}:
                conta.setdefault(m, {"marcador": m, "contactos": 0, "leads": 0, "organizacoes": 0})
                conta[m][{"Contact": "contactos", "CRM Lead": "leads", "CRM Organization": "organizacoes"}[dt]] += 1
    return {"marcadores": sorted(conta.values(), key=lambda x: x["marcador"].lower())}


def _por(doctype: str, nome: str, marcador: str, tirar: bool) -> bool:
    from frappe.desk.doctype.tag.tag import DocTags
    actuais = {x.strip() for x in (frappe.db.get_value(doctype, nome, "_user_tags") or "").split(",") if x.strip()}
    if tirar:
        if marcador not in actuais:
            return False
        DocTags(doctype).remove(nome, marcador)
    else:
        if marcador in actuais:
            return False
        DocTags(doctype).add(nome, marcador)
    return True


@frappe.whitelist()
def marcar(doctype: str, nomes="[]", marcador: str = "", tirar: int = 0) -> dict:
    """Pôr (ou tirar) um marcador em vários registos de uma vez — ficha, «Marcar…» nas listas e importação."""
    if doctype not in DOCTYPES:
        frappe.throw(_("Os marcadores são para contactos, leads e organizações."))
    marcador = (marcador or "").strip().replace(",", " ")[:140]
    if not marcador:
        frappe.throw(_("Falta o marcador."))
    nomes = json.loads(nomes) if isinstance(nomes, str) else (nomes or [])
    if len(nomes) > 5000:
        frappe.throw(_("No máximo 5 000 de cada vez."))
    n = 0
    for nome in nomes:
        if frappe.has_permission(doctype, "write", nome) and _por(doctype, nome, marcador, bool(cint(tirar))):
            n += 1
    return {"mudados": n, "marcador": marcador}


@frappe.whitelist()
def do_registo(doctype: str, nome: str) -> list:
    frappe.has_permission(doctype, "read", nome, throw=True)
    return [x.strip() for x in (frappe.db.get_value(doctype, nome, "_user_tags") or "").split(",") if x.strip()]


def marcadores_automaticos() -> None:
    """De hora a hora: quem cumprir as regras de um segmento com «Pôr o marcador» ganha-o. Sobre todos os registos
    (também quem não pode receber — o marcador é para ver e filtrar, não para enviar). Nunca tira."""
    if not frappe.db.exists("DocType", "Segmento de Marketing") or \
            not frappe.get_meta("Segmento de Marketing").has_field("marcador_auto"):
        return
    segs = frappe.get_all("Segmento de Marketing", filters={"marcador_auto": ("is", "set")}, pluck="name")
    if not segs:
        return
    todos = destinatarios._registos(True)
    for s in segs:
        try:
            marcador = frappe.db.get_value("Segmento de Marketing", s, "marcador_auto").strip()
            regras, logica = destinatarios._regras(s)
            if not regras:
                continue  # sem regras seria toda a gente — não se marca a base inteira por engano
            for r in destinatarios.filtrar(todos, regras, logica):
                if marcador.lower() not in (r.get("marcadores") or set()):
                    _por(r["doctype"], r["name"], marcador, False)
            frappe.db.commit()
        except Exception:  # noqa: BLE001
            frappe.db.rollback()
            frappe.log_error(title=f"Marketing: marcador automático ({s})", message=frappe.get_traceback())


def converter_segmento_texto() -> None:
    """S8 (after_migrate): o «Segmento» em texto livre da ficha passa a marcador e o campo fica escondido."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    for dt in ("Contact", "CRM Lead"):
        if not (frappe.db.exists("DocType", dt) and frappe.get_meta(dt).has_field("mkt_segmento")):
            continue
        for r in frappe.get_all(dt, filters={"mkt_segmento": ("is", "set")}, fields=["name", "mkt_segmento"],
                                limit_page_length=0):
            for m in [x.strip() for x in (r.mkt_segmento or "").split(",") if x.strip()]:
                _por(dt, r.name, m[:140], False)
            frappe.db.set_value(dt, r.name, "mkt_segmento", None, update_modified=False)
        if not frappe.db.exists("Property Setter", {"doc_type": dt, "field_name": "mkt_segmento", "property": "hidden"}):
            make_property_setter(dt, "mkt_segmento", "hidden", 1, "Check")
        nome = f"{dt}-Side Panel"
        if frappe.db.exists("DocType", "CRM Fields Layout") and frappe.db.exists("CRM Fields Layout", nome):
            doc = frappe.get_doc("CRM Fields Layout", nome)
            layout = json.loads(doc.layout or "[]")
            mudou = False
            for sec in layout:
                for col in sec.get("columns") or []:
                    if "mkt_segmento" in (col.get("fields") or []):
                        col["fields"] = [f for f in col["fields"] if f != "mkt_segmento"]
                        mudou = True
            if mudou:
                doc.layout = json.dumps(layout)
                doc.save(ignore_permissions=True)
    frappe.db.commit()
