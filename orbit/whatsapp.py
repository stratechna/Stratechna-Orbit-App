"""WhatsApp no CRM do Orbit — a porta do webhook da Meta (27-11-2026).

docs/PLANO-WHATSAPP-ORBIT.md (D3) no repositório stratechna-work.

O motor é o `frappe_whatsapp` (MIT) com a integração nativa do Frappe CRM. O
webhook dele (`frappe_whatsapp.utils.webhook.webhook`) é público e NÃO verifica
a assinatura da Meta — qualquer pessoa que soubesse o endereço podia meter
mensagens falsas no CRM. Por isso, pelo `override_whitelisted_methods` do
hooks.py, esse mesmo endereço passa por aqui:

  * GET (verificação do endereço pela Meta) → segue tal e qual para o
    `frappe_whatsapp`, que confere o `hub.verify_token` da conta;
  * POST (mensagens e estados) → só segue se o `X-Hub-Signature-256` for o HMAC
    SHA-256 do corpo com o segredo da app da Meta (`orbit_whatsapp_app_secret`
    no site_config ou no common_site_config). Sem segredo configurado, recusa:
    melhor não receber do que receber sem saber de quem.

Os sites sem o `frappe_whatsapp` instalado respondem 404, como antes.
"""

import hashlib
import hmac

import frappe


def _segredo() -> str:
    return (frappe.conf.get("orbit_whatsapp_app_secret") or "").strip()


def assinatura_valida(corpo: bytes, cabecalho: str, segredo: str) -> bool:
    """`sha256=<hex>` do HMAC do corpo tal como chegou (antes de qualquer leitura de JSON)."""
    if not (segredo and cabecalho and cabecalho.startswith("sha256=")):
        return False
    esperado = hmac.new(segredo.encode(), corpo or b"", hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho[len("sha256="):].strip().lower())


@frappe.whitelist(allow_guest=True)
def webhook():
    if "frappe_whatsapp" not in frappe.get_installed_apps():
        frappe.local.response.http_status_code = 404
        return "Não existe"

    from frappe_whatsapp.utils import webhook as fw

    if frappe.request.method == "GET":
        return fw.get()

    corpo = frappe.request.get_data(cache=True) or b""
    if not assinatura_valida(corpo, frappe.get_request_header("X-Hub-Signature-256") or "", _segredo()):
        frappe.log_error(
            title="WhatsApp: pedido recusado (assinatura da Meta inválida ou sem segredo)",
            message=f"IP {frappe.local.request_ip}, {len(corpo)} bytes",
        )
        frappe.local.response.http_status_code = 403
        return "Assinatura inválida"

    return fw.post()
