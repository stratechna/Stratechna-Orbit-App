"""Palavra-passe universal: a mudança feita no Orbit sobe ao portal (28-10-2026).

Plano: docs/PLANO-ENTRADAS-INDEPENDENTES.md (área de trabalho), passo 1 e decisões D9–D10. Para o mesmo email há
uma só palavra-passe, que vale no portal, nas lojas, no Orbit e na caixa de correio. O portal é o cofre e o
distribuidor: quem a muda aqui, muda-a em todo o lado.

**Onde se apanha.**
  · `update_password` (sobreposto em hooks.py) — «Esqueci-me» (ligação com `key`) e «Mudar palavra-passe» com a
    actual (`old_password`);
  · `User.validate` + `on_update` — Definições › Palavra-passe (o campo `new_password` do próprio utilizador).
A palavra-passe que o portal põe aqui (verbo `palavra-passe` no Apps02) usa `frappe.utils.password.update_password`
directamente, sem gravar o User: não passa por nenhum destes dois sítios e não volta ao portal.

**Quem sobe.** Só a mudança feita pela própria pessoa. A palavra-passe que um administrador do tenant põe a
outra pessoa é temporária e não sai daqui (D4).

**Nunca** se escreve a palavra-passe em registo nenhum: os erros vão para o Error Log só com o tipo.
"""
import frappe
from frappe.core.doctype.user import user as _user

DESTINO = "https://portal.stratechna.com/api/v1/palavra-passe/orbit"
_TECNICAS = {"Administrator", "Guest", "portal@stratechna.com", "suporte@stratechna.pt"}


def _avisar_portal(email: str, senha: str) -> None:
    import requests
    c = frappe.conf.get("stratechna_login") or {}
    if not c.get("client_id") or not c.get("client_secret") or email in _TECNICAS:
        return
    try:
        r = requests.post(DESTINO, data={"email": email, "senha": senha, "host": frappe.local.site},
                          auth=(c["client_id"], c["client_secret"]), timeout=15)
        if r.status_code != 200:
            # 404 = sem conta no portal; 403 = este tenant não é o da pessoa. Fica só no Orbit.
            frappe.log_error(title="orbit.palavra_passe: o portal não aceitou",
                             message=f"{email}: HTTP {r.status_code} {r.text[:200]}")
    except Exception as e:
        frappe.log_error(title="orbit.palavra_passe: portal inacessível", message=f"{email}: {type(e).__name__}")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password(new_password: str, logout_all_sessions: int = 0, key: str | None = None,
                    old_password: str | None = None):
    """O `update_password` do Frappe, e no fim avisa o portal."""
    from frappe.utils import sha256_hash
    quem = None
    if key:
        quem = frappe.db.get_value("User", {"reset_password_key": sha256_hash(key)}, "name")
    elif old_password:
        quem = frappe.session.user
    resposta = _user.update_password(new_password, logout_all_sessions=logout_all_sessions, key=key,
                                     old_password=old_password)
    if quem and (frappe.local.response or {}).get("http_status_code") != 410:
        _avisar_portal(quem, new_password)
    return resposta


def validar(doc, method=None):
    """User.validate (corre depois do do Frappe, que já tirou `new_password` para `__new_password`)."""
    nova = getattr(doc, "_User__new_password", None)
    if nova and not doc.flags.in_insert and frappe.session.user == doc.name:
        doc.flags.orbit_palavra_nova = nova


def gravado(doc, method=None):
    """User.on_update: só depois do commit, para não avisar o portal de uma mudança que não ficou."""
    nova = doc.flags.pop("orbit_palavra_nova", None) if doc.flags else None
    if nova:
        email = doc.name
        frappe.db.after_commit.add(lambda: _avisar_portal(email, nova))
