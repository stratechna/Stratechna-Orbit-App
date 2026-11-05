"""A Ligacao Faturacao de cada empresa: credenciais, adaptador e os três botões (testar, ler opções, ensaiar)."""
from __future__ import annotations

import json
from typing import Optional

import frappe
from frappe.utils import add_days, now_datetime, today

from orbit.faturacao.base import CONSUMIDOR_FINAL, Cliente, ErroFaturacao, Linha, Pedido, adaptador

DT = "Ligacao Faturacao"
CAMPOS_PASSWORD = ("client_secret", "palavra_passe", "access_token", "refresh_token")
CAMPOS = ("client_id", "utilizador", "empresa_id", "zona_fiscal", "token_expira", "serie_fatura",
          "serie_fatura_recibo", "serie_nota_credito", "serie_recibo", "prazo_id", "metodo_pagamento_id",
          "metodo_envio_id", "categoria_id", "unidade_id", "motivo_isencao")


def da_empresa(company: str) -> Optional["frappe.model.document.Document"]:
    """A ligação ACTIVA da empresa, ou None — sem ela nada muda no comportamento do ERPNext."""
    if not company or not frappe.db.table_exists("tabLigacao Faturacao"):
        return None
    nome = frappe.db.get_value(DT, {"company": company, "activa": 1}, "name")
    return frappe.get_doc(DT, nome) if nome else None


def _cfg(lig) -> dict:
    cfg = {c: lig.get(c) for c in CAMPOS}
    for c in CAMPOS_PASSWORD:
        try:
            cfg[c] = lig.get_password(c, raise_exception=False) or ""
        except Exception:  # noqa: BLE001
            cfg[c] = ""
    return cfg


def adaptador_de(lig):
    def guardar(novos: dict):
        # tokens renovados pelo adaptador: gravam-se sem mexer no resto (db_set não corre validate)
        for k, v in novos.items():
            if k in CAMPOS_PASSWORD:
                from frappe.utils.password import set_encrypted_password
                set_encrypted_password(DT, lig.name, v or "", k)
            else:
                lig.db_set(k, v, update_modified=False)
    return adaptador(lig.programa, _cfg(lig), guardar=guardar)


def _registar_erro(lig, e: Exception):
    lig.db_set("ultimo_erro", f"{now_datetime():%Y-%m-%d %H:%M} — {e}"[:1000], update_modified=False)


@frappe.whitelist()
def testar(ligacao: str) -> dict:
    lig = frappe.get_doc(DT, ligacao)
    lig.check_permission("write")
    try:
        r = adaptador_de(lig).testar_ligacao()
    except ErroFaturacao as e:
        _registar_erro(lig, e)
        frappe.throw(str(e))
    lig.db_set({"ultimo_teste": now_datetime(), "ultimo_erro": ""}, update_modified=False)
    return r


@frappe.whitelist()
def ler_opcoes(ligacao: str) -> dict:
    """Lê do programa as séries, taxas, prazos, métodos, unidades e categorias, para se escolherem os ids."""
    lig = frappe.get_doc(DT, ligacao)
    lig.check_permission("write")
    try:
        op = adaptador_de(lig).opcoes()
    except ErroFaturacao as e:
        _registar_erro(lig, e)
        frappe.throw(str(e))
    lig.db_set("opcoes", json.dumps(op, ensure_ascii=False, indent=1), update_modified=False)
    return {k: len(v) for k, v in op.items()}


@frappe.whitelist()
def ensaiar(ligacao: str) -> dict:
    """O ensaio que destranca o modo Real: cria um RASCUNHO de fatura ao Consumidor Final com uma linha, lê-o de
    volta e apaga-o. Nunca cria um documento fiscal."""
    lig = frappe.get_doc(DT, ligacao)
    lig.check_permission("write")
    ad = adaptador_de(lig)
    ref = f"ENSAIO-ORBIT-{frappe.generate_hash(length=8)}"
    pedido = Pedido(tipo="fatura", referencia=ref, data=today(), vencimento=add_days(today(), 30),
                    cliente=Cliente(nome="Consumidor Final", nif=CONSUMIDOR_FINAL),
                    linhas=[Linha(codigo="ORBIT-ENSAIO", nome="Ensaio da ligação do Orbit (rascunho, apagado)",
                                  quantidade=1, preco_unitario=1.0, taxa_iva=23.0)],
                    notas="Ensaio automático do Stratechna Orbit — rascunho apagado de seguida.", rascunho=True)
    passos = {}
    try:
        res = ad.emitir(pedido)
        passos["rascunho"] = res.id_externo
        if res.estado != "rascunho":
            raise ErroFaturacao(f"o programa devolveu o ensaio como «{res.estado}» e não como rascunho — "
                                f"verifique-o no programa (id {res.id_externo})")
        ad.apagar_rascunho("fatura", res.id_externo)
        passos["apagado"] = True
    except ErroFaturacao as e:
        _registar_erro(lig, e)
        frappe.throw(f"Ensaio falhou: {e}<br>Passos: {passos}")
    lig.db_set({"ultimo_ensaio_ok": now_datetime(), "ultimo_erro": ""}, update_modified=False)
    return {"ok": True, **passos}
