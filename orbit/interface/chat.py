"""Chat dentro da interface /orbit (A7 do plano da interface única, 20-11-2026).

O Stratechna Chat (Zulip) do tenant fica como motor. Aqui fala-se com a API dele **como a própria pessoa**, com a
chave de API pessoal dela: a pessoa liga o Chat uma vez no /orbit com a palavra-passe do Chat (o Zulip só aceita a
dele — `ZULIP_AUTH_BACKENDS=EmailAuthBackend`, fora da regra da caixa até à DP6/R4); o Orbit troca-a pela chave em
`/api/v1/fetch_api_key`, guarda **só a chave**, cifrada (`orbit_chat_chave` do User), e esquece a palavra-passe.
Cada pessoa vê só o que vê no Chat. Mensagens em texto (markdown cru), nunca HTML do servidor no ecrã.
"""
from __future__ import annotations

import json
import re

import frappe
import requests
from frappe.utils import cint

CAMPO = "orbit_chat_chave"


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _base() -> str:
    from orbit import marca
    return f"https://{marca._chat_do_tenant()}"


def _chave():
    from frappe.utils.password import get_decrypted_password
    return get_decrypted_password("User", frappe.session.user, CAMPO, raise_exception=False)


def _api(metodo, caminho, **kw):
    k = _chave()
    if not k:
        return None
    r = requests.request(metodo, _base() + "/api/v1" + caminho, auth=(frappe.session.user, k), timeout=20, **kw)
    if r.status_code == 401:
        from frappe.utils.password import remove_encrypted_password
        remove_encrypted_password("User", frappe.session.user, CAMPO)
        frappe.db.commit()
        return None
    if r.status_code >= 400:
        try:
            msg = r.json().get("msg")
        except Exception:  # noqa: BLE001
            msg = None
        frappe.throw(msg or f"O Chat respondeu {r.status_code}.")
    return r.json()


@frappe.whitelist(methods=["POST"])
def ligar(pwd: str):
    _guarda()
    u = frappe.session.user
    chave = f"orbit:chat:tentativas:{u}"
    n = cint(frappe.cache.get_value(chave))
    if n >= 5:
        frappe.throw("Demasiadas tentativas. Espere 10 minutos.")
    frappe.cache.set_value(chave, n + 1, expires_in_sec=600)
    r = requests.post(_base() + "/api/v1/fetch_api_key", data={"username": u, "password": pwd or ""}, timeout=20)
    if r.status_code != 200 or r.json().get("result") != "success":
        frappe.throw("O Chat não aceitou essa palavra-passe (é a do Stratechna Chat, não a da caixa).")
    from frappe.utils.password import set_encrypted_password
    set_encrypted_password("User", u, r.json()["api_key"], CAMPO)
    frappe.cache.delete_value(chave)
    return {"ok": True}


@frappe.whitelist()
def estado():
    _guarda()
    return {"ligado": bool(_chave()), "base": _base(), "utilizador": frappe.session.user}


@frappe.whitelist()
def conversas():
    """Canais subscritos com os tópicos recentes, e as conversas directas — a partir das 300 mensagens mais recentes."""
    _guarda()
    subs = _api("GET", "/users/me/subscriptions")
    if subs is None:
        return {"ligado": False}
    # 27-11-2026: «Arquivar» e «Mudar o nome» só para quem o Chat deixa — administradores da organização e quem criou o canal
    me = _api("GET", "/users/me") or {}
    admin = cint(me.get("role") or 400) <= 200
    canais = {s["stream_id"]: {"id": s["stream_id"], "nome": s["name"], "cor": s.get("color"), "descricao": s.get("description") or "",
                               "admin": admin or (s.get("creator_id") and s.get("creator_id") == me.get("user_id")), "topicos": {}, "ult": 0}
              for s in subs.get("subscriptions", [])}
    msgs = _api("GET", "/messages", params={"anchor": "newest", "num_before": 300, "num_after": 0, "apply_markdown": "false",
                                            "narrow": "[]"}) or {}
    directas = {}
    eu = frappe.session.user.lower()
    # 27-11-2026: os nomes vêm sempre da lista actual de utilizadores (o «Welcome Bot» passou a «Stratechna Chat»)
    nomes = {u["user_id"]: u.get("full_name") for u in ((_api("GET", "/users") or {}).get("members") or [])}
    for m in msgs.get("messages", []):
        lida = "read" in (m.get("flags") or [])
        if m["type"] == "stream" and m.get("stream_id") in canais:
            c = canais[m["stream_id"]]
            t = c["topicos"].setdefault(m["subject"], {"nome": m["subject"], "ult": 0, "por_ler": 0})
            t["ult"] = max(t["ult"], m["timestamp"])
            t["por_ler"] += 0 if lida else 1
            c["ult"] = max(c["ult"], m["timestamp"])
        elif m["type"] == "private":
            outros = [x for x in m.get("display_recipient", []) if (x.get("email") or "").lower() != eu] or m.get("display_recipient", [])
            chave = ",".join(sorted(str(x["id"]) for x in outros))
            d = directas.setdefault(chave, {"ids": [x["id"] for x in outros], "nome": ", ".join(nomes.get(x["id"]) or x.get("full_name") or x.get("email") for x in outros),
                                             "ult": 0, "por_ler": 0})
            d["ult"] = max(d["ult"], m["timestamp"])
            d["por_ler"] += 0 if lida else 1
    lista = []
    for c in canais.values():
        c["topicos"] = sorted(c["topicos"].values(), key=lambda t: -t["ult"])[:8]
        c["por_ler"] = sum(t["por_ler"] for t in c["topicos"])
        lista.append(c)
    lista.sort(key=lambda c: (-c["ult"], c["nome"].lower()))
    return {"ligado": True, "base": _base(), "canais": lista, "directas": sorted(directas.values(), key=lambda d: -d["ult"])[:20]}


def _narrow(canal=None, topico=None, ids=None):
    if ids:
        return [{"operator": "dm", "operand": [cint(i) for i in ids]}]
    n = [{"operator": "channel", "operand": cint(canal)}]
    if topico:
        n.append({"operator": "topic", "operand": topico})
    return n


@frappe.whitelist()
def mensagens(canal: str = None, topico: str = None, ids: str = None, marcar: int = 1):
    _guarda()
    lst_ids = [i for i in re.split(r"[,\s]+", ids or "") if i.isdigit()]
    d = _api("GET", "/messages", params={"anchor": "newest", "num_before": 100, "num_after": 0, "apply_markdown": "false",
                                         "narrow": json.dumps(_narrow(canal, topico, lst_ids))})
    if d is None:
        return {"ligado": False, "mensagens": []}
    out, por_ler = [], []
    nomes = {u["user_id"]: u.get("full_name") for u in ((_api("GET", "/users") or {}).get("members") or [])}
    for m in d.get("messages", []):
        out.append({"id": m["id"], "quem": nomes.get(m.get("sender_id")) or m.get("sender_full_name"), "email": m.get("sender_email"), "quando": m["timestamp"],
                    "texto": m.get("content") or "", "topico": m.get("subject") or "",
                    "meu": (m.get("sender_email") or "").lower() == frappe.session.user.lower()})
        if "read" not in (m.get("flags") or []):
            por_ler.append(m["id"])
    if por_ler and cint(marcar):
        _api("POST", "/messages/flags", data={"messages": json.dumps(por_ler), "op": "add", "flag": "read"})
    return {"ligado": True, "mensagens": out, "por_ler": len(por_ler)}


@frappe.whitelist(methods=["POST"])
def enviar(texto: str, canal: str = None, topico: str = None, ids: str = None):
    _guarda()
    texto = (texto or "").strip()
    if not texto:
        frappe.throw("Mensagem vazia.")
    lst_ids = [cint(i) for i in re.split(r"[,\s]+", ids or "") if i.isdigit()]
    if lst_ids:
        dados = {"type": "direct", "to": json.dumps(lst_ids), "content": texto[:10000]}
    else:
        dados = {"type": "stream", "to": cint(canal), "topic": (topico or "geral")[:60], "content": texto[:10000]}
    r = _api("POST", "/messages", data=dados)
    if r is None:
        frappe.throw("Ligue primeiro o Chat.")
    return {"ok": True, "id": r.get("id")}


@frappe.whitelist()
def pessoas():
    _guarda()
    d = _api("GET", "/users")
    if d is None:
        return []
    eu = frappe.session.user.lower()
    return sorted([{"id": u["user_id"], "nome": u.get("full_name"), "email": u.get("email")} for u in d.get("members", [])
                   if u.get("is_active") and not u.get("is_bot") and (u.get("email") or "").lower() != eu],
                  key=lambda x: (x["nome"] or "").lower())


# 27-11-2026 (Vítor: os botões que o tutorial do Chat menciona): criar canal e começar conversa (tópico) no /orbit
@frappe.whitelist(methods=["POST"])
def criar_canal(nome: str, descricao: str = "", privado: int = 0, pessoas: str = None):
    _guarda()
    nome = (nome or "").strip().lstrip("#").strip()
    if not nome:
        frappe.throw("Indique o nome do canal.")
    quem = [cint(i) for i in json.loads(pessoas or "[]") if str(i).isdigit()]
    eu = (_api("GET", "/users/me") or {}).get("user_id")
    dados = {"subscriptions": json.dumps([{"name": nome[:60], "description": (descricao or "")[:1024]}]),
             "invite_only": json.dumps(bool(cint(privado)))}
    if quem:
        dados["principals"] = json.dumps(sorted(set(quem + ([eu] if eu else []))))
    r = _api("POST", "/users/me/subscriptions", data=dados)
    if r is None:
        frappe.throw("Ligue primeiro o Chat.")
    sid = (_api("GET", "/get_stream_id", params={"stream": nome[:60]}) or {}).get("stream_id")
    return {"ok": True, "id": sid, "nome": nome[:60]}


@frappe.whitelist(methods=["POST"])
def arquivar_canal(canal: str):
    """«Apagar» no Chat é arquivar o canal (DELETE /streams/{id}); o Chat recusa a quem não pode."""
    _guarda()
    if _api("DELETE", f"/streams/{cint(canal)}") is None:
        frappe.throw("Ligue primeiro o Chat.")
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def editar_canal(canal: str, nome: str = None, descricao: str = None):
    _guarda()
    dados = {}
    if nome and nome.strip():
        dados["new_name"] = nome.strip().lstrip("#").strip()[:60]
    if descricao is not None:
        dados["description"] = descricao[:1024]
    if not dados:
        return {"ok": True}
    if _api("PATCH", f"/streams/{cint(canal)}", data=dados) is None:
        frappe.throw("Ligue primeiro o Chat.")
    return {"ok": True}
