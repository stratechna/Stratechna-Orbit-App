"""Definições › CRM › Funis (27-11-2026, docs/PLANO-FUNIS-CRM-ORBIT.md §2.3; motor em orbit/funis.py).

Só administradores do tenant (System Manager) criam, mudam e apagam funis e fases (F5). Ler: quem vê o CRM.
Cada funil precisa sempre de pelo menos uma fase aberta, uma de ganho e uma de perda.
"""
from __future__ import annotations

import json

import frappe
from frappe.utils import cint, flt

from orbit import funis as F

TIPOS = [{"v": "Open", "r": "Aberta"}, {"v": "Ongoing", "r": "Em curso"}, {"v": "On Hold", "r": "Em pausa"},
         {"v": "Won", "r": "Ganho"}, {"v": "Lost", "r": "Perdido"}]
CORES = ["gray", "blue", "cyan", "teal", "green", "amber", "yellow", "orange", "red", "pink", "violet", "purple", "black"]

# F7: modelos de partida (fase, tipo, probabilidade, cor) — editáveis depois de criados
MODELOS = {
    "vendas": ("Vendas", True, [("Qualificação", "Open", 10, "gray"), ("Proposta", "Ongoing", 40, "blue"),
                                ("Negociação", "Ongoing", 70, "amber"), ("Ganho", "Won", 100, "green"),
                                ("Perdido", "Lost", 0, "red")]),
    "compras": ("Compras", True, [("Pedir preços", "Open", 10, "gray"), ("Cotações recebidas", "Ongoing", 40, "blue"),
                                  ("Em negociação", "Ongoing", 70, "amber"), ("Adjudicado", "Won", 100, "green"),
                                  ("Desistido", "Lost", 0, "red")]),
    "parcerias": ("Parcerias", False, [("Identificada", "Open", 10, "gray"), ("Primeiro contacto", "Ongoing", 30, "blue"),
                                       ("Em conversa", "Ongoing", 60, "amber"), ("Acordo assinado", "Won", 100, "green"),
                                       ("Sem acordo", "Lost", 0, "red")]),
    "recrutamento": ("Recrutamento", False, [("Candidatura", "Open", 10, "gray"), ("Entrevista", "Ongoing", 40, "blue"),
                                             ("Proposta feita", "Ongoing", 80, "amber"), ("Contratado", "Won", 100, "green"),
                                             ("Não seguiu", "Lost", 0, "red")]),
    "projetos": ("Projetos e obras", True, [("Pedido", "Open", 10, "gray"), ("Visita / levantamento", "Ongoing", 25, "cyan"),
                                            ("Orçamento enviado", "Ongoing", 50, "blue"), ("Em decisão", "Ongoing", 75, "amber"),
                                            ("Adjudicado", "Won", 100, "green"), ("Não adjudicado", "Lost", 0, "red")]),
    "branco": ("", True, [("Em curso", "Open", 10, "gray"), ("Ganho", "Won", 100, "green"), ("Perdido", "Lost", 0, "red")]),
}
ROTULO_MODELO = {"vendas": "Vendas", "compras": "Compras / fornecedores", "parcerias": "Parcerias",
                 "recrutamento": "Recrutamento", "projetos": "Projetos / obras", "branco": "Em branco"}


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _admin():
    _guarda()
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Só os administradores do Orbit criam e mudam funis.", frappe.PermissionError)


def _rot(nome):
    from orbit.interface.api import _rotulo_estado
    return _rotulo_estado(nome)


@frappe.whitelist()
def listar():
    _guarda()
    from orbit.interface.marcas import lista as marcas
    abertos = {r[0]: cint(r[1]) for r in frappe.db.sql(
        "select status, count(*) from `tabCRM Deal` group by status")}
    out = []
    for f in frappe.get_all(F.DT, fields=["name", "por_omissao", "mostra_valor", "desligado", "ordem", "cor", "descricao"],
                            order_by="ordem asc, name asc"):
        fs = F.fases(f.name)
        f.marcas = frappe.get_all("Marca do Contacto", filters={"parent": f.name, "parenttype": F.DT}, pluck="marca")
        f.fases = [{"name": s.name, "rotulo": _rot(s.name), "tipo": s.type, "cor": s.color, "probabilidade": flt(s.probability),
                    "n": abertos.get(s.name, 0)} for s in fs]
        f.abertos = sum(x["n"] for x in f.fases if x["tipo"] not in F.FECHADOS)
        f.total = sum(x["n"] for x in f.fases)
        out.append(f)
    return {"funis": out, "tipos": TIPOS, "cores": CORES, "pode": "System Manager" in frappe.get_roles(),
            "modelos": [{"v": k, "r": ROTULO_MODELO[k], "fases": [x[0] for x in MODELOS[k][2]]} for k in MODELOS],
            "marcas": [m if isinstance(m, str) else (m.get("name") or m.get("marca")) for m in (marcas() or [])]}


def _nova_fase(funil, rotulo, tipo, prob=0, cor="gray"):
    rotulo = (rotulo or "").strip()
    if not rotulo:
        frappe.throw("Escreva o nome da fase.")
    if tipo not in [t["v"] for t in TIPOS]:
        frappe.throw("Tipo de fase desconhecido.")
    nome = f"{funil} · {rotulo}"[:140]
    if frappe.db.exists("CRM Deal Status", nome):
        frappe.throw(f"Já existe a fase «{rotulo}» neste funil.")
    pos = (frappe.db.sql("select max(position) from `tabCRM Deal Status`")[0][0] or 0) + 1
    d = frappe.get_doc({"doctype": "CRM Deal Status", "deal_status": nome, "type": tipo, "probability": prob,
                        "color": cor if cor in CORES else "gray", "position": pos, "orbit_funil": funil,
                        "orbit_rotulo": rotulo})
    d.insert(ignore_permissions=True)
    return d.name


@frappe.whitelist(methods=["POST"])
def criar(nome: str, modelo: str = "branco", marcas: str = "[]", mostra_valor: int = None):
    _admin()
    nome = (nome or "").strip()
    if not nome:
        frappe.throw("Escreva o nome do funil.")
    if frappe.db.exists(F.DT, nome):
        frappe.throw("Já existe um funil com esse nome.")
    _n, valor, fases = MODELOS.get(modelo) or MODELOS["branco"]
    f = frappe.get_doc({"doctype": F.DT, "nome": nome, "modelo": modelo,
                        "mostra_valor": cint(valor if mostra_valor in (None, "") else mostra_valor),
                        "ordem": (frappe.db.sql(f"select max(ordem) from `tab{F.DT}`")[0][0] or 0) + 1,
                        "marcas": [{"marca": m} for m in json.loads(marcas or "[]") if frappe.db.exists("Brand", m)]})
    f.insert()
    for rotulo, tipo, prob, cor in fases:
        _nova_fase(f.name, rotulo, tipo, prob, cor)
    F._esquecer()
    return {"ok": True, "nome": f.name}


@frappe.whitelist(methods=["POST"])
def gravar(nome: str, dados: str):
    _admin()
    d = json.loads(dados) if isinstance(dados, str) else dados
    f = frappe.get_doc(F.DT, nome)
    for k in ("por_omissao", "mostra_valor", "desligado"):
        if k in d:
            f.set(k, cint(d[k]))
    if "descricao" in d:
        f.descricao = d["descricao"]
    if "marcas" in d:
        f.set("marcas", [{"marca": m} for m in d["marcas"] if frappe.db.exists("Brand", m)])
    f.save()
    novo = (d.get("nome") or "").strip()
    if novo and novo != nome:
        if frappe.db.exists(F.DT, novo):
            frappe.throw("Já existe um funil com esse nome.")
        frappe.rename_doc(F.DT, nome, novo, merge=False)   # os negócios e as fases seguem (ligações)
        frappe.db.set_value(F.DT, novo, "nome", novo)
        nome = novo
    F._esquecer()
    return {"ok": True, "nome": nome}


@frappe.whitelist(methods=["POST"])
def ordenar(nomes: str):
    _admin()
    for i, n in enumerate(json.loads(nomes), start=1):
        frappe.db.set_value(F.DT, n, "ordem", i)
    _reposicionar()
    return {"ok": True}


def _reposicionar(funil=None, ordem=None):
    """Posições das fases em blocos por funil (o /crm original mostra-as por esta ordem)."""
    pos = 1
    for f in frappe.get_all(F.DT, pluck="name", order_by="ordem asc, name asc"):
        nomes = ordem if (funil == f and ordem) else [s.name for s in F.fases(f)]
        for n in nomes:
            frappe.db.set_value("CRM Deal Status", n, "position", pos, update_modified=False)
            pos += 1
    F._esquecer()


def _verificar_minimo(funil, sem=None, tipo_novo=None):
    """`sem` sai (apagar) ou muda para `tipo_novo`; o funil tem de ficar com aberta + ganho + perda."""
    tipos = []
    for s in F.fases(funil):
        if s.name == sem:
            if tipo_novo:
                tipos.append(tipo_novo)
            continue
        tipos.append(s.type)
    if not any(t not in F.FECHADOS for t in tipos):
        frappe.throw("O funil precisa de pelo menos uma fase aberta.")
    if "Won" not in tipos:
        frappe.throw("O funil precisa de uma fase de ganho.")
    if "Lost" not in tipos:
        frappe.throw("O funil precisa de uma fase de perda.")


@frappe.whitelist(methods=["POST"])
def apagar(nome: str, passar_para: str = ""):
    """Sem negócios: apaga o funil e as fases. Com negócios: só passando-os para outro funil (ou desligar)."""
    _admin()
    if cint(frappe.db.get_value(F.DT, nome, "por_omissao")):
        frappe.throw("O funil por omissão não se apaga. Escolha outro como «por omissão» primeiro.")
    fases = [s.name for s in F.fases(nome)]
    negocios = frappe.get_all("CRM Deal", filters={"orbit_funil": nome}, pluck="name", limit_page_length=0)
    if negocios:
        if not passar_para or not frappe.db.exists(F.DT, passar_para) or passar_para == nome:
            frappe.throw(f"Este funil tem {len(negocios)} negócio(s). Escolha para onde passam, ou desligue o funil.")
        for n in negocios:
            d = frappe.get_doc("CRM Deal", n)
            d.orbit_funil = passar_para
            d.flags.ignore_permissions = True
            d.save()
    for s in fases:
        if frappe.db.count("CRM Deal", {"status": s}):
            frappe.throw(f"A fase «{_rot(s)}» ainda tem negócios.")
    for s in fases:
        frappe.delete_doc("CRM Deal Status", s, ignore_permissions=True)
    frappe.delete_doc(F.DT, nome)
    F._esquecer()
    return {"ok": True, "passaram": len(negocios)}


@frappe.whitelist(methods=["POST"])
def fase_criar(funil: str, rotulo: str, tipo: str = "Ongoing", cor: str = "gray", probabilidade: float = 0):
    _admin()
    if not frappe.db.exists(F.DT, funil):
        frappe.throw("Funil desconhecido.")
    n = _nova_fase(funil, rotulo, tipo, flt(probabilidade), cor)
    # nova fase aberta entra antes das de ganho/perda
    fs = F.fases(funil)
    abertas = [s.name for s in fs if s.type not in F.FECHADOS and s.name != n]
    fecho = [s.name for s in fs if s.type in F.FECHADOS and s.name != n]
    _reposicionar(funil, abertas + [n] + fecho if tipo not in F.FECHADOS else abertas + fecho + [n])
    return {"ok": True, "nome": n}


@frappe.whitelist(methods=["POST"])
def fase_gravar(nome: str, dados: str):
    _admin()
    d = json.loads(dados) if isinstance(dados, str) else dados
    s = frappe.get_doc("CRM Deal Status", nome)
    if d.get("tipo") and d["tipo"] != s.type:
        if d["tipo"] not in [t["v"] for t in TIPOS]:
            frappe.throw("Tipo de fase desconhecido.")
        _verificar_minimo(s.orbit_funil, sem=nome, tipo_novo=d["tipo"])
        s.type = d["tipo"]
    if "rotulo" in d and (d["rotulo"] or "").strip():
        s.orbit_rotulo = d["rotulo"].strip()
    if d.get("cor") in CORES:
        s.color = d["cor"]
    if "probabilidade" in d:
        s.probability = flt(d["probabilidade"])
    s.save(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def fase_apagar(nome: str):
    _admin()
    s = frappe.get_doc("CRM Deal Status", nome)
    n = frappe.db.count("CRM Deal", {"status": nome})
    if n:
        frappe.throw(f"Há {n} negócio(s) nesta fase. Mude-os de fase primeiro.")
    _verificar_minimo(s.orbit_funil, sem=nome)
    try:
        frappe.delete_doc("CRM Deal Status", nome, ignore_permissions=True)
    except frappe.LinkExistsError:
        frappe.throw("Esta fase está em uso (fluxos, segmentos ou registos antigos) — não se pode apagar.")
    F._esquecer()
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def fases_ordenar(funil: str, nomes: str):
    _admin()
    nomes = json.loads(nomes)
    certas = {s.name for s in F.fases(funil)}
    if set(nomes) != certas:
        frappe.throw("A lista de fases não corresponde ao funil.")
    _reposicionar(funil, nomes)
    return {"ok": True}
