"""Vistas guardadas, filtros à escolha, colunas, ações em massa e exportar (H7 do plano da interface única, 20-11-2026).

* Filtros: só sobre campos de uma lista branca por lista (`FILTRAVEIS`), com operadores conhecidos — nada vindo do
  browser vai cru para a consulta. Tudo por `frappe.get_list` (permissões da pessoa).
* Vistas: guardadas por pessoa nas preferências do Frappe (`frappe.defaults`, chave `orbit_vistas_<lista>`); as
  partilhadas com a equipa numa chave global (`orbit_vistas_eq_<lista>`) — partilha quem pode escrever nessa lista.
* Ações em massa: atribuir responsável, mudar fase/estado/ciclo de vida, apagar — registo a registo com `doc.save()` /
  `frappe.delete_doc` (as permissões e os ganchos de cada um valem, ex.: apagar a lead apaga o que é dela).
* Exportar: CSV (separador «;», UTF-8 com BOM para o Excel) com as colunas da vista, até 10 000 linhas.
"""
from __future__ import annotations

import csv
import io
import json

import frappe

OPS = {"igual": "=", "diferente": "!=", "contem": "like", "vazio": "is", "preenchido": "is", "maior": ">", "menor": "<",
       "depois": ">", "antes": "<"}

# lista → [(campo, rótulo, tipo, origem das opções)]
FILTRAVEIS = {
    "contactos": [("_user_tags", "Marcador", "texto", None), ("orbit_responsavel", "Responsável", "user", None), ("orbit_ciclo", "Fase do ciclo de vida", "select", None),
                  ("origem", "Origem", "link", "CRM Lead Source"), ("company_name", "Empresa", "texto", None),
                  ("email_id", "Email", "texto", None), ("mkt_estado", "Marketing por email", "select", None),
                  ("orbit_ultima_atividade", "Última atividade", "data", None), ("creation", "Criado", "data", None)],
    "empresas": [("_user_tags", "Marcador", "texto", None), ("orbit_responsavel", "Responsável", "user", None), ("orbit_ciclo", "Fase do ciclo de vida", "select", None),
                 ("industry", "Setor", "link", "CRM Industry"), ("territory", "Território", "link", "CRM Territory"),
                 ("tipo_conta", "Tipo de conta", "select", None), ("estado_conta", "Estado da conta", "select", None),
                 ("marca", "Marca", "link", "Brand"), ("orbit_ultima_atividade", "Última atividade", "data", None),
                 ("creation", "Criado", "data", None)],
    "negocios": [("deal_owner", "Responsável", "user", None), ("status", "Fase", "link", "CRM Deal Status"),
                 ("source", "Origem", "link", "CRM Lead Source"), ("marca", "Marca", "link", "Brand"),
                 ("organization", "Empresa", "texto", None), ("deal_value", "Valor", "numero", None),
                 ("expected_closure_date", "Fecho previsto", "data", None), ("orbit_ultima_atividade", "Última atividade", "data", None),
                 ("creation", "Criado", "data", None)],
    "leads": [("_user_tags", "Marcador", "texto", None), ("lead_owner", "Responsável", "user", None), ("status", "Estado", "link", "CRM Lead Status"),
              ("source", "Origem", "link", "CRM Lead Source"), ("organization", "Empresa", "texto", None),
              ("marca", "Marca", "link", "Brand"), ("orbit_ultima_atividade", "Última atividade", "data", None),
              ("creation", "Criado", "data", None)],
}
COLUNAS = {
    "contactos": [("full_name", "Nome"), ("company_name", "Empresa"), ("marcas", "Marcas"), ("email_id", "Email"), ("mobile_no", "Telemóvel"),
                  ("phone", "Telefone"), ("designation", "Cargo"), ("nif", "NIF"), ("orbit_ciclo", "Fase"), ("orbit_responsavel", "Responsável"),
                  ("origem", "Origem"), ("mkt_estado", "Marketing"), ("orbit_ultima_atividade", "Última atividade"), ("creation", "Criado")],
    "empresas": [("organization_name", "Empresa"), ("website", "Site"), ("telefone", "Telefone"), ("email_geral", "Email"),
                 ("nipc", "NIPC"), ("marca", "Marca"), ("industry", "Setor"), ("territory", "Território"), ("orbit_ciclo", "Fase"),
                 ("orbit_responsavel", "Responsável"), ("tipo_conta", "Tipo"), ("estado_conta", "Estado"),
                 ("orbit_ultima_atividade", "Última atividade"), ("creation", "Criado")],
    "negocios": [("titulo", "Negócio"), ("organization", "Empresa"), ("status", "Fase"), ("deal_value", "Valor"),
                 ("probability", "Probabilidade"), ("expected_closure_date", "Fecho previsto"), ("deal_owner", "Responsável"),
                 ("source", "Origem"), ("marca", "Marca"), ("email", "Email"), ("orbit_ultima_atividade", "Última atividade"),
                 ("creation", "Criado")],
    "leads": [("lead_name", "Nome"), ("organization", "Empresa"), ("email", "Email"), ("mobile_no", "Telemóvel"),
              ("status", "Estado"), ("source", "Origem"), ("lead_owner", "Responsável"), ("marca", "Marca"),
              ("orbit_ultima_atividade", "Última atividade"), ("creation", "Criado")],
}


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def colunas_personalizadas(objeto) -> list:
    """Os campos criados em Definições › Campos personalizados (orbit/interface/campos.py) — colunas e filtros."""
    from orbit.interface.campos import OBJETOS, personalizados
    dt = OBJETOS.get(objeto)
    if not dt or not frappe.db.exists("DocType", dt):
        return []
    out = []
    for f in personalizados(dt):
        tipo = {"Date": "data", "Float": "numero", "Int": "numero", "Currency": "numero", "Select": "select",
                "Check": "select"}.get(f.fieldtype, "texto")
        opcoes = None
        if f.fieldtype == "Select":
            opcoes = [{"v": o, "r": o} for o in (f.options or "").split("\n") if o]
        elif f.fieldtype == "Check":
            opcoes = [{"v": "1", "r": "Sim"}, {"v": "0", "r": "Não"}]
        out.append({"campo": f.fieldname, "rotulo": f.label, "tipo": tipo, "opcoes": opcoes})
    return out


def _dt(objeto):
    from orbit.interface.api import _LISTAS
    if objeto not in _LISTAS:
        frappe.throw("Lista desconhecida")
    return _LISTAS[objeto]["dt"]


def traduzir(objeto: str, filtros) -> list:
    """[[campo, op, valor], …] do browser → filtros do Frappe, só com campos e operadores conhecidos."""
    if isinstance(filtros, str):
        filtros = json.loads(filtros or "[]")
    meta = frappe.get_meta(_dt(objeto))
    ok = {c for c, *_ in FILTRAVEIS.get(objeto, [])} | {c["campo"] for c in colunas_personalizadas(objeto)}
    out = []
    for f in (filtros or [])[:12]:
        if not isinstance(f, (list, tuple)) or len(f) < 2:
            continue
        campo, op = f[0], f[1]
        valor = f[2] if len(f) > 2 else None
        if campo not in ok or op not in OPS or not (meta.has_field(campo) or campo in ("creation", "_user_tags")):
            continue
        if op == "vazio":
            out.append([campo, "is", "not set"])
        elif op == "preenchido":
            out.append([campo, "is", "set"])
        elif op == "contem":
            out.append([campo, "like", f"%{str(valor or '')[:100]}%"])
        else:
            out.append([campo, OPS[op], str(valor or "")[:100]])
    return out


@frappe.whitelist()
def metadados(objeto: str):
    _guarda()
    dt = _dt(objeto)
    meta = frappe.get_meta(dt)
    from orbit.interface.api import _rotulo_estado, _nome_user
    campos = []
    for campo, rot, tipo, origem in FILTRAVEIS.get(objeto, []):
        if not (meta.has_field(campo) or campo in ("creation", "_user_tags")):
            continue
        opcoes = None
        if tipo == "user":
            us = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
                                pluck="name")
            opcoes = [{"v": u, "r": _nome_user(u)} for u in us]
        elif tipo == "select":
            opcoes = [{"v": o, "r": o} for o in (meta.get_field(campo).options or "").split("\n") if o]
        elif tipo == "link" and origem and frappe.db.exists("DocType", origem):
            opcoes = [{"v": o, "r": _rotulo_estado(o)} for o in frappe.get_all(origem, pluck="name", limit=300)]
        campos.append({"campo": campo, "rotulo": rot, "tipo": tipo, "opcoes": opcoes})
    pers = colunas_personalizadas(objeto)
    campos += pers
    colunas = [{"campo": c, "rotulo": r} for c, r in COLUNAS.get(objeto, []) if meta.has_field(c) or c == "creation"]
    colunas += [{"campo": c["campo"], "rotulo": c["rotulo"]} for c in pers]
    from orbit.interface.marcas import lista as _marcas
    tem_marca = meta.has_field("marcas" if objeto == "contactos" else "marca")
    return {"filtraveis": campos, "colunas": colunas, "marcas": _marcas() if tem_marca else [], "pode_partilhar": frappe.has_permission(dt, "write"),
            "pode_apagar": frappe.has_permission(dt, "delete"), "pode_editar": frappe.has_permission(dt, "write")}


def _chave(objeto, partilhada=False):
    return f"orbit_vistas_{'eq_' if partilhada else ''}{objeto}"


def _ler(chave, global_=False):
    v = frappe.defaults.get_global_default(chave) if global_ else frappe.defaults.get_user_default(chave)
    try:
        return json.loads(v) if v else []
    except ValueError:
        return []


@frappe.whitelist()
def vistas(objeto: str):
    _guarda()
    _dt(objeto)
    minhas = [{**v, "partilhada": False} for v in _ler(_chave(objeto))]
    eq = [{**v, "partilhada": True} for v in _ler(_chave(objeto, True), True)]
    return minhas + eq


@frappe.whitelist(methods=["POST"])
def guardar_vista(objeto: str, nome: str, config: str, partilhada: int = 0):
    _guarda()
    dt = _dt(objeto)
    nome = (nome or "").strip()[:60]
    if not nome:
        frappe.throw("Dê um nome à vista.")
    cfg = json.loads(config or "{}")
    cfg = {"filtros": cfg.get("filtros") or [], "colunas": [c for c in (cfg.get("colunas") or []) if isinstance(c, str)][:12],
           "ordem": str(cfg.get("ordem") or "")[:60], "base": str(cfg.get("base") or "todos")[:20]}
    traduzir(objeto, cfg["filtros"])  # valida
    if int(partilhada):
        if not frappe.has_permission(dt, "write"):
            frappe.throw("Sem permissão para partilhar vistas.", frappe.PermissionError)
        lst = [v for v in _ler(_chave(objeto, True), True) if v.get("nome") != nome]
        lst.append({"nome": nome, "config": cfg, "por": frappe.session.user})
        frappe.defaults.set_global_default(_chave(objeto, True), json.dumps(lst[-30:]))
    else:
        lst = [v for v in _ler(_chave(objeto)) if v.get("nome") != nome]
        lst.append({"nome": nome, "config": cfg})
        frappe.defaults.set_user_default(_chave(objeto), json.dumps(lst[-30:]))
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def apagar_vista(objeto: str, nome: str, partilhada: int = 0):
    _guarda()
    dt = _dt(objeto)
    if int(partilhada):
        if not frappe.has_permission(dt, "write"):
            frappe.throw("Sem permissão.", frappe.PermissionError)
        frappe.defaults.set_global_default(_chave(objeto, True), json.dumps([v for v in _ler(_chave(objeto, True), True) if v.get("nome") != nome]))
    else:
        frappe.defaults.set_user_default(_chave(objeto), json.dumps([v for v in _ler(_chave(objeto)) if v.get("nome") != nome]))
    return {"ok": True}


_ACOES = {
    "responsavel": {"contactos": "orbit_responsavel", "empresas": "orbit_responsavel", "negocios": "deal_owner", "leads": "lead_owner"},
    "estado": {"negocios": "status", "leads": "status"},
    "ciclo": {"contactos": "orbit_ciclo", "empresas": "orbit_ciclo"},
}


@frappe.whitelist(methods=["POST"])
def em_massa(objeto: str, nomes: str, acao: str, valor: str = None):
    _guarda()
    dt = _dt(objeto)
    lista = [n for n in json.loads(nomes or "[]") if isinstance(n, str)][:500]
    feitos, falhas = 0, []
    for n in lista:
        try:
            if acao == "apagar":
                frappe.delete_doc(dt, n)
            else:
                campo = _ACOES.get(acao, {}).get(objeto)
                if not campo:
                    frappe.throw("Ação desconhecida")
                d = frappe.get_doc(dt, n)
                d.set(campo, valor or None)
                d.save()
            feitos += 1
        except frappe.PermissionError:
            falhas.append(f"{n}: sem permissão")
        except frappe.LinkExistsError:
            falhas.append(f"{n}: está em uso")
        except Exception as e:  # noqa: BLE001
            falhas.append(f"{n}: {str(e)[:80]}")
    return {"feitos": feitos, "falhas": falhas[:20]}


@frappe.whitelist()
def exportar(objeto: str, vista: str = "todos", q: str = "", filtros: str = "", colunas: str = "", nomes: str = ""):
    _guarda()
    from orbit.interface.api import _LISTAS, _nome_user, _rotulo_estado
    dt = _dt(objeto)
    meta = frappe.get_meta(dt)
    disp = dict(COLUNAS.get(objeto, []))
    cols = [c for c in (json.loads(colunas) if colunas else [c for c, _ in COLUNAS.get(objeto, [])]) if c in disp and (meta.has_field(c) or c == "creation")]
    f = traduzir(objeto, filtros)
    cfg = _LISTAS[objeto]
    if cfg.get("base"):
        f += [[k, "=", v] for k, v in cfg["base"].items()]
    sel = [n for n in json.loads(nomes or "[]") if isinstance(n, str)]
    if sel:
        f.append(["name", "in", sel[:5000]])
    q = (q or "").strip()
    or_f = [[c, "like", f"%{q}%"] for c in cfg["pesquisa"]] if q else None
    linhas = frappe.get_list(dt, filters=f, or_filters=or_f, fields=["name"] + cols, limit=10000, order_by="modified desc")
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["ID"] + [disp[c] for c in cols])
    for l in linhas:
        linha = [l.name]
        for c in cols:
            v = l.get(c)
            if c in ("orbit_responsavel", "deal_owner", "lead_owner") and v:
                v = _nome_user(v)
            elif c == "status" and v:
                v = _rotulo_estado(v)
            linha.append("" if v is None else str(v))
        w.writerow(linha)
    frappe.local.response.filename = f"{objeto}-{frappe.utils.nowdate()}.csv"
    frappe.local.response.filecontent = "﻿" + buf.getvalue()
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "attachment"
