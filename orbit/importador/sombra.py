"""Modo sombra do motor do importador no Orbit (21-11-2026, docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md F5.3).

O portal continua a mandar. Para os fornecedores em sombra, o portal envia ao Orbit (ponte `importador-sombra`):
  * `semear` — uma vez, o estado actual dos produtos do fornecedor (ponto de partida igual nos dois lados);
  * `push` — cada push real capturado, por ordem, com as regras do fornecedor tal como o portal as tem
    (o ctx do motor sem os `existentes`); o Orbit junta-lhe o SEU estado («Produto do Fornecedor»), corre o
    motor da F5.1 e grava o resultado;
  * `estado` — devolve o estado do Orbit, que o portal compara com o seu.
Nada disto chega às lojas nem ao inventário: é só para provar que o Orbit, como motor, chega ao mesmo sítio.
"""
import gzip
import json
import re
from datetime import datetime, timezone

import frappe

from orbit.importador import motor


def _dt(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v
    try:
        x = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _sem_fuso(v):
    x = _dt(v)
    return x.astimezone(timezone.utc).replace(tzinfo=None) if x else None


def _estado(fid: int) -> dict:
    out = {}
    for r in frappe.get_all("Produto do Fornecedor", filters={"fornecedor_id": fid}, fields=["produto_ref", "registo"],
                            limit_page_length=0):
        try:
            out[r.produto_ref] = json.loads(r.registo or "{}")
        except ValueError:
            continue
    return out


def _gravar(fid: int, regs: dict) -> int:
    """Grava os registos alterados (por referência). Escrita directa: não há regras de documento a correr."""
    n = 0
    for ref, reg in regs.items():
        chave = f"{fid}:{ref}"
        valores = {"registo": json.dumps(reg, ensure_ascii=False, default=str),
                   "hash_preco_stock": (reg.get("hash_preco_stock") or "")[:140],
                   "ausente_desde": _sem_fuso(reg.get("ausente_desde")), "actualizado_em": frappe.utils.now_datetime()}
        nome = frappe.db.get_value("Produto do Fornecedor", {"chave": chave}, "name")
        if nome:
            frappe.db.set_value("Produto do Fornecedor", nome, valores, update_modified=False)
        else:
            frappe.get_doc({"doctype": "Produto do Fornecedor", "fornecedor_id": fid, "produto_ref": ref[:140],
                            "chave": chave[:140], **valores}).insert(ignore_permissions=True)
        n += 1
    return n


def semear(dados: dict) -> dict:
    fid = int(dados["fid"])
    frappe.db.delete("Produto do Fornecedor", {"fornecedor_id": fid})
    n = _gravar(fid, {r["produto_ref"]: r for r in dados.get("produtos") or [] if r.get("produto_ref")})
    frappe.db.commit()
    return {"ok": True, "semeados": n}


def push(dados: dict) -> dict:
    """Um push real: o motor da F5.1 sobre o estado do Orbit, com as regras que o portal mandou."""
    fid = int(dados["fid"])
    ctx = dict(dados["ctx"])
    ctx["agora"] = _dt(ctx.get("agora")) or datetime.now(timezone.utc)
    estado = _estado(fid)
    ctx["existentes"] = estado
    linhas = motor.converter_linhas_push(dados.get("linhas") or [])
    finalizar, cobertura = motor.parametros_push(ctx.get("sync_run_id"), bool(dados.get("finalizar")),
                                                 bool(dados.get("cobertura_completa")))
    res = motor.normalizar(linhas, ctx, parcial=bool(dados.get("parcial")), finalizar=finalizar,
                           cobertura_completa=cobertura)
    mudou = {}
    for reg in res["linhas"]:
        junto = dict(estado.get(reg["produto_ref"]) or {})
        junto.update({k: v for k, v in reg.items() if k != "conteudo_mudou"})
        mudou[reg["produto_ref"]] = junto
    for ref in res["ausentes"]:
        base = mudou.get(ref) or estado.get(ref)
        if base is not None:
            mudou[ref] = motor.aplicar_ausencia(dict(base), ctx["agora"])
    n = _gravar(fid, mudou)
    frappe.db.commit()
    return {"ok": True, "gravados": n, "ausentes": len(res["ausentes"]),
            "resumo": {k: v for k, v in (res.get("resumo") or {}).items() if not isinstance(v, (list, dict))}}


def estado_ficheiro(fid: int, caminho: str) -> dict:
    if not re.fullmatch(r"/tmp/orbit-sombra-[A-Za-z0-9_-]+\.json\.gz", caminho or ""):
        return {"ok": False, "erro": "caminho inválido"}
    est = _estado(int(fid))
    with gzip.open(caminho, "wt", encoding="utf-8") as f:
        json.dump({"fid": int(fid), "produtos": est}, f, ensure_ascii=False, default=str)
    return {"ok": True, "produtos": len(est)}


def receber_ficheiro(acao: str, caminho: str) -> dict:
    """Para a ponte: o pedido (semear ou push) chega num ficheiro gzip de JSON no /tmp do contentor."""
    if acao not in ("semear", "push") or not re.fullmatch(r"/tmp/orbit-sombra-[A-Za-z0-9_-]+\.json\.gz", caminho or ""):
        return {"ok": False, "erro": "pedido inválido"}
    frappe.set_user("Administrator")
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        dados = json.load(f)
    return semear(dados) if acao == "semear" else push(dados)


# ── F5.4: o Orbit como motor (sem estado próprio) ──────────────────────────────────────────────────────
def calcular(dados: dict) -> dict:
    """Um push calculado pelo motor do Orbit com o estado que o PORTAL manda (`ctx.existentes`). Não grava nada:
    o portal grava o resultado nas suas tabelas, para que tudo o que vem depois (feed, Sync3, IA) fique igual."""
    ctx = dict(dados["ctx"])
    ctx["agora"] = _dt(ctx.get("agora")) or datetime.now(timezone.utc)
    linhas = motor.converter_linhas_push(dados.get("linhas") or [])
    finalizar, cobertura = motor.parametros_push(ctx.get("sync_run_id"), bool(dados.get("finalizar")),
                                                 bool(dados.get("cobertura_completa")))
    res = motor.normalizar(linhas, ctx, parcial=bool(dados.get("parcial")), finalizar=finalizar,
                           cobertura_completa=cobertura)
    return {"ok": True, "linhas": res["linhas"], "ausentes": res["ausentes"], "ignoradas": res["ignoradas"],
            "resumo": res["resumo"]}


def calcular_ficheiro(entrada: str, saida: str) -> dict:
    padrao = r"/tmp/orbit-sombra-[A-Za-z0-9_-]+\.json\.gz"
    if not (re.fullmatch(padrao, entrada or "") and re.fullmatch(padrao, saida or "")):
        return {"ok": False, "erro": "caminho inválido"}
    with gzip.open(entrada, "rt", encoding="utf-8") as f:
        dados = json.load(f)
    r = calcular(dados)
    with gzip.open(saida, "wt", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, default=str)
    return {"ok": True, "linhas": len(r["linhas"])}
