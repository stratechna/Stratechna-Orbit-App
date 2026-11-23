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


def _validar(m, pasta: str):
    if pasta not in _pastas_validas(m):
        frappe.throw("Caixa sem acesso.")


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
