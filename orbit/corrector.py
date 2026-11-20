"""«Rever texto» no CRM, no Desk e no ERP (20-11-2026, docs/PLANO-CORRECTOR-LANGUAGETOOL.md, F3).

O navegador chama `orbit.corrector.verificar` (sessão do Frappe, nunca convidados); este método chama o LanguageTool
próprio (corrector.stratechna.com) com a credencial que só o servidor conhece: `orbit_corrector` no
common_site_config.json — {"url": "https://corrector.stratechna.com/v2/check", "auth": "<Basic em base64>"}.
Sem essa chave o método responde que o corrector não está ligado. O texto não é guardado nem registado.

A língua é detectada no texto (pt-PT, es, en-GB, fr…); se a detecção hesitar, revê-se na língua da pessoa
(`User.language`, que o portal mantém — plano I18N-ORBIT-APPS).
"""
import frappe
import requests
from frappe import _
from frappe.rate_limiter import rate_limit

MAXIMO = 50000
VARIANTES = {"pt": "pt-PT", "en": "en-GB", "es": "es", "fr": "fr"}


def _lingua_da_pessoa():
	lang = (frappe.db.get_value("User", frappe.session.user, "language") or frappe.local.lang or "pt").lower()
	return VARIANTES.get(lang.split("-")[0], "pt-PT")


def _pedir(conf, texto, lingua):
	dados = {"text": texto}
	if lingua:
		dados["language"] = lingua
	else:
		dados.update({"language": "auto", "preferredVariants": "pt-PT,en-GB,de-DE,ca-ES"})
	r = requests.post(
		conf.get("url") or "https://corrector.stratechna.com/v2/check",
		data=dados,
		headers={"Authorization": "Basic " + conf["auth"]},
		timeout=25,
	)
	if r.status_code in (429, 503):
		frappe.throw(_("O corrector está ocupado. Tente daqui a um momento."))
	r.raise_for_status()
	return r.json()


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60, user_based=True, ip_based=False)
def verificar(texto=None, lingua=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Não autorizado"), frappe.PermissionError)
	conf = frappe.conf.get("orbit_corrector") or {}
	if not conf.get("auth"):
		frappe.throw(_("O corrector não está ligado neste Orbit."))
	texto = (texto or "")[:MAXIMO]
	pessoa = _lingua_da_pessoa()
	if not texto.strip():
		return {"lingua": None, "lingua_pessoa": pessoa, "erros": []}
	try:
		r = _pedir(conf, texto, lingua if lingua in VARIANTES.values() else None)
		det = (r.get("language") or {}).get("detectedLanguage") or {}
		if not lingua and (det.get("confidence") or 0) < 0.9 and (r.get("language") or {}).get("code") != pessoa:
			r = _pedir(conf, texto, pessoa)
	except requests.RequestException:
		frappe.throw(_("Não foi possível rever o texto."))
	erros = []
	for m in r.get("matches") or []:
		regra = m.get("rule") or {}
		erros.append({
			"offset": m.get("offset"),
			"length": m.get("length"),
			"message": m.get("message") or "",
			"replacements": [x.get("value") for x in (m.get("replacements") or [])[:5]],
			"ortografia": regra.get("issueType") == "misspelling"
			or any(k in (regra.get("id") or "") for k in ("MORFOLOGIK", "HUNSPELL", "SPELLER")),
		})
	return {"lingua": (r.get("language") or {}).get("code"), "lingua_pessoa": pessoa, "erros": erros}
