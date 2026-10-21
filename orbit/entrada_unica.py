"""Entrada única: o Orbit entra pelo portal (OpenID Connect) — 17-10-2026, Fase 2.

Plano: docs/PLANO-ENTRADA-UNICA-2FA.md (área de trabalho). Pedido do Vítor: entrar numa app abre todas;
sair de uma sai de todas.

**Entrar.** Cada tenant tem um `Social Login Key` «Stratechna» (criado aqui, no after_migrate, a partir
de `stratechna_login` no common_site_config — o segredo do cliente `orbit` no portal, igual para todos os
tenants). O botão aparece na página de entrada. O regresso não usa o `custom` do Frappe mas `regresso`
(abaixo): troca o código, **verifica a assinatura do id_token** pela JWKS do portal e guarda o `sid` da
sessão central ao lado da sessão do Frappe. Depois é o fluxo do Frappe (`login_oauth_user`): o utilizador
tem de existir com o mesmo email — não se criam contas por aqui (sign_ups = Deny).

**Sair.**
  · no Orbit → `on_logout` avisa o portal (`/api/oidc/terminar`, servidor a servidor), que termina a
    sessão central: o portal, o webmail e os outros tenants caem;
  · noutra app → o portal chama `saida_canal` (Back-Channel Logout) com um `logout_token` assinado; aqui
    apagam-se as sessões do Frappe nascidas dessa sessão central (só essas: quem entrou com palavra-passe
    noutro computador não é posto fora).

**A entrada por palavra-passe continua** durante a transição. `orbit_entrada_stratechna_auto = 1` no
site_config faz a página de entrada seguir logo para o portal (com `?senha=1` volta-se ao formulário).
"""
import json
import time

import frappe
from frappe.rate_limiter import rate_limit

PROVEDOR = "stratechna"
PORTAL = "https://portal.stratechna.com"
EMISSOR = PORTAL + "/api/oidc"
REGRESSO = "/api/method/orbit.entrada_unica.regresso"
EVENTO_SAIDA = "http://schemas.openid.net/event/backchannel-logout"
_CHAVE_CACHE = "orbit_entrada_unica:sid:"
_JWKS: dict = {}


def _q(d: dict) -> str:
    from urllib.parse import urlencode
    return urlencode(d)


def _conf() -> dict | None:
    c = frappe.conf.get("stratechna_login") or {}
    return c if c.get("client_id") and c.get("client_secret") else None


# ── after_migrate ────────────────────────────────────────────────────────────

def garantir() -> None:
    try:
        _garantir()
    except Exception:
        frappe.log_error(title="orbit.entrada_unica.garantir")


def _garantir() -> None:
    # A «ligação por e-mail» do Frappe não faz sentido com a entrada única (Vítor, 19-10-2026): entra-se pelo portal
    # sem se ver nada, ou pelo formulário com as credenciais do Orbit. Desligada em todos os tenants, também nos novos.
    if frappe.db.get_single_value("System Settings", "login_with_email_link"):
        frappe.db.set_single_value("System Settings", "login_with_email_link", 0)
    c = _conf()
    if not c:
        return
    valores = {
        "provider_name": "Stratechna",
        "social_login_provider": "Custom",
        "enable_social_login": 1,
        "client_id": c["client_id"],
        "client_secret": c["client_secret"],
        "custom_base_url": 1,
        "base_url": PORTAL,
        "authorize_url": "/api/oidc/authorize",
        "access_token_url": "/api/oidc/token",
        "api_endpoint": "/api/oidc/userinfo",
        "redirect_url": REGRESSO,
        "auth_url_data": json.dumps({"response_type": "code", "scope": "openid email profile"}),
        "user_id_property": "sub",
        "sign_ups": "Deny",
    }
    if frappe.db.exists("Social Login Key", PROVEDOR):
        doc = frappe.get_doc("Social Login Key", PROVEDOR)
        mudou = any(str(doc.get(k) or "") != str(v) for k, v in valores.items() if k != "client_secret") \
            or doc.get_password("client_secret", raise_exception=False) != c["client_secret"]
        if not mudou:
            return
        doc.update(valores)
    else:
        doc = frappe.get_doc({"doctype": "Social Login Key", **valores})
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()


# ── regresso do portal ───────────────────────────────────────────────────────

def _jwks(forcar: bool = False) -> dict:
    if forcar or not _JWKS or time.time() - _JWKS.get("_em", 0) > 3600:
        import requests
        r = requests.get(EMISSOR + "/jwks", timeout=10)
        r.raise_for_status()
        _JWKS.clear()
        _JWKS.update({k["kid"]: k for k in r.json().get("keys", [])})
        _JWKS["_em"] = time.time()
    return _JWKS


def _verificar(token: str, audiencia: str, exigir_exp: bool = True) -> dict:
    import jwt
    kid = jwt.get_unverified_header(token).get("kid")
    chaves = _jwks()
    if kid not in chaves:
        chaves = _jwks(forcar=True)
    chave = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(chaves[kid]))
    return jwt.decode(token, chave, algorithms=["RS256"], audience=audiencia, issuer=EMISSOR,
                      options={"verify_exp": exigir_exp}, leeway=30)


@frappe.whitelist(allow_guest=True)
def regresso(code: str | None = None, state: str | None = None, error: str | None = None, **_):
    import requests
    from frappe.utils.oauth import login_oauth_user, get_redirect_uri
    from frappe.utils.oauth import consume_oauth_state
    c = _conf()
    if error or not code or not c:
        # A pergunta silenciosa (prompt=none) da página de entrada: sem sessão no portal, mostra-se o ecrã do Orbit.
        destino = consume_oauth_state(state) if state else None
        q = {"nativo": 1}
        if destino:
            q["redirect-to"] = destino
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/login?" + _q(q)
        return
    r = requests.post(EMISSOR + "/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": get_redirect_uri(PROVEDOR),
        "client_id": c["client_id"], "client_secret": c["client_secret"]}, timeout=15)
    if r.status_code != 200:
        frappe.log_error(title="orbit.entrada_unica.regresso", message=r.text[:500])
        frappe.respond_as_web_page("Entrada com a Stratechna", "O pedido expirou. Volte a tentar.",
                                   http_status_code=400, indicator_color="red")
        return
    tok = r.json()
    idt = _verificar(tok["id_token"], c["client_id"])
    dados = {k: idt.get(k) for k in ("sub", "email", "email_verified", "name", "given_name", "family_name",
                                     "first_name", "last_name")}
    # 19-10-2026 (Vítor): a sessão do portal pode ser de alguém que não tem conta NESTE tenant (ex.: o Vítor a abrir o
    # tenant de demonstração). Em vez do «Signup is Disabled» do Frappe, mostra-se o formulário do Orbit, para entrar
    # com uma conta deste tenant. Nunca se cria conta pela entrada única (sign_ups = Deny).
    email = (idt.get("email") or "").strip().lower()
    utilizador = frappe.db.get_value("User", {"email": email}, ["name", "enabled"], as_dict=True) if email else None
    # 21-10-2026: um administrador do portal sem conta neste tenant entra em assistência (ver _assistencia).
    if (not utilizador or not utilizador.enabled or email == ASSISTENCIA) and idt.get("stratechna_equipa") is True:
        return _assistencia(idt, state)
    if email == ASSISTENCIA:
        utilizador = None          # a conta de assistência só abre com uma sessão de administrador do portal
    if not utilizador or not utilizador.enabled or utilizador.name in ("Guest", "Administrator"):
        destino = consume_oauth_state(state) if state else None
        q = {"nativo": 1, "sem_conta": 1}
        if destino:
            q["redirect-to"] = destino
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/login?" + _q(q)
        return
    frappe.flags.orbit_via_portal = True      # a sessão central já existe: não é preciso a ponte
    # 18-10-2026: a língua é a do portal (idioma_pessoa; casa = pt) — antes do login_oauth_user, que já
    # desenha a resposta: a primeira página abre logo na língua certa. Ver orbit/lingua.py.
    lingua = "sem locale"
    if idt.get("locale") and idt.get("email"):
        from orbit.lingua import definir
        try:
            lingua = definir(idt["email"], idt["locale"])
        except Exception:
            frappe.log_error(title="orbit.entrada_unica.lingua")
    login_oauth_user(dados, provider=PROVEDOR, state=state)
    if lingua == "sem utilizador":          # primeira entrada: o utilizador acabou de nascer
        try:
            definir(idt["email"], idt["locale"])
        except Exception:
            frappe.log_error(title="orbit.entrada_unica.lingua")
    sid_frappe = getattr(frappe.local, "session", None) and frappe.local.session.sid
    if sid_frappe and sid_frappe != "Guest" and idt.get("sid"):
        frappe.cache.set_value(_CHAVE_CACHE + sid_frappe, idt["sid"], expires_in_sec=31 * 86400)


# ── assistência (21-10-2026) ─────────────────────────────────────────────────
# Pedido do Vítor: quem está no portal como administrador tem de conseguir entrar no Orbit de qualquer cliente
# (assistência), mesmo sem conta lá. Decisões A1–A3 (21-10): um só utilizador por tenant, suporte@stratechna.pt,
# com os papéis de um administrador do tenant, que não conta para os utilizadores contratados; o nome de quem
# entrou fica registado (Activity Log do tenant e `orbit_assistencias` no portal); sem email ao cliente.
# O portal só põe `stratechna_equipa` no id_token de um administrador (is_admin). A conta nunca tem palavra-passe:
# só se entra nela por aqui. Sair da assistência fecha só esta sessão — a do portal continua.
ASSISTENCIA = "suporte@stratechna.pt"   # .pt, não .com (Vítor, 21-10)
_ASSIST = "orbit_entrada_unica:assistencia:"
_PAPEIS_FORA = {"Administrator", "Guest", "All", "Desk User"}


def _papeis_de_admin() -> set:
    """Os papéis que têm os administradores (System Manager) activos deste tenant — «iguais às de um admin»."""
    adm = [u for u in frappe.get_all("Has Role", filters={"role": "System Manager", "parenttype": "User"},
                                     pluck="parent")
           if u not in ("Administrator", ASSISTENCIA) and frappe.db.get_value("User", u, "enabled")]
    papeis = set(frappe.get_all("Has Role", filters={"parenttype": "User", "parent": ["in", adm]}, pluck="role")) if adm else set()
    return (papeis | {"System Manager"}) - _PAPEIS_FORA


def _garantir_assistencia() -> None:
    if not frappe.db.exists("User", ASSISTENCIA):
        u = frappe.get_doc({"doctype": "User", "email": ASSISTENCIA, "first_name": "Assistência",
                            "last_name": "Stratechna", "user_type": "System User", "enabled": 1,
                            "send_welcome_email": 0, "language": "pt"})
        u.flags.ignore_permissions = True
        u.flags.no_welcome_mail = True
        u.insert()
    u = frappe.get_doc("User", ASSISTENCIA)
    mudou = False
    if not u.enabled or u.user_type != "System User":
        u.enabled, u.user_type, mudou = 1, "System User", True
    falta = _papeis_de_admin() - {r.role for r in u.roles}
    for p in sorted(falta):
        u.append("roles", {"role": p})
        mudou = True
    if mudou:
        u.flags.ignore_permissions = True
        u.save()


def _assistencia(idt: dict, state: str | None):
    from frappe.utils.oauth import consume_oauth_state
    destino = (consume_oauth_state(state) if state else None) or "/app"
    quem = {"nome": idt.get("name") or idt.get("email"), "email": (idt.get("email") or "").lower(),
            "sid": idt.get("sid")}
    try:
        frappe.set_user("Administrator")
        _garantir_assistencia()
        frappe.get_doc({"doctype": "Activity Log", "user": ASSISTENCIA, "full_name": quem["nome"],
                        "operation": "Login", "status": "Success", "reference_doctype": "User",
                        "reference_name": ASSISTENCIA,
                        "subject": f"Assistência Stratechna: {quem['nome']} <{quem['email']}>"}
                       ).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.entrada_unica.assistencia")
        frappe.set_user("Guest")
        frappe.respond_as_web_page("Assistência Stratechna", "Não foi possível abrir a assistência neste Orbit.",
                                   http_status_code=500, indicator_color="red")
        return
    frappe.flags.orbit_via_portal = True
    # audit_user (Frappe 16): cada Version gravada nesta sessão leva o email de quem está em assistência.
    frappe.local.login_manager.login_as(ASSISTENCIA, audit_user=quem["email"])
    sid_frappe = frappe.local.session.sid
    if quem["sid"]:
        frappe.cache.set_value(_CHAVE_CACHE + sid_frappe, quem["sid"], expires_in_sec=31 * 86400)
    frappe.cache.set_value(_ASSIST + sid_frappe, quem, expires_in_sec=31 * 86400)
    c = _conf()
    try:
        import requests
        requests.post(EMISSOR + "/assistencia", data={"sid": quem["sid"] or "", "host": frappe.local.request.host},
                      auth=(c["client_id"], c["client_secret"]), timeout=8)
    except Exception:
        frappe.log_error(title="orbit.entrada_unica.assistencia (registo no portal)")
    frappe.local.response["type"] = "redirect"
    from urllib.parse import urlparse
    u = urlparse(destino)
    proprio = (frappe.local.request.host or "").split(":")[0].lower()
    if destino.startswith("//") or (u.netloc and (u.scheme != "https" or (u.hostname or "").lower() != proprio)):
        destino = "/app"
    frappe.local.response["location"] = destino


# Entrada com a própria caixa (Vítor, 21-10): no formulário do Orbit, suporte@stratechna.pt + a palavra-passe da
# caixa. A palavra-passe verifica-se no IMAP do BDS (rede privada, 10.0.0.4) e nunca se guarda no Orbit. O BDS
# apresenta um certificado próprio (CN/SAN StratechnaHostingBDS, até 2036 — o mesmo que o SOGo usa,
# /opt/orbit/config/bds-mail.crt): é ele a única autoridade aceite, com o nome verificado. Aqui não se sabe quem
# é a pessoa: o registo diz «caixa suporte@». Sobrepõe-se com `orbit_assistencia_imap` no site_config.
_IMAP = {"host": "10.0.0.4", "porta": 993, "nome": "StratechnaHostingBDS"}


def _caixa_aceita(pwd: str) -> bool:
    import imaplib
    import os
    import socket
    import ssl
    c = {**_IMAP, **(frappe.conf.get("orbit_assistencia_imap") or {})}
    ctx = ssl.create_default_context(cafile=os.path.join(os.path.dirname(__file__), "bds-mail.crt"))

    class _Imap(imaplib.IMAP4_SSL):
        # liga ao endereço privado mas verifica o certificado pelo nome do BDS (não há DNS para ele aqui)
        def _create_socket(self, timeout):
            return self.ssl_context.wrap_socket(socket.create_connection((c["host"], int(c["porta"])), timeout),
                                                server_hostname=c["nome"])

    m = _Imap(c["nome"], int(c["porta"]), ssl_context=ctx, timeout=10)
    try:
        m.login(ASSISTENCIA, pwd)
    except imaplib.IMAP4.error:
        return False
    finally:
        try:
            m.logout()
        except Exception:
            pass
    return True


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=600)
def entrar_assistencia(usr: str | None = None, pwd: str | None = None):
    if (usr or "").strip().lower() != ASSISTENCIA or not pwd:
        frappe.throw("Credenciais inválidas.", frappe.AuthenticationError)
    try:
        ok = _caixa_aceita(pwd)
    except Exception:
        frappe.log_error(title="orbit.entrada_unica.caixa")
        frappe.throw("Não foi possível verificar a caixa de correio. Tente outra vez.")
    if not ok:
        frappe.throw("Credenciais inválidas.", frappe.AuthenticationError)
    ip = frappe.local.request_ip
    frappe.set_user("Administrator")
    _garantir_assistencia()
    frappe.get_doc({"doctype": "Activity Log", "user": ASSISTENCIA, "full_name": "Assistência Stratechna",
                    "operation": "Login", "status": "Success", "reference_doctype": "User",
                    "reference_name": ASSISTENCIA,
                    "subject": f"Assistência Stratechna: entrada com a caixa {ASSISTENCIA} (IP {ip})"}
                   ).insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.flags.orbit_via_portal = True      # sem ponte para o portal: esta entrada não é de ninguém do portal
    frappe.local.login_manager.login_as(ASSISTENCIA, audit_user=ASSISTENCIA)
    frappe.cache.set_value(_ASSIST + frappe.local.session.sid, {"nome": ASSISTENCIA, "email": ASSISTENCIA, "sid": None},
                           expires_in_sec=31 * 86400)
    return {"ok": 1}


def em_assistencia() -> dict | None:
    sid = getattr(frappe.session, "sid", None)
    return frappe.cache.get_value(_ASSIST + sid) if sid and frappe.session.user == ASSISTENCIA else None


# ── sair ─────────────────────────────────────────────────────────────────────

def ao_sair(login_manager=None) -> None:
    """on_logout: quem sai do Orbit sai também do portal, do webmail e dos outros tenants."""
    try:
        # Só quando é a própria pessoa a sair (o `logout` com outro utilizador limpa as sessões dele, e
        # aí não se mexe na sessão central de quem carregou no botão).
        if (frappe.local.form_dict.get("cmd") or "").split(".")[-1] not in ("logout", "web_logout") \
                and not (frappe.request and frappe.request.path.rstrip("/").endswith(("/logout", "/web_logout"))):
            return
        sid_frappe = frappe.session.sid
        if sid_frappe and frappe.cache.get_value(_ASSIST + sid_frappe):
            # Sair da assistência fecha só esta sessão; quem estava em assistência continua no portal.
            frappe.cache.delete_value(_ASSIST + sid_frappe)
            frappe.cache.delete_value(_CHAVE_CACHE + sid_frappe)
            return
        sid = frappe.cache.get_value(_CHAVE_CACHE + sid_frappe) if sid_frappe else None
        c = _conf()
        if not sid or not c:
            return
        frappe.cache.delete_value(_CHAVE_CACHE + sid_frappe)
        import requests
        requests.post(EMISSOR + "/terminar", data={"sid": sid}, auth=(c["client_id"], c["client_secret"]), timeout=8)
    except Exception:
        frappe.log_error(title="orbit.entrada_unica.ao_sair")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def saida_canal(logout_token: str | None = None):
    """OIDC Back-Channel Logout: a sessão central terminou noutra app."""
    c = _conf()
    if not c or not logout_token:
        frappe.local.response.http_status_code = 400
        return
    try:
        d = _verificar(logout_token, c["client_id"])
    except Exception:
        frappe.local.response.http_status_code = 400
        return
    if EVENTO_SAIDA not in (d.get("events") or {}) or "nonce" in d or not d.get("sid"):
        frappe.local.response.http_status_code = 400
        return
    email = (d.get("email") or "").lower()
    # A sessão central pode ter aberto aqui a conta da própria pessoa ou a da assistência (suporte@).
    contas = [u for u in {email, ASSISTENCIA} if u and frappe.db.exists("User", u)]
    if not contas:
        return {"saidas": 0}
    from frappe.sessions import delete_session
    n = 0
    t = frappe.qb.DocType("Sessions")
    for conta in contas:
        for s in frappe.qb.from_(t).where(t.user == conta).select(t.sid).run(pluck=True):
            if frappe.cache.get_value(_CHAVE_CACHE + s) == d["sid"]:
                delete_session(s, user=conta, reason="Saiu noutra aplicação Stratechna")
                frappe.cache.delete_value(_CHAVE_CACHE + s)
                frappe.cache.delete_value(_ASSIST + s)
                n += 1
    frappe.db.commit()
    return {"saidas": n}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def automatica() -> dict:
    """A página de entrada segue logo para o portal? (`orbit_entrada_stratechna_auto` no site_config)"""
    return {"auto": bool(_conf() and frappe.conf.get("orbit_entrada_stratechna_auto"))}



# ── Ponte para o portal (18-10-2026) ─────────────────────────────────────────────────────────────────────────
# Vítor: «Mantemos os logins separados mas a lógica mantém-se: se o utilizador já entrou numa qualquer app do Orbit
# está logado no portal e vice-versa». Quem entra pelo formulário do Orbit (palavra-passe) fica também com a sessão
# central do portal: logo a seguir, o navegador passa por ligar_portal → portal /api/oidc/ligar (cookie) → volta.
_PONTE = "orbit_entrada_unica:ponte:"


def sessao_criada(login_manager=None) -> None:
    """on_session_creation: entrou pelo formulário do Orbit (não pelo portal)? Fica marcado para a ponte."""
    try:
        if frappe.flags.get("orbit_via_portal") or not _conf() or not frappe.conf.get("orbit_entrada_stratechna_auto"):
            return
        sid = getattr(frappe.local, "session", None) and frappe.local.session.sid
        if sid and sid != "Guest" and (getattr(login_manager, "user", None) or "") not in ("Administrator", "Guest", ASSISTENCIA):
            frappe.cache.set_value(_PONTE + sid, 1, expires_in_sec=3600)
    except Exception:
        frappe.log_error(title="orbit.entrada_unica.sessao_criada")


def boot(bootinfo) -> None:
    """O desk segue a ponte logo ao abrir, se ficou por fazer (entrada pelo formulário com destino directo)."""
    sid = frappe.session.sid
    quem = em_assistencia()
    if quem:
        bootinfo["orbit_assistencia"] = {"nome": quem.get("nome"), "email": quem.get("email")}
        return
    if sid and frappe.cache.get_value(_PONTE + sid):
        bootinfo["orbit_ligar_portal"] = "/api/method/orbit.entrada_unica.ligar_portal?" + _q({"volta": frappe.request.url if frappe.request else "/app"})


def _volta_local(volta: str) -> str:
    from urllib.parse import urlparse
    if not volta:
        return "/app"
    u = urlparse(volta)
    if not u.scheme and volta.startswith("/") and not volta.startswith("//"):
        return frappe.utils.get_url(volta)
    h = (u.hostname or "").lower()
    if u.scheme == "https" and (h == "portal.stratechna.com" or h.endswith("orbit.stratechna.com") or h == (frappe.local.request.host or "").split(":")[0]):
        return volta
    return frappe.utils.get_url("/app")


@frappe.whitelist(methods=["GET"])
def ligar_portal(volta: str | None = None):
    """Dá ao navegador a sessão central do portal e devolve-o a `volta`."""
    import requests
    c = _conf()
    destino = _volta_local(volta or "/app")
    sid_frappe = frappe.session.sid
    frappe.cache.delete_value(_PONTE + sid_frappe)
    frappe.local.response["type"] = "redirect"
    if not c or frappe.session.user in ("Guest", "Administrator", ASSISTENCIA):
        frappe.local.response["location"] = destino
        return
    try:
        r = requests.post(EMISSOR + "/bilhete", data={"email": frappe.session.user, "host": frappe.local.request.host},
                          auth=(c["client_id"], c["client_secret"]), timeout=10)
        if r.status_code != 200:
            # sem conta no portal: segue sem ponte; nunca de volta ao portal (que mandaria outra vez para aqui)
            frappe.local.response["location"] = destino if "portal.stratechna.com" not in destino else frappe.utils.get_url("/app")
            return
        d = r.json()
        frappe.cache.set_value(_CHAVE_CACHE + sid_frappe, d["sid"], expires_in_sec=31 * 86400)
        frappe.local.response["location"] = EMISSOR + "/ligar?" + _q({"b": d["bilhete"], "volta": destino})
    except Exception:
        frappe.log_error(title="orbit.entrada_unica.ligar_portal")
        frappe.local.response["location"] = destino if "portal.stratechna.com" not in destino else frappe.utils.get_url("/app")
