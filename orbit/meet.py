"""O Stratechna Meet aberto a partir do painel, com o utilizador já identificado.

O Meet autentica por token e recusa quem não traga um (`allow_empty_token =
false` no prosody). Isso é de propósito: sem isso, qualquer pessoa na internet
criaria salas no nosso servidor. Mas significa que o atalho da grelha não pode
ser um link directo — tem de passar por aqui, onde se sabe quem está a clicar.

O que este módulo faz é a ponte: confirma a sessão do Frappe, emite um token
curto para esse utilizador e esse inquilino, e reencaminha para a sala.

**O inquilino vai no token E no caminho** (`/<cliente>/<sala>`). É o que permite
uma só instalação do Jitsi servir todos os clientes sem lista de utilizadores
própria: quem entra é sempre alguém que já tinha sessão no Orbit dele.
"""

import re
import time
import unicodedata

import frappe

MEET = "https://meet.orbit.stratechna.com"
EMISSOR = "orbit"          # asap_accepted_issuers no prosody
AUDIENCIA = "orbit"        # asap_accepted_audiences
VALIDADE = 4 * 60 * 60     # 4 horas: cobre uma reunião longa sem deixar um
                           # token válido a passear durante dias


def _inquilino() -> str:
    """O nome do cliente, tal como aparece no caminho do URL do Meet.

    Vem do `site_config.json` quando lá estiver (`orbit_inquilino`); senão
    deriva-se do nome do site, que é `<cliente>.orbit.stratechna.com`. O
    domínio próprio de um cliente não serve — dois sites do mesmo cliente têm
    de dar o mesmo inquilino, ou as salas deixam de se encontrar.
    """
    posto = frappe.conf.get("orbit_inquilino")
    if posto:
        return str(posto)

    sitio = frappe.local.site or ""
    if sitio.endswith(".orbit.stratechna.com"):
        return sitio.split(".", 1)[0]
    # Um site com domínio próprio (ou o `orbit.stratechna.com` da casa): usa-se
    # o nome inteiro, limpo, para continuar a ser estável e único.
    return re.sub(r"[^a-z0-9-]+", "-", sitio.lower()).strip("-") or "orbit"


def _limpar_sala(nome: str) -> str:
    """Um nome de sala que sobreviva a um URL.

    O Jitsi aceita quase tudo, mas espaços e acentos num link partilhado por
    email transformam-se em coisas diferentes consoante o cliente de correio, e
    duas pessoas acabam em salas diferentes a perguntar por onde anda a outra.

    Os acentos são TRANSLITERADOS e não removidos: «Reunião» tem de dar
    `reuniao` e não `reuni-o`, que é o que sai de trocar tudo o que não é ASCII
    por hífen — e que ninguém reconhece como o nome que escreveu.
    """
    nome = unicodedata.normalize("NFKD", (nome or "").strip().lower())
    nome = nome.encode("ascii", "ignore").decode("ascii")
    nome = re.sub(r"[^a-z0-9-]+", "-", nome).strip("-")
    return nome[:60]


def _segredo() -> str:
    s = frappe.conf.get("meet_jwt_secret")
    if not s:
        frappe.throw(
            "O Stratechna Meet ainda não está configurado neste site "
            "(falta `meet_jwt_secret`).",
            title="Meet indisponível",
        )
    return s


def emitir_token(sala: str = "*") -> str:
    """O token de entrada do utilizador autenticado. Sem efeitos secundários.

    Separado do `entrar` de propósito: assim dá para pedir o token sem sair da
    página — é o que uma integração de calendário vai querer.
    """
    import jwt

    utilizador = frappe.session.user
    if not utilizador or utilizador == "Guest":
        raise frappe.PermissionError("é preciso ter sessão iniciada")

    u = frappe.get_cached_doc("User", utilizador)
    agora = int(time.time())
    conteudo = {
        "aud": AUDIENCIA,
        "iss": EMISSOR,
        # Com `enable_domain_verification = false` o `sub` não é confrontado com
        # o domínio, mas põe-se na mesma o inquilino: é o que o Jitsi usa para
        # separar salas com o mesmo nome de clientes diferentes.
        "sub": _inquilino(),
        "room": sala or "*",
        "iat": agora,
        "nbf": agora - 10,          # folga para relógios desalinhados
        "exp": agora + VALIDADE,
        "context": {
            "user": {
                "id": utilizador,
                "name": u.full_name or utilizador,
                "email": u.email or utilizador,
                "avatar": u.user_image or "",
            }
        },
    }
    return jwt.encode(conteudo, _segredo(), algorithm="HS256")


@frappe.whitelist()
def entrar(sala: str = None):
    """Abre o Meet numa sala, já autenticado. É este o destino do atalho."""
    nome = _limpar_sala(sala)
    if not nome:
        # Sem sala indicada vai-se à página inicial do Meet, que é onde se
        # escolhe ou cria uma. O token cobre qualquer sala (`room: "*"`).
        destino = f"{MEET}/{_inquilino()}/"
    else:
        destino = f"{MEET}/{_inquilino()}/{nome}"

    token = emitir_token("*" if not nome else nome)
    separador = "&" if "?" in destino else "?"

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = f"{destino}{separador}jwt={token}"
