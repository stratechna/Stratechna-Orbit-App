"""Os doze modelos de email, montados com blocos e gerados em MJML.

Porque modelos e blocos, e não um editor livre (decisões do utilizador de
02-10 e 03-10-2026): a IA sabe encher um modelo; num editor livre cada
campanha passava a ser trabalho de paginação, e a identidade do cliente
perdia-se ao terceiro email. A variedade vem das doze estruturas e dos blocos;
a coerência vem de serem todas desenhadas com as cores, o logótipo, as fontes
e os dados da MARCA (`marca_identidade`).

## O desenho (segunda versão, 03-10-2026)

A primeira versão era correcta mas pobre — o utilizador comparou-a, com razão,
aos emails das grandes marcas. Esta segue o que eles fazem:

* **Cabeçalho e rodapé da marca.** Quando a identidade tem o logótipo para
  fundo escuro, o cabeçalho é uma faixa escura com um filete na cor de acento
  por cima — é o desenho dos emails de sistema da Stratechna (filete vermelho,
  faixa escura, logótipo a cores), e qualquer marca com as duas versões do
  logótipo fica assim. Sem essa versão, o cabeçalho é branco.
* **Fotografia a toda a largura**, com o texto num cartão por baixo ou num
  painel translúcido por cima; **imagem e texto lado a lado**, alternando;
  **cartões de produto** com fundo próprio, etiqueta, preço antigo riscado e
  botão; **faixas de chamada**, **números**, **testemunho**, **galeria** e
  **cupão** — os blocos que se vêem numa página feita em Elementor.
* **Tipografia com escala**: sobretítulo pequeno em maiúsculas na cor de
  acento, títulos grandes e pesados, texto a 16 px com entrelinha larga.
* **Imagens recortadas**, nunca esticadas: quem chama o `gerar` passa `img`,
  que devolve o endereço de uma versão recortada à medida (o portal e o Orbit
  têm cada um o seu recortador). Sem `img`, as fotografias da Pexels são
  recortadas pela própria Pexels e as outras seguem como vêm.

Porque MJML: um email não é uma página. O Outlook desenha com o motor do Word,
o Gmail corta estilos, e o telemóvel precisa de colunas que empilham. O MJML
traduz uma estrutura simples para as tabelas aninhadas que funcionam em todos.
Corre em Python (`mjml-python`, sem Node no servidor).

O conteúdo de uma campanha é um dicionário com campos opcionais; cada modelo
usa os que lhe servem e ignora os outros:

    modelo, rotulo, imagem_topo, titulo, subtitulo, paragrafos[], cta_texto, cta_url,
    produtos[{nome, descricao, preco, preco_antigo, etiqueta, url, imagem}],
    destaque{texto, subtexto}, itens[{titulo, texto, url, imagem}],
    evento{data, hora, local}, assinatura, blocos[]

Tudo o que é texto é escapado aqui. Nada do conteúdo entra no HTML em bruto.

UM SÓ MOTOR, DUAS CÓPIAS IGUAIS: o original vive no Orbit
(`orbit/marketing/modelos.py`, Stratechna-Orbit-App) e o portal usa uma cópia
fiel em `app/mailing_modelos.py`, para a pré-visualização que o cliente aprova
ser a mensagem que sai. Muda-se no Orbit e copia-se para cá — nunca o inverso.
É código puro, sem Frappe: testa-se e lê-se sem um site à volta.
"""
import html
import re
from typing import Callable, Optional

MODELOS = {
    "newsletter":     {"nome": "Newsletter", "para": "notícias e artigos do mês",
                       "usa": ["imagem_topo", "titulo", "paragrafos", "itens", "cta"]},
    "novidades":      {"nome": "Novidades", "para": "produtos ou serviços que chegaram",
                       "usa": ["titulo", "subtitulo", "paragrafos", "produtos", "cta"]},
    "promocao":       {"nome": "Promoção", "para": "desconto ou campanha com prazo",
                       "usa": ["imagem_topo", "destaque", "titulo", "paragrafos", "produtos", "cta"]},
    "produto":        {"nome": "Produto em destaque", "para": "um produto principal e alguns relacionados",
                       "usa": ["produtos", "titulo", "paragrafos", "cta"]},
    "catalogo":       {"nome": "Catálogo", "para": "uma montra de até seis produtos",
                       "usa": ["titulo", "subtitulo", "produtos", "cta"]},
    "sazonal":        {"nome": "Campanha sazonal", "para": "Natal, verão, regresso às aulas…",
                       "usa": ["imagem_topo", "titulo", "subtitulo", "paragrafos", "produtos", "cta"]},
    "evento":         {"nome": "Convite ou evento", "para": "feira, apresentação, webinar",
                       "usa": ["imagem_topo", "titulo", "evento", "paragrafos", "cta"]},
    "institucional":  {"nome": "Comunicado", "para": "aviso, mudança, novidade da empresa",
                       "usa": ["titulo", "paragrafos", "assinatura"]},
    "servicos":       {"nome": "Serviços", "para": "três serviços ou vantagens",
                       "usa": ["imagem_topo", "titulo", "subtitulo", "itens", "cta"]},
    "artigos":        {"nome": "Artigos", "para": "resumo de publicações do blog",
                       "usa": ["titulo", "paragrafos", "itens"]},
    "boas_vindas":    {"nome": "Boas-vindas", "para": "quem acabou de chegar",
                       "usa": ["imagem_topo", "titulo", "paragrafos", "itens", "cta"]},
    "relacao":        {"nome": "Relação com o cliente", "para": "pós-compra, lembretes, reactivação",
                       "usa": ["titulo", "paragrafos", "produtos", "cta"]},
}

LARGURA = 640
LATERAL = 40          # margem lateral do conteúdo
FUNDO_PAGINA = "#eceef1"
CINZA_TEXTO = "#4a4f57"
CINZA_SUAVE = "#8a9099"
LINHA = "#e6e8eb"
FUNDO_CARTAO = "#f5f6f8"


def _e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def _url(u) -> str:
    u = str(u or "").strip()
    return u if u.lower().startswith(("https://", "http://")) else ""


def _lum(cor: str) -> float:
    c = (cor or "#000000").lstrip("#")
    try:
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 0.0
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _sobre(cor: str) -> str:
    """Texto legível sobre esta cor: branco ou quase preto, o que der mais contraste."""
    l = _lum(cor)
    return "#ffffff" if (1.05 / (l + 0.05)) >= ((l + 0.05) / 0.0625) else "#1d1d1f"


def _misturar(cor: str, com: str, quanto: float) -> str:
    def rgb(x):
        x = (x or "#888888").lstrip("#")
        try:
            return [int(x[i:i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            return [136, 136, 136]
    a, b = rgb(cor), rgb(com)
    return "#" + "".join(f"{int(p + (q - p) * quanto):02x}" for p, q in zip(a, b))


def _clarear(cor: str, quanto: float = 0.9) -> str:
    return _misturar(cor, "#ffffff", quanto)


def _escurecer(cor: str, quanto: float = 0.3) -> str:
    return _misturar(cor, "#000000", quanto)


def _pexels(u: str, w: int, h: Optional[int]) -> str:
    """As fotografias da Pexels recortam-se no próprio endereço."""
    base = u.split("?")[0]
    return f"{base}?auto=compress&cs=tinysrgb&w={w}" + (f"&h={h}&fit=crop" if h else "")


class _Tema:
    def __init__(self, ident: dict, img: Optional[Callable] = None):
        cores = ident.get("cores") or {}
        self.primaria = cores.get("primaria") or "#22303d"
        self.acento = cores.get("acento") or cores.get("secundaria") or self.primaria
        self.texto = cores.get("texto") or CINZA_TEXTO
        # Os títulos na cor da marca só quando ela é escura o bastante para
        # ser lida como texto; senão, quase preto.
        self.titulos = self.primaria if _lum(self.primaria) < 0.18 else "#16191d"
        self.fundo_pagina = FUNDO_PAGINA
        self.suave = _clarear(self.primaria, 0.93)
        self.sobre_primaria = _sobre(self.primaria)
        self.sobre_acento = _sobre(self.acento)
        # A faixa escura do cabeçalho e do rodapé: a própria cor da marca se
        # for escura, senão um quase-preto.
        self.escuro = self.primaria if _lum(self.primaria) < 0.06 else "#15181c"
        fontes = ident.get("fontes") or {}
        self.fonte_titulos = fontes.get("titulos")
        self.fonte_texto = fontes.get("texto")
        logos = ident.get("logotipos") or {}
        self.logo = _url(logos.get("claro"))
        self.logo_escuro = _url(logos.get("escuro"))
        self.nome = ident.get("nome") or ""
        self._img = img

    def familia(self, titulos=False) -> str:
        f = self.fonte_titulos if titulos else self.fonte_texto
        base = "'Helvetica Neue', Helvetica, Arial, sans-serif"
        return f"'{f}', {base}" if f else base

    def img(self, u, w: int, h: Optional[int] = None) -> str:
        """O endereço da imagem à medida (`w`×`h` em píxeis reais, já com a
        densidade dos ecrãs de retina): recortada, nunca esticada."""
        u = _url(u)
        if not u:
            return ""
        if self._img:
            try:
                return self._img(u, w, h) or u
            except Exception:  # noqa: BLE001 — uma imagem nunca deita a mensagem abaixo
                return u
        if "images.pexels.com/" in u:
            return _pexels(u, w, h)
        return u


def _sec(conteudo: str, fundo="#ffffff", padding=f"0 {LATERAL}px", extra="") -> str:
    return f'<mj-section background-color="{fundo}" padding="{padding}"{extra}>{conteudo}</mj-section>'


def _col(conteudo: str, largura=None, extra="") -> str:
    w = f' width="{largura}"' if largura else ""
    return f'<mj-column{w}{extra}>{conteudo}</mj-column>'


def _paragrafos_html(ps) -> str:
    return "".join(f'<p style="margin:0 0 16px">{_e(p).replace(chr(10), "<br>")}</p>' for p in ps)


# ── Peças ──────────────────────────────────────────────────────────────────

def _rotulo(t: _Tema, texto, alinhar="left", cor=None) -> str:
    if not texto:
        return ""
    return (f'<mj-text align="{alinhar}" font-size="12px" font-weight="700" letter-spacing="2px" '
            f'text-transform="uppercase" color="{cor or t.acento}" padding="0 0 10px">{_e(texto)}</mj-text>')


def _cabecalho(t: _Tema, ident: dict) -> str:
    site = _url((ident.get("contactos") or {}).get("site"))
    if site:
        rotulo_site = re.sub(r"^https?://(www\.)?", "", site).rstrip("/")
    escuro = bool(t.logo_escuro)
    fundo = t.escuro if escuro else "#ffffff"
    logo = t.logo_escuro if escuro else t.logo
    cor_lig = "#c5cad1" if escuro else CINZA_SUAVE
    marca = (f'<mj-image src="{_e(logo)}" alt="{_e(t.nome)}" width="150px" align="left" padding="0" />'
             if logo else
             f'<mj-text font-size="22px" font-weight="800" color="{_sobre(fundo) if escuro else t.titulos}" '
             f'padding="0" font-family="{t.familia(True)}">{_e(t.nome)}</mj-text>')
    direita = (f'<mj-text align="right" font-size="13px" padding="0"><a href="{_e(site)}" '
               f'style="color:{cor_lig};text-decoration:none">{_e(rotulo_site)} &rarr;</a></mj-text>'
               if site else "")
    return (_sec(_col('<mj-spacer height="4px" />'), t.acento, "0")
            + f'<mj-section background-color="{fundo}" padding="26px {LATERAL}px">'
            + _col(marca, "60%", ' vertical-align="middle"') + _col(direita, "40%", ' vertical-align="middle"')
            + '</mj-section>'
            + ("" if escuro else _sec(_col(f'<mj-divider border-width="1px" border-color="{LINHA}" padding="0" />'), "#ffffff", "0")))


def _titulo(t: _Tema, c: dict, tamanho=30, alinhar="left", fundo="#ffffff", cor=None, padding_topo=40) -> str:
    partes = [_rotulo(t, c.get("rotulo"), alinhar)]
    if c.get("titulo"):
        partes.append(f'<mj-text font-size="{tamanho}px" line-height="1.18" font-weight="800" '
                      f'letter-spacing="-0.4px" align="{alinhar}" color="{cor or t.titulos}" '
                      f'font-family="{t.familia(True)}" padding="0 0 12px">{_e(c["titulo"])}</mj-text>')
    if c.get("subtitulo"):
        partes.append(f'<mj-text font-size="18px" line-height="1.5" align="{alinhar}" '
                      f'color="{cor or t.texto}" padding="0">{_e(c["subtitulo"])}</mj-text>')
    if not "".join(partes):
        return ""
    return _sec(_col("".join(partes)), fundo, f"{padding_topo}px {LATERAL}px 8px")


def _texto(t: _Tema, c: dict, fundo="#ffffff", alinhar="left") -> str:
    ps = [p for p in c.get("paragrafos") or [] if str(p).strip()]
    if not ps:
        return ""
    return _sec(_col(f'<mj-text font-size="16px" line-height="1.7" align="{alinhar}" color="{t.texto}" '
                     f'padding="0">{_paragrafos_html(ps)}</mj-text>'), fundo, f"16px {LATERAL}px 4px")


def _botao_mj(t: _Tema, texto, url, ir, cor=None, alinhar="left", largura_total=False, contorno=False,
              tamanho=16, padding="0") -> str:
    if not (texto and _url(url)):
        return ""
    cor = cor or t.primaria
    fundo, letra = ("transparent", cor) if contorno else (cor, _sobre(cor))
    borda = f' border="2px solid {cor}"' if contorno else ""
    largura = ' width="100%"' if largura_total else ""
    return (f'<mj-button href="{_e(ir(url))}" background-color="{fundo}" color="{letra}"{borda}{largura} '
            f'font-size="{tamanho}px" font-weight="700" border-radius="8px" inner-padding="15px 34px" '
            f'align="{alinhar}" padding="{padding}" font-family="{t.familia(True)}">{_e(texto)}</mj-button>')


def _botao(t: _Tema, c: dict, ir, cor=None, alinhar="left", fundo="#ffffff") -> str:
    b = _botao_mj(t, c.get("cta_texto"), c.get("cta_url"), ir, cor, alinhar)
    return _sec(_col(b), fundo, f"20px {LATERAL}px 40px") if b else ""


def _imagem(t: _Tema, url, ir, ligar=None, margens=False, altura=None) -> str:
    """Uma fotografia a toda a largura, ou com margens e cantos redondos —
    recortada a 16:9 por omissão, para uma fotografia ao alto não ocupar o ecrã."""
    largura = LARGURA - (2 * LATERAL if margens else 0)
    altura = altura or int(largura * 9 / 16)
    src = t.img(url, largura * 2, altura * 2 if altura else None)
    if not src:
        return ""
    href = f' href="{_e(ir(ligar))}"' if _url(ligar) else ""
    raio = ' border-radius="12px"' if margens else ""
    return _sec(_col(f'<mj-image src="{_e(src)}" alt=""{href}{raio} padding="0" fluid-on-mobile="true" />'),
                "#ffffff", f"{'24px ' + str(LATERAL) + 'px 0' if margens else '0'}")


def _heroi(t: _Tema, c: dict, ir) -> str:
    """Fotografia larga com o título por cima, num painel escuro translúcido —
    lê-se sobre qualquer fotografia. Sem fotografia, uma faixa na cor da marca."""
    img = t.img(c.get("imagem_topo"), LARGURA * 2, 920)
    botao = _botao_mj(t, c.get("cta_texto"), c.get("cta_url"), ir, t.acento, "center", padding="18px 0 0")
    rot = _rotulo(t, c.get("rotulo"), "center", "#ffffff")
    titulo = (f'<mj-text align="center" font-size="38px" font-weight="800" line-height="1.12" letter-spacing="-0.6px" '
              f'color="#ffffff" font-family="{t.familia(True)}" padding="0 0 12px">{_e(c.get("titulo"))}</mj-text>'
              if c.get("titulo") else "")
    sub = (f'<mj-text align="center" font-size="18px" line-height="1.5" color="#eef0f3" padding="0">'
           f'{_e(c.get("subtitulo"))}</mj-text>' if c.get("subtitulo") else "")
    if not img:
        fundo = t.escuro
        return (f'<mj-section background-color="{fundo}" padding="64px {LATERAL}px">'
                + _col(rot + titulo + sub + botao) + '</mj-section>')
    painel = (f'<mj-column background-color="rgba(12,14,18,0.62)" padding="34px 30px" border-radius="12px">'
              f'{rot}{titulo}{sub}{botao}</mj-column>')
    return (f'<mj-section background-url="{_e(img)}" background-size="cover" background-position="center center" '
            f'background-repeat="no-repeat" background-color="{t.escuro}" padding="90px 46px">{painel}</mj-section>')


def _faixa(t: _Tema, c: dict) -> str:
    """A faixa de promoção: o número grande na cor de acento."""
    d = c.get("destaque") or {}
    if not d.get("texto"):
        return ""
    sub = (f'<mj-text align="center" font-size="17px" font-weight="600" letter-spacing="0.5px" '
           f'color="{t.sobre_acento}" padding="6px 0 0">{_e(d.get("subtexto"))}</mj-text>' if d.get("subtexto") else "")
    return (f'<mj-section background-color="{t.acento}" padding="38px {LATERAL}px">'
            + _col(f'<mj-text align="center" font-size="58px" font-weight="900" line-height="1" letter-spacing="-1px" '
                   f'color="{t.sobre_acento}" font-family="{t.familia(True)}" padding="0">{_e(d["texto"])}</mj-text>{sub}')
            + '</mj-section>')


def _chamada(t: _Tema, c: dict, ir, imagem=None) -> str:
    """A faixa de chamada que fecha a mensagem: título, frase e botão sobre a
    cor escura da marca (ou sobre uma fotografia)."""
    if not (c.get("titulo") or c.get("cta_texto")):
        return ""
    titulo = (f'<mj-text align="center" font-size="28px" font-weight="800" line-height="1.2" color="#ffffff" '
              f'font-family="{t.familia(True)}" padding="0 0 10px">{_e(c.get("titulo"))}</mj-text>' if c.get("titulo") else "")
    texto = (f'<mj-text align="center" font-size="16px" line-height="1.6" color="#d9dde3" padding="0">'
             f'{_e(c.get("texto"))}</mj-text>' if c.get("texto") else "")
    botao = _botao_mj(t, c.get("cta_texto"), c.get("cta_url"), ir, t.acento, "center", padding="22px 0 0")
    src = t.img(imagem, LARGURA * 2, 700) if imagem else ""
    if src:
        return (f'<mj-section background-url="{_e(src)}" background-size="cover" background-position="center center" '
                f'background-color="{t.escuro}" padding="64px 46px">'
                f'<mj-column background-color="rgba(12,14,18,0.6)" padding="30px 26px" border-radius="12px">'
                f'{titulo}{texto}{botao}</mj-column></mj-section>')
    return (f'<mj-section background-color="{t.escuro}" padding="54px {LATERAL}px">'
            + _col(titulo + texto + botao) + '</mj-section>')


def _preco(t: _Tema, p: dict, tamanho=18, alinhar="left") -> str:
    if not p.get("preco"):
        return ""
    antigo = (f' <span style="font-size:{tamanho - 4}px;font-weight:400;color:{CINZA_SUAVE};'
              f'text-decoration:line-through">{_e(p["preco_antigo"])}</span>' if p.get("preco_antigo") else "")
    return (f'<mj-text align="{alinhar}" font-size="{tamanho}px" font-weight="800" color="{t.titulos}" '
            f'padding="8px 0 0">{_e(p["preco"])}{antigo}</mj-text>')


def _cartao_produto(t: _Tema, p: dict, ir, colunas: int) -> str:
    lado = int((LARGURA - 2 * 28) / colunas) - 16
    src = t.img(p.get("imagem"), lado * 2, lado * 2)
    etiqueta = (f'<mj-text font-size="11px" font-weight="800" letter-spacing="1px" text-transform="uppercase" '
                f'padding="0 0 10px"><span style="background:{t.acento};color:{t.sobre_acento};padding:4px 9px;'
                f'border-radius:4px">{_e(p["etiqueta"])}</span></mj-text>' if p.get("etiqueta") else "")
    img = (f'<mj-image src="{_e(src)}" alt="{_e(p.get("nome"))}" href="{_e(ir(p.get("url")))}" '
           f'border-radius="8px" padding="0 0 14px" />' if src else "")
    desc = (f'<mj-text font-size="13px" line-height="1.5" color="{CINZA_SUAVE}" padding="6px 0 0">'
            f'{_e(p["descricao"])}</mj-text>' if p.get("descricao") else "")
    botao = _botao_mj(t, "Comprar" if p.get("preco") else "Ver mais", p.get("url"), ir, t.primaria,
                      largura_total=True, contorno=True, tamanho=14, padding="14px 0 0")
    return (f'<mj-column width="{100 / colunas:.3f}%" padding="0 8px 16px">'
            f'{etiqueta}{img}'
            f'<mj-text font-size="15px" font-weight="700" line-height="1.35" color="{t.titulos}" padding="0">'
            f'<a href="{_e(ir(p.get("url")))}" style="color:{t.titulos};text-decoration:none">{_e(p.get("nome"))}</a>'
            f'</mj-text>{desc}{_preco(t, p, 17)}{botao}</mj-column>')


def _grelha(t: _Tema, produtos: list, ir, colunas=3, fundo="#ffffff", maximo=6) -> str:
    ps = [p for p in produtos or [] if p.get("nome")][:maximo]
    if not ps:
        return ""
    colunas = min(colunas, len(ps)) if len(ps) < colunas else colunas
    linhas = []
    for i in range(0, len(ps), colunas):
        cols = "".join(_cartao_produto(t, p, ir, colunas) for p in ps[i:i + colunas])
        linhas.append(f'<mj-section background-color="{fundo}" padding="16px 28px 8px">{cols}</mj-section>')
    return "".join(linhas)


def _destaque_produto(t: _Tema, p: dict, c: dict, ir) -> str:
    """Fotografia grande de um lado, nome, preço e botão do outro."""
    if not p:
        return ""
    src = t.img(p.get("imagem"), 560, 560)
    img = (f'<mj-image src="{_e(src)}" alt="{_e(p.get("nome"))}" href="{_e(ir(p.get("url")))}" '
           f'padding="0" border-radius="12px" />' if src else "")
    texto = (_rotulo(t, c.get("rotulo") or p.get("etiqueta") or "Em destaque")
             + f'<mj-text font-size="28px" font-weight="800" line-height="1.15" letter-spacing="-0.4px" '
               f'color="{t.titulos}" font-family="{t.familia(True)}" padding="0 0 10px">{_e(p.get("nome"))}</mj-text>'
             + (f'<mj-text font-size="15px" line-height="1.6" color="{t.texto}" padding="0">'
                f'{_e(p["descricao"])}</mj-text>' if p.get("descricao") else "")
             + _preco(t, p, 24)
             + _botao_mj(t, c.get("cta_texto") or "Ver produto", p.get("url"), ir, t.acento, padding="18px 0 0"))
    return (f'<mj-section background-color="{t.suave}" padding="40px 28px">'
            f'<mj-column width="50%" padding="0 12px" vertical-align="middle">{img}</mj-column>'
            f'<mj-column width="50%" padding="0 12px" vertical-align="middle">{texto}</mj-column></mj-section>')


def _imagem_texto(t: _Tema, b: dict, ir, fundo="#ffffff") -> str:
    """Imagem de um lado e texto do outro — o bloco de duas colunas das páginas."""
    src = t.img(b.get("imagem"), 540, 440)
    if not (src or b.get("titulo") or b.get("texto")):
        return ""
    img = (f'<mj-column width="50%" padding="0 12px" vertical-align="middle"><mj-image src="{_e(src)}" alt="" '
           + (f'href="{_e(ir(b["url"]))}" ' if _url(b.get("url")) else "")
           + 'border-radius="12px" padding="0 0 18px" /></mj-column>') if src else ""
    texto = (_rotulo(t, b.get("rotulo"))
             + (f'<mj-text font-size="24px" font-weight="800" line-height="1.2" color="{t.titulos}" '
                f'font-family="{t.familia(True)}" padding="0 0 10px">{_e(b["titulo"])}</mj-text>' if b.get("titulo") else "")
             + (f'<mj-text font-size="15px" line-height="1.65" color="{t.texto}" padding="0">'
                f'{_paragrafos_html(_paragrafos(b.get("texto")))}</mj-text>' if b.get("texto") else "")
             + (f'<mj-text font-size="15px" font-weight="700" padding="4px 0 0"><a href="{_e(ir(b["url"]))}" '
                f'style="color:{t.acento};text-decoration:none">{_e(b.get("botao_texto") or "Saber mais")} &rarr;</a></mj-text>'
                if _url(b.get("url")) else ""))
    col_texto = f'<mj-column width="{"50%" if src else "100%"}" padding="0 12px" vertical-align="middle">{texto}</mj-column>'
    direita = b.get("posicao") == "Imagem à direita"
    direccao = ' direction="rtl"' if direita and src else ""
    return f'<mj-section background-color="{fundo}" padding="32px 28px"{direccao}>{img}{col_texto}</mj-section>'


def _icone(t: _Tema, n, i: dict, fundo) -> str:
    src = t.img(i.get("imagem"), 112, 112) if i.get("imagem") else ""
    if src:
        return f'<mj-image src="{_e(src)}" width="56px" alt="" border-radius="28px" padding="0 0 16px" />'
    return (f'<mj-text align="center" padding="0 0 16px"><span style="display:inline-block;width:52px;height:52px;'
            f'line-height:52px;border-radius:26px;background:{_clarear(t.acento, 0.86) if fundo == "#ffffff" else "#ffffff"};'
            f'color:{t.acento};font-weight:800;font-size:20px;font-family:Arial,sans-serif">{n}</span></mj-text>')


def _itens_colunas(t: _Tema, itens: list, ir, fundo="#ffffff") -> str:
    """Três colunas com ícone (imagem ou número), título e texto: serviços, razões."""
    its = [i for i in itens or [] if i.get("titulo")][:3]
    if not its:
        return ""
    largura = f"{100 / len(its):.3f}%"
    cols = []
    for n, i in enumerate(its, 1):
        ligacao = (f'<mj-text align="center" font-size="14px" padding="10px 0 0"><a href="{_e(ir(i["url"]))}" '
                   f'style="color:{t.acento};font-weight:700;text-decoration:none">Saber mais &rarr;</a></mj-text>'
                   if _url(i.get("url")) else "")
        cols.append(f'<mj-column width="{largura}" padding="0 12px 24px">{_icone(t, n, i, fundo)}'
                    f'<mj-text align="center" font-size="18px" font-weight="800" color="{t.titulos}" '
                    f'font-family="{t.familia(True)}" padding="0 0 8px">{_e(i["titulo"])}</mj-text>'
                    f'<mj-text align="center" font-size="14px" line-height="1.6" color="{t.texto}" padding="0">'
                    f'{_e(i.get("texto"))}</mj-text>{ligacao}</mj-column>')
    return f'<mj-section background-color="{fundo}" padding="32px 22px 12px">{"".join(cols)}</mj-section>'


def _numeros(t: _Tema, itens: list, fundo="#ffffff") -> str:
    """Três números grandes com a legenda por baixo (o título de cada item é o
    número, o texto é a legenda)."""
    its = [i for i in itens or [] if i.get("titulo")][:3]
    if not its:
        return ""
    largura = f"{100 / len(its):.3f}%"
    cols = "".join(
        f'<mj-column width="{largura}" padding="0 8px">'
        f'<mj-text align="center" font-size="40px" font-weight="900" letter-spacing="-1px" color="{t.acento}" '
        f'font-family="{t.familia(True)}" padding="0 0 4px">{_e(i["titulo"])}</mj-text>'
        f'<mj-text align="center" font-size="14px" line-height="1.5" color="{t.texto}" padding="0">{_e(i.get("texto"))}</mj-text>'
        f'</mj-column>' for i in its)
    return (f'<mj-section background-color="{fundo}" padding="36px 28px" border-top="1px solid {LINHA}" '
            f'border-bottom="1px solid {LINHA}">{cols}</mj-section>')


def _lista_artigos(t: _Tema, itens: list, ir) -> str:
    """Cartões de artigo: fotografia à esquerda, título, resumo e «Ler artigo»."""
    linhas = []
    for i in [i for i in itens or [] if i.get("titulo")][:5]:
        src = t.img(i.get("imagem"), 400, 300)
        img = (f'<mj-column width="38%" padding="0 16px 0 0" vertical-align="middle"><mj-image src="{_e(src)}" alt="" '
               f'href="{_e(ir(i.get("url")))}" padding="0" border-radius="10px" /></mj-column>' if src else "")
        ler = (f'<mj-text font-size="14px" padding="10px 0 0"><a href="{_e(ir(i["url"]))}" '
               f'style="color:{t.acento};font-weight:700;text-decoration:none">Ler artigo &rarr;</a></mj-text>'
               if _url(i.get("url")) else "")
        linhas.append(f'<mj-section background-color="#ffffff" padding="18px {LATERAL}px">{img}'
                      f'<mj-column width="{"62%" if img else "100%"}" vertical-align="middle">'
                      f'<mj-text font-size="19px" font-weight="800" line-height="1.3" color="{t.titulos}" padding="0 0 6px" '
                      f'font-family="{t.familia(True)}">{_e(i["titulo"])}</mj-text>'
                      f'<mj-text font-size="14px" line-height="1.6" color="{t.texto}" padding="0">'
                      f'{_e(i.get("texto"))}</mj-text>{ler}</mj-column></mj-section>')
    return "".join(linhas)


def _evento(t: _Tema, c: dict) -> str:
    ev = c.get("evento") or {}
    campos = [(r, ev.get(k)) for r, k in (("Data", "data"), ("Hora", "hora"), ("Local", "local")) if ev.get(k)]
    if not campos:
        return ""
    cols = "".join(f'<mj-column padding="0 8px"><mj-text align="center" font-size="11px" font-weight="700" '
                   f'color="{_misturar(t.sobre_primaria, t.primaria, 0.35)}" '
                   f'text-transform="uppercase" letter-spacing="2px" padding="0">{_e(r)}</mj-text>'
                   f'<mj-text align="center" font-size="20px" font-weight="800" color="{t.sobre_primaria}" '
                   f'padding="6px 0 0">{_e(v)}</mj-text></mj-column>' for r, v in campos)
    return f'<mj-section background-color="{t.primaria}" padding="28px 28px">{cols}</mj-section>'


def _testemunho(t: _Tema, b: dict) -> str:
    if not b.get("texto"):
        return ""
    src = t.img(b.get("imagem"), 128, 128)
    foto = (f'<mj-image src="{_e(src)}" width="64px" alt="" border-radius="32px" padding="20px 0 10px" />' if src else "")
    quem = (f'<mj-text align="center" font-size="15px" font-weight="800" color="{t.titulos}" padding="{"0" if src else "18px 0 0"}">'
            f'{_e(b.get("titulo"))}</mj-text>' if b.get("titulo") else "")
    cargo = (f'<mj-text align="center" font-size="13px" color="{CINZA_SUAVE}" padding="2px 0 0">{_e(b["subtitulo"])}</mj-text>'
             if b.get("subtitulo") else "")
    return (f'<mj-section background-color="{t.suave}" padding="44px 56px">'
            + _col(f'<mj-text align="center" font-size="56px" line-height="0.6" color="{t.acento}" '
                   f'font-family="Georgia, serif" padding="10px 0 6px">&ldquo;</mj-text>'
                   f'<mj-text align="center" font-size="19px" line-height="1.6" font-style="italic" color="{t.titulos}" '
                   f'font-family="Georgia, \'Times New Roman\', serif" padding="0">{_e(b["texto"])}</mj-text>'
                   f'{foto}{quem}{cargo}')
            + '</mj-section>')


def _galeria(t: _Tema, imagens: list, ir, ligar=None) -> str:
    srcs = [u for u in imagens if _url(u)][:3]
    if not srcs:
        return ""
    n = len(srcs)
    lado = int((LARGURA - 2 * 28) / n) - 12
    href = f' href="{_e(ir(ligar))}"' if _url(ligar) else ""
    cols = "".join(f'<mj-column width="{100 / n:.3f}%" padding="0 6px"><mj-image src="{_e(t.img(u, lado * 2, int(lado * 2 * (0.75 if n > 1 else 0.56))))}" '
                   f'alt=""{href} border-radius="10px" padding="0" /></mj-column>' for u in srcs)
    return f'<mj-section background-color="#ffffff" padding="16px 28px">{cols}</mj-section>'


def _cupao(t: _Tema, b: dict) -> str:
    if not b.get("titulo"):
        return ""
    return (f'<mj-section background-color="#ffffff" padding="24px {LATERAL}px">'
            f'<mj-column border="2px dashed {t.acento}" border-radius="12px" padding="26px 20px" background-color="{_clarear(t.acento, 0.94)}">'
            + _rotulo(t, b.get("rotulo") or "O seu código", "center")
            + f'<mj-text align="center" font-size="32px" font-weight="900" letter-spacing="4px" color="{t.titulos}" '
              f'font-family="\'Courier New\', Courier, monospace" padding="0">{_e(b["titulo"])}</mj-text>'
            + (f'<mj-text align="center" font-size="15px" line-height="1.5" color="{t.texto}" padding="10px 0 0">'
               f'{_e(b["texto"])}</mj-text>' if b.get("texto") else "")
            + (f'<mj-text align="center" font-size="12px" color="{CINZA_SUAVE}" padding="8px 0 0">{_e(b["subtitulo"])}</mj-text>'
               if b.get("subtitulo") else "")
            + '</mj-column></mj-section>')


def _assinatura(t: _Tema, c: dict) -> str:
    if not c.get("assinatura"):
        return ""
    return _sec(_col(f'<mj-text font-size="16px" line-height="1.6" color="{t.texto}" padding="0">'
                     f'{_e(c["assinatura"]).replace(chr(10), "<br>")}</mj-text>'), "#ffffff", f"8px {LATERAL}px 40px")


def _separador(t: _Tema) -> str:
    return _sec(_col(f'<mj-divider border-width="1px" border-color="{LINHA}" padding="0" />'), "#ffffff", f"20px {LATERAL}px")


def _espaco(altura=28) -> str:
    return _sec(_col(f'<mj-spacer height="{altura}px" />'), "#ffffff", "0")


_REDES = {"facebook": "Facebook", "instagram": "Instagram", "linkedin": "LinkedIn",
          "youtube": "YouTube", "tiktok": "TikTok", "x": "X", "pinterest": "Pinterest"}


def _rodape(t: _Tema, ident: dict, motivo: str, remover: str, legal_texto: str) -> str:
    redes = ident.get("redes") or {}
    pilulas = "&nbsp; ".join(
        f'<a href="{_e(u)}" style="display:inline-block;color:#ffffff;text-decoration:none;font-weight:700;'
        f'font-size:12px;letter-spacing:0.5px;border:1px solid #4b525c;border-radius:20px;padding:6px 14px;margin:0 0 6px">{n}</a>'
        for k, n in _REDES.items() if _url(u := redes.get(k)))
    cont = ident.get("contactos") or {}
    contactos = " &nbsp;·&nbsp; ".join(_e(v) for v in (cont.get("telefone"), cont.get("email"),
                                                        re.sub(r"^https?://(www\.)?", "", cont.get("site") or "").rstrip("/")) if v)
    logo = t.logo_escuro or ""
    marca = (f'<mj-image src="{_e(logo)}" alt="{_e(t.nome)}" width="120px" padding="0 0 18px" />' if logo else
             f'<mj-text align="center" font-size="18px" font-weight="800" color="#ffffff" padding="0 0 14px">{_e(t.nome)}</mj-text>')
    faixa = (f'<mj-section background-color="{t.escuro}" padding="40px {LATERAL}px 34px">'
             + _col(marca
                    + (f'<mj-text align="center" padding="0 0 12px">{pilulas}</mj-text>' if pilulas else "")
                    + (f'<mj-text align="center" font-size="13px" line-height="1.6" color="#aab0b9" padding="0">{contactos}</mj-text>'
                       if contactos else ""))
             + '</mj-section>')
    return (faixa
            + _sec(_col(f'<mj-text align="center" font-size="12px" line-height="1.7" color="#8a9099" padding="0">'
                        f'{_e(legal_texto).replace(chr(10), "<br>")}<br><br>{_e(motivo)} '
                        f'<a href="{_e(remover)}" style="color:#6b717a;text-decoration:underline">Deixar de receber</a>.'
                        f'</mj-text>'), t.fundo_pagina, f"24px {LATERAL}px 36px"))


# ── Os doze ────────────────────────────────────────────────────────────────

def _corpo(chave: str, t: _Tema, c: dict, ir) -> str:
    """Cada modelo é a sua sequência de blocos (a mesma que «Montar a partir
    do modelo» põe no editor)."""
    return _desenhar(t, blocos_do_modelo(chave, c), c, ir)


def _desenhar(t: _Tema, blocos: list, c: dict, ir) -> str:
    """Os blocos pela ordem. Depois de um «Produto em destaque», as grelhas
    seguintes deixam de fora o produto que ele já mostrou."""
    saida = []
    for b in blocos:
        saida.append(_bloco(t, b, c, ir))
        if b.get("tipo") == "Produto em destaque" and c.get("produtos"):
            c = {**c, "produtos": c["produtos"][1:]}
    return "".join(saida)


# ── O editor de blocos ────────────────────────────────────────────────────
#
# Os doze modelos são sequências fixas destes blocos. O editor deixa a
# sequência na mão de quem escreve — acrescentar, tirar, reordenar — sem lhe
# dar a paginação: cada bloco usa as mesmas peças, com as cores, fontes e
# logótipo da marca. Decisão do utilizador de 03-10-2026: blocos estruturados
# dentro da marca, não um editor livre de arrastar e largar.

def _paragrafos(texto) -> list:
    return [p.strip() for p in str(texto or "").split("\n\n") if p.strip()]


def _bloco(t: _Tema, b: dict, c: dict, ir) -> str:
    tipo = b.get("tipo")
    alinhar = "center" if b.get("alinhar") == "Centro" else "left"
    fundo = t.suave if b.get("fundo") == "Suave" else "#ffffff"
    ps = c.get("produtos") or []
    if tipo == "Título":
        return _titulo(t, {"rotulo": b.get("rotulo"), "titulo": b.get("titulo"), "subtitulo": b.get("subtitulo")},
                       30, alinhar, fundo)
    if tipo == "Texto":
        return _texto(t, {"paragrafos": _paragrafos(b.get("texto"))}, fundo, alinhar)
    if tipo == "Botão":
        cor = t.acento if b.get("cor_botao") == "Destaque" else None
        return _botao(t, {"cta_texto": b.get("botao_texto"), "cta_url": b.get("url")}, ir, cor, alinhar, fundo)
    if tipo == "Imagem":
        return _imagem(t, b.get("imagem"), ir, b.get("url"), margens=b.get("margens") == "Com margens")
    if tipo == "Imagem com título":
        d = {"rotulo": b.get("rotulo"), "imagem_topo": b.get("imagem"), "titulo": b.get("titulo"),
             "subtitulo": b.get("subtitulo"), "cta_texto": b.get("botao_texto"), "cta_url": b.get("url")}
        return _heroi(t, d, ir)
    if tipo == "Imagem e texto":
        return _imagem_texto(t, b, ir, fundo)
    if tipo == "Faixa de destaque":
        return _faixa(t, {"destaque": {"texto": b.get("titulo"), "subtexto": b.get("subtitulo")}})
    if tipo == "Faixa de chamada":
        return _chamada(t, {"titulo": b.get("titulo"), "texto": b.get("texto"), "cta_texto": b.get("botao_texto"),
                            "cta_url": b.get("url")}, ir, b.get("imagem"))
    if tipo == "Produtos":
        colunas = 2 if str(b.get("colunas")) == "2" else 3
        return _grelha(t, ps, ir, colunas, fundo, int(b.get("maximo") or 6))
    if tipo == "Produto em destaque":
        return _destaque_produto(t, ps[0] if ps else None, {"cta_texto": b.get("botao_texto"),
                                                             "rotulo": b.get("rotulo")}, ir)
    if tipo == "Vantagens em colunas":
        return _itens_colunas(t, c.get("itens"), ir, fundo)
    if tipo == "Números":
        return _numeros(t, c.get("itens"), fundo)
    if tipo == "Lista de artigos":
        return _lista_artigos(t, c.get("itens"), ir)
    if tipo == "Evento":
        return _evento(t, c)
    if tipo == "Testemunho":
        return _testemunho(t, b)
    if tipo == "Galeria":
        return _galeria(t, [b.get("imagem"), b.get("imagem_2"), b.get("imagem_3")], ir, b.get("url"))
    if tipo == "Cupão":
        return _cupao(t, b)
    if tipo == "Assinatura":
        return _assinatura(t, {"assinatura": b.get("texto")})
    if tipo == "Separador":
        return _separador(t)
    if tipo == "Espaço":
        return _espaco()
    return ""


def blocos_do_modelo(chave: str, c: dict) -> list:
    """A sequência de um modelo como lista de blocos, cheia com o conteúdo que
    já existe — o desenho do modelo e o ponto de partida do editor."""
    ps = c.get("produtos") or []
    tit = {"tipo": "Título", "rotulo": c.get("rotulo"), "titulo": c.get("titulo"), "subtitulo": c.get("subtitulo")}
    txt = {"tipo": "Texto", "texto": "\n\n".join(c.get("paragrafos") or [])}
    bot = {"tipo": "Botão", "botao_texto": c.get("cta_texto"), "url": c.get("cta_url")}
    heroi = {"tipo": "Imagem com título", "rotulo": c.get("rotulo"), "imagem": c.get("imagem_topo"),
             "titulo": c.get("titulo"), "subtitulo": c.get("subtitulo"),
             "botao_texto": c.get("cta_texto"), "url": c.get("cta_url")}
    foto = {"tipo": "Imagem", "imagem": c.get("imagem_topo")}
    centro = {"alinhar": "Centro"}
    suave = {"fundo": "Suave"}
    destaque = c.get("destaque") or {}
    faixa = {"tipo": "Faixa de destaque", "titulo": destaque.get("texto"), "subtitulo": destaque.get("subtexto")}
    tem_foto = bool(_url(c.get("imagem_topo")))
    seq = {
        "newsletter": ([foto] if tem_foto else []) + [tit, txt, {"tipo": "Lista de artigos"}, {**bot, **centro}],
        "novidades": [{**tit, **centro}, {**txt, **centro}, {"tipo": "Produtos"}, {**bot, **centro}],
        "promocao": [faixa] + ([foto] if tem_foto else []) + [{**tit, **centro}, {**txt, **centro},
                                                             {"tipo": "Produtos"}, {**bot, **centro, "cor_botao": "Destaque"}],
        "produto": [{"tipo": "Produto em destaque", "botao_texto": c.get("cta_texto")}, tit, txt]
                   + ([{"tipo": "Produtos", "maximo": 3}] if len(ps) > 1 else []) + [bot],
        "catalogo": [{**tit, **centro}, {"tipo": "Produtos", "colunas": "2"}, {**bot, **centro}],
        "sazonal": [heroi, {**txt, **centro}] + ([{"tipo": "Produtos", "maximo": 3}] if ps else []),
        "evento": ([foto] if tem_foto else []) + [{**tit, **centro}, {"tipo": "Evento"}, txt,
                                                 {**bot, **centro, "cor_botao": "Destaque"}],
        "institucional": [tit, txt, {"tipo": "Assinatura", "texto": c.get("assinatura")}],
        "servicos": ([foto] if tem_foto else []) + [{**tit, **centro}, {"tipo": "Vantagens em colunas", **suave},
                                                   {"tipo": "Faixa de chamada", "titulo": c.get("cta_titulo") or "Vamos falar?",
                                                    "texto": c.get("cta_frase"), "botao_texto": c.get("cta_texto"),
                                                    "url": c.get("cta_url")}],
        "artigos": [tit, txt, {"tipo": "Lista de artigos"}],
        "boas_vindas": [heroi if tem_foto else {**tit, **centro}, {**txt, **centro},
                        {"tipo": "Vantagens em colunas", **suave}, {**bot, **centro}],
    }.get(chave) or [tit, txt] + ([{"tipo": "Produtos", "maximo": 3}] if ps else []) + [bot]
    return [{k: v for k, v in b.items() if v not in (None, "")} for b in seq]


def gerar(conteudo: dict, ident: dict, *, ir: Callable[[str], str], remover: str, motivo: str,
          legal_texto: str, pixel: Optional[str] = None, assunto: str = "",
          pre_cabecalho: str = "", img: Optional[Callable] = None) -> str:
    """O HTML final da mensagem. `ir` transforma cada endereço no que é medido;
    `img(url, largura, altura)` devolve o endereço da imagem recortada à medida."""
    from mjml import mjml2html
    t = _Tema(ident, img)
    chave = conteudo.get("modelo") if conteudo.get("modelo") in MODELOS else "relacao"
    fontes = "".join(
        f'<mj-font name="{_e(f)}" href="https://fonts.googleapis.com/css2?family={_e(f).replace(" ", "+")}:wght@400;700;800&amp;display=swap" />'
        for f in {x for x in (t.fonte_titulos, t.fonte_texto) if x})
    rastos = f'<mj-raw><img src="{_e(pixel)}" width="1" height="1" alt="" style="display:block;border:0" /></mj-raw>' if pixel else ""
    corpo = (_desenhar(t, conteudo["blocos"], conteudo, ir) if conteudo.get("blocos")
             else _corpo(chave, t, conteudo, ir))
    fonte_mjml = (
        f'<mjml lang="pt"><mj-head><mj-title>{_e(assunto)}</mj-title>'
        f'<mj-preview>{_e(pre_cabecalho)}</mj-preview>{fontes}'
        f'<mj-attributes><mj-all font-family="{t.familia()}" /><mj-text color="{t.texto}" />'
        f'<mj-section text-align="left" /></mj-attributes>'
        f'<mj-style>a {{ color: {t.acento}; }} '
        f'@media (max-width:480px) {{ .mj-column-per-50, .mj-column-per-33-333, .mj-column-per-38, .mj-column-per-62 '
        f'{{ width:100% !important; max-width:100% !important; }} }}</mj-style>'
        f'</mj-head><mj-body background-color="{t.fundo_pagina}" width="{LARGURA}px">'
        f'<mj-wrapper padding="28px 0 0" background-color="{t.fundo_pagina}">'
        + _cabecalho(t, ident) + corpo + _espaco(12) + _rodape(t, ident, motivo, remover, legal_texto)
        + f'</mj-wrapper>{rastos}</mj-body></mjml>')
    resultado = mjml2html(fonte_mjml)
    return resultado if isinstance(resultado, str) else getattr(resultado, "html", str(resultado))


def ligacoes(conteudo: dict) -> list:
    """Todos os endereços para onde a mensagem leva, por ordem fixa."""
    urls = [conteudo.get("cta_url")]
    urls += [p.get("url") for p in conteudo.get("produtos") or []]
    urls += [i.get("url") for i in conteudo.get("itens") or []]
    # Os blocos no fim: as posições acima não mudam, e um clique registado
    # numa campanha antiga continua a apontar para o mesmo sítio.
    urls += [b.get("url") for b in conteudo.get("blocos") or []]
    saida = []
    for u in urls:
        u = _url(u)
        if u and u not in saida:
            saida.append(u)
    return saida


_PX = "https://images.pexels.com/photos/{0}/pexels-photo-{0}.jpeg"
FOTOS_EXEMPLO = {
    "topo": _PX.format(4884116), "promocao": _PX.format(7987752), "sazonal": _PX.format(6334749),
    "evento": _PX.format(9275222), "equipa": _PX.format(8190827), "retrato": _PX.format(16160809),
    "artigos": [_PX.format(7693692), _PX.format(326514), _PX.format(204511)],
    "produtos": [_PX.format(3394653), _PX.format(6157408), _PX.format(12269763),
                 _PX.format(31785816), _PX.format(9058883), _PX.format(1464625)],
}


def exemplo(chave: str) -> dict:
    """Conteúdo de exemplo para mostrar um modelo antes de haver texto — com
    fotografias reais, para se ver o desenho como vai ficar."""
    nomes = ["Auscultadores sem fios", "Relógio clássico", "Cadeira ergonómica", "Caneca de cerâmica",
             "Auscultadores estúdio", "Conjunto desportivo"]
    produtos = [{"nome": nomes[n], "preco": f"{49 + n * 30},90 €", "url": "https://exemplo.pt/p",
                 "descricao": "Uma frase curta que diz porque vale a pena.", "imagem": FOTOS_EXEMPLO["produtos"][n],
                 **({"preco_antigo": f"{69 + n * 30},90 €", "etiqueta": "−25%"} if chave == "promocao" else {}),
                 **({"etiqueta": "Novo"} if chave == "novidades" and n == 0 else {})} for n in range(6)]
    artigos = [{"titulo": t, "texto": "Um resumo de duas linhas que leva a ler o artigo completo no site.",
                "url": "https://exemplo.pt/blog", "imagem": FOTOS_EXEMPLO["artigos"][n]}
               for n, t in enumerate(("Cinco tendências para este trimestre", "Como renovámos o nosso site",
                                      "O guia rápido para começar"))]
    vantagens = [{"titulo": t, "texto": "Uma frase que explica a vantagem para quem compra.", "url": "https://exemplo.pt/s"}
                 for t in ("Rapidez", "Qualidade", "Apoio próximo")]
    foto = {"newsletter": FOTOS_EXEMPLO["topo"], "promocao": FOTOS_EXEMPLO["promocao"],
            "sazonal": FOTOS_EXEMPLO["sazonal"], "evento": FOTOS_EXEMPLO["evento"],
            "servicos": FOTOS_EXEMPLO["equipa"], "boas_vindas": FOTOS_EXEMPLO["equipa"]}.get(chave)
    rotulo = {"newsletter": "Newsletter de Outubro", "novidades": "Acabou de chegar", "promocao": "Só esta semana",
              "sazonal": "Especial de Natal", "evento": "Convite", "servicos": "O que fazemos",
              "boas_vindas": "Bem-vindo", "catalogo": "Catálogo", "artigos": "Do nosso blog"}.get(chave)
    return {"modelo": chave, "rotulo": rotulo, "titulo": MODELOS[chave]["nome"] if chave != "boas_vindas" else "Que bom tê-lo connosco",
            "subtitulo": MODELOS[chave]["para"].capitalize(), "imagem_topo": foto,
            "paragrafos": ["{{nome}}, este é um texto de exemplo para mostrar como fica o modelo com a sua marca.",
                           "Na campanha a sério, este texto é escrito para a ocasião, com o tom da sua empresa."],
            "cta_texto": "Ver mais", "cta_url": "https://exemplo.pt", "produtos": produtos,
            "itens": artigos if chave in ("newsletter", "artigos") else vantagens,
            "destaque": {"texto": "−25%", "subtexto": "Em toda a loja, até domingo"},
            "evento": {"data": "15 de Novembro", "hora": "18h30", "local": "Lisboa"},
            "assinatura": "Com os melhores cumprimentos,\nA equipa"}


# Os nomes que o utilizador escolhe no Orbit → as chaves dos modelos.
POR_NOME = {m["nome"]: k for k, m in MODELOS.items()}
POR_NOME.update({"Comunicado": "institucional"})
