"""A agenda do utilizador, lida do Stratechna Mail, para o ecrã de apps.

Porque é que vem do SOGo e não do Frappe: é no webmail que a equipa marca
reuniões. O Frappe tem um doctype `Event` e o CRM tem tarefas, mas na prática
estão vazios — verificado a 17-09-2026, zero registos em ambos. Um widget
alimentado por aí mostrava um calendário permanentemente vazio e ninguém
perceberia porquê.

Lê-se a base do SOGo directamente, com um utilizador **só de leitura**
(`orbit_agenda`), pela mesma razão e da mesma forma que o SOGo lê os contactos
do CRM: é a via que não obriga a ter as credenciais do utilizador. Se este
código tiver um defeito, o pior que faz é mostrar mal — não apaga compromissos.

As tabelas do SOGo: `sogo_folder_info` diz onde mora o calendário de cada
pessoa, e cada calendário tem uma tabela `<id>_quick` com os campos já
indexados (início, fim, título, local). É para isto que essa tabela existe —
a outra guarda o iCal inteiro e obrigaria a interpretá-lo aqui.
"""

import datetime
import pathlib

import frappe

SOGO_HOST = "sogo-db"
SOGO_BD = "sogo"
SOGO_UTILIZADOR = "orbit_agenda"
SEGREDO = "/opt/orbit/segredos/orbit-agenda-db.txt"


def _senha() -> str:
    s = frappe.conf.get("agenda_db_password")
    if s:
        return s
    try:
        return pathlib.Path(SEGREDO).read_text().strip()
    except OSError:
        return ""


def _ligar():
    import psycopg2

    senha = _senha()
    if not senha:
        return None
    return psycopg2.connect(
        host=SOGO_HOST, dbname=SOGO_BD, user=SOGO_UTILIZADOR, password=senha,
        connect_timeout=4,
    )


def _tabela(cur, email: str):
    """A tabela do calendário desta pessoa, ou None se ainda não tiver um.

    Só se devolve o que é do próprio: o `c_path2` é a caixa dona da pasta, e
    filtrar por ele aqui é o que impede alguém de ver a agenda de outro. Não é
    uma questão de apresentação — é a fronteira, e por isso está na consulta e
    não no ecrã.
    """
    cur.execute(
        "SELECT c_location FROM sogo_folder_info "
        "WHERE c_path2 = %s AND c_folder_type = 'Appointment' "
        "ORDER BY c_path3 LIMIT 1",
        (email,),
    )
    linha = cur.fetchone()
    if not linha or not linha[0]:
        return None
    # c_location é um URL: .../sogo/<tabela>
    tabela = linha[0].rstrip("/").rsplit("/", 1)[-1]
    # O nome vem da base de dados e vai para dentro de uma consulta. Não há
    # forma de o parametrizar (é um identificador, não um valor), por isso
    # valida-se o formato em vez de confiar.
    if not tabela.replace("_", "").isalnum():
        return None
    return tabela


def _eventos(cur, tabela: str, inicio: int, fim: int):
    cur.execute(
        f'SELECT c_title, c_startdate, c_enddate, c_isallday, c_location '  # noqa: S608
        f'FROM "{tabela}_quick" '
        f"WHERE c_startdate < %s AND COALESCE(c_enddate, c_startdate) >= %s "
        f"AND COALESCE(c_status, 0) <> 3 "   # 3 = cancelado
        f"ORDER BY c_startdate",
        (fim, inicio),
    )
    return cur.fetchall()


def _do_orbit(email: str, de: datetime.datetime, ate: datetime.datetime) -> list:
    """Os `Event` do Frappe desta pessoa, na mesma forma das linhas do SOGo.

    É onde caem as reuniões marcadas pelo portal e as do «Marcar reunião»
    (ver `marcacao`). Chegam ao webmail por um feed subscrito, que não é o
    calendário pessoal lido acima — sem isto, uma reunião marcada não aparecia
    no ecrã de apps. Do SOGo e daqui nada é igual, por isso não há duplicados
    a resolver; a guarda por (título, início) em `resumo` é só cinto e
    suspensórios para o dia em que alguém importe o feed à mão.
    """
    from orbit.marcacao import FUSO

    def epoca(d, dia_inteiro):
        # O dia inteiro guarda-se como o SOGo o guarda — meia-noite UTC —
        # para que `resumo` o leia da mesma maneira venha de onde vier.
        return int(d.replace(tzinfo=datetime.timezone.utc if dia_inteiro else FUSO).timestamp())

    linhas = frappe.get_all(
        "Event",
        filters={"owner": email, "status": ("!=", "Cancelled"),
                 "starts_on": ("<", ate)},
        or_filters={"ends_on": (">=", de), "starts_on": (">=", de)},
        fields=["subject", "starts_on", "ends_on", "all_day"],
        order_by="starts_on",
        limit_page_length=500,
    )
    return [(l.subject, epoca(l.starts_on, l.all_day),
             epoca(l.ends_on, l.all_day) if l.ends_on else None,
             l.all_day, "") for l in linhas]


@frappe.whitelist()
def resumo(ano: int = None, mes: int = None) -> dict:
    """O dia de hoje ao detalhe e os compromissos de cada dia do mês, num só pedido.

    Num só pedido de propósito: o ecrã desenha-se de uma vez, e dois pedidos
    faziam os widgets aparecer em momentos diferentes. O «Hoje» e o mês saem da
    mesma leitura e da mesma repartição por dias — se divergissem, o quadro do
    dia e o ponto do dia de hoje no mês podiam contar coisas diferentes.
    """
    utilizador = frappe.session.user
    if not utilizador or utilizador == "Guest":
        raise frappe.PermissionError("é preciso ter sessão iniciada")

    from orbit.marcacao import hora_local

    hoje = hora_local(datetime.datetime.now().timestamp()).date()
    ano = int(ano or hoje.year)
    mes = int(mes or hoje.month)

    vazio = {"hoje": [], "ocupados": [], "dias": {}, "ano": ano, "mes": mes,
             "ligado": False}

    primeiro = datetime.date(ano, mes, 1)
    seguinte = (datetime.date(ano + 1, 1, 1) if mes == 12
                else datetime.date(ano, mes + 1, 1))
    amanha = hoje + datetime.timedelta(days=1)
    de, ate = min(primeiro, hoje), max(seguinte, amanha)

    def instante(d: datetime.date) -> datetime.datetime:
        return datetime.datetime.combine(d, datetime.time.min)

    def carimbo(d: datetime.date) -> int:
        from orbit.marcacao import FUSO
        return int(instante(d).replace(tzinfo=FUSO).timestamp())

    email = frappe.db.get_value("User", utilizador, "email") or utilizador

    # Os do Orbit lêem-se primeiro e não dependem do correio: com o Mail em
    # baixo, as reuniões marcadas continuam a ver-se.
    try:
        linhas = _do_orbit(email, instante(de), instante(ate))
    except Exception as e:
        frappe.log_error(f"Agenda: falhou a leitura dos Event: {e}", "Orbit Agenda")
        linhas = []

    ligado = False
    try:
        ligacao = _ligar()
    except Exception as e:
        frappe.log_error(f"Agenda: não foi possível ligar ao Mail: {e}", "Orbit Agenda")
        ligacao = None
    if ligacao is not None:
        try:
            with ligacao, ligacao.cursor() as cur:
                tabela = _tabela(cur, email)
                # Sem tabela ainda não estreou o calendário. Não é erro: é o
                # estado de quem nunca marcou nada.
                if tabela:
                    linhas += _eventos(cur, tabela, carimbo(de), carimbo(ate))
                ligado = True
        except Exception as e:
            frappe.log_error(f"Agenda: falhou a leitura: {e}", "Orbit Agenda")
        finally:
            try:
                ligacao.close()
            except Exception:
                pass

    if not ligado and not linhas:
        return vazio

    def formatar(linha):
        titulo, inicio, fim, dia_inteiro, local = linha
        # **O fuso é dito, não herdado** — ver `marcacao.hora_local`. O
        # contentor corre em UTC e o site está em Europe/Lisbon: sem isto, no
        # horário de Verão a agenda mostrava tudo uma hora mais cedo do que a
        # pessoa marcou, e ninguém desconfiava porque parecia só «uma hora».
        d = hora_local(inicio)
        return {
            "titulo": titulo or "(sem título)",
            "hora": "" if dia_inteiro else d.strftime("%H:%M"),
            "dia_inteiro": bool(dia_inteiro),
            "local": local or "",
            # O que tem sala do Meet mostra o símbolo e leva lá directamente.
            "meet": "meet.orbit.stratechna.com" in (local or ""),
        }

    # Um compromisso de vários dias aparece em cada um deles, e não só no
    # primeiro: umas férias de 3 a 7 ocupam o dia 5. O fim é exclusivo (o SOGo
    # guarda o dia inteiro até à meia-noite do dia seguinte), daí o segundo a
    # menos. O tecto de 62 dias impede que um evento sem fim plausível encha o
    # mês inteiro.
    por_dia: dict = {}
    vistos = set()
    for l in sorted(linhas, key=lambda l: (l[1] or 0)):
        if not l[1] or (l[0], l[1]) in vistos:
            continue
        vistos.add((l[0], l[1]))
        # O dia inteiro é uma data, não um instante: o SOGo guarda-o à
        # meia-noite UTC, e passado para a hora de Lisboa no Verão o fim caía
        # à 01:00 do dia seguinte — umas férias de um dia ocupavam dois.
        data = (
            (lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date())
            if l[3] else (lambda t: hora_local(t).date())
        )
        i = data(l[1])
        f = data(l[2] - 1) if l[2] and l[2] > l[1] else i
        dia, ultimo = i, min(f, i + datetime.timedelta(days=62))
        while dia <= ultimo:
            if de <= dia < ate:
                por_dia.setdefault(dia, []).append(l)
            dia += datetime.timedelta(days=1)

    def lista(d):
        # Os de dia inteiro primeiro, como em qualquer agenda: não têm hora
        # e ficavam perdidos a meio da lista.
        return [formatar(l) for l in
                sorted(por_dia.get(d, []), key=lambda l: (not l[3], l[1]))]

    dias = {d.day: lista(d) for d in sorted(por_dia) if primeiro <= d < seguinte}
    return {
        "hoje": lista(hoje),
        "ocupados": sorted(dias),
        "dias": dias,
        "ano": ano,
        "mes": mes,
        "ligado": ligado,
    }
