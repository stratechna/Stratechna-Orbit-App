"""Marcação de reuniões: a disponibilidade de uma pessoa e o compromisso criado.

Este módulo é **deliberadamente fino**. Não sabe horários de trabalho, não sabe
durações, não sabe que serviços é que o cliente comprou — isso é do portal, que
é quem vende. Aqui responde-se a três perguntas e mais nenhuma:

  1. **Quando é que esta pessoa está ocupada?** (`ocupado`)
  2. **Marca isto na agenda dela.** (`criar`)
  3. **Dá-me a agenda dela em iCalendar.** (`feed`)

## Porque é que o calendário é o `Event` do Frappe e não o SOGo

Porque a pergunta que deu origem a isto foi «quero que **todas as apps do Orbit**
reconheçam o calendário», e todas as apps do Frappe — Desk, CRM, Helpdesk, HR —
lêem o doctype `Event`. O que nasce como `Event` é reconhecido por elas **sem
sincronia nenhuma**: não há nada a reconhecer, já é o calendário delas.

## E porque é que não se escreve no SOGo

Escrever na agenda do webmail de outra pessoa exige uma conta com
`SOGoSuperUsernames` — uma chave que lê o correio e as agendas de toda a gente.
É chave grande de mais para esta porta. Em vez disso:

```
o que nós criamos  →  Event do Frappe  →  feed ICS privado  →  o SOGo subscreve
o que a pessoa escreve no webmail  →  fica no SOGo  →  o Orbit lê (agenda.py)
```

Cada lado continua dono do que cria e **vê** o do outro. Nada é escrito duas
vezes, por isso não há eventos duplicados nem conflitos de UID — que é onde
estas integrações costumam partir.

O preço, dito por extenso: um compromisso criado aqui **vê-se** no webmail mas
não se **edita** lá. Trocámos a edição cruzada por não ter uma chave-mestra ao
correio de toda a gente.
"""

import datetime
import hashlib
import secrets
import zoneinfo

import frappe

from orbit import agenda

# Quanto do futuro é que o feed carrega. Um ano chega para qualquer agenda e
# evita que uma conta antiga arraste anos de histórico a cada leitura do SOGo.
# **O fuso tem de ser dito, não herdado.** O contentor do Frappe corre em UTC
# (verificado a 05-10-2026: `TZ` vazio, `date` dá UTC) mas o site está em
# Europe/Lisbon — e é o site que manda, porque é nele que estão as horas de
# trabalho e os `Event`. Converter um instante do SOGo com
# `datetime.fromtimestamp()` dava a hora do contentor: no horário de Verão,
# **uma hora mais cedo do que a verdadeira**. Uma reunião real das 11:00
# aparecia ocupada às 10:00, e as 11:00 eram oferecidas a quem quisesse marcar
# por cima dela.
FUSO = zoneinfo.ZoneInfo("Europe/Lisbon")

DIAS_DO_FEED = 365
DIAS_PASSADOS_NO_FEED = 30


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quando é que esta pessoa está ocupada
# ═══════════════════════════════════════════════════════════════════════════

def hora_local(epoca) -> datetime.datetime:
    """Um instante do SOGo na hora de Lisboa, sem fuso agarrado.

    Devolve-se «ingénuo» (sem `tzinfo`) de propósito: é assim que o Frappe
    guarda os `Event` e é assim que o portal compara com o horário de
    atendimento. Misturar datas com e sem fuso numa comparação levanta
    `TypeError` — e numa que não levante, mente.
    """
    return datetime.datetime.fromtimestamp(epoca, FUSO).replace(tzinfo=None)


def _ocupado_no_sogo(email: str, de: datetime.datetime, ate: datetime.datetime) -> list:
    """Os intervalos ocupados no calendário do webmail.

    **Devolve horas, nunca títulos.** Quem chama isto é um widget público no
    site de um cliente: dizer-lhe que às 15:00 há «Reunião com a concorrência»
    seria uma fuga de informação por uma porta que nem sequer pede sessão. A
    fronteira está aqui, na função, e não no ecrã — um ecrã muda-se sem dar por
    isso.
    """
    try:
        ligacao = agenda._ligar()
    except Exception as e:
        frappe.log_error(f"Marcação: não liguei ao Mail: {e}", "Orbit Marcação")
        raise
    if ligacao is None:
        # **Não se devolve lista vazia.** Vazio quer dizer «não tem nada
        # marcado», e é indistinguível de «não consegui ler» — com a diferença
        # de que o segundo caso oferece todas as horas de alguém cuja agenda
        # está cheia. Quem chama tem de saber que não sabe.
        raise frappe.ValidationError(
            "Não consegui ler a agenda do Mail — a disponibilidade não pode ser calculada.")

    try:
        with ligacao, ligacao.cursor() as cur:
            tabela = agenda._tabela(cur, email)
            if not tabela:
                return []
            linhas = agenda._eventos(cur, tabela, int(de.timestamp()), int(ate.timestamp()))
    except Exception as e:
        frappe.log_error(f"Marcação: falhou a leitura do Mail: {e}", "Orbit Marcação")
        raise
    finally:
        try:
            ligacao.close()
        except Exception:
            pass

    ocupados = []
    for titulo, inicio, fim, dia_inteiro, local in linhas:
        if not inicio:
            continue
        i = hora_local(inicio)
        # Sem fim marcado, assume-se uma hora: é melhor reservar a mais do que
        # oferecer uma hora que afinal está tomada.
        f = hora_local(fim) if fim else i + datetime.timedelta(hours=1)
        if dia_inteiro:
            # O dia inteiro ocupa o dia inteiro. Não se adivinha o horário de
            # expediente aqui — quem o conhece é o portal.
            i = datetime.datetime.combine(i.date(), datetime.time.min)
            f = i + datetime.timedelta(days=1)
        ocupados.append({"inicio": i.isoformat(timespec="minutes"),
                         "fim": f.isoformat(timespec="minutes")})
    return ocupados


def _ocupado_no_frappe(email: str, de: datetime.datetime, ate: datetime.datetime) -> list:
    """Os intervalos ocupados pelo que foi criado dentro do Orbit.

    Sem isto, duas marcações seguidas caíam na mesma hora: a primeira ainda não
    tinha chegado ao SOGo (o feed é lido de tempos a tempos, não ao segundo) e a
    segunda não a via.
    """
    linhas = frappe.get_all(
        "Event",
        filters={"owner": email, "status": ("!=", "Cancelled"),
                 "starts_on": ("<", ate), "ends_on": (">", de)},
        fields=["starts_on", "ends_on", "all_day"],
        limit_page_length=0,
    )
    ocupados = []
    for l in linhas:
        i, f = l.starts_on, l.ends_on or (l.starts_on + datetime.timedelta(hours=1))
        if l.all_day:
            i = datetime.datetime.combine(i.date(), datetime.time.min)
            f = i + datetime.timedelta(days=1)
        ocupados.append({"inicio": i.isoformat(timespec="minutes"),
                         "fim": f.isoformat(timespec="minutes")})
    return ocupados


def _juntar(intervalos: list) -> list:
    """Funde os que se sobrepõem, para não devolver a mesma hora três vezes."""
    if not intervalos:
        return []
    ordenados = sorted(intervalos, key=lambda x: x["inicio"])
    juntos = [ordenados[0]]
    for i in ordenados[1:]:
        ultimo = juntos[-1]
        if i["inicio"] <= ultimo["fim"]:
            if i["fim"] > ultimo["fim"]:
                ultimo["fim"] = i["fim"]
        else:
            juntos.append(i)
    return juntos


@frappe.whitelist()
def ocupado(anfitriao: str, de: str, ate: str) -> dict:
    """As horas tomadas de uma pessoa, das duas origens, já fundidas.

    Chamada pelo portal com chave de API. Não é `allow_guest`: o widget do site
    do cliente fala com o portal, e é o portal que fala com o Orbit. Assim a
    chave vive num servidor nosso e nunca num site WordPress.
    """
    inicio = frappe.utils.get_datetime(de)
    fim = frappe.utils.get_datetime(ate)
    if fim <= inicio:
        frappe.throw("O fim tem de ser depois do início.")
    if (fim - inicio).days > 120:
        frappe.throw("Janela demasiado larga: no máximo 120 dias de cada vez.")

    email = frappe.db.get_value("User", anfitriao, "email") or anfitriao
    tudo = _ocupado_no_sogo(email, inicio, fim) + _ocupado_no_frappe(email, inicio, fim)
    return {"anfitriao": email, "ocupado": _juntar(tudo)}


# ═══════════════════════════════════════════════════════════════════════════
# 2. Marcar
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def criar(anfitriao: str, assunto: str, inicio: str, fim: str,
          descricao: str = None, local: str = None, convidado: str = None,
          referencia: str = None) -> dict:
    """Cria o compromisso na agenda do anfitrião.

    O `Event` fica **com o anfitrião por dono** — é isso, e não um campo de
    participantes, que o faz aparecer no calendário dele em todas as apps.

    `referencia` é a marcação no portal. Guarda-se para que uma segunda chamada
    com a mesma referência não crie um segundo compromisso: o portal repete
    pedidos quando a rede falha, e sem isto repetir era duplicar.
    """
    email = frappe.db.get_value("User", anfitriao, "email")
    if not email:
        frappe.throw(f"Não há utilizador «{anfitriao}» neste Orbit.")

    if referencia:
        ja = frappe.db.get_value("Event", {"custom_referencia_marcacao": referencia}, "name")
        if ja:
            return {"ok": True, "evento": ja, "repetido": True}

    e = frappe.new_doc("Event")
    e.subject = assunto
    e.starts_on = frappe.utils.get_datetime(inicio)
    e.ends_on = frappe.utils.get_datetime(fim)
    e.event_type = "Private"
    e.status = "Open"
    e.description = descricao or ""
    if local:
        # O `Event` do Frappe não tem campo de local. Vai no princípio da
        # descrição, que é onde o feed o vai buscar para o `LOCATION:` do
        # iCalendar — e onde quem abre o evento o lê primeiro.
        e.description = f"{local}\n\n{e.description}".strip()
    if referencia and e.meta.has_field("custom_referencia_marcacao"):
        e.custom_referencia_marcacao = referencia
    e.insert(ignore_permissions=True)

    # O dono não se define no `new_doc` — o Frappe põe lá quem está a chamar.
    # Corrige-se depois da inserção, que é o que faz o evento ser **dele**.
    frappe.db.set_value("Event", e.name, "owner", email, update_modified=False)

    if convidado:
        _juntar_convidado(e.name, convidado)

    frappe.db.commit()
    return {"ok": True, "evento": e.name}


def _juntar_convidado(evento: str, email: str) -> None:
    """Liga o contacto do convidado ao evento, se esse contacto existir.

    Não se cria contacto nenhum aqui: criar fichas a partir de um formulário
    público é como se enche um CRM de lixo. Quem decide se aquele email merece
    ficha é o portal, que já sabe distinguir um cliente de um curioso.
    """
    nome = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
    if not nome:
        return
    try:
        doc = frappe.get_doc("Event", evento)
        doc.append("event_participants", {"reference_doctype": "Contact",
                                          "reference_docname": nome})
        doc.save(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Marcação: não liguei o contacto {nome}: {e}", "Orbit Marcação")


@frappe.whitelist()
def cancelar(referencia: str, motivo: str = None) -> dict:
    """Cancela o compromisso de uma marcação.

    **Existe porque o `frappe.client.set_value` genérico é recusado** à conta de
    integração do portal — 403 `PermissionError`, verificado a 04-10-2026. A
    saída tentadora era dar-lhe mais poderes; a certa é esta: um método estreito
    que só mexe no estado de um `Event` que nasceu de uma marcação nossa. A
    conta continua sem poder alterar nada no resto do Orbit.

    Procura-se pela referência e não pelo nome do documento de propósito: o
    portal conhece a referência, e assim não pode pedir o cancelamento de um
    compromisso qualquer indicando-lhe o nome.
    """
    nome = frappe.db.get_value("Event", {"custom_referencia_marcacao": referencia}, "name")
    if not nome:
        return {"ok": False, "erro": "sem compromisso para esta referência"}

    frappe.db.set_value("Event", nome, "status", "Cancelled", update_modified=True)
    if motivo:
        actual = frappe.db.get_value("Event", nome, "description") or ""
        frappe.db.set_value("Event", nome, "description",
                            f"{actual}\n\nCANCELADA: {motivo}".strip(),
                            update_modified=False)
    frappe.db.commit()
    return {"ok": True, "evento": nome}


@frappe.whitelist()
def reagendar(referencia: str, inicio: str, fim: str) -> dict:
    """Move o compromisso para outra hora, mantendo-o.

    Mover e não apagar-e-criar: o `Event` é o mesmo documento, por isso o que
    estiver ligado a ele — participantes, anexos, histórico — sobrevive. E quem
    já tem o compromisso no telemóvel vê-o mudar de hora em vez de aparecer um
    segundo ao lado do primeiro.
    """
    nome = frappe.db.get_value("Event", {"custom_referencia_marcacao": referencia}, "name")
    if not nome:
        return {"ok": False, "erro": "sem compromisso para esta referência"}

    frappe.db.set_value("Event", nome, {
        "starts_on": frappe.utils.get_datetime(inicio),
        "ends_on": frappe.utils.get_datetime(fim),
        "status": "Open",
    }, update_modified=True)
    frappe.db.commit()
    return {"ok": True, "evento": nome}


# ═══════════════════════════════════════════════════════════════════════════
# 3. O feed iCalendar que o webmail subscreve
# ═══════════════════════════════════════════════════════════════════════════

def _segredo_do_feed(email: str, criar_se_faltar: bool = False) -> str:
    """O segredo que serve de credencial ao feed desta pessoa.

    Fica no `User` como campo próprio. É um segredo e não a sessão porque quem
    lê o feed é o SOGo, de servidor para servidor, sem ninguém sentado à frente
    — é a mesma escolha que a Google faz com os endereços privados de ICS.
    """
    actual = frappe.db.get_value("User", email, "custom_segredo_agenda")
    if actual:
        return actual
    if not criar_se_faltar:
        return ""
    novo = secrets.token_urlsafe(24)
    frappe.db.set_value("User", email, "custom_segredo_agenda", novo, update_modified=False)
    frappe.db.commit()
    return novo


def _escapar(texto: str) -> str:
    """O iCalendar escapa vírgulas, pontos e vírgulas e barras — e quebras."""
    t = (texto or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return t.replace("\r\n", "\\n").replace("\n", "\\n")


def _dobrar(linha: str) -> str:
    """Nenhuma linha passa dos 75 octetos — é regra do formato, não estética.

    Clientes de calendário a sério recusam o ficheiro inteiro por causa disto,
    e o erro que dão não fala em comprimento de linha nenhum.
    """
    bruto = linha.encode("utf-8")
    if len(bruto) <= 75:
        return linha
    pedacos, actual = [], b""
    for caracter in linha:
        c = caracter.encode("utf-8")
        if len(actual) + len(c) > 73:
            pedacos.append(actual.decode("utf-8"))
            actual = b" "
        actual += c
    pedacos.append(actual.decode("utf-8"))
    return "\r\n".join(pedacos)


@frappe.whitelist(allow_guest=True)
def feed(u: str = None, t: str = None):
    """A agenda de uma pessoa em iCalendar, para o webmail subscrever.

    `allow_guest` de propósito: quem chama é o SOGo, que não tem sessão do
    Frappe. A credencial é o segredo no endereço, e um segredo errado responde
    404 e não 403 — um 403 confirmaria que aquela pessoa existe.
    """
    email = (u or "").strip()
    segredo = (t or "").strip()
    esperado = _segredo_do_feed(email) if email else ""
    if not email or not segredo or not esperado or not secrets.compare_digest(segredo, esperado):
        raise frappe.DoesNotExistError

    agora = datetime.datetime.now()
    de = agora - datetime.timedelta(days=DIAS_PASSADOS_NO_FEED)
    ate = agora + datetime.timedelta(days=DIAS_DO_FEED)

    linhas = frappe.get_all(
        "Event",
        filters={"owner": email, "status": ("!=", "Cancelled"),
                 "starts_on": ("<", ate), "ends_on": (">", de)},
        fields=["name", "subject", "description", "starts_on", "ends_on",
                "all_day", "modified"],
        limit_page_length=0,
    )

    def carimbo(d, dia_inteiro=False):
        return d.strftime("%Y%m%d") if dia_inteiro else d.strftime("%Y%m%dT%H%M%S")

    saida = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//Stratechna//Orbit//PT", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", "X-WR-CALNAME:Orbit"]
    for l in linhas:
        # O UID tem de ser estável entre leituras, senão o SOGo apaga e recria
        # tudo a cada sincronização e o telemóvel toca com avisos repetidos.
        uid = hashlib.sha1(f"{l.name}@orbit".encode()).hexdigest()
        descricao = l.description or ""
        # A primeira linha da descrição é o local (ver `criar`).
        local, _, resto = descricao.partition("\n")
        tem_local = local and ("://" in local or local.lower().startswith(
            ("presencial", "telefone", "telefónica", "telefonica")))
        saida += [
            "BEGIN:VEVENT",
            f"UID:{uid}@orbit.stratechna.com",
            f"DTSTAMP:{carimbo(l.modified or agora)}",
            _dobrar(f"SUMMARY:{_escapar(l.subject)}"),
        ]
        if l.all_day:
            saida += [f"DTSTART;VALUE=DATE:{carimbo(l.starts_on, True)}",
                      f"DTEND;VALUE=DATE:{carimbo((l.ends_on or l.starts_on), True)}"]
        else:
            saida += [f"DTSTART:{carimbo(l.starts_on)}",
                      f"DTEND:{carimbo(l.ends_on or l.starts_on)}"]
        if tem_local:
            saida.append(_dobrar(f"LOCATION:{_escapar(local)}"))
        corpo = resto.strip() if tem_local else descricao
        if corpo:
            saida.append(_dobrar(f"DESCRIPTION:{_escapar(corpo)}"))
        saida += ["END:VEVENT"]
    saida.append("END:VCALENDAR")

    frappe.response["type"] = "binary"
    frappe.response["filename"] = "orbit.ics"
    frappe.response["filecontent"] = ("\r\n".join(saida) + "\r\n").encode("utf-8")
    frappe.response["content_type"] = "text/calendar; charset=utf-8"


@frappe.whitelist()
def endereco_do_feed(anfitriao: str = None) -> dict:
    """O endereço a colar no webmail, criando o segredo na primeira vez."""
    email = frappe.db.get_value("User", anfitriao or frappe.session.user, "email")
    if not email:
        frappe.throw("Utilizador desconhecido.")
    segredo = _segredo_do_feed(email, criar_se_faltar=True)
    base = frappe.utils.get_url()
    return {"url": f"{base}/api/method/orbit.marcacao.feed"
                   f"?u={frappe.utils.quoted(email)}&t={segredo}"}


# ═══════════════════════════════════════════════════════════════════════════
# Os dois campos próprios, garantidos em cada migração
# ═══════════════════════════════════════════════════════════════════════════

CAMPOS_PROPRIOS = [
    # No `Event`: a referência da marcação no portal. É o que torna o pedido
    # idempotente — o portal repete quando a rede falha, e sem isto repetir
    # criava um segundo compromisso à mesma hora.
    ("Event", {"fieldname": "custom_referencia_marcacao",
               "label": "Referência da marcação", "fieldtype": "Data",
               "read_only": 1, "no_copy": 1, "insert_after": "subject",
               "description": "A marcação no portal que deu origem a este compromisso"}),
    # No `User`: a credencial do feed. Oculto, porque quem o vê pode ler a
    # agenda inteira daquela pessoa.
    ("User", {"fieldname": "custom_segredo_agenda",
              "label": "Segredo da agenda", "fieldtype": "Data",
              "read_only": 1, "no_copy": 1, "hidden": 1, "insert_after": "username",
              "description": "Credencial do feed iCalendar subscrito pelo webmail"}),
]


def garantir() -> None:
    """Corre em `after_migrate` e `after_install`, em todos os tenants."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_field

    for dt, campo in CAMPOS_PROPRIOS:
        if not frappe.db.exists("DocType", dt):
            continue
        if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": campo["fieldname"]}):
            create_custom_field(dt, campo)
    frappe.db.commit()
