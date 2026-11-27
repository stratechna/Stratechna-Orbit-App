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

    if _so_estados_desconhecidos(frappe.local.form_dict):
        return "ok"
    # Assinatura confirmada: o pedido é da Meta. Corre como sistema — chega sem sessão («Guest») e o CRM, ao avisar o
    # responsável de uma lead nova, lê-a com verificação de permissões (403 «Guest não tem acesso a Lead do CRM»).
    # O set_user limpa o frappe.local.form_dict (onde o Frappe já leu o JSON da Meta): guarda-se e repõe-se.
    dados = frappe.local.form_dict
    frappe.set_user("Administrator")
    frappe.local.form_dict = dados
    return fw.post()


def _so_estados_desconhecidos(d) -> bool:
    """Estados (entregue/lida) de mensagens que o Orbit não conhece — p. ex. as enviadas pela caixa da Meta. O
    `update_message_status` do frappe_whatsapp rebenta com 500 e a Meta repetia o pedido durante dias."""
    try:
        v = d["entry"][0]["changes"][0]
    except Exception:  # noqa: BLE001
        return False
    val = v.get("value") or {}
    if v.get("field") != "messages" or val.get("messages"):
        return False
    ids = [x.get("id") for x in (val.get("statuses") or []) if x.get("id")]
    return not any(frappe.db.exists("WhatsApp Message", {"message_id": i}) for i in ids)


# ── W3 (D4–D6): a mensagem na ficha certa, lead para números novos, aviso no Chat ─────────────────────────────
ORIGEM = "WhatsApp"
FICHA_URL = {"CRM Lead": "/crm/leads/{}", "CRM Deal": "/crm/deals/{}", "Contact": "/crm/contacts/{}"}


def _digitos(doc) -> str:
    n = doc.get("from") if doc.type == "Incoming" else doc.get("to")
    return "".join(c for c in (n or "") if c.isdigit())


def ligar_ficha(doc, method=None):
    """validate — depois do do Frappe CRM. O WhatsApp manda o número com o indicativo e sem «+» («351964…»); o CRM lê-o
    como número da Índia (país por omissão) e procura-o inteiro, por isso «964 …» guardado na ficha nunca casava.
    Com o «+» o phonenumbers reconhece o país e o CRM procura pelo número nacional."""
    if doc.reference_doctype and doc.reference_name:
        return
    dig = _digitos(doc)
    if len(dig) < 8:
        return
    try:
        from crm.integrations.api import get_contact_lead_or_deal_from_number
        nome, dt = get_contact_lead_or_deal_from_number("+" + dig)
    except Exception:  # noqa: BLE001
        nome = dt = None
    if nome:
        doc.reference_doctype, doc.reference_name = dt, nome


def _origem():
    if not frappe.db.exists("CRM Lead Source", ORIGEM):
        frappe.get_doc({"doctype": "CRM Lead Source", "source_name": ORIGEM}).insert(ignore_permissions=True)
    return ORIGEM


def _criar_lead(doc) -> str:
    dig = _digitos(doc)
    perfil = (doc.get("profile_name") or "").strip()
    primeiro, _, resto = (perfil or ("+" + dig)).partition(" ")
    dono = (frappe.conf.get("orbit_whatsapp_responsavel") or "").strip()
    lead = frappe.get_doc({
        "doctype": "CRM Lead", "first_name": primeiro[:140], "last_name": resto[:140] or None,
        "mobile_no": "+" + dig, "source": _origem(),
        "lead_owner": dono if dono and frappe.db.exists("User", {"name": dono, "enabled": 1}) else None,
    })
    lead.insert(ignore_permissions=True)
    return lead.name


def mensagem_nova(doc, method=None):
    """after_insert — corre antes do on_update do CRM, que avisa os responsáveis da ficha: por isso a lead nasce aqui."""
    if doc.type != "Incoming" or doc.get("content_type") == "reaction":
        return
    if not (doc.reference_doctype and doc.reference_name):
        try:
            nome = _criar_lead(doc)
        except Exception:  # noqa: BLE001
            frappe.log_error(title="WhatsApp: não foi possível criar a lead", message=frappe.get_traceback())
            return
        doc.db_set({"reference_doctype": "CRM Lead", "reference_name": nome}, update_modified=False)
    if (frappe.conf.get("orbit_whatsapp_chat") or {}).get("chave"):
        frappe.enqueue("orbit.whatsapp.avisar_chat", queue="short", nome=doc.name, enqueue_after_commit=True)


def _titulo(dt, dn) -> str:
    campo = {"CRM Lead": "lead_name", "CRM Deal": "organization", "Contact": "full_name"}.get(dt)
    return (campo and frappe.db.get_value(dt, dn, campo)) or dn


def avisar_chat(nome: str):
    """D6: no canal «WhatsApp» do Chat da organização, só nome, primeira linha e a ligação — nunca a conversa."""
    import requests
    from orbit import marca
    cfg = frappe.conf.get("orbit_whatsapp_chat") or {}
    doc = frappe.get_doc("WhatsApp Message", nome)
    quem = (doc.get("profile_name") or "").strip() or "+" + _digitos(doc)
    linha = (doc.message or "").strip().splitlines()[0][:160] if (doc.message or "").strip() else f"({doc.content_type})"
    url = frappe.utils.get_url(FICHA_URL.get(doc.reference_doctype, "/app/whatsapp-message/{}").format(
        doc.reference_name if doc.reference_doctype in FICHA_URL else doc.name))
    titulo = _titulo(doc.reference_doctype, doc.reference_name) if doc.reference_name else quem
    texto = f"**{quem}** escreveu no WhatsApp:\n> {linha}\n\n[Abrir a ficha]({url})"
    r = requests.post(f"https://{marca._chat_do_tenant()}/api/v1/messages", auth=(cfg["email"], cfg["chave"]),
                      data={"type": "stream", "to": cfg.get("canal") or "WhatsApp", "topic": titulo[:60],
                            "content": texto}, timeout=20)
    if r.status_code >= 400:
        frappe.log_error(title="WhatsApp: aviso no Chat falhou", message=f"{r.status_code} {r.text[:300]}")
