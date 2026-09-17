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


@frappe.whitelist()
def resumo(ano: int = None, mes: int = None) -> dict:
    """O dia de hoje ao detalhe e os dias ocupados do mês, num só pedido.

    Num só pedido de propósito: o ecrã desenha-se de uma vez, e dois pedidos
    faziam os widgets aparecer em momentos diferentes.
    """
    utilizador = frappe.session.user
    if not utilizador or utilizador == "Guest":
        raise frappe.PermissionError("é preciso ter sessão iniciada")

    hoje = datetime.date.today()
    ano = int(ano or hoje.year)
    mes = int(mes or hoje.month)

    vazio = {"hoje": [], "ocupados": [], "ano": ano, "mes": mes, "ligado": False}

    email = frappe.db.get_value("User", utilizador, "email") or utilizador
    try:
        ligacao = _ligar()
    except Exception as e:
        frappe.log_error(f"Agenda: não foi possível ligar ao Mail: {e}", "Orbit Agenda")
        return vazio
    if ligacao is None:
        return vazio

    try:
        with ligacao, ligacao.cursor() as cur:
            tabela = _tabela(cur, email)
            if not tabela:
                # Ainda não estreou o calendário. Não é erro: é o estado de
                # quem nunca marcou nada.
                return dict(vazio, ligado=True)

            def carimbo(d: datetime.date) -> int:
                return int(datetime.datetime.combine(d, datetime.time.min).timestamp())

            amanha = hoje + datetime.timedelta(days=1)
            do_dia = _eventos(cur, tabela, carimbo(hoje), carimbo(amanha))

            primeiro = datetime.date(ano, mes, 1)
            seguinte = (datetime.date(ano + 1, 1, 1) if mes == 12
                        else datetime.date(ano, mes + 1, 1))
            do_mes = _eventos(cur, tabela, carimbo(primeiro), carimbo(seguinte))
    except Exception as e:
        frappe.log_error(f"Agenda: falhou a leitura: {e}", "Orbit Agenda")
        return vazio
    finally:
        try:
            ligacao.close()
        except Exception:
            pass

    def formatar(linha):
        titulo, inicio, fim, dia_inteiro, local = linha
        d = datetime.datetime.fromtimestamp(inicio)
        return {
            "titulo": titulo or "(sem título)",
            "hora": "" if dia_inteiro else d.strftime("%H:%M"),
            "dia_inteiro": bool(dia_inteiro),
            "local": local or "",
            # O que tem sala do Meet mostra o símbolo e leva lá directamente.
            "meet": "meet.orbit.stratechna.com" in (local or ""),
        }

    ocupados = sorted({
        datetime.datetime.fromtimestamp(l[1]).day
        for l in do_mes
        if datetime.datetime.fromtimestamp(l[1]).month == mes
    })

    return {
        "hoje": [formatar(l) for l in do_dia],
        "ocupados": ocupados,
        "ano": ano,
        "mes": mes,
        "ligado": True,
    }
