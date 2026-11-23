"""Ecrã Definições › CRM › Fluxos (23-11-2026). Só System Manager. Motor em orbit/fluxos.py."""
from __future__ import annotations

import json

import frappe
from frappe import _

GATILHOS = [("criado", "Quando é criado"), ("campo_muda", "Quando um campo muda"), ("sem_atividade", "Dias sem atividade"),
            ("data", "Dias depois de uma data"), ("email_recebido", "Quando chega um email")]
ACOES = [("atribuir", "Atribuir responsável"), ("tarefa", "Criar tarefa"), ("aviso", "Avisar no sino"),
         ("email", "Enviar email de modelo"), ("mudar", "Mudar um campo")]
OPS = [("igual", "é"), ("diferente", "não é"), ("em", "é um de"), ("nao_em", "não é nenhum de"), ("contem", "contém"),
       ("vazio", "está vazio"), ("preenchido", "está preenchido"), ("maior", "maior que"), ("menor", "menor que")]
NOMES = {"CRM Lead": "Leads", "CRM Deal": "Negócios", "Contact": "Contactos", "CRM Organization": "Empresas", "HD Ticket": "Tickets"}
_TIPOS = ("Data", "Select", "Link", "Check", "Int", "Float", "Currency", "Percent", "Date", "Datetime", "Small Text")


def _guarda():
    from orbit.interface.api import _guarda as g
    g()
    frappe.only_for("System Manager")


def _resumo(f) -> dict:
    g = dict(GATILHOS).get(f.gatilho, f.gatilho)
    if f.gatilho == "campo_muda":
        g = f"Quando «{f.campo}» passa a {f.valor or 'outro valor'}"
    elif f.gatilho in ("sem_atividade", "data"):
        g = f"{f.dias} dias " + ("sem atividade" if f.gatilho == "sem_atividade" else f"depois de «{f.campo or 'criação'}»")
    try:
        ac = [dict(ACOES).get(a.get("tipo"), a.get("tipo")) for a in json.loads(f.acoes or "[]")]
    except ValueError:
        ac = []
    n = frappe.db.count("Execucao do Fluxo", {"fluxo": f.name})
    return {"name": f.name, "titulo": f.titulo, "ativo": bool(f.ativo), "objeto": f.objeto, "objeto_nome": NOMES.get(f.objeto, f.objeto),
            "gatilho": g, "acoes": ac, "execucoes": n, "descricao": f.descricao, "modelo": f.modelo}


@frappe.whitelist()
def listar():
    _guarda()
    fs = frappe.get_all("Fluxo", fields=["name", "titulo", "ativo", "objeto", "gatilho", "campo", "valor", "dias", "acoes",
                                         "descricao", "modelo"], order_by="objeto asc, titulo asc")
    return [_resumo(frappe._dict(f)) for f in fs]


@frappe.whitelist()
def metadados():
    _guarda()
    campos = {}
    for dt in NOMES:
        if not frappe.db.exists("DocType", dt):
            continue
        m = frappe.get_meta(dt)
        lista = [{"campo": "creation", "rotulo": "Criado", "tipo": "Datetime", "opcoes": None}]
        for f in m.fields:
            if f.fieldtype not in _TIPOS or f.hidden:
                continue
            ops = None
            if f.fieldtype == "Select":
                ops = [o for o in (f.options or "").split("\n") if o]
            elif f.fieldtype == "Link" and f.options and f.options != "User":
                try:
                    if frappe.db.count(f.options) <= 200:
                        ops = frappe.get_all(f.options, pluck="name", limit=200)
                except Exception:
                    ops = None
            lista.append({"campo": f.fieldname, "rotulo": _(f.label or f.fieldname), "tipo": f.fieldtype, "opcoes": ops,
                          "utilizador": f.fieldtype == "Link" and f.options == "User"})
        if dt == "Contact":
            from orbit.interface.marcas import lista as marcas
            lista.append({"campo": "marca", "rotulo": "Marca (uma das marcas do contacto)", "tipo": "Select", "opcoes": marcas()})
        campos[dt] = sorted(lista, key=lambda x: x["rotulo"].lower())
    pessoas = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
                             fields=["name", "full_name"], order_by="full_name asc")
    return {"objetos": [{"v": k, "r": v} for k, v in NOMES.items() if frappe.db.exists("DocType", k)],
            "gatilhos": [{"v": k, "r": v} for k, v in GATILHOS], "acoes": [{"v": k, "r": v} for k, v in ACOES],
            "ops": [{"v": k, "r": v} for k, v in OPS], "campos": campos,
            "pessoas": [{"v": p.name, "r": p.full_name or p.name} for p in pessoas],
            "modelos_email": frappe.get_all("Email Template", pluck="name", order_by="name asc", limit=200)}


@frappe.whitelist()
def obter(nome: str):
    _guarda()
    f = frappe.get_doc("Fluxo", nome)
    d = f.as_dict()
    d["condicoes"] = json.loads(f.condicoes or "[]")
    d["acoes"] = json.loads(f.acoes or "[]")
    return d


@frappe.whitelist(methods=["POST"])
def gravar(dados: str):
    _guarda()
    d = json.loads(dados)
    if not (d.get("titulo") or "").strip() or d.get("objeto") not in NOMES or d.get("gatilho") not in dict(GATILHOS):
        frappe.throw("Dê um título e escolha o registo e o gatilho.")
    if d.get("gatilho") == "campo_muda" and not d.get("campo"):
        frappe.throw("Escolha o campo que faz disparar o fluxo.")
    if d.get("gatilho") in ("sem_atividade", "data") and int(d.get("dias") or 0) == 0:
        frappe.throw("Indique o número de dias.")
    for a in d.get("acoes") or []:
        if a.get("tipo") == "atribuir" and not a.get("pessoas"):
            frappe.throw("Escolha a quem atribuir.")
        if a.get("tipo") == "email" and not a.get("modelo"):
            frappe.throw("Escolha o modelo de email.")
    f = frappe.get_doc("Fluxo", d["name"]) if d.get("name") else frappe.new_doc("Fluxo")
    for k in ("titulo", "objeto", "gatilho", "campo", "valor", "descricao"):
        f.set(k, (d.get(k) or "").strip() if isinstance(d.get(k), str) else d.get(k))
    f.dias = int(d.get("dias") or 0)
    f.ativo = 1 if d.get("ativo") else 0
    f.condicoes = json.dumps(d.get("condicoes") or [], ensure_ascii=False)
    f.acoes = json.dumps(d.get("acoes") or [], ensure_ascii=False)
    f.save(ignore_permissions=True)
    return {"ok": True, "name": f.name}


@frappe.whitelist(methods=["POST"])
def ligar(nome: str, ativo: int):
    _guarda()
    f = frappe.get_doc("Fluxo", nome)
    if int(ativo):
        try:
            acoes = json.loads(f.acoes or "[]")
        except ValueError:
            acoes = []
        if any(a.get("tipo") == "atribuir" and not a.get("pessoas") for a in acoes):
            frappe.throw("Antes de ligar, escolha a quem este fluxo atribui (abra o fluxo).")
        if any(a.get("tipo") == "email" and not a.get("modelo") for a in acoes):
            frappe.throw("Antes de ligar, escolha o modelo de email (abra o fluxo).")
    f.ativo = 1 if int(ativo) else 0
    f.save(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def apagar(nome: str):
    _guarda()
    frappe.db.delete("Execucao do Fluxo", {"fluxo": nome})
    frappe.delete_doc("Fluxo", nome, ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist()
def registo(nome: str = ""):
    _guarda()
    filtros = {"fluxo": nome} if nome else {}
    linhas = frappe.get_all("Execucao do Fluxo", filters=filtros, fields=["fluxo", "ref_doctype", "ref_name", "ok", "resultado", "creation"],
                            order_by="creation desc", limit=100)
    titulos = {f.name: f.titulo for f in frappe.get_all("Fluxo", fields=["name", "titulo"])}
    for l in linhas:
        l.fluxo_titulo = titulos.get(l.fluxo, l.fluxo)
    return linhas
