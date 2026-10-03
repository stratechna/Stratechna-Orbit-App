"""A saída das campanhas. Corre ao minuto (`scheduler_events` → cron).

Duas passagens:
  1. As campanhas aprovadas cuja hora chegou fixam os destinatários — no
     momento da saída e não no da aprovação: quem saiu entretanto já não
     recebe — e passam a «A enviar».
  2. Cada campanha a enviar põe na fila do Frappe um lote: o limite por hora
     dividido por sessenta. Uma lista de 3.000 a 200/hora leva 15 horas, e é
     essa a intenção — um domínio que despeja tudo de uma vez é tratado como
     spam antes de alguém ler a primeira mensagem.

Quem envia de facto é a fila do Frappe (`frappe.email.queue.flush`), pela
conta indicada nas definições. Daqui só se decide quem, quando e o quê.

Em simulação (o modo por omissão, e o que vale enquanto faltar a conta de
envio ou a identificação legal) o ciclo corre inteiro e nada entra na fila.
"""

import json
import math
import uuid

import frappe
from frappe.utils import cint, now_datetime

from orbit.marketing import destinatarios, mensagem


def falta_para_enviar(d=None) -> list[str]:
    d = d or mensagem.definicoes()
    falta = []
    if not d.email_account:
        falta.append("a conta de envio (relay)")
    if not (d.legal_texto or "").strip():
        falta.append("a identificação legal do remetente")
    return falta


def simula(d=None) -> bool:
    d = d or mensagem.definicoes()
    return d.modo != "Real" or bool(falta_para_enviar(d))


def preparar(campanha) -> int:
    quem = destinatarios.da_campanha(campanha)
    for r in quem:
        frappe.get_doc({
            "doctype": "Envio de Marketing", "campanha": campanha.name, "email": r["email"],
            "estado": "Na fila", "referencia_doctype": r["doctype"], "referencia_nome": r["name"],
            "nome_destinatario": " ".join(x for x in (r.get("nome"), r.get("apelido")) if x)[:140],
            "token": uuid.uuid4().hex,
        }).insert(ignore_permissions=True)
    campanha.db_set({"estado": "A enviar", "destinatarios": len(quem), "simulada": int(simula())})
    campanha.add_comment("Info", f"Saída começou: {len(quem)} destinatários"
                         + (" (simulação: nada sai)" if simula() else ""))
    return len(quem)


def _registo(e) -> dict:
    """O destinatário como o modelo o precisa: nome e base legal, lidos agora
    do CRM (a base legal pode ter mudado desde que se fixou a lista)."""
    campos = ["mkt_base_legal", "mkt_estado"] + (["first_name"] if e.referencia_doctype in ("Contact", "CRM Lead") else [])
    v = frappe.db.get_value(e.referencia_doctype, e.referencia_nome, campos, as_dict=True) or {}
    return {"nome": v.get("first_name") or (e.nome_destinatario or "").split(" ")[0],
            "mkt_base_legal": v.get("mkt_base_legal"), "mkt_estado": v.get("mkt_estado")}


# O travão. Acima destas taxas, nas primeiras centenas de envios, alguma coisa
# está errada com a lista — e continuar é o que põe o domínio do cliente nas
# listas negras. A Google corta acima de 0,3% de queixas; aqui pára-se muito
# antes. Só se avalia a partir de AMOSTRA envios, senão uma devolução nos
# primeiros dez dava 10%.
AMOSTRA = 100
TECTO_DEVOLUCOES = 0.05
TECTO_QUEIXAS = 0.001


def _chave(dono) -> str:
    return "automacao" if dono.doctype == "Automacao de Marketing" else "campanha"


def travao(nome: str, chave: str = "campanha") -> str | None:
    """A razão para parar esta campanha (ou automação), ou None."""
    c = frappe.db.sql(f"""SELECT SUM(estado IN ('Enviado', 'Devolvido', 'Queixa')) AS saidos,
            SUM(estado = 'Devolvido') AS devolvidos, SUM(estado = 'Queixa') AS queixas
        FROM `tabEnvio de Marketing` WHERE {chave} = %s""", nome, as_dict=True)[0]
    saidos = cint(c.saidos)
    if saidos < AMOSTRA:
        return None
    if cint(c.devolvidos) / saidos > TECTO_DEVOLUCOES:
        return f"{cint(c.devolvidos)} devoluções em {saidos} envios (acima de {TECTO_DEVOLUCOES:.0%})"
    if cint(c.queixas) / saidos > TECTO_QUEIXAS:
        return f"{cint(c.queixas)} queixas de spam em {saidos} envios (acima de {TECTO_QUEIXAS:.1%})"
    return None


def pausar(campanha, razao: str) -> None:
    campanha.db_set("estado", "Pausada")
    if campanha.doctype == "Automacao de Marketing":
        for e in frappe.get_all("Envio de Marketing", filters={"automacao": campanha.name, "estado": "Na fila"}, pluck="name"):
            frappe.db.set_value("Envio de Marketing", e, "estado", "Cancelado")
    campanha.add_comment("Comment", f"Parada automaticamente: {razao}. "
                                    "Reveja a lista antes de retomar.")
    aprovador = campanha.aprovada_por
    if aprovador:
        frappe.get_doc({"doctype": "Notification Log", "for_user": aprovador, "type": "Alert",
                        "document_type": campanha.doctype, "document_name": campanha.name,
                        "subject": f"«{campanha.get('titulo') or campanha.name}» parada: {razao}"}).insert(ignore_permissions=True)


def despachar(campanha, lote: int | None = None) -> None:
    """Faz sair um lote de uma campanha ou de uma automação. Para uma
    automação a fila não acaba — volta a encher na corrida seguinte — e a
    simulação lê-se a cada passagem, porque ela vive meses."""
    chave = _chave(campanha)
    razao = travao(campanha.name, chave)
    if razao:
        pausar(campanha, razao)
        return
    d = mensagem.definicoes()
    lote = lote or max(1, math.ceil(cint(d.limite_hora or 200) / 60))
    fila = frappe.get_all("Envio de Marketing", filters={chave: campanha.name, "estado": "Na fila"},
                          fields=["name"], order_by="creation", limit_page_length=lote)
    if not fila:
        if chave == "campanha":
            campanha.db_set({"estado": "Enviada", "enviada_em": now_datetime()})
        actualizar_contagens(campanha.name, chave)
        return
    simulada = cint(campanha.simulada) if chave == "campanha" else int(simula(d))
    remetente = frappe.db.get_value("Email Account", d.email_account, "email_id") if d.email_account else None
    for linha in fila:
        e = frappe.get_doc("Envio de Marketing", linha.name)
        r = _registo(e)
        # A última verificação: entre a fixação da lista e este minuto, a
        # pessoa pode ter saído ou alguém pode ter mudado o CRM.
        if r.get("mkt_estado") != "Pode receber":
            e.db_set({"estado": "Saltado", "erro": "deixou de poder receber"})
            continue
        if simulada:
            e.db_set({"estado": "Simulado", "enviado_em": now_datetime()})
            continue
        try:
            m = mensagem.compor(campanha, r, e.token, json.loads(e.dados) if e.get("dados") else None)
            # Os cabeçalhos X- passam pelo Frappe tal e qual. São eles que
            # deixam o portal ligar uma devolução ou queixa do relay ao envio
            # certo, no tenant certo.
            cabecalhos = {"X-Orbit-Envio": e.token, "X-Orbit-Tenant": (frappe.local.site or "").split(".")[0]}
            if d.conjunto_configuracao:
                cabecalhos["X-SES-CONFIGURATION-SET"] = d.conjunto_configuracao
            q = frappe.sendmail(
                recipients=[e.email], sender=remetente, subject=m["assunto"], message=m["html"],
                email_headers=cabecalhos,
                reference_doctype="Envio de Marketing", reference_name=e.name,
                add_unsubscribe_link=0, with_container=False, delayed=True, raw_html=True,
                # Os modelos MJML já levam os estilos em linha. A folha do
                # Frappe por cima mudava o desenho do email do cliente.
                add_css=False, send_priority=0)
            if q:
                mensagem.acrescentar_cabecalhos(q.name, m["sair_um_clique"])
            e.db_set({"estado": "Enviado", "enviado_em": now_datetime(),
                      "email_queue": q.name if q else None})
        except Exception as x:  # noqa: BLE001
            # O sítio exacto do erro vai com ele: «NoneType has no attribute
            # get» sozinho não diz se falhou a mensagem, a conta ou a fila.
            sitio = [l.strip() for l in frappe.get_traceback().splitlines() if l.strip().startswith("File ")][-3:]
            e.db_set({"estado": "Falhou", "erro": (f"{type(x).__name__}: {x} | " + " | ".join(sitio))[:1000]})
            frappe.log_error(f"Campanha {campanha.name}", frappe.get_traceback())


def actualizar_contagens(nome: str, chave: str = "campanha") -> None:
    """Os números da campanha (ou automação), a partir dos envios. A fila do
    Frappe diz o que falhou depois de entregue a ela."""
    for e in frappe.get_all("Envio de Marketing", filters={chave: nome, "estado": "Enviado",
                                                           "email_queue": ("is", "set")},
                            fields=["name", "email_queue"]):
        if frappe.db.get_value("Email Queue", e.email_queue, "status") == "Error":
            frappe.db.set_value("Envio de Marketing", e.name, "estado", "Falhou", update_modified=False)
    c = frappe.db.sql("""SELECT
            SUM(estado IN ('Enviado', 'Simulado')) AS enviados,
            SUM(aberto_em IS NOT NULL) AS aberturas, SUM(clicado_em IS NOT NULL) AS cliques,
            SUM(saiu_em IS NOT NULL) AS saidas, SUM(estado = 'Falhou') AS falhas
        FROM `tabEnvio de Marketing` WHERE {chave} = %s""".replace("{chave}", chave), nome, as_dict=True)[0]
    doctype = "Automacao de Marketing" if chave == "automacao" else "Campanha de Marketing"
    frappe.db.set_value(doctype, nome, {k: cint(v) for k, v in c.items()}, update_modified=False)


def processar() -> None:
    agora = now_datetime()
    for nome in frappe.get_all("Campanha de Marketing",
                               filters={"estado": "Aprovada", "agendar_para": ("<=", agora)}, pluck="name"):
        try:
            preparar(frappe.get_doc("Campanha de Marketing", nome))
            frappe.db.commit()
        except Exception:  # noqa: BLE001
            frappe.db.rollback()
            frappe.log_error(f"Abrir a campanha {nome}", frappe.get_traceback())
    for doctype, filtro in (("Campanha de Marketing", {"estado": "A enviar"}),
                            ("Automacao de Marketing", {"estado": "Activa"})):
        for nome in frappe.get_all(doctype, filters=filtro, pluck="name"):
            try:
                despachar(frappe.get_doc(doctype, nome))
                frappe.db.commit()
            except Exception:  # noqa: BLE001
                frappe.db.rollback()
                frappe.log_error(f"Despachar {doctype} {nome}", frappe.get_traceback())


def contagens_do_dia() -> None:
    """De hora a hora: as aberturas e cliques chegam muito depois da saída."""
    for nome in frappe.get_all("Campanha de Marketing", filters={"estado": ("in", ["A enviar", "Enviada"]),
                               "modified": (">=", frappe.utils.add_days(now_datetime(), -30))}, pluck="name"):
        actualizar_contagens(nome)
    for nome in frappe.get_all("Automacao de Marketing", pluck="name"):
        actualizar_contagens(nome, "automacao")
    frappe.db.commit()
