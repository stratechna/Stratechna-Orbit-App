"""O Stratechna Chat no CRM (docs/PLANO-CHAT-NO-CRM.md, D1–D8 aceites a 27-11-2026).

* C1 — um tópico de um canal PÚBLICO ligado a uma ficha (negócio, empresa, contacto, lead) pelo «Ligar ao CRM» do Chat
  do /orbit: tudo o que se diz nesse tópico, também o que já lá estava (D4), entra na actividade da ficha.
* C2 — a reacção :crm: numa mensagem de um canal público (das últimas 1000): entra na ficha do tópico ligado ou na ficha cujo email/
  nome de empresa aparece no texto; sem nenhuma fica em «Chat por arrumar». Tirar a reacção tira-a do CRM.
* C3 — só sugestão: ao abrir um tópico não ligado, o /orbit propõe «Ligar este tópico a …?». Nada se liga sozinho.

Nunca entram mensagens diretas (D2), canais privados (D3) nem mensagens de robôs.

Lê-se com a chave do robô «Orbit CRM» da organização (`orbit_chat_robo` = {email, chave} no site_config; criado pelo
`chat-robo-crm.sh` do Apps02), que só lê canais públicos. Escreve-se um `Communication` com meio «Chat» (tipo «Automated Message», sem «enviado/recebido») por
tópico, por ficha e por dia (D7), ligado à ficha por `reference_*` — visível a quem pode abrir a ficha (D5). Anexos
ficam como ligação para o Chat (D6). Grava-se sem os eventos do Communication (db_insert): não mexe no estado dos negócios/leads nem
dispara os fluxos de «mensagem do cliente» do CRM: é conversa da equipa, não do cliente.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from html import escape
from urllib.parse import quote

import frappe
import requests
from frappe.utils import cint, get_datetime, now_datetime

DT = "Ligacao do Chat"
FICHAS = {"CRM Deal": "negócio", "CRM Organization": "empresa", "Contact": "contacto", "CRM Lead": "lead"}
EMOJI = "crm"
JANELA_MSG = 1000      # reacções :crm: procuram-se nas últimas 1000 mensagens dos canais públicos
MAX_TOPICO = 5000      # mensagens trazidas ao ligar um tópico (D4: o tópico inteiro)


# ── acesso ao Chat com a chave do robô ─────────────────────────────────────────────────────────────────
def _robo():
    r = frappe.conf.get("orbit_chat_robo") or {}
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except Exception:  # noqa: BLE001
            r = {}
    return (r.get("email"), r.get("chave")) if r.get("email") and r.get("chave") else (None, None)


def _base() -> str:
    from orbit import marca
    return f"https://{marca._chat_do_tenant()}"


def _api(caminho, **params):
    email, chave = _robo()
    if not chave:
        return None
    r = requests.get(_base() + "/api/v1" + caminho, auth=(email, chave), params=params, timeout=30)
    if r.status_code >= 400:
        frappe.log_error(f"Chat {caminho}: {r.status_code} {r.text[:300]}", "Chat no CRM")
        return None
    return r.json()


def _mensagens(narrow, anchor="newest", antes=0, depois=0):
    d = _api("/messages", anchor=anchor, num_before=antes, num_after=depois, apply_markdown="false",
             narrow=json.dumps(narrow)) or {}
    return d.get("messages") or []


def _topico_inteiro(canal_id, topico):
    """Todas as mensagens de um tópico, da mais antiga à mais recente (paginado, até MAX_TOPICO)."""
    out, ancora = [], "oldest"
    narrow = [{"operator": "channel", "operand": cint(canal_id)}, {"operator": "topic", "operand": topico}]
    while len(out) < MAX_TOPICO:
        lote = _mensagens(narrow, anchor=ancora, depois=1000)
        lote = [m for m in lote if not out or m["id"] > out[-1]["id"]]
        if not lote:
            break
        out += lote
        ancora = str(lote[-1]["id"])
        if len(lote) < 999:
            break
    return out


def _robos():
    """Ids dos robôs da organização (as mensagens deles nunca entram)."""
    chave = f"orbit:chat:robos:{frappe.local.site}"
    v = frappe.cache.get_value(chave)
    if v is None:
        d = _api("/users") or {}
        v = [u["user_id"] for u in d.get("members", []) if u.get("is_bot")]
        frappe.cache.set_value(chave, v, expires_in_sec=3600)
    return set(v)


def _canais_publicos(fresco=False):
    chave = f"orbit:chat:publicos:{frappe.local.site}"
    v = None if fresco else frappe.cache.get_value(chave)
    if v is None:
        d = _api("/streams", include_public="true", include_subscribed="false") or {}
        v = {str(s["stream_id"]): s["name"] for s in d.get("streams", []) if not s.get("invite_only")}
        frappe.cache.set_value(chave, v, expires_in_sec=600)
    return v


# ── texto ─────────────────────────────────────────────────────────────────────────────────────────────
def _enc(x: str) -> str:
    """A codificação dos endereços #narrow do Zulip (encodeURIComponent, «.»→%2E, «%»→«.»)."""
    return quote(x, safe="").replace(".", "%2E").replace("%", ".")


def endereco_topico(canal_id, canal, topico) -> str:
    return f"{_base()}/#narrow/channel/{cint(canal_id)}-{_enc(canal or '')}/topic/{_enc(topico or '')}"


def endereco_mensagem(canal_id, canal, topico, mid) -> str:
    return endereco_topico(canal_id, canal, topico) + f"/near/{cint(mid)}"


def _limpo(texto: str) -> str:
    """Markdown do Chat em texto: anexos (/user_uploads/…) com o endereço completo do Chat (D6), nada de HTML."""
    base = _base()
    t = re.sub(r"\]\((/user_uploads/[^)\s]+)\)", lambda m: f"]({base}{m.group(1)})", texto or "")
    return t


def _hora(ts) -> datetime:
    """Hora do Chat (UTC) na hora do sistema do Orbit (Lisboa), sem fuso — como as datas do Frappe."""
    from frappe.utils.data import convert_utc_to_system_timezone
    return convert_utc_to_system_timezone(datetime.utcfromtimestamp(cint(ts))).replace(tzinfo=None)


def _corpo_dia(msgs, canal_id, canal, topico) -> str:
    """O conteúdo do registo de um dia: «HH:MM Nome» e o texto de cada mensagem, escapado (nunca HTML do servidor)."""
    linhas = [f'<p><a href="{escape(endereco_topico(canal_id, canal, topico))}" target="_blank">Abrir no Chat</a></p>']
    for m in msgs:
        t = escape(_limpo(m.get("content") or "")).replace("\n", "<br>")
        linhas.append(f"<p><b>{_hora(m['timestamp']).strftime('%H:%M')} · {escape(m.get('sender_full_name') or '')}</b><br>{t}</p>")
    return "\n".join(linhas)


# ── registos no CRM ───────────────────────────────────────────────────────────────────────────────────
def _chave_registo(*partes) -> str:
    return "orbit-chat-" + hashlib.md5("|".join(str(p) for p in partes).encode()).hexdigest()


def _gravar(chave, ref_dt, ref_dn, assunto, corpo, quando, quem):
    """Cria ou actualiza um Communication «Chat» pela chave (no message_id); devolve o nome."""
    nome = frappe.db.get_value("Communication", {"message_id": chave}, "name")
    if nome:
        atual = frappe.db.get_value("Communication", nome, ["content", "subject"], as_dict=1)
        if atual.content != corpo or atual.subject != assunto:
            frappe.db.set_value("Communication", nome, {"content": corpo, "subject": assunto, "communication_date": quando,
                                                        "sender_full_name": quem[:140]}, update_modified=True)
        return nome
    # db_insert, sem os eventos do Communication: o CRM marcava o negócio como «respondido» e os fluxos de «mensagem do
    # cliente» disparavam — isto é conversa da equipa
    c = frappe.new_doc("Communication")
    c.update({"communication_type": "Automated Message", "communication_medium": "Chat", "sent_or_received": "Received",
              "subject": assunto[:140], "content": corpo, "sender_full_name": quem[:140], "communication_date": quando,
              "message_id": chave, "reference_doctype": ref_dt, "reference_name": ref_dn, "status": "Linked",
              "owner": "Administrator"})
    c.set_new_name()
    c.db_insert()
    return c.name


def _apagar_registo(nome):
    if nome and frappe.db.exists("Communication", nome):
        frappe.delete_doc("Communication", nome, ignore_permissions=True, force=True)


def sincronizar_topico(lig, msgs=None, completo=False):
    """Reescreve os registos por dia de um tópico ligado. `msgs` = as mensagens já lidas (senão lê-se do Chat):
    com `completo` o tópico inteiro, senão as mais recentes (as edições e apagamentos dos últimos dias)."""
    if lig.tipo != "Tópico" or not lig.ref_name:
        return 0
    if msgs is None:
        if completo:
            msgs = _topico_inteiro(lig.canal_id, lig.topico)
        else:
            msgs = _mensagens([{"operator": "channel", "operand": cint(lig.canal_id)},
                               {"operator": "topic", "operand": lig.topico}], antes=300)
    robos = _robos()
    msgs = [m for m in msgs if m.get("sender_id") not in robos]
    por_dia = {}
    for m in msgs:
        por_dia.setdefault(_hora(m["timestamp"]).date(), []).append(m)
    assunto = f"# {lig.canal} › {lig.topico}"
    feitos = 0
    for dia, lista in por_dia.items():
        lista.sort(key=lambda m: m["id"])
        quem = ", ".join(dict.fromkeys(m.get("sender_full_name") or "" for m in lista))
        _gravar(_chave_registo(lig.canal_id, lig.topico, dia, lig.ref_doctype, lig.ref_name), lig.ref_doctype, lig.ref_name,
                assunto, _corpo_dia(lista, lig.canal_id, lig.canal, lig.topico), _hora(lista[-1]["timestamp"]), quem)
        feitos += 1
    # dias que ficaram sem mensagens (tudo apagado no Chat) dentro do que se leu
    if msgs and not completo:
        primeiro = min(_hora(m["timestamp"]) for m in msgs)
        for d in range((now_datetime().date() - primeiro.date()).days + 1):
            dia = primeiro.date() + timedelta(days=d)
            if dia not in por_dia:
                _apagar_registo(frappe.db.get_value("Communication", {"message_id": _chave_registo(
                    lig.canal_id, lig.topico, dia, lig.ref_doctype, lig.ref_name)}, "name"))
    frappe.db.set_value(DT, lig.name, "sincronizado", now_datetime(), update_modified=False)
    return feitos


def _apagar_registos_topico(lig):
    for nome in frappe.get_all("Communication", filters={"communication_medium": "Chat", "reference_doctype": lig.ref_doctype,
                                                          "reference_name": lig.ref_name,
                                                          "subject": f"# {lig.canal} › {lig.topico}"[:140]}, pluck="name"):
        _apagar_registo(nome)


def _registo_mensagem(lig, m=None):
    """C2: a mensagem guardada pela reacção numa ficha — um registo próprio."""
    chave = _chave_registo("msg", lig.mensagem_id, lig.ref_doctype, lig.ref_name)
    if not lig.ref_name:
        return None
    texto = (m or {}).get("content") if m else lig.texto
    autor = (m or {}).get("sender_full_name") if m else lig.autor
    quando = _hora(m["timestamp"]) if m else lig.creation
    corpo = (f'<p><a href="{escape(endereco_mensagem(lig.canal_id, lig.canal, lig.topico, lig.mensagem_id))}" '
             f'target="_blank">Abrir no Chat</a></p><p><b>{escape(autor or "")}</b><br>'
             f'{escape(_limpo(texto or "")).replace(chr(10), "<br>")}</p>')
    return _gravar(chave, lig.ref_doctype, lig.ref_name, f"# {lig.canal} › {lig.topico}", corpo, quando, autor or "")


# ── C2/C3: fichas que aparecem num texto ──────────────────────────────────────────────────────────────
def _organizacoes():
    chave = f"orbit:chat:orgs:{frappe.local.site}"
    v = frappe.cache.get_value(chave)
    if v is None:
        v = [(n, (t or n)) for n, t in frappe.get_all("CRM Organization", fields=["name", "organization_name"], as_list=1,
                                                      limit_page_length=20000) if len((t or n or "").strip()) >= 4]
        frappe.cache.set_value(chave, v, expires_in_sec=900)
    return v


def fichas_no_texto(texto: str, limite=3):
    """Fichas do CRM cujo email ou nome exacto de empresa aparece no texto (sem adivinhar por palavras soltas)."""
    out, vistos = [], set()

    def junta(dt, dn, titulo):
        if (dt, dn) not in vistos and len(out) < limite:
            vistos.add((dt, dn))
            out.append({"doctype": dt, "name": dn, "titulo": titulo or dn, "tipo": FICHAS[dt]})

    t = texto or ""
    for e in dict.fromkeys(x.lower() for x in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", t)):
        for c in frappe.get_all("Contact Email", filters={"email_id": e, "parenttype": "Contact"}, pluck="parent", limit=2):
            junta("Contact", c, frappe.db.get_value("Contact", c, "full_name"))
        for l in frappe.get_all("CRM Lead", filters={"email": e, "converted": 0}, fields=["name", "lead_name"], limit=2):
            junta("CRM Lead", l.name, l.lead_name)
    baixo = t.lower()
    for nome, titulo in _organizacoes():
        tl = titulo.lower()
        if tl in baixo and re.search(r"(?<!\w)" + re.escape(tl) + r"(?!\w)", baixo):
            junta("CRM Organization", nome, titulo)
    return out


# ── trabalho de 2 em 2 minutos ────────────────────────────────────────────────────────────────────────
def periodico():
    if not _robo()[1] or not frappe.db.table_exists(DT):
        return
    try:
        _ler()
        frappe.db.commit()
    except Exception:  # noqa: BLE001
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Chat no CRM")


def _ler():
    publicos = _canais_publicos()
    # C1: os tópicos ligados (canal ainda público) — as mensagens recentes, para apanhar novas, edições e apagamentos
    for lig in frappe.get_all(DT, filters={"tipo": "Tópico", "ref_name": ["is", "set"]},
                              fields=["name", "tipo", "canal_id", "canal", "topico", "ref_doctype", "ref_name", "sincronizado"]):
        if str(lig.canal_id) not in publicos:
            continue
        lig.canal = publicos[str(lig.canal_id)]
        sincronizar_topico(frappe._dict(lig), completo=not lig.sincronizado)
    # C2: reacções :crm: nas últimas 1000 mensagens dos canais públicos, seja qual for a data (reage-se hoje a uma
    # mensagem de há uma semana; o Chat não deixa pedir «mensagens com esta reacção»)
    recentes = [m for m in _mensagens([{"operator": "channels", "operand": "public"}], antes=JANELA_MSG) if m.get("type") == "stream"]
    robos = _robos()
    com_reaccao = {m["id"]: m for m in recentes if m.get("sender_id") not in robos
                   and any(r.get("emoji_name") == EMOJI and r.get("user_id") not in robos for r in m.get("reactions") or [])}
    ligados = {(cint(l.canal_id), l.topico): l for l in frappe.get_all(DT, filters={"tipo": "Tópico", "ref_name": ["is", "set"]},
                                                                       fields=["canal_id", "topico", "ref_doctype", "ref_name"])}
    for mid, m in com_reaccao.items():
        if frappe.db.exists(DT, {"tipo": "Mensagem", "mensagem_id": mid}):
            continue
        canal = publicos.get(str(m.get("stream_id"))) or m.get("display_recipient")
        base = {"doctype": DT, "tipo": "Mensagem", "canal_id": m["stream_id"], "canal": canal, "topico": m.get("subject"),
                "mensagem_id": mid, "texto": (m.get("content") or "")[:5000], "autor": m.get("sender_full_name")}
        lt = ligados.get((cint(m["stream_id"]), m.get("subject")))
        destinos = ([{"doctype": lt.ref_doctype, "name": lt.ref_name, "titulo": None}] if lt
                    else fichas_no_texto(m.get("content") or "", limite=2))
        for d in destinos or [None]:
            lig = frappe.get_doc({**base, "ref_doctype": d and d["doctype"], "ref_name": d and d["name"],
                                  "ref_titulo": d and (d.get("titulo") or _titulo(d["doctype"], d["name"]))})
            lig.insert(ignore_permissions=True)
            if d and not lt:
                _registo_mensagem(lig, m)
    # reacção tirada (dentro da janela): sai do CRM
    vistas = {m["id"] for m in recentes}
    for l in frappe.get_all(DT, filters={"tipo": "Mensagem", "mensagem_id": ["in", list(vistas) or [0]]},
                            fields=["name", "mensagem_id", "ref_doctype", "ref_name"]):
        if l.mensagem_id not in com_reaccao:
            if l.ref_name:
                _apagar_registo(frappe.db.get_value("Communication", {"message_id": _chave_registo(
                    "msg", l.mensagem_id, l.ref_doctype, l.ref_name)}, "name"))
            frappe.delete_doc(DT, l.name, ignore_permissions=True, force=True)


def _titulo(dt, dn):
    if dt == "CRM Deal":
        campos = [c for c in ("titulo", "organization", "lead_name") if frappe.get_meta(dt).has_field(c)]
        v = frappe.db.get_value(dt, dn, campos, as_dict=1) or {}
        return next((v[c] for c in campos if v.get(c)), dn)
    campo = {"CRM Organization": "organization_name", "Contact": "full_name", "CRM Lead": "lead_name"}[dt]
    return frappe.db.get_value(dt, dn, campo) or dn


# ── API do /orbit ─────────────────────────────────────────────────────────────────────────────────────
def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _pode_ficha(dt, dn, ptype="read"):
    if dt not in FICHAS:
        frappe.throw("Tipo de ficha desconhecido.")
    frappe.get_doc(dt, dn).check_permission(ptype)


@frappe.whitelist()
def do_topico(canal: str, topico: str, texto: str = ""):
    """As fichas ligadas a um tópico e, se não houver nenhuma, sugestões pelo que se disse (C3)."""
    _guarda()
    ligs = frappe.get_all(DT, filters={"tipo": "Tópico", "canal_id": cint(canal), "topico": topico, "ref_name": ["is", "set"]},
                          fields=["name", "ref_doctype", "ref_name", "ref_titulo", "ligado_por"])
    out = {"robo": bool(_robo()[1]), "publico": str(cint(canal)) in (_canais_publicos() if _robo()[1] else {}),
           "ligacoes": [{"id": l.name, "doctype": l.ref_doctype, "name": l.ref_name, "titulo": l.ref_titulo or l.ref_name,
                         "tipo": FICHAS.get(l.ref_doctype, "")} for l in ligs], "sugestoes": []}
    if not ligs and texto and out["publico"]:
        out["sugestoes"] = fichas_no_texto(texto)
    return out


@frappe.whitelist(methods=["POST"])
def ligar(canal: str, canal_nome: str, topico: str, doctype: str, name: str):
    """C1: liga o tópico à ficha e traz já o tópico inteiro (D4)."""
    _guarda()
    _pode_ficha(doctype, name)
    if not _robo()[1]:
        frappe.throw("O Chat desta organização ainda não tem o robô «Orbit CRM». Peça à Stratechna para o ligar.")
    publicos = _canais_publicos(fresco=True)
    if str(cint(canal)) not in publicos:
        frappe.throw("Este canal é privado: as conversas de canais privados não entram no CRM.")
    topico = (topico or "").strip()
    if not topico:
        frappe.throw("Escolha primeiro um tópico.")
    if frappe.db.exists(DT, {"tipo": "Tópico", "canal_id": cint(canal), "topico": topico, "ref_doctype": doctype, "ref_name": name}):
        return {"ok": True, "ja": True}
    lig = frappe.get_doc({"doctype": DT, "tipo": "Tópico", "canal_id": cint(canal), "canal": publicos[str(cint(canal))],
                          "topico": topico, "ref_doctype": doctype, "ref_name": name, "ref_titulo": _titulo(doctype, name),
                          "ligado_por": frappe.session.user})
    lig.insert(ignore_permissions=True)
    n = sincronizar_topico(lig, completo=True)
    return {"ok": True, "dias": n}


@frappe.whitelist(methods=["POST"])
def desligar(id: str):
    _guarda()
    lig = frappe.get_doc(DT, id)
    _pode_ficha(lig.ref_doctype, lig.ref_name)
    _apagar_registos_topico(lig)
    frappe.delete_doc(DT, lig.name, ignore_permissions=True, force=True)
    return {"ok": True}


@frappe.whitelist()
def por_arrumar():
    """C2: mensagens com :crm: sem ficha encontrada."""
    _guarda()
    return [{"id": l.name, "canal": l.canal, "topico": l.topico, "texto": l.texto, "autor": l.autor, "quando": l.creation,
             "endereco": endereco_mensagem(l.canal_id, l.canal, l.topico, l.mensagem_id)}
            for l in frappe.get_all(DT, filters={"tipo": "Mensagem", "ref_name": ["is", "not set"], "ignorada": 0},
                                    fields=["name", "canal_id", "canal", "topico", "texto", "autor", "creation", "mensagem_id"],
                                    order_by="creation desc", limit=100)]


@frappe.whitelist(methods=["POST"])
def arrumar(id: str, doctype: str = None, name: str = None, ignorar: int = 0):
    _guarda()
    lig = frappe.get_doc(DT, id)
    if lig.tipo != "Mensagem" or lig.ref_name:
        frappe.throw("Esta mensagem já está arrumada.")
    if cint(ignorar):
        lig.db_set("ignorada", 1)
        return {"ok": True}
    _pode_ficha(doctype, name)
    lig.ref_doctype, lig.ref_name, lig.ref_titulo, lig.ligado_por = doctype, name, _titulo(doctype, name), frappe.session.user
    lig.save(ignore_permissions=True)
    _registo_mensagem(lig)
    return {"ok": True}


def da_ficha(doctype, name, rel=None):
    """As conversas do Chat ligadas a uma ficha (e às fichas relacionadas) — «Conversas no Chat»."""
    pares = [(doctype, name)] + [(dt, n) for dt, ns in (rel or {}).items() for n in ns if (dt, n) != (doctype, name)]
    out, vistos = [], set()
    for dt, n in pares:
        for l in frappe.get_all(DT, filters={"tipo": "Tópico", "ref_doctype": dt, "ref_name": n},
                                fields=["name", "canal_id", "canal", "topico", "ref_doctype", "ref_name", "ref_titulo"]):
            if (l.canal_id, l.topico) in vistos:
                continue
            vistos.add((l.canal_id, l.topico))
            out.append({"id": l.name, "canal": l.canal, "topico": l.topico, "endereco": endereco_topico(l.canal_id, l.canal, l.topico),
                        "propria": (dt, n) == (doctype, name), "ficha": l.ref_titulo, "tipo": FICHAS.get(dt, "")})
    return out
