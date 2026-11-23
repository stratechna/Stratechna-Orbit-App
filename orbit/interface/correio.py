"""Correio na caixa de entrada do Orbit, por IMAP como a própria pessoa (F1, 23-11-2026).

Ver docs/PLANO-CAIXA-ENTRADA-UNICA.md. O que se faz aqui faz-se no servidor de correio: aparece igual no Orbit Mail e
no telemóvel. Entrando como a pessoa, as partilhadas em «lido por pessoa» (namespace `Partilhadas.<caixa>` do Dovecot)
têm o «lido» de cada um.

A palavra-passe é a da caixa, que o Orbit já guarda cifrada para o calendário (`calendario._senha`). Se não a tiver,
ou se o servidor a recusar, as funções respondem `{"ligar": true}` e o ecrã pede-a uma vez (`calendario.ligar`).
"""
from __future__ import annotations

import email
import imaplib
import re
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

import frappe
from frappe.utils import cint

POR_PAGINA = 50
PARTILHADAS = re.compile(r"^Partilhadas[./]([^./]+)$")


def _guarda():
    from orbit.interface.api import _guarda as g
    g()


def _servidor(user: str):
    dominio = user.split("@")[-1].lower()
    for nome in [dominio] + frappe.get_all("Email Domain", pluck="name"):
        d = frappe.db.get_value("Email Domain", nome, ["email_server", "incoming_port", "use_ssl"], as_dict=True)
        if d and d.email_server:
            return d.email_server, cint(d.incoming_port) or 993, bool(d.use_ssl) or cint(d.incoming_port) in (0, 993)
    return f"mail.{dominio}", 993, True


class _SemLigacao(Exception):
    pass


def _ligar():
    from orbit.interface.calendario import _senha
    user = frappe.session.user
    pwd = _senha(user)
    if not pwd or "@" not in user:
        raise _SemLigacao()
    host, porta, ssl = _servidor(user)
    m = imaplib.IMAP4_SSL(host, porta, timeout=20) if ssl else imaplib.IMAP4(host, porta, timeout=20)
    try:
        m.login(user, pwd)
    except imaplib.IMAP4.error:
        raise _SemLigacao()
    return m


def _sair(m):
    try:
        m.logout()
    except Exception:
        pass


def _q(pasta: str) -> str:
    return '"' + pasta.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dec(v) -> str:
    try:
        return str(make_header(decode_header(v or ""))).strip()
    except Exception:
        return str(v or "").strip()


def _pastas_validas(m) -> list:
    """Entrada pessoal + Entradas das partilhadas do namespace."""
    _, linhas = m.list()
    nomes = []
    for l in linhas or []:
        t = l.decode("utf-8", "replace")
        mm = re.match(r'^\((?P<f>[^)]*)\) (?:"(?P<s>[^"]*)"|NIL) (?P<n>.+)$', t)
        if not mm:
            continue
        n = mm.group("n").strip()
        if n.startswith('"') and n.endswith('"'):
            n = n[1:-1].replace('\\"', '"')
        if "\\Noselect" in mm.group("f"):
            continue
        nomes.append(n)
    out = ["INBOX"] if "INBOX" in [x.upper() for x in nomes] else []
    out += sorted(n for n in nomes if PARTILHADAS.match(n))
    return out


def _rotulo(pasta: str, user: str) -> tuple[str, str]:
    if pasta.upper() == "INBOX":
        return user, "Entrada"
    caixa = PARTILHADAS.match(pasta).group(1)
    end = f"{caixa}@{user.split('@')[-1]}"
    return end, caixa.replace("-", " ").replace("_", " ").capitalize()


def _todas(m) -> list:
    _, linhas = m.list()
    out = []
    for l in linhas or []:
        t = l.decode("utf-8", "replace")
        mm = re.match(r'^\((?P<f>[^)]*)\) (?:"(?P<s>[^"]*)"|NIL) (?P<n>.+)$', t)
        if not mm:
            continue
        n = mm.group("n").strip()
        if n.startswith('"') and n.endswith('"'):
            n = n[1:-1].replace('\\"', '"')
        out.append((n, mm.group("f")))
    return out


def _caixa(pasta: str) -> str:
    """A caixa a que a pasta pertence: "" (a pessoal) ou "Partilhadas.<caixa>"."""
    mm = re.match(r"^(Partilhadas[./][^./]+)", pasta)
    return mm.group(1) if mm else ""


def _da_caixa(nome: str, caixa: str) -> bool:
    if caixa:
        return nome == caixa or nome.startswith(caixa + ".")
    return not nome.startswith("Partilhadas")


def _validar(m, pasta: str):
    """F2 (23-11-2026): qualquer pasta da caixa pessoal ou de uma partilhada do namespace — nunca fora delas."""
    entradas = _pastas_validas(m)
    caixa = _caixa(pasta)
    if caixa and caixa not in entradas:
        frappe.throw("Caixa sem acesso.")
    if not any(n == pasta and "\\Noselect" not in f for n, f in _todas(m)):
        frappe.throw("Caixa sem acesso.")


def _utf7(nome: str) -> str:
    """IMAP modified UTF-7 → texto (só para mostrar)."""
    import base64
    def troca(mm):
        x = mm.group(1)
        if not x:
            return "&"
        try:
            return base64.b64decode(x.replace(",", "/") + "=" * (-len(x) % 4)).decode("utf-16-be")
        except Exception:
            return mm.group(0)
    return re.sub(r"&([^-]*)-", troca, nome)


ESPECIAIS = {"INBOX": ("Entrada", 0), "Sent": ("Enviados", 1), "Drafts": ("Rascunhos", 2), "Arquivo": ("Arquivo", 3),
             "Agendados": ("Agendados", 4), "Spam": ("Spam", 8), "Trash": ("Lixo", 9)}


@frappe.whitelist()
def pastas_da_caixa(pasta: str):
    """As pastas da caixa a que `pasta` pertence (Entrada, Enviados, Arquivo, Lixo… e as próprias)."""
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True, "pastas": []}
    try:
        _validar(m, pasta)
        caixa = _caixa(pasta)
        out = []
        for n, f in _todas(m):
            if "\\Noselect" in f or not _da_caixa(n, caixa):
                continue
            curto = n[len(caixa) + 1:] if caixa and n != caixa else ("INBOX" if caixa else n)
            rot, ordem = ESPECIAIS.get(curto, (None, 5))
            out.append({"pasta": n, "nome": rot or _utf7(curto).replace(".", " › "), "ordem": ordem})
        out.sort(key=lambda x: (x["ordem"], x["nome"].lower()))
        return {"ligar": False, "pastas": out}
    finally:
        _sair(m)


def _destino(m, pasta: str, curto: str, criar: bool = False) -> str:
    caixa = _caixa(pasta)
    alvo = f"{caixa}.{curto}" if caixa else curto
    if not any(n == alvo for n, _f in _todas(m)):
        if not criar:
            frappe.throw("Esta caixa não tem a pasta «%s»." % ESPECIAIS.get(curto, (curto,))[0])
        m.create(_q(alvo))
        m.subscribe(_q(alvo))
    return alvo


def _mover(m, pasta: str, uid: str, destino: str):
    m.select(_q(pasta))
    t, r = m.uid("MOVE", str(cint(uid)), _q(destino))
    if t != "OK":
        frappe.throw("O servidor não deixou mover a mensagem.")


@frappe.whitelist(methods=["POST"])
def mover(pasta: str, uid: str, destino: str):
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True}
    try:
        _validar(m, pasta)
        _validar(m, destino)
        if _caixa(destino) != _caixa(pasta):
            frappe.throw("Só se move dentro da mesma caixa.")
        _mover(m, pasta, uid, destino)
        return {"ok": True}
    finally:
        _sair(m)


@frappe.whitelist(methods=["POST"])
def arquivar(pasta: str, uid: str):
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True}
    try:
        _validar(m, pasta)
        _mover(m, pasta, uid, _destino(m, pasta, "Arquivo", criar=True))
        return {"ok": True}
    finally:
        _sair(m)


@frappe.whitelist(methods=["POST"])
def apagar(pasta: str, uid: str):
    """Para o Lixo da mesma caixa (como no Orbit Mail). No próprio Lixo não se apaga daqui."""
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True}
    try:
        _validar(m, pasta)
        lixo = _destino(m, pasta, "Trash", criar=True)
        if pasta == lixo:
            frappe.throw("Já está no Lixo — apaga-se de vez no Orbit Mail.")
        _mover(m, pasta, uid, lixo)
        return {"ok": True}
    finally:
        _sair(m)


@frappe.whitelist()
def anexo(pasta: str, uid: str, i: int = 0):
    """Descarrega o anexo n.º i (pela ordem de `mensagem`)."""
    _guarda()
    m = _ligar()
    try:
        _validar(m, pasta)
        m.select(_q(pasta), readonly=True)
        _, dados = m.uid("FETCH", str(cint(uid)), "(BODY.PEEK[])")
        bruto = next((p[1] for p in dados if isinstance(p, tuple)), None)
        if not bruto:
            frappe.throw("A mensagem já não existe nesta caixa.")
        partes = [p for p in email.message_from_bytes(bruto).walk() if not p.is_multipart()
                  and (p.get_filename() or (p.get("Content-Disposition") or "").lower().startswith("attachment"))]
        if cint(i) >= len(partes):
            frappe.throw("Anexo inexistente.")
        p = partes[cint(i)]
        frappe.local.response.filename = _dec(p.get_filename()) or "anexo"
        frappe.local.response.filecontent = p.get_payload(decode=True) or b""
        frappe.local.response.type = "download"
    finally:
        _sair(m)


@frappe.whitelist()
def pastas():
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True, "pastas": []}
    try:
        user = frappe.session.user
        out = []
        for p in _pastas_validas(m):
            _, r = m.status(_q(p), "(MESSAGES UNSEEN)")
            s = r[0].decode() if r and r[0] else ""
            end, nome = _rotulo(p, user)
            out.append({"pasta": p, "email": end, "nome": nome, "pessoal": p.upper() == "INBOX",
                        "por_ler": int((re.search(r"UNSEEN (\d+)", s) or [0, 0])[1]),
                        "total": int((re.search(r"MESSAGES (\d+)", s) or [0, 0])[1])})
        return {"ligar": False, "pastas": out}
    finally:
        _sair(m)


@frappe.whitelist()
def lista(pasta: str, pagina: int = 0, so_por_ler: int = 0):
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True, "itens": []}
    try:
        _validar(m, pasta)
        m.select(_q(pasta), readonly=True)
        _, r = m.uid("SEARCH", None, "UNSEEN" if cint(so_por_ler) else "ALL")
        uids = (r[0] or b"").split()
        uids.reverse()
        pg = max(cint(pagina), 0)
        fatia = uids[pg * POR_PAGINA:(pg + 1) * POR_PAGINA]
        itens = []
        if fatia:
            _, dados = m.uid("FETCH", b",".join(fatia),
                             "(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE CONTENT-TYPE)])")
            atual = {}
            for parte in dados:
                if not isinstance(parte, tuple):
                    continue
                cab = parte[0].decode("utf-8", "replace")
                uid = (re.search(r"UID (\d+)", cab) or [None, None])[1]
                flags = (re.search(r"FLAGS \(([^)]*)\)", cab) or [None, ""])[1]
                h = email.message_from_bytes(parte[1])
                nome, end = parseaddr(_dec(h.get("From")))
                try:
                    quando = parsedate_to_datetime(h.get("Date")).isoformat()
                except Exception:
                    quando = None
                atual[uid] = {"tipo": "mail", "id": uid, "pasta": pasta, "quem": nome or end, "email": end.lower(),
                              "titulo": _dec(h.get("Subject")) or "(sem assunto)", "data": quando,
                              "lida": "\\Seen" in flags, "por_responder": "\\Seen" not in flags,
                              "respondida": "\\Answered" in flags,
                              "anexos": "multipart/mixed" in (h.get("Content-Type") or "").lower()}
            itens = [atual[u.decode()] for u in fatia if u.decode() in atual]
        return {"ligar": False, "itens": itens, "mais": len(uids) > (pg + 1) * POR_PAGINA, "total": len(uids)}
    finally:
        _sair(m)


def _corpo(msg) -> tuple[str, list]:
    html, texto, anexos = None, None, []
    for parte in msg.walk():
        if parte.is_multipart():
            continue
        tipo = parte.get_content_type()
        disp = (parte.get("Content-Disposition") or "").lower()
        nome = parte.get_filename()
        if nome or disp.startswith("attachment"):
            anexos.append({"nome": _dec(nome) or "anexo", "tamanho": len(parte.get_payload(decode=True) or b""), "tipo": tipo})
            continue
        try:
            conteudo = (parte.get_payload(decode=True) or b"").decode(parte.get_content_charset() or "utf-8", "replace")
        except Exception:
            conteudo = ""
        if tipo == "text/html" and html is None:
            html = conteudo
        elif tipo == "text/plain" and texto is None:
            texto = conteudo
    if html is None:
        from html import escape
        html = "<div style='white-space:pre-wrap'>" + escape(texto or "") + "</div>"
    # imagens externas bloqueadas (como no Orbit Mail) — o ecrã pode mostrá-las a pedido
    html = re.sub(r"(<img\b[^>]*?)\ssrc=([\"'])(https?:)", r"\1 data-orbit-src=\2\3", html, flags=re.I)
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.I | re.S)
    return html, anexos


@frappe.whitelist()
def mensagem(pasta: str, uid: str):
    """Abre a mensagem e marca-a como lida no servidor (como no Orbit Mail)."""
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True}
    try:
        _validar(m, pasta)
        m.select(_q(pasta))
        uid = str(cint(uid))
        _, dados = m.uid("FETCH", uid, "(FLAGS BODY.PEEK[])")
        bruto = next((p[1] for p in dados if isinstance(p, tuple)), None)
        if not bruto:
            frappe.throw("A mensagem já não existe nesta caixa.")
        m.uid("STORE", uid, "+FLAGS", "(\\Seen)")
        msg = email.message_from_bytes(bruto)
        html, anexos = _corpo(msg)
        nome, end = parseaddr(_dec(msg.get("From")))
        try:
            quando = parsedate_to_datetime(msg.get("Date")).isoformat()
        except Exception:
            quando = None
        fmt = lambda v: ", ".join((f"{n} <{e}>" if n else e) for n, e in getaddresses([_dec(v)]) if e)  # noqa: E731
        return {"ligar": False, "pasta": pasta, "uid": uid, "assunto": _dec(msg.get("Subject")) or "(sem assunto)",
                "de": nome or end, "email": end.lower(), "para": fmt(msg.get("To")), "cc": fmt(msg.get("Cc")),
                "data": quando, "html": html, "anexos": anexos, "imagens_externas": "data-orbit-src=" in html}
    finally:
        _sair(m)


@frappe.whitelist(methods=["POST"])
def marcar(pasta: str, uid: str, lida: int = 1):
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True}
    try:
        _validar(m, pasta)
        m.select(_q(pasta))
        m.uid("STORE", str(cint(uid)), "+FLAGS" if cint(lida) else "-FLAGS", "(\\Seen)")
        return {"ok": True}
    finally:
        _sair(m)


# ── Responder / responder a todos / reencaminhar (F2, 23-11-2026) ───────────────────────────────────────────────
# Envia por SMTP como a própria pessoa (o mesmo servidor e a mesma palavra-passe do IMAP); numa partilhada, o remetente
# é a caixa partilhada (o servidor só o deixa a quem tem acesso a ela — `sender_login_partilhas`). A cópia fica nos
# Enviados da caixa e a original fica marcada como respondida (ou reencaminhada) — tudo visível no Orbit Mail.

def _remetente(pasta: str, user: str) -> tuple[str, str]:
    if not _caixa(pasta):
        return frappe.db.get_value("User", user, "full_name") or "", user
    end, nome = _rotulo(_caixa(pasta), user)
    return "", end


@frappe.whitelist(methods=["POST"])
def enviar(pasta: str, uid: str, modo: str = "responder", para: str = "", cc: str = "", texto: str = ""):
    import html as _html
    import smtplib
    from email.message import EmailMessage
    from email.utils import formataddr, formatdate, make_msgid
    _guarda()
    if modo not in ("responder", "todos", "reencaminhar"):
        frappe.throw("Modo desconhecido.")
    if not (para or "").strip():
        frappe.throw("Falta o destinatário.")
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True}
    from orbit.interface.calendario import _senha
    user = frappe.session.user
    try:
        _validar(m, pasta)
        m.select(_q(pasta))
        uid = str(cint(uid))
        _, dados = m.uid("FETCH", uid, "(BODY.PEEK[])")
        bruto = next((p[1] for p in dados if isinstance(p, tuple)), None)
        if not bruto:
            frappe.throw("A mensagem já não existe nesta caixa.")
        orig = email.message_from_bytes(bruto)
        html_orig, _anx = _corpo(orig)
        assunto = _dec(orig.get("Subject")) or ""
        pre = "Fwd: " if modo == "reencaminhar" else "Re: "
        if not re.match(r"^\s*(re|fwd?|enc|res)\s*:", assunto, re.I):
            assunto = pre + assunto
        nome, de = _remetente(pasta, user)
        msg = EmailMessage()
        msg["From"] = formataddr((nome, de)) if nome else de
        msg["To"] = para
        if (cc or "").strip():
            msg["Cc"] = cc
        msg["Subject"] = assunto
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=de.split("@")[-1])
        if modo != "reencaminhar" and orig.get("Message-ID"):
            msg["In-Reply-To"] = orig.get("Message-ID")
            msg["References"] = ((orig.get("References") or "") + " " + orig.get("Message-ID")).strip()
        quando = _dec(orig.get("Date"))
        quem = _dec(orig.get("From"))
        cab = (f"<p>---------- Mensagem reencaminhada ----------<br>De: {_html.escape(quem)}<br>Data: {_html.escape(quando)}<br>"
               f"Assunto: {_html.escape(_dec(orig.get('Subject')))}</p>") if modo == "reencaminhar" \
            else f"<p>Em {_html.escape(quando)}, {_html.escape(quem)} escreveu:</p>"
        novo = "".join("<p>" + _html.escape(p).replace("\n", "<br>") + "</p>" for p in re.split(r"\n{2,}", (texto or "").strip()) if p)
        html_orig = html_orig.replace("data-orbit-src=", "src=")
        corpo_html = (f"<div>{novo}</div><br>{cab}"
                      f"<blockquote style='margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex'>{html_orig}</blockquote>")
        msg.set_content((texto or "").strip() + "\n\n" + re.sub(r"<[^>]+>", "", cab).strip())
        msg.add_alternative(corpo_html, subtype="html")
        if modo == "reencaminhar":
            for p in orig.walk():
                if p.is_multipart():
                    continue
                fn = p.get_filename()
                if fn or (p.get("Content-Disposition") or "").lower().startswith("attachment"):
                    mt, st = (p.get_content_type() or "application/octet-stream").split("/", 1)
                    msg.add_attachment(p.get_payload(decode=True) or b"", maintype=mt, subtype=st, filename=_dec(fn) or "anexo")
        host, _porta, _ssl = _servidor(user)
        destinos = [e for _n, e in getaddresses([para, cc or ""]) if e]
        with smtplib.SMTP(host, 587, timeout=30) as s:
            s.starttls()
            s.login(user, _senha(user))
            s.send_message(msg, from_addr=de, to_addrs=destinos)
        # cópia nos Enviados da caixa e a original marcada
        try:
            enviados = _destino(m, pasta, "Sent", criar=True)
            import time
            m.append(_q(enviados), "(\\Seen)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        except Exception:  # noqa: BLE001
            frappe.log_error(title="Orbit correio: cópia nos Enviados")
        m.select(_q(pasta))
        m.uid("STORE", uid, "+FLAGS", "($Forwarded)" if modo == "reencaminhar" else "(\\Answered)")
        return {"ok": True, "de": de}
    finally:
        _sair(m)


@frappe.whitelist()
def destinatarios(pasta: str, uid: str, modo: str = "responder"):
    """Para / Cc pré-preenchidos para responder (ao remetente, ou a todos menos à própria caixa)."""
    _guarda()
    try:
        m = _ligar()
    except _SemLigacao:
        return {"ligar": True}
    try:
        _validar(m, pasta)
        m.select(_q(pasta), readonly=True)
        _, dados = m.uid("FETCH", str(cint(uid)), "(BODY.PEEK[HEADER])")
        bruto = next((p[1] for p in dados if isinstance(p, tuple)), b"")
        h = email.message_from_bytes(bruto)
        _n, de = _remetente(pasta, frappe.session.user)
        meu = {de.lower(), frappe.session.user.lower()}
        resp = getaddresses([_dec(h.get("Reply-To") or h.get("From"))])
        if modo == "reencaminhar":
            return {"para": "", "cc": ""}
        para = [e for _n2, e in resp if e and e.lower() not in meu]
        cc = []
        if modo == "todos":
            cc = [e for _n2, e in getaddresses([_dec(h.get("To")), _dec(h.get("Cc"))]) if e and e.lower() not in meu and e not in para]
        return {"para": ", ".join(para), "cc": ", ".join(dict.fromkeys(cc))}
    finally:
        _sair(m)
