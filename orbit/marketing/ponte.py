"""O que o portal da Stratechna pede a um tenant, pela ponte SSH.

Chega aqui por `/opt/orbit/scripts/marketing.sh <slug> <accao>` (comando
forçado da chave do portal), com o pedido em JSON pelo stdin. Cada função
recebe esse dicionário e devolve outro, que vai de volta ao portal.

O que entra é entrada, não instrução: só se aceitam as chaves escritas aqui,
com o tipo esperado. Uma chave desconhecida é ignorada, não gravada.

  definicoes  a marca (da identidade no portal) e o que o plano inclui
  opcoes      segmentos e assuntos que existem, para o portal escolher
  campanha    uma campanha proposta pela IA e já aprovada pela Stratechna;
              entra em «Para aprovação», à espera do cliente
  resultados  o estado e os números das campanhas, para os relatórios
"""

import json

import frappe
from frappe.utils import cint, get_datetime

from orbit.marketing import destinatarios, modelos

_DEFINICOES = {
    "marca_nome": str, "logo_url": str, "cor_primaria": str, "cor_acento": str,
    "fonte_titulos": str, "fonte_texto": str, "legal_texto": str,
    "redes": dict, "contactos": dict,
    "plano_nome": str, "plano_contactos": int, "plano_campanhas_mes": int,
}

_CAMPANHA = ("titulo", "modelo", "linha_assunto", "pre_cabecalho", "titulo_email", "subtitulo",
             "texto", "cta_texto", "cta_url", "imagem_topo", "destaque_texto", "destaque_subtexto",
             "evento_data", "evento_hora", "evento_local", "assinatura", "agendar_para")


def definicoes(pedido: dict) -> dict:
    d = frappe.get_single("Definicoes de Marketing")
    mudou = []
    for chave, tipo in _DEFINICOES.items():
        if chave not in pedido:
            continue
        v = pedido[chave]
        if tipo is dict:
            v = json.dumps(v if isinstance(v, dict) else {}, ensure_ascii=False)
        elif tipo is int:
            v = max(0, cint(v))
        else:
            v = str(v or "")[:2000] or None
        if d.get(chave) != v:
            d.set(chave, v)
            mudou.append(chave)
    if mudou:
        d.flags.ignore_permissions = True
        d.save()
    return {"ok": True, "mudou": mudou}


def opcoes(pedido: dict) -> dict:
    base = destinatarios.contactaveis()
    return {
        "ok": True,
        "contactaveis": len(base),
        "segmentos": [{"nome": s, "contactaveis": len(destinatarios.do_segmento(s, base))}
                      for s in frappe.get_all("Segmento de Marketing", pluck="name", order_by="name")],
        "assuntos": frappe.get_all("Assunto de Marketing", pluck="name", order_by="name"),
        "modelos": [m["nome"] for m in modelos.MODELOS.values()],
    }


def campanha(pedido: dict) -> dict:
    ref = str(pedido.get("portal_ref") or "").strip()
    if not ref:
        return {"ok": False, "erro": "falta a referência do portal"}
    existente = frappe.db.get_value("Campanha de Marketing", {"portal_ref": ref}, ["name", "estado"], as_dict=True)
    if existente:
        # Repetir o pedido (um corte de rede a meio) não cria outra campanha.
        return {"ok": True, "nome": existente.name, "estado": existente.estado, "repetido": True}

    segmentos = [s for s in pedido.get("segmentos") or [] if frappe.db.exists("Segmento de Marketing", s)]
    if not segmentos:
        return {"ok": False, "erro": "nenhum dos segmentos indicados existe neste tenant"}
    assunto = pedido.get("assunto")
    if assunto and not frappe.db.exists("Assunto de Marketing", assunto):
        return {"ok": False, "erro": f"o assunto «{assunto}» não existe neste tenant"}
    if pedido.get("modelo") not in modelos.POR_NOME:
        return {"ok": False, "erro": "modelo desconhecido"}

    valores = {k: pedido.get(k) for k in _CAMPANHA if pedido.get(k) not in (None, "")}
    if valores.get("agendar_para"):
        valores["agendar_para"] = get_datetime(valores["agendar_para"])
    doc = frappe.get_doc({
        "doctype": "Campanha de Marketing", **valores, "portal_ref": ref,
        "assunto_marketing": assunto or None,
        "segmentos": [{"segmento": s} for s in segmentos],
        "itens": [{k: i.get(k) for k in ("titulo", "texto", "url", "imagem")}
                  for i in (pedido.get("itens") or [])[:6] if isinstance(i, dict) and i.get("titulo")],
        "produtos": [{k: p.get(k) for k in ("nome", "preco", "url", "imagem", "descricao")}
                     for p in (pedido.get("produtos") or [])[:6] if isinstance(p, dict) and p.get("nome")],
    })
    doc.flags.do_portal = True
    doc.insert(ignore_permissions=True)
    quem = str(pedido.get("aprovada_por") or "a Stratechna")[:140]
    doc.add_comment("Comment", f"Proposta pela Stratechna no portal e revista por {quem}. "
                               "Falta a sua aprovação para sair.")
    return {"ok": True, "nome": doc.name, "estado": doc.estado}


def resultados(pedido: dict) -> dict:
    filtros = {}
    if pedido.get("desde"):
        filtros["modified"] = (">=", get_datetime(pedido["desde"]))
    campos = ["name", "titulo", "estado", "origem", "portal_ref", "agendar_para", "enviada_em",
              "destinatarios", "enviados", "aberturas", "cliques", "saidas", "falhas", "simulada",
              "aprovada_por", "aprovada_em", "modified"]
    return {"ok": True, "campanhas": frappe.get_all("Campanha de Marketing", filters=filtros, fields=campos,
                                                    order_by="modified desc", limit=500)}


def relay(pedido: dict) -> dict:
    """A conta de envio pelo relay, criada ou actualizada pelo portal. A
    palavra-passe chega pelo stdin da ponte e fica no campo cifrado do Frappe;
    nunca vai à linha de comandos nem ao registo."""
    email = str(pedido.get("email_id") or "").strip().lower()
    if "@" not in email or not pedido.get("smtp_server") or not pedido.get("login"):
        return {"ok": False, "erro": "faltam o remetente, o servidor ou o utilizador do relay"}
    nome = "Marketing (relay)"
    doc = frappe.get_doc("Email Account", nome) if frappe.db.exists("Email Account", nome) else \
        frappe.new_doc("Email Account")
    doc.update({"email_account_name": nome, "email_id": email, "enable_outgoing": 1, "enable_incoming": 0,
                "smtp_server": pedido["smtp_server"], "smtp_port": str(cint(pedido.get("smtp_port") or 587)),
                "use_tls": 1, "login_id_is_different": 1, "login_id": pedido["login"],
                "always_use_account_email_id_as_sender": 1,
                "always_use_account_name_as_sender_name": 0, "default_outgoing": 0,
                "send_unsubscribe_message": 0, "track_email_status": 0})
    if pedido.get("password"):
        doc.password = pedido["password"]
        doc.awaiting_password = 0
    doc.flags.ignore_permissions = True
    # Validar a ligação SMTP ao gravar não serve aqui: o relay só aceita
    # o remetente depois de o domínio estar verificado, e isso é assíncrono.
    doc.flags.ignore_validate = bool(pedido.get("sem_validar"))
    doc.save() if not doc.is_new() else doc.insert()
    d = frappe.get_single("Definicoes de Marketing")
    d.email_account = doc.name
    if pedido.get("conjunto_configuracao"):
        d.conjunto_configuracao = str(pedido["conjunto_configuracao"])[:140]
    d.flags.ignore_permissions = True
    d.save()
    return {"ok": True, "conta": doc.name}


def evento(pedido: dict) -> dict:
    """Uma devolução definitiva ou uma queixa, vinda do relay pelo portal."""
    from frappe.utils import now_datetime
    tipo = pedido.get("tipo")
    if tipo not in ("devolvido", "queixa"):
        return {"ok": False, "erro": "tipo de evento desconhecido"}
    t = str(pedido.get("token") or "")
    envio = frappe.db.get_value("Envio de Marketing", {"token": t}, ["name", "campanha", "email"], as_dict=True) if t else None
    emails = {str(e).strip().lower() for e in pedido.get("emails") or [] if "@" in str(e)}
    if envio:
        emails.add(envio.email.lower())
        frappe.db.set_value("Envio de Marketing", envio.name, {
            "estado": "Devolvido" if tipo == "devolvido" else "Queixa",
            "erro": str(pedido.get("detalhe") or "")[:300]}, update_modified=False)
    for email in emails:
        if not frappe.db.exists("Supressao de Marketing", email):
            frappe.get_doc({"doctype": "Supressao de Marketing", "email": email,
                            "motivo": "Devolvido" if tipo == "devolvido" else "Queixa",
                            "detalhe": str(pedido.get("detalhe") or "")[:500],
                            "campanha": envio.campanha if envio else None,
                            "data": now_datetime()}).insert(ignore_permissions=True)
        if tipo == "queixa":
            # Uma queixa é também uma saída: o CRM passa a dizê-lo.
            if not frappe.db.exists("Email Unsubscribe", {"email": email, "global_unsubscribe": 1}):
                frappe.get_doc({"doctype": "Email Unsubscribe", "email": email,
                                "global_unsubscribe": 1}).insert(ignore_permissions=True)
            for nome in frappe.get_all("Contact Email", filters={"email_id": email}, pluck="parent"):
                frappe.db.set_value("Contact", nome, {"mkt_estado": "Retirou", "unsubscribed": 1})
            for nome in frappe.get_all("CRM Lead", filters={"email": email}, pluck="name") \
                    if frappe.db.exists("DocType", "CRM Lead") else []:
                frappe.db.set_value("CRM Lead", nome, "mkt_estado", "Retirou")
    return {"ok": True, "suprimidos": sorted(emails), "envio": envio.name if envio else None}


ACCOES = {"definicoes": definicoes, "opcoes": opcoes, "campanha": campanha, "resultados": resultados,
          "relay": relay, "evento": evento}
