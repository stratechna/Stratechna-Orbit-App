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

PROVEDOR = "stratechna"
PORTAL = "https://portal.stratechna.com"
EMISSOR = PORTAL + "/api/oidc"
REGRESSO = "/api/method/orbit.entrada_unica.regresso"
EVENTO_SAIDA = "http://schemas.openid.net/event/backchannel-logout"
_CHAVE_CACHE = "orbit_entrada_unica:sid:"
_JWKS: dict = {}


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
    c = _conf()
    if error or not code or not c:
        frappe.respond_as_web_page("Entrada com a Stratechna",
                                   "Não foi possível entrar. Volte à página de entrada e tente de novo.",
                                   http_status_code=400, indicator_color="red")
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
    login_oauth_user(dados, provider=PROVEDOR, state=state)
    sid_frappe = getattr(frappe.local, "session", None) and frappe.local.session.sid
    if sid_frappe and sid_frappe != "Guest" and idt.get("sid"):
        frappe.cache.set_value(_CHAVE_CACHE + sid_frappe, idt["sid"], expires_in_sec=31 * 86400)


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
    if not email or not frappe.db.exists("User", email):
        return {"saidas": 0}
    from frappe.sessions import delete_session
    n = 0
    t = frappe.qb.DocType("Sessions")
    for s in frappe.qb.from_(t).where(t.user == email).select(t.sid).run(pluck=True):
        if frappe.cache.get_value(_CHAVE_CACHE + s) == d["sid"]:
            delete_session(s, user=email, reason="Saiu noutra aplicação Stratechna")
            frappe.cache.delete_value(_CHAVE_CACHE + s)
            n += 1
    frappe.db.commit()
    return {"saidas": n}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def automatica() -> dict:
    """A página de entrada segue logo para o portal? (`orbit_entrada_stratechna_auto` no site_config)"""
    return {"auto": bool(_conf() and frappe.conf.get("orbit_entrada_stratechna_auto"))}
