"""Calendário dentro da interface /orbit (A1 do plano da interface única, 20-11-2026).

A agenda de cada pessoa continua no Orbit Mail (SOGo) — é lá que o iPhone, o Android e os convites a vêem.
Aqui lê-se e escreve-se nela por CalDAV **com as credenciais da própria pessoa** (a palavra-passe do Orbit é a da
caixa: regra da palavra-passe universal). Nunca uma conta de superutilizador do SOGo: um tenant comprometido daria
as agendas de todos os clientes.

* A palavra-passe guarda-se cifrada pelo Frappe (`set_encrypted_password`, como as das contas de email), no tenant
  da pessoa, ao entrar no Orbit (`ao_entrar`, gancho on_login) ou pelo «Ligar o calendário» do ecrã (`ligar`).
* Se o SOGo a recusar (mudou de palavra-passe), apaga-se e o ecrã volta a pedir.
* Também aparecem os Event do Frappe (reuniões do Booking, do CRM), sem repetir os que nasceram aqui.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET

import frappe
import requests
from frappe.utils import cint, get_datetime, getdate, now_datetime

CAMPO = "orbit_caldav"
NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav", "a": "http://apple.com/ns/ical/", "cs": "http://calendarserver.org/ns/"}
TZ = "Europe/Lisbon"


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _base(user: str) -> str:
    from orbit import marca
    return f"https://{marca._mail_do_tenant()}/SOGo/dav/{user}/Calendar/"


def _senha(user: str):
    from frappe.utils.password import get_decrypted_password
    return get_decrypted_password("User", user, CAMPO, raise_exception=False)


def _gravar(user: str, pwd: str):
    from frappe.utils.password import set_encrypted_password
    set_encrypted_password("User", user, pwd, CAMPO)


def _esquecer(user: str):
    from frappe.utils.password import remove_encrypted_password
    remove_encrypted_password("User", user, CAMPO)


def _pedido(metodo: str, url: str, user: str, pwd: str, corpo: str = None, cab: dict = None, timeout=20):
    h = {"Content-Type": "application/xml; charset=utf-8"}
    h.update(cab or {})
    return requests.request(metodo, url, data=(corpo.encode() if corpo else None), headers=h, auth=(user, pwd),
                            timeout=timeout)


def ao_entrar(login_manager=None):
    """on_login: guarda a palavra-passe com que a pessoa entrou (é a da caixa) para o calendário da interface."""
    try:
        from orbit.interface.api import ligada
        if not ligada():
            return
        user = getattr(login_manager, "user", None) or frappe.session.user
        pwd = frappe.form_dict.get("pwd")
        if not pwd or not user or user in ("Administrator", "Guest") or "@" not in user or len(pwd) > 128:
            return
        _gravar(user, pwd)
    except Exception:  # noqa: BLE001 — nunca impedir a entrada por causa do calendário
        frappe.log_error(title="orbit.interface.calendario.ao_entrar")


@frappe.whitelist(methods=["POST"])
def ligar(pwd: str):
    """«Ligar o calendário»: confirma a palavra-passe da caixa no SOGo e guarda-a."""
    _guarda()
    user = frappe.session.user
    chave = f"orbit:calendario:tentativas:{user}"
    n = cint(frappe.cache.get_value(chave))
    if n >= 5:
        frappe.throw("Demasiadas tentativas. Espere 10 minutos.")
    frappe.cache.set_value(chave, n + 1, expires_in_sec=600)
    r = _pedido("PROPFIND", _base(user), user, pwd or "", '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:displayname/></d:prop></d:propfind>',
                {"Depth": "0"})
    if r.status_code in (401, 403):
        frappe.throw("O Orbit Mail não aceitou essa palavra-passe da caixa.")
    if r.status_code != 207:
        frappe.throw(f"O calendário não respondeu ({r.status_code}).")
    _gravar(user, pwd)
    frappe.cache.delete_value(chave)
    return {"ok": True}


def _credenciais():
    user = frappe.session.user
    pwd = _senha(user)
    return user, pwd


def _calendarios(user, pwd):
    corpo = ('<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:a="http://apple.com/ns/ical/" '
             'xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><d:displayname/><d:resourcetype/><a:calendar-color/>'
             '<d:current-user-privilege-set/></d:prop></d:propfind>')
    r = _pedido("PROPFIND", _base(user), user, pwd, corpo, {"Depth": "1"})
    if r.status_code in (401, 403):
        return None
    r.raise_for_status()
    raiz = ET.fromstring(r.content)
    out = []
    for resp in raiz.findall("d:response", NS):
        href = resp.findtext("d:href", namespaces=NS) or ""
        prop = resp.find("d:propstat/d:prop", NS)
        if prop is None or prop.find("d:resourcetype/c:calendar", NS) is None:
            continue
        nome = prop.findtext("d:displayname", namespaces=NS) or href.rstrip("/").rsplit("/", 1)[-1]
        cor = (prop.findtext("a:calendar-color", namespaces=NS) or "").strip()[:7] or "#46607e"
        escreve = any(p.tag.endswith("write") or p.tag.endswith("all") for p in prop.findall("d:current-user-privilege-set/d:privilege/*", NS))
        out.append({"href": href, "nome": nome, "cor": cor, "escreve": escreve,
                    "pessoal": href.rstrip("/").endswith("/personal")})
    out.sort(key=lambda c: (not c["pessoal"], c["nome"].lower()))
    return out


def _abs(href: str) -> str:
    from orbit import marca
    return href if href.startswith("http") else f"https://{marca._mail_do_tenant()}{href}"


def _ics_eventos(texto: str, inicio: datetime, fim: datetime):
    import icalendar
    import recurring_ical_events
    cal = icalendar.Calendar.from_ical(texto)
    for ev in recurring_ical_events.of(cal).between(inicio, fim):
        ini = ev.get("DTSTART").dt if ev.get("DTSTART") else None
        fi = ev.get("DTEND").dt if ev.get("DTEND") else None
        if ini is None:
            continue
        dia_todo = isinstance(ini, date) and not isinstance(ini, datetime)
        if fi is None:
            fi = ini + (timedelta(days=1) if dia_todo else timedelta(hours=1))
        yield {"uid": str(ev.get("UID") or ""), "titulo": str(ev.get("SUMMARY") or "(sem título)"),
               "inicio": _iso(ini), "fim": _iso(fi), "dia_todo": dia_todo,
               "local": str(ev.get("LOCATION") or ""), "descricao": str(ev.get("DESCRIPTION") or "")[:500],
               "convidados": [str(a).replace("mailto:", "").replace("MAILTO:", "") for a in (ev.get("ATTENDEE") if isinstance(ev.get("ATTENDEE"), list) else ([ev.get("ATTENDEE")] if ev.get("ATTENDEE") else []))][:20]}


def _iso(x):
    if isinstance(x, datetime):
        if x.tzinfo:
            from zoneinfo import ZoneInfo
            x = x.astimezone(ZoneInfo(TZ)).replace(tzinfo=None)
        return x.strftime("%Y-%m-%dT%H:%M:%S")
    return x.strftime("%Y-%m-%d")


@frappe.whitelist()
def eventos(inicio: str, fim: str):
    _guarda()
    from zoneinfo import ZoneInfo
    ini = get_datetime(inicio).replace(tzinfo=ZoneInfo(TZ))
    fi = get_datetime(fim).replace(tzinfo=ZoneInfo(TZ))
    user, pwd = _credenciais()
    out, cals, ligado = [], [], False
    if pwd:
        try:
            cals = _calendarios(user, pwd)
        except Exception:  # noqa: BLE001
            frappe.log_error(title="orbit.interface.calendario: PROPFIND")
            cals = []
        if cals is None:          # a palavra-passe mudou: pedir de novo
            _esquecer(user)
            frappe.db.commit()
            cals = []
        else:
            ligado = True
    faixa = (f'<c:time-range start="{ini.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")}" '
             f'end="{fi.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")}"/>')
    corpo = ('<?xml version="1.0"?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
             '<d:prop><d:getetag/><c:calendar-data/></d:prop><c:filter><c:comp-filter name="VCALENDAR">'
             f'<c:comp-filter name="VEVENT">{faixa}</c:comp-filter></c:comp-filter></c:filter></c:calendar-query>')
    vistos = set()
    for c in cals:
        try:
            r = _pedido("REPORT", _abs(c["href"]), user, pwd, corpo, {"Depth": "1"}, timeout=30)
            if r.status_code != 207:
                continue
            for resp in ET.fromstring(r.content).findall("d:response", NS):
                href = resp.findtext("d:href", namespaces=NS) or ""
                dados = resp.findtext("d:propstat/d:prop/c:calendar-data", namespaces=NS)
                if not dados:
                    continue
                for ev in _ics_eventos(dados, ini, fi):
                    vistos.add(ev["uid"])
                    out.append({**ev, "id": f'{href}#{ev["inicio"]}', "href": href, "calendario": c["nome"],
                                "cor": c["cor"], "origem": "agenda"})
        except Exception:  # noqa: BLE001
            frappe.log_error(title=f"orbit.interface.calendario: REPORT {c['nome']}")
    # Event do Frappe (Booking, CRM) — sem os que nasceram aqui (já estão na agenda)
    a, b = ini.replace(tzinfo=None), fi.replace(tzinfo=None)
    vistos_ev = {}
    campos = ["name", "subject", "starts_on", "ends_on", "all_day", "location", "reference_doctype", "reference_docname",
              "custom_referencia_marcacao"]
    for f in ({"starts_on": ["between", [a, b]]}, {"starts_on": ["<", a], "ends_on": [">=", a]}):
        for e in frappe.get_list("Event", filters=f, fields=campos, limit=300):
            vistos_ev[e.name] = e
    for e in vistos_ev.values():
        ref = e.custom_referencia_marcacao or ""
        if ref.startswith("caldav:") and ref[7:] in vistos:
            continue
        s_ini = get_datetime(e.starts_on)
        s_fim = get_datetime(e.ends_on) if e.ends_on else s_ini + timedelta(hours=1)
        out.append({"id": f"event:{e.name}", "titulo": e.subject, "inicio": _iso(s_ini), "fim": _iso(s_fim),
                    "dia_todo": bool(e.all_day), "local": e.location or "", "calendario": "Orbit (CRM e Booking)",
                    "cor": "#b45309", "origem": "orbit",
                    "ref": [e.reference_doctype, e.reference_docname] if e.reference_docname else None})
    out.sort(key=lambda x: x["inicio"])
    return {"ligado": ligado, "calendarios": cals, "eventos": out, "utilizador": user}


@frappe.whitelist(methods=["POST"])
def criar(titulo: str, inicio: str, fim: str, calendario: str = None, convidados: str = "", meet: int = 0,
          descricao: str = "", local: str = "", ref_doctype: str = None, ref_name: str = None):
    """Nova reunião na agenda da pessoa (SOGo): os convidados recebem o convite pelo Orbit Mail. Com `meet`, a sala
    do Meet do tenant vai no local e na descrição. Com um registo do CRM, fica também na cronologia dele."""
    _guarda()
    import icalendar
    from zoneinfo import ZoneInfo
    user, pwd = _credenciais()
    if not pwd:
        frappe.throw("Ligue primeiro o calendário.")
    titulo = (titulo or "").strip()[:200]
    if not titulo:
        frappe.throw("Falta o título.")
    ini, fi = get_datetime(inicio), get_datetime(fim)
    if fi <= ini:
        frappe.throw("O fim tem de ser depois do início.")
    cals = _calendarios(user, pwd) or []
    alvo = next((c for c in cals if c["href"] == calendario and c["escreve"]), None) or next((c for c in cals if c["pessoal"]), None)
    if not alvo:
        frappe.throw("Não encontrei um calendário onde possa escrever.")
    emails = [e for e in re.findall(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+", convidados or "") if e.lower() != user.lower()][:30]
    uid = str(uuid.uuid4()).upper()
    sala = ""
    if cint(meet):
        from orbit import meet as m
        sala = f"{m._meet_base()}/{m._inquilino()}/{re.sub(r'[^a-z0-9]+', '-', titulo.lower()).strip('-')[:40]}-{uid[:6].lower()}"
    ev = icalendar.Event()
    ev.add("uid", uid)
    ev.add("summary", titulo)
    tz = ZoneInfo(TZ)
    ev.add("dtstart", ini.replace(tzinfo=tz))
    ev.add("dtend", fi.replace(tzinfo=tz))
    ev.add("dtstamp", datetime.now(tz=ZoneInfo("UTC")))
    if local or sala:
        ev.add("location", local or sala)
    texto = (descricao or "").strip()
    if sala:
        texto = (texto + "\n\n" if texto else "") + f"Reunião no Stratechna Meet: {sala}"
    if texto:
        ev.add("description", texto)
    nome = frappe.db.get_value("User", user, "full_name") or user
    org = icalendar.vCalAddress(f"mailto:{user}")
    org.params["cn"] = icalendar.vText(nome)
    ev.add("organizer", org)
    for e in emails:
        a = icalendar.vCalAddress(f"mailto:{e}")
        a.params.update({"role": icalendar.vText("REQ-PARTICIPANT"), "partstat": icalendar.vText("NEEDS-ACTION"),
                         "rsvp": icalendar.vText("TRUE")})
        ev.add("attendee", a, encode=0)
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Stratechna//Orbit//PT")
    cal.add("version", "2.0")
    cal.add_component(ev)
    url = _abs(alvo["href"]).rstrip("/") + f"/{uid}.ics"
    r = _pedido("PUT", url, user, pwd, cal.to_ical().decode(), {"Content-Type": "text/calendar; charset=utf-8",
                                                               "If-None-Match": "*"})
    if r.status_code not in (200, 201, 204):
        frappe.throw(f"A agenda recusou a reunião ({r.status_code}).")
    if ref_doctype and ref_name:
        frappe.get_doc(ref_doctype, ref_name).check_permission("read")
        frappe.get_doc({"doctype": "Event", "subject": titulo, "starts_on": ini, "ends_on": fi, "event_type": "Private",
                        "event_category": "Meeting", "location": local or sala, "description": texto,
                        "reference_doctype": ref_doctype, "reference_docname": ref_name,
                        "custom_referencia_marcacao": f"caldav:{uid}"}).insert()
    return {"ok": True, "uid": uid, "meet": sala, "calendario": alvo["nome"]}


@frappe.whitelist(methods=["POST"])
def apagar(href: str):
    """Apaga um evento da agenda da pessoa (só os do calendário dela; o SOGo avisa os convidados)."""
    _guarda()
    user, pwd = _credenciais()
    if not pwd or not href.startswith(f"/SOGo/dav/{user}/Calendar/"):
        frappe.throw("Sem permissão.", frappe.PermissionError)
    r = _pedido("DELETE", _abs(href), user, pwd)
    if r.status_code not in (200, 204, 404):
        frappe.throw(f"A agenda não apagou ({r.status_code}).")
    return {"ok": True}


# ── Equipa: disponibilidade (livre/ocupado) dos colegas, sem os detalhes (20-11-2026) ────────────────────
# O SOGo dá o «freebusy» de qualquer pessoa do mesmo servidor a quem está autenticado — só blocos ocupados, nunca o
# assunto. Usa-se a credencial da própria pessoa que pergunta (não há leitura das agendas dos outros).
CORES_EQUIPA = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#0891b2", "#db2777", "#65a30d", "#ea580c"]


@frappe.whitelist()
def equipa():
    _guarda()
    eu = frappe.session.user
    us = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest", eu]]},
                        fields=["name", "full_name"], order_by="full_name asc")
    us = [u for u in us if "@" in u.name and not u.name.startswith(("portal@", "suporte@", "it@", "noreply@"))]
    return [{"email": u.name, "nome": u.full_name or u.name, "cor": CORES_EQUIPA[i % len(CORES_EQUIPA)]} for i, u in enumerate(us)]


def _ocupado(alvo: str, ini, fim, user, pwd):
    from orbit import marca
    r = requests.get(f"https://{marca._mail_do_tenant()}/SOGo/dav/{alvo}/freebusy.ifb",
                     params={"sday": ini.strftime("%Y%m%d"), "eday": fim.strftime("%Y%m%d")}, auth=(user, pwd), timeout=20)
    if r.status_code != 200:
        return None
    from zoneinfo import ZoneInfo
    out = []
    janela = re.search(r"DTSTART:(\d{8}T\d{6}Z)[\s\S]*?DTEND:(\d{8}T\d{6}Z)", r.text)
    if janela:   # a janela que o SOGo cobriu de facto (ignora sday/eday): fica no atributo da lista
        _ocupado.janela = tuple(_iso(datetime.strptime(x, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC"))) for x in janela.groups())
    else:
        _ocupado.janela = None
    for linha in r.text.replace("\r\n ", "").splitlines():
        if not linha.startswith("FREEBUSY"):
            continue
        tipo = "BUSY"
        m = re.search(r"FBTYPE=([A-Z\-]+)", linha)
        if m:
            tipo = m.group(1)
        if tipo == "FREE":
            continue
        for per in linha.split(":", 1)[1].split(","):
            try:
                a, b = per.split("/")
                da = datetime.strptime(a, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(TZ))
                if b.startswith("P"):
                    h = re.search(r"(\d+)H", b); mi = re.search(r"(\d+)M", b)
                    db = da + timedelta(hours=int(h.group(1)) if h else 0, minutes=int(mi.group(1)) if mi else 0)
                else:
                    db = datetime.strptime(b, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(TZ))
                out.append({"inicio": _iso(da), "fim": _iso(db), "tentativo": tipo == "BUSY-TENTATIVE"})
            except Exception:  # noqa: BLE001
                continue
    return out


# ── Partilha da agenda com a equipa (23-11-2026, pedido do Vítor): três modos por pessoa ───────────────────────
# «nenhum» = sem partilha; «livre» = livre/ocupado (por omissão); «tudo» = os colegas vêem as marcações (assunto, hora,
# local). Fica nos valores por omissão da pessoa no Frappe (`orbit_cal_partilha`); quem aplica nas permissões do Orbit
# Mail é o vigia do servidor (/opt/orbit/scripts/sogo-livre-ocupado.py, de 2 em 2 min), que lê `partilhas_sogo()`.
PARTILHA = "orbit_cal_partilha"
MODOS_PARTILHA = ("nenhum", "livre", "tudo")


def _modo(user: str) -> str:
    v = frappe.defaults.get_user_default(PARTILHA, user=user)
    return v if v in MODOS_PARTILHA else "livre"


@frappe.whitelist()
def minha_partilha():
    _guarda()
    return {"modo": _modo(frappe.session.user)}


@frappe.whitelist(methods=["POST"])
def definir_partilha(modo: str):
    _guarda()
    if modo not in MODOS_PARTILHA:
        frappe.throw("Modo de partilha desconhecido.")
    frappe.defaults.set_user_default(PARTILHA, modo, user=frappe.session.user)
    return {"modo": modo, "aviso": "Fica activo nos próximos 2 minutos."}


def partilhas_sogo():
    """Para o vigia do servidor (bench execute, sem sessão): {email: modo} de todas as pessoas deste Orbit."""
    us = frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, pluck="name")
    return {u.lower(): _modo(u) for u in us
            if "@" in u and not u.lower().startswith(("portal@", "suporte@", "it@", "noreply@", "admin@", "calendarios-sync@"))}


def _marcacoes_de(alvo: str, ini, fim, user, pwd):
    """As marcações de um colega que partilha «tudo»: o calendário pessoal dele, lido com a credencial de quem pede
    (o SOGo só o deixa ler se o colega deu a permissão). None se não se conseguir ler."""
    from zoneinfo import ZoneInfo
    a = ini.replace(tzinfo=ZoneInfo(TZ)) if ini.tzinfo is None else ini
    b = fim.replace(tzinfo=ZoneInfo(TZ)) if fim.tzinfo is None else fim
    faixa = (f'<c:time-range start="{a.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")}" '
             f'end="{b.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")}"/>')
    corpo = ('<?xml version="1.0"?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
             '<d:prop><c:calendar-data/></d:prop><c:filter><c:comp-filter name="VCALENDAR">'
             f'<c:comp-filter name="VEVENT">{faixa}</c:comp-filter></c:comp-filter></c:filter></c:calendar-query>')
    # Todos os calendários próprios do colega (o pessoal e os de fora, ex.: «MBontime»), não só o pessoal.
    pf = _pedido("PROPFIND", _base(alvo), user, pwd, '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop>'
                 '<d:resourcetype/></d:prop></d:propfind>', {"Depth": "1"})
    hrefs = []
    if pf.status_code == 207:
        for resp in ET.fromstring(pf.content).findall("d:response", NS):
            if resp.find("d:propstat/d:prop/d:resourcetype/c:calendar", NS) is not None:
                hrefs.append(_abs(resp.findtext("d:href", namespaces=NS) or ""))
    if not hrefs:
        hrefs = [_base(alvo) + "personal/"]
    out, lidos = [], 0
    for h in hrefs:
        r = _pedido("REPORT", h, user, pwd, corpo, {"Depth": "1"}, timeout=30)
        if r.status_code != 207:
            continue
        lidos += 1
        for resp in ET.fromstring(r.content).findall("d:response", NS):
            dados = resp.findtext("d:propstat/d:prop/c:calendar-data", namespaces=NS)
            if not dados:
                continue
            for ev in _ics_eventos(dados, a, b):
                if ev["dia_todo"]:
                    continue
                out.append({"inicio": ev["inicio"], "fim": ev["fim"], "tentativo": False, "titulo": ev["titulo"],
                            "local": ev["local"]})
    return out if lidos else None


@frappe.whitelist()
def disponibilidade(pessoas: str, inicio: str, fim: str):
    """Blocos ocupados de cada colega (`pessoas` = emails separados por vírgulas) entre `inicio` e `fim`, conforme a
    partilha que cada um escolheu: sem partilha → nada; livre/ocupado → só os blocos; tudo → com o assunto."""
    _guarda()
    user, pwd = _credenciais()
    if not pwd:
        return {"ligado": False}
    ini, fi = get_datetime(inicio), get_datetime(fim)
    lista = [e.strip().lower() for e in (pessoas or "").split(",") if "@" in e][:12]
    validos = set(frappe.get_all("User", filters={"enabled": 1, "name": ["in", lista]}, pluck="name"))
    out, modos = {}, {}
    for e in lista:
        if e not in validos:
            continue
        modos[e] = _modo(e)
        if modos[e] == "nenhum":
            out[e] = []
            continue
        # Lê-se a agenda do colega pelas datas pedidas (o freebusy.ifb do SOGo ignora as datas e devolve sempre a
        # mesma janela de ±7 dias — as semanas seguintes ficavam vazias). Em «livre» o SOGo já esconde o assunto
        # («(Evento Público)») e aqui tira-se de vez; o freebusy fica só de recurso.
        # Duas leituras (23-11-2026): o livre/ocupado do SOGo é o que a pessoa vê no Orbit Mail (o SOGo interpreta as
        # séries com exceções editadas à sua maneira — a Margot vê 14:30 onde a regra diz 09:30), mas só cobre uma
        # janela fixa de ±2 semanas e ignora as datas pedidas; fora dela lê-se a agenda pelas datas (CalDAV). Em
        # «tudo» o assunto vem da agenda; em «livre» o SOGo já o esconde e aqui tira-se de vez.
        fb = _ocupado(e, ini, fi, user, pwd)
        jan = getattr(_ocupado, "janela", None) if fb is not None else None
        try:
            agenda = _marcacoes_de(e, ini, fi, user, pwd)
        except Exception:  # noqa: BLE001
            agenda = None
        if agenda is None:
            out[e] = [x for x in (fb or []) if x["inicio"] < _iso(fi) and x["fim"] > _iso(ini)]
            continue
        dentro = (lambda x: jan[0] <= x["inicio"] < jan[1]) if jan else (lambda x: False)
        a_iso, b_iso = _iso(ini), _iso(fi)
        blocos = [x for x in (fb or []) if dentro(x)] + [x for x in agenda if not dentro(x)]
        blocos = [x for x in blocos if x["inicio"] < b_iso and x["fim"] > a_iso]
        if modos[e] == "tudo":
            for x in blocos:
                if "titulo" not in x:
                    igual = [y for y in agenda if y["inicio"][:10] == x["inicio"][:10] and y["inicio"] < x["fim"] and y["fim"] > x["inicio"]]
                    x["titulo"] = igual[0]["titulo"] if igual else ""
        else:
            blocos = [{"inicio": x["inicio"], "fim": x["fim"], "tentativo": x.get("tentativo", False)} for x in blocos]
        out[e] = blocos
    return {"ligado": True, "ocupado": out, "modos": modos}


@frappe.whitelist()
def primeiro_livre(pessoas: str, duracao: int = 60, desde: str = None, dias: int = 10):
    """O primeiro horário em que a pessoa e os colegas indicados estão todos livres, em dias úteis, 9h–13h e 14h–18h30
    (o horário da casa), em passos de 15 min."""
    _guarda()
    user, pwd = _credenciais()
    if not pwd:
        frappe.throw("Ligue primeiro o calendário.")
    dur = max(cint(duracao), 15)
    ini = get_datetime(desde) if desde else now_datetime()
    ini = ini.replace(second=0, microsecond=0)
    ini += timedelta(minutes=(15 - ini.minute % 15) % 15)
    fim = ini + timedelta(days=max(cint(dias), 1))
    todos = [user] + [e.strip().lower() for e in (pessoas or "").split(",") if "@" in e and e.strip().lower() != user][:10]
    blocos = []
    for e in todos:
        oc = _ocupado(e, ini, fim, user, pwd) or []
        blocos += [(get_datetime(b["inicio"]), get_datetime(b["fim"])) for b in oc]
    janelas = [((9, 0), (13, 0)), ((14, 0), (18, 30))]
    t = ini
    while t < fim:
        if t.weekday() < 5:
            for (h1, m1), (h2, m2) in janelas:
                a = t.replace(hour=h1, minute=m1)
                b = t.replace(hour=h2, minute=m2)
                c = max(a, t)
                while c + timedelta(minutes=dur) <= b:
                    d = c + timedelta(minutes=dur)
                    if not any(x < d and y > c for x, y in blocos):
                        return {"inicio": _iso(c), "fim": _iso(d), "pessoas": todos}
                    c += timedelta(minutes=15)
        t = (t + timedelta(days=1)).replace(hour=0, minute=0)
    return {"inicio": None}
