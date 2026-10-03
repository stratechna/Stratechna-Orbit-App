"""Automações: o correio que sai sozinho, a quem cumprir uma condição.

O cliente aprova o MODELO de cada automação, uma vez — uma automação que pedisse
aprovação por envio não era uma automação. Corre de hora a hora e só decide
QUEM entra na fila e com que produtos; quem faz sair é a mesma passagem ao
minuto das campanhas (`envio.processar`), com o mesmo ritmo, travão, remoção e
medição.

Quatro travões, por esta ordem:
  1. só quem pode receber (`destinatarios.contactaveis`) — sem excepção;
  2. uma vez por motivo: a mesma encomenda não gera dois agradecimentos;
  3. tecto de frequência: ninguém recebe correio automático duas vezes em menos
     de `intervalo_minimo_dias` (3 por omissão) — sem isto, quem compra recebia
     o agradecimento, a venda cruzada e as boas-vindas na mesma semana;
  4. só conta o que acontece DEPOIS de a automação ser activada: ligar o
     «depois da compra» não escreve a quem comprou no ano passado. A excepção é
     a reactivação, cujo alvo é precisamente o passado — e entra em lotes
     pequenos.
"""

import json
import uuid
from datetime import timedelta

import frappe
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime, nowdate

from orbit.marketing import destinatarios, loja, mensagem

LOTE = 200
LOTE_REACTIVACAO = 50

TIPOS = {
    "Boas-vindas": {"loja": False, "chave": "boas_vindas"},
    "Depois da compra": {"loja": True, "chave": "pos_compra"},
    "Venda cruzada": {"loja": True, "chave": "venda_cruzada"},
    "Reactivação": {"loja": True, "chave": "reactivacao"},
    "Pagamento por concluir": {"loja": True, "chave": "pagamento_por_concluir"},
}


def permitidas() -> set[str]:
    """As automações que o plano inclui, vindas do portal. Vazio = todas
    (contas da casa e tenants sem plano definido pelo portal)."""
    texto = (mensagem.definicoes().get("plano_automacoes") or "").strip()
    if not texto:
        return set(TIPOS)
    chaves = {c.strip() for c in texto.split(",") if c.strip()}
    return {nome for nome, t in TIPOS.items() if t["chave"] in chaves}


def _ja_recebeu(automacao: str, email: str, ref: str) -> bool:
    return bool(frappe.db.exists("Envio de Marketing", {"automacao": automacao, "email": email, "ref": ref}))


def _recebeu_automatico_ha_pouco(email: str, dias: int) -> bool:
    desde = now_datetime() - timedelta(days=dias)
    return bool(frappe.db.sql("""SELECT 1 FROM `tabEnvio de Marketing`
        WHERE email = %s AND COALESCE(automacao, '') <> '' AND creation >= %s
          AND estado IN ('Na fila', 'Enviado', 'Simulado') LIMIT 1""", (email, desde)))


def _candidatos(a) -> list[tuple]:
    """(registo, ref, dados) de quem entra hoje, antes dos travões 1-3."""
    base = {r["email"]: r for r in destinatarios.contactaveis(a.assunto_marketing)}
    desde = get_datetime(a.activa_desde)
    saida = []
    if a.tipo == "Boas-vindas":
        # Quem passou a poder receber depois de a automação ser ligada.
        for r in base.values():
            data = r.get("mkt_data")
            if data and getdate(data) >= desde.date():
                saida.append((r, "boas_vindas", {}))
        return saida
    if a.tipo in ("Depois da compra", "Venda cruzada"):
        dias = cint(a.dias_apos) or (7 if a.tipo == "Depois da compra" else 14)
        limite = add_days(nowdate(), -dias)
        for e in loja.encomendas(True, desde=desde.date()):
            if e["email"] in base and getdate(e["data"]) <= getdate(limite):
                saida.append((base[e["email"]], f"{TIPOS[a.tipo]['chave']}:{e['name']}", {"_encomenda": e}))
        return saida
    if a.tipo == "Reactivação":
        dias = cint(a.dias_sem_compra) or 120
        for email, x in loja.ultima_compra().items():
            if email in base and getdate(x["ultima"]) < getdate(add_days(nowdate(), -dias)):
                saida.append((base[email], f"reactivacao:{x['ultima']}", {}))
        return saida[:LOTE_REACTIVACAO]
    if a.tipo == "Pagamento por concluir":
        horas = cint(a.horas_apos) or 4
        ate = cint(a.ate_dias) or 3
        pagas = {e["email"]: e["creation"] for e in loja.encomendas(True, desde=add_days(nowdate(), -ate))}
        for e in loja.encomendas(False, desde=add_days(nowdate(), -ate)):
            criada = get_datetime(e["creation"])
            if (e["email"] in base and criada >= desde and criada <= now_datetime() - timedelta(hours=horas)
                    # quem falhou o pagamento e comprou a seguir não precisa de lembrete
                    and not (e["email"] in pagas and get_datetime(pagas[e["email"]]) >= criada)):
                saida.append((base[e["email"]], f"por_pagar:{e['name']}", {"_encomenda": e}))
        return saida
    return []


def _dados(a, extra: dict) -> dict | None:
    """O que é só deste destinatário. `None` = não há o que mostrar, e então
    não se envia: uma venda cruzada sem produtos é «talvez lhe interesse»
    seguido de nada."""
    e = extra.get("_encomenda")
    if a.tipo == "Venda cruzada":
        comprados = {i["item_code"] for i in e["itens"]}
        grupos = {i["item_group"] for i in e["itens"] if i.get("item_group")}
        p = loja.mais_vendidos(grupos, excluir=comprados, quantos=3)
        return {"produtos": p} if p else None
    if a.tipo == "Reactivação":
        return {"produtos": loja.novidades(3)}
    if a.tipo == "Pagamento por concluir":
        produtos = [p for p in (loja.produto(i["item_code"]) for i in e["itens"]) if p]
        base = (produtos[0]["url"].split("/?")[0] if produtos else None)
        return {"produtos": produtos[:4], **({"cta_url": base} if base else {})}
    return {}


def correr_uma(a) -> dict:
    if a.tipo not in permitidas():
        nota = "o plano já não inclui esta automação"
        a.db_set({"ultima_corrida": now_datetime(), "ultima_nota": nota})
        return {"entraram": 0, "nota": nota}
    intervalo = cint(mensagem.definicoes().get("intervalo_minimo_dias")) or 3
    entraram, saltados, vistos = 0, 0, set()
    for r, ref, extra in _candidatos(a)[:LOTE]:
        email = r["email"]
        if email in vistos or _ja_recebeu(a.name, email, ref) or _recebeu_automatico_ha_pouco(email, intervalo):
            continue
        vistos.add(email)
        dados = _dados(a, extra)
        frappe.get_doc({
            "doctype": "Envio de Marketing", "automacao": a.name, "email": email, "ref": ref,
            "estado": "Na fila" if dados is not None else "Saltado",
            "erro": None if dados is not None else "sem produtos para mostrar",
            "dados": json.dumps(dados or {}, ensure_ascii=False, default=str),
            "referencia_doctype": r["doctype"], "referencia_nome": r["name"],
            "nome_destinatario": " ".join(x for x in (r.get("nome"), r.get("apelido")) if x)[:140],
            "token": uuid.uuid4().hex,
        }).insert(ignore_permissions=True)
        if dados is None:
            saltados += 1
        else:
            entraram += 1
    nota = f"{entraram} entraram na fila" + (f", {saltados} sem produtos para mostrar" if saltados else "")
    a.db_set({"ultima_corrida": now_datetime(), "ultima_nota": nota})
    return {"entraram": entraram, "saltados": saltados, "nota": nota}


def correr() -> None:
    """De hora a hora."""
    for nome in frappe.get_all("Automacao de Marketing", filters={"estado": "Activa"}, pluck="name"):
        try:
            correr_uma(frappe.get_doc("Automacao de Marketing", nome))
            frappe.db.commit()
        except Exception:  # noqa: BLE001
            frappe.db.rollback()
            frappe.log_error(f"Automação {nome}", frappe.get_traceback())
