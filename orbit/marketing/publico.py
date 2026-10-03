"""O que o destinatário faz: abrir, clicar, sair. Sem sessão.

O token do envio (32 caracteres aleatórios) é a única credencial, e só serve
para isto. O clique segue o ÍNDICE da ligação na campanha, nunca um endereço
vindo no pedido: um redireccionamento que aceita o destino por parâmetro é um
presente para quem faz phishing com o domínio do cliente.

A saída de tudo escreve no CRM: «Retirou», com a data, e o contacto fica
`unsubscribed`. Sem isso, a próxima pessoa a abrir a ficha via um
consentimento que já não existe.
"""

import base64

import frappe
from frappe.utils import now_datetime, today

from orbit.marketing import mensagem, modelos

_GIF = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


def _envio(t: str):
    if not t or len(t) != 32 or not t.isalnum():
        return None
    nome = frappe.db.get_value("Envio de Marketing", {"token": t}, "name")
    return frappe.get_doc("Envio de Marketing", nome) if nome else None


@frappe.whitelist(allow_guest=True, methods=["GET"])
def aberto(t: str = ""):
    try:
        e = _envio(t)
        if e:
            frappe.db.set_value("Envio de Marketing", e.name,
                                {"aberturas": (e.aberturas or 0) + 1, "aberto_em": e.aberto_em or now_datetime()},
                                update_modified=False)
            frappe.db.commit()
    except Exception:  # noqa: BLE001
        # A imagem responde sempre: um píxel partido num email já entregue
        # não se corrige, e não vale um erro no ecrã de ninguém.
        frappe.db.rollback()
    frappe.local.response.update({"type": "binary", "filename": "p.gif", "filecontent": _GIF,
                                  "content_type": "image/gif"})


@frappe.whitelist(allow_guest=True, methods=["GET"])
def ir(t: str = "", i: int = 0):
    e = _envio(t)
    if not e:
        frappe.throw("Ligação desconhecida", frappe.DoesNotExistError)
    c = frappe.get_doc("Campanha de Marketing", e.campanha)
    ligacoes = modelos.ligacoes(mensagem.conteudo(c))
    i = int(i)
    if not 0 <= i < len(ligacoes):
        frappe.throw("Ligação desconhecida", frappe.DoesNotExistError)
    agora = now_datetime()
    frappe.db.set_value("Envio de Marketing", e.name,
                        {"cliques": (e.cliques or 0) + 1, "clicado_em": e.clicado_em or agora,
                         "aberto_em": e.aberto_em or agora}, update_modified=False)
    frappe.db.commit()
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = ligacoes[i]


def remover(t: str, tudo: bool) -> dict | None:
    e = _envio(t)
    if not e:
        return None
    assunto = frappe.db.get_value("Campanha de Marketing", e.campanha, "assunto_marketing")
    if tudo or not assunto:
        if not frappe.db.exists("Email Unsubscribe", {"email": e.email, "global_unsubscribe": 1}):
            frappe.get_doc({"doctype": "Email Unsubscribe", "email": e.email,
                            "global_unsubscribe": 1}).insert(ignore_permissions=True)
        if e.referencia_doctype in ("Contact", "CRM Lead") and frappe.db.exists(e.referencia_doctype, e.referencia_nome):
            valores = {"mkt_estado": "Retirou", "mkt_data": today()}
            if e.referencia_doctype == "Contact":
                valores["unsubscribed"] = 1
            doc = frappe.get_doc(e.referencia_doctype, e.referencia_nome)
            doc.update(valores)
            doc.flags.ignore_permissions = True
            doc.save()
            doc.add_comment("Comment", "Deixou de receber comunicações de marketing (pedido no email).")
        saiu_de = "tudo"
    else:
        if not frappe.db.exists("Email Unsubscribe", {"email": e.email, "reference_doctype": "Assunto de Marketing",
                                                      "reference_name": assunto}):
            frappe.get_doc({"doctype": "Email Unsubscribe", "email": e.email,
                            "reference_doctype": "Assunto de Marketing",
                            "reference_name": assunto}).insert(ignore_permissions=True)
        saiu_de = assunto
    frappe.db.set_value("Envio de Marketing", e.name, "saiu_em", e.saiu_em or now_datetime(), update_modified=False)
    frappe.db.commit()
    return {"email": e.email, "saiu_de": saiu_de}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def sair(t: str = "", tudo: int = 0):
    """A remoção num clique (RFC 8058): o cliente de correio faz POST sem
    pessoa nenhuma a olhar para a resposta. Sai do assunto da campanha — é
    disso que a pessoa se quis livrar ao carregar no botão do Gmail."""
    r = remover(t, bool(int(tudo or 0)))
    return {"ok": bool(r)}
