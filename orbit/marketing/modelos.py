"""Os doze modelos de email, montados com blocos e gerados em MJML.

Porque modelos e não um editor livre (decisão do utilizador, 02-10-2026): a IA
sabe encher um modelo; num editor livre cada campanha passava a ser trabalho de
paginação, e a identidade do cliente perdia-se ao terceiro email. A variedade
vem de doze estruturas diferentes; a coerência vem de serem todas desenhadas
com as cores, o logótipo, as fontes e os dados da MARCA (`marca_identidade`).

Porque MJML: um email não é uma página. O Outlook desenha com o motor do Word,
o Gmail corta estilos, e o telemóvel precisa de colunas que empilham. O MJML
traduz uma estrutura simples para as tabelas aninhadas que funcionam em todos.
Corre em Python (`mjml-python`, sem Node no servidor).

O conteúdo de uma campanha é um dicionário com campos opcionais; cada modelo
usa os que lhe servem e ignora os outros:

    modelo, imagem_topo, titulo, subtitulo, paragrafos[], cta_texto, cta_url,
    produtos[{nome, descricao, preco, url, imagem}],
    destaque{texto, subtexto}, itens[{titulo, texto, url, imagem}],
    evento{data, hora, local}, assinatura

Tudo o que é texto é escapado aqui. Nada do conteúdo entra no HTML em bruto.

Este ficheiro nasceu no portal (`app/mailing_modelos.py`) e passou para o
Orbit a 03-10-2026, quando o email marketing passou a viver aqui. É código
puro, sem Frappe: testa-se e lê-se sem um site à volta.
"""
import html
from typing import Callable, Optional

MODELOS = {
    "newsletter":     {"nome": "Newsletter", "para": "notícias e artigos do mês",
                       "usa": ["imagem_topo", "titulo", "paragrafos", "itens", "cta"]},
    "novidades":      {"nome": "Novidades", "para": "produtos ou serviços que chegaram",
                       "usa": ["titulo", "subtitulo", "paragrafos", "produtos", "cta"]},
    "promocao":       {"nome": "Promoção", "para": "desconto ou campanha com prazo",
                       "usa": ["destaque", "titulo", "paragrafos", "produtos", "cta"]},
    "produto":        {"nome": "Produto em destaque", "para": "um produto principal e alguns relacionados",
                       "usa": ["produtos", "titulo", "paragrafos", "cta"]},
    "catalogo":       {"nome": "Catálogo", "para": "uma montra de até seis produtos",
                       "usa": ["titulo", "subtitulo", "produtos", "cta"]},
    "sazonal":        {"nome": "Campanha sazonal", "para": "Natal, verão, regresso às aulas…",
                       "usa": ["imagem_topo", "titulo", "subtitulo", "paragrafos", "cta"]},
    "evento":         {"nome": "Convite ou evento", "para": "feira, apresentação, webinar",
                       "usa": ["imagem_topo", "titulo", "evento", "paragrafos", "cta"]},
    "institucional":  {"nome": "Comunicado", "para": "aviso, mudança, novidade da empresa",
                       "usa": ["titulo", "paragrafos", "assinatura"]},
    "servicos":       {"nome": "Serviços", "para": "três serviços ou vantagens",
                       "usa": ["titulo", "subtitulo", "itens", "cta"]},
    "artigos":        {"nome": "Artigos", "para": "resumo de publicações do blog",
                       "usa": ["titulo", "paragrafos", "itens"]},
    "boas_vindas":    {"nome": "Boas-vindas", "para": "quem acabou de chegar",
                       "usa": ["titulo", "paragrafos", "itens", "cta"]},
    "relacao":        {"nome": "Relação com o cliente", "para": "pós-compra, lembretes, reactivação",
                       "usa": ["titulo", "paragrafos", "produtos", "cta"]},
}


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


def _clarear(cor: str, quanto: float = 0.9) -> str:
    c = (cor or "#888888").lstrip("#")
    try:
        r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#f4f4f2"
    r, g, b = (int(x + (255 - x) * quanto) for x in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


class _Tema:
    def __init__(self, ident: dict):
        cores = ident.get("cores") or {}
        self.primaria = cores.get("primaria") or "#22303d"
        self.acento = cores.get("acento") or cores.get("secundaria") or self.primaria
        self.texto = cores.get("texto") or "#2b2b2b"
        self.fundo_pagina = "#f2f2f0"
        self.suave = _clarear(self.primaria, 0.92)
        self.sobre_primaria = _sobre(self.primaria)
        self.sobre_acento = _sobre(self.acento)
        fontes = ident.get("fontes") or {}
        self.fonte_titulos = fontes.get("titulos")
        self.fonte_texto = fontes.get("texto")
        self.logo = _url((ident.get("logotipos") or {}).get("claro"))
        self.logo_escuro = _url((ident.get("logotipos") or {}).get("escuro"))
        self.nome = ident.get("nome") or ""

    def familia(self, titulos=False) -> str:
        f = self.fonte_titulos if titulos else self.fonte_texto
        return f"'{f}', Arial, Helvetica, sans-serif" if f else "Arial, Helvetica, sans-serif"


# ── Blocos ─────────────────────────────────────────────────────────────────

def _cabecalho(t: _Tema, ir) -> str:
    marca = (f'<mj-image src="{_e(t.logo)}" alt="{_e(t.nome)}" width="170px" align="left" padding="0" />'
             if t.logo else
             f'<mj-text font-size="22px" font-weight="700" color="{t.primaria}" padding="0" '
             f'font-family="{t.familia(True)}">{_e(t.nome)}</mj-text>')
    return (f'<mj-section background-color="#ffffff" padding="24px 32px 18px">'
            f'<mj-column>{marca}</mj-column></mj-section>'
            f'<mj-section background-color="{t.primaria}" padding="0"><mj-column>'
            f'<mj-spacer height="5px" /></mj-column></mj-section>')


def _titulo(t: _Tema, c: dict, tamanho=28, alinhar="left", fundo="#ffffff", cor=None) -> str:
    partes = []
    if c.get("titulo"):
        partes.append(f'<mj-text font-size="{tamanho}px" line-height="1.2" font-weight="700" '
                      f'align="{alinhar}" color="{cor or t.primaria}" font-family="{t.familia(True)}" '
                      f'padding="0 0 8px">{_e(c["titulo"])}</mj-text>')
    if c.get("subtitulo"):
        partes.append(f'<mj-text font-size="17px" line-height="1.45" align="{alinhar}" '
                      f'color="{cor or t.texto}" padding="0">{_e(c["subtitulo"])}</mj-text>')
    if not partes:
        return ""
    return (f'<mj-section background-color="{fundo}" padding="32px 32px 8px">'
            f'<mj-column>{"".join(partes)}</mj-column></mj-section>')


def _texto(t: _Tema, c: dict, fundo="#ffffff") -> str:
    ps = [p for p in c.get("paragrafos") or [] if str(p).strip()]
    if not ps:
        return ""
    corpo = "".join(f'<p style="margin:0 0 14px">{_e(p).replace(chr(10), "<br>")}</p>' for p in ps)
    return (f'<mj-section background-color="{fundo}" padding="16px 32px 4px"><mj-column>'
            f'<mj-text font-size="16px" line-height="1.6" color="{t.texto}" padding="0">{corpo}</mj-text>'
            f'</mj-column></mj-section>')


def _botao(t: _Tema, c: dict, ir, cor=None, alinhar="left", fundo="#ffffff") -> str:
    if not (c.get("cta_texto") and _url(c.get("cta_url"))):
        return ""
    cor = cor or t.primaria
    return (f'<mj-section background-color="{fundo}" padding="18px 32px 28px"><mj-column>'
            f'<mj-button href="{_e(ir(c["cta_url"]))}" background-color="{cor}" color="{_sobre(cor)}" '
            f'font-size="16px" font-weight="700" border-radius="6px" inner-padding="14px 28px" '
            f'align="{alinhar}" padding="0" font-family="{t.familia(True)}">{_e(c["cta_texto"])}</mj-button>'
            f'</mj-column></mj-section>')


def _imagem_topo(t: _Tema, c: dict, ir, com_texto=False) -> str:
    img = _url(c.get("imagem_topo"))
    if not img:
        return ""
    if not com_texto:
        return (f'<mj-section padding="0"><mj-column><mj-image src="{_e(img)}" alt="" padding="0" '
                f'fluid-on-mobile="true" /></mj-column></mj-section>')
    # Imagem a toda a largura com o título por cima: o modelo sazonal.
    # Texto branco sobre fotografia só se lê com sombra: a fotografia é do
    # cliente e pode ser clara no sítio exacto onde o título cai. A faixa
    # translúcida por trás garante-o onde a sombra não é suportada (Outlook
    # ignora as duas coisas e mostra a cor primária como fundo).
    sombra = "text-shadow:0 2px 14px rgba(0,0,0,.75),0 0 3px rgba(0,0,0,.6)"
    sobre = "".join(
        f'<mj-text align="center" font-size="{tam}px" font-weight="{peso}" color="#ffffff" '
        f'line-height="1.2" font-family="{t.familia(True)}" padding="0 24px 10px" '
        f'container-background-color="rgba(0,0,0,0.38)"><span style="{sombra}">{_e(c[k])}</span></mj-text>'
        for k, tam, peso in (("titulo", 34, 800), ("subtitulo", 18, 400)) if c.get(k))
    botao = (f'<mj-button href="{_e(ir(c["cta_url"]))}" background-color="{t.acento}" '
             f'color="{t.sobre_acento}" font-weight="700" border-radius="6px" inner-padding="14px 28px" '
             f'padding="10px 0 0">{_e(c["cta_texto"])}</mj-button>'
             if c.get("cta_texto") and _url(c.get("cta_url")) else "")
    return (f'<mj-hero mode="fluid-height" background-url="{_e(img)}" background-color="{t.primaria}" '
            f'padding="90px 24px">{sobre}{botao}</mj-hero>')


def _faixa(t: _Tema, c: dict) -> str:
    """A faixa de promoção: o número grande na cor de acento."""
    d = c.get("destaque") or {}
    if not d.get("texto"):
        return ""
    sub = (f'<mj-text align="center" font-size="17px" color="{t.sobre_acento}" padding="4px 0 0">'
           f'{_e(d.get("subtexto"))}</mj-text>' if d.get("subtexto") else "")
    return (f'<mj-section background-color="{t.acento}" padding="34px 24px"><mj-column>'
            f'<mj-text align="center" font-size="44px" font-weight="800" line-height="1.05" '
            f'color="{t.sobre_acento}" font-family="{t.familia(True)}" padding="0">{_e(d["texto"])}</mj-text>'
            f'{sub}</mj-column></mj-section>')


def _cartao_produto(t: _Tema, p: dict, ir, botao=True) -> str:
    img = (f'<mj-image src="{_e(p["imagem"])}" alt="{_e(p.get("nome"))}" href="{_e(ir(p.get("url")))}" '
           f'padding="0 0 10px" border-radius="6px" />' if _url(p.get("imagem")) else "")
    preco = (f'<mj-text font-size="16px" font-weight="700" color="{t.primaria}" padding="4px 0 0">'
             f'{_e(p["preco"])}</mj-text>' if p.get("preco") else "")
    desc = (f'<mj-text font-size="13px" line-height="1.45" color="#666666" padding="4px 0 0">'
            f'{_e(p["descricao"])}</mj-text>' if p.get("descricao") else "")
    ver = (f'<mj-button href="{_e(ir(p.get("url")))}" background-color="{t.primaria}" '
           f'color="{t.sobre_primaria}" font-size="13px" font-weight="700" border-radius="4px" '
           f'inner-padding="8px 16px" align="left" padding="10px 0 0">Ver</mj-button>'
           if botao and _url(p.get("url")) else "")
    return (f'{img}<mj-text font-size="15px" font-weight="700" line-height="1.35" color="{t.texto}" '
            f'padding="0"><a href="{_e(ir(p.get("url")))}" style="color:{t.texto};text-decoration:none">'
            f'{_e(p.get("nome"))}</a></mj-text>{desc}{preco}{ver}')


def _grelha(t: _Tema, produtos: list, ir, colunas=3, fundo="#ffffff", maximo=6) -> str:
    ps = [p for p in produtos or [] if p.get("nome")][:maximo]
    if not ps:
        return ""
    largura = f"{100 / colunas:.2f}%"
    linhas = []
    for i in range(0, len(ps), colunas):
        cols = "".join(f'<mj-column width="{largura}" padding="0 8px 18px">{_cartao_produto(t, p, ir)}</mj-column>'
                       for p in ps[i:i + colunas])
        linhas.append(f'<mj-section background-color="{fundo}" padding="8px 24px 0">{cols}</mj-section>')
    return "".join(linhas)


def _destaque_produto(t: _Tema, p: dict, c: dict, ir) -> str:
    """Imagem de um lado, texto do outro — o modelo «produto em destaque»."""
    if not p:
        return ""
    img = (f'<mj-image src="{_e(p["imagem"])}" alt="{_e(p.get("nome"))}" href="{_e(ir(p.get("url")))}" '
           f'padding="0" border-radius="8px" />' if _url(p.get("imagem")) else "")
    texto = (f'<mj-text font-size="13px" font-weight="700" color="{t.acento}" padding="0 0 6px" '
             f'text-transform="uppercase" letter-spacing="1px">{_e(c.get("subtitulo") or "Em destaque")}</mj-text>'
             f'<mj-text font-size="24px" font-weight="800" line-height="1.2" color="{t.primaria}" '
             f'font-family="{t.familia(True)}" padding="0 0 8px">{_e(p.get("nome"))}</mj-text>'
             + (f'<mj-text font-size="15px" line-height="1.5" color="{t.texto}" padding="0 0 8px">'
                f'{_e(p["descricao"])}</mj-text>' if p.get("descricao") else "")
             + (f'<mj-text font-size="22px" font-weight="800" color="{t.primaria}" padding="0 0 12px">'
                f'{_e(p["preco"])}</mj-text>' if p.get("preco") else "")
             + (f'<mj-button href="{_e(ir(p.get("url")))}" background-color="{t.acento}" color="{t.sobre_acento}" '
                f'font-weight="700" border-radius="6px" inner-padding="12px 24px" align="left" padding="0">'
                f'{_e(c.get("cta_texto") or "Ver produto")}</mj-button>' if _url(p.get("url")) else ""))
    return (f'<mj-section background-color="{t.suave}" padding="32px 24px">'
            f'<mj-column width="50%" padding="0 8px">{img}</mj-column>'
            f'<mj-column width="50%" padding="0 8px" vertical-align="middle">{texto}</mj-column></mj-section>')


def _itens_colunas(t: _Tema, itens: list, ir, fundo="#ffffff") -> str:
    """Três colunas com um número ou imagem pequena, título e texto: serviços, razões."""
    its = [i for i in itens or [] if i.get("titulo")][:3]
    if not its:
        return ""
    largura = f"{100 / len(its):.2f}%"
    cols = []
    for n, i in enumerate(its, 1):
        topo = (f'<mj-image src="{_e(i["imagem"])}" width="56px" alt="" padding="0 0 12px" />'
                if _url(i.get("imagem")) else
                f'<mj-text align="center" padding="0 0 10px"><span style="display:inline-block;width:44px;'
                f'height:44px;line-height:44px;border-radius:22px;background:{t.primaria};color:{t.sobre_primaria};'
                f'font-weight:700;font-size:18px;font-family:Arial,sans-serif">{n}</span></mj-text>')
        ligacao = (f'<mj-text align="center" font-size="14px" padding="8px 0 0"><a href="{_e(ir(i["url"]))}" '
                   f'style="color:{t.primaria};font-weight:700">Saber mais</a></mj-text>' if _url(i.get("url")) else "")
        cols.append(f'<mj-column width="{largura}" padding="0 10px 18px">{topo}'
                    f'<mj-text align="center" font-size="17px" font-weight="700" color="{t.primaria}" '
                    f'font-family="{t.familia(True)}" padding="0 0 6px">{_e(i["titulo"])}</mj-text>'
                    f'<mj-text align="center" font-size="14px" line-height="1.5" color="{t.texto}" padding="0">'
                    f'{_e(i.get("texto"))}</mj-text>{ligacao}</mj-column>')
    return f'<mj-section background-color="{fundo}" padding="18px 22px 8px">{"".join(cols)}</mj-section>'


def _lista_artigos(t: _Tema, itens: list, ir) -> str:
    """Imagem pequena à esquerda e resumo à direita, um por linha."""
    linhas = []
    for i in [i for i in itens or [] if i.get("titulo")][:5]:
        img = (f'<mj-column width="34%" padding="0 12px 0 0"><mj-image src="{_e(i["imagem"])}" alt="" '
               f'href="{_e(ir(i.get("url")))}" padding="0" border-radius="6px" /></mj-column>'
               if _url(i.get("imagem")) else "")
        largura = "66%" if img else "100%"
        ler = (f'<mj-text font-size="14px" padding="6px 0 0"><a href="{_e(ir(i["url"]))}" '
               f'style="color:{t.primaria};font-weight:700">Ler mais →</a></mj-text>' if _url(i.get("url")) else "")
        linhas.append(f'<mj-section background-color="#ffffff" padding="12px 32px">{img}'
                      f'<mj-column width="{largura}" vertical-align="middle">'
                      f'<mj-text font-size="17px" font-weight="700" color="{t.primaria}" padding="0 0 4px" '
                      f'font-family="{t.familia(True)}">{_e(i["titulo"])}</mj-text>'
                      f'<mj-text font-size="14px" line-height="1.5" color="{t.texto}" padding="0">'
                      f'{_e(i.get("texto"))}</mj-text>{ler}</mj-column></mj-section>')
    return "".join(linhas)


def _evento(t: _Tema, c: dict) -> str:
    ev = c.get("evento") or {}
    campos = [(r, ev.get(k)) for r, k in (("Data", "data"), ("Hora", "hora"), ("Local", "local")) if ev.get(k)]
    if not campos:
        return ""
    cols = "".join(f'<mj-column padding="0 8px"><mj-text align="center" font-size="12px" color="{t.sobre_primaria}" '
                   f'text-transform="uppercase" letter-spacing="1px" padding="0">{_e(r)}</mj-text>'
                   f'<mj-text align="center" font-size="19px" font-weight="700" color="{t.sobre_primaria}" '
                   f'padding="4px 0 0">{_e(v)}</mj-text></mj-column>' for r, v in campos)
    return f'<mj-section background-color="{t.primaria}" padding="24px 24px">{cols}</mj-section>'


def _assinatura(t: _Tema, c: dict) -> str:
    if not c.get("assinatura"):
        return ""
    return (f'<mj-section background-color="#ffffff" padding="4px 32px 24px"><mj-column>'
            f'<mj-text font-size="16px" line-height="1.5" color="{t.texto}" padding="0">'
            f'{_e(c["assinatura"]).replace(chr(10), "<br>")}</mj-text></mj-column></mj-section>')


_REDES = {"facebook": "Facebook", "instagram": "Instagram", "linkedin": "LinkedIn",
          "youtube": "YouTube", "tiktok": "TikTok", "x": "X", "pinterest": "Pinterest"}


def _rodape(t: _Tema, ident: dict, motivo: str, remover: str, legal_texto: str) -> str:
    redes = ident.get("redes") or {}
    ligacoes = " · ".join(f'<a href="{_e(u)}" style="color:{t.sobre_primaria};text-decoration:none">{n}</a>'
                          for k, n in _REDES.items() if _url(u := redes.get(k)))
    cont = ident.get("contactos") or {}
    contactos = " · ".join(_e(v) for v in (cont.get("telefone"), cont.get("email"), cont.get("site")) if v)
    # Sem redes nem contactos a faixa fica só como fecho de cor, fina.
    faixa = (f'<mj-section background-color="{t.primaria}" padding="26px 32px"><mj-column>'
             + (f'<mj-text align="center" font-size="14px" font-weight="700" color="{t.sobre_primaria}" '
                f'padding="0 0 8px">{ligacoes}</mj-text>' if ligacoes else "")
             + (f'<mj-text align="center" font-size="13px" color="{t.sobre_primaria}" padding="0">'
                f'{contactos}</mj-text>' if contactos else "")
             + '</mj-column></mj-section>') if (ligacoes or contactos) else (
        f'<mj-section background-color="{t.primaria}" padding="0"><mj-column>'
        f'<mj-spacer height="5px" /></mj-column></mj-section>')
    return (faixa +
            f'<mj-section padding="18px 32px 30px"><mj-column>'
            f'<mj-text align="center" font-size="12px" line-height="1.6" color="#7a7a7a" padding="0">'
            f'{_e(legal_texto).replace(chr(10), "<br>")}<br><br>{_e(motivo)} '
            f'<a href="{_e(remover)}" style="color:#7a7a7a;text-decoration:underline">Deixar de receber</a>.'
            f'</mj-text></mj-column></mj-section>')


# ── Os doze ────────────────────────────────────────────────────────────────

def _corpo(chave: str, t: _Tema, c: dict, ir) -> str:
    ps = c.get("produtos") or []
    if chave == "newsletter":
        return (_imagem_topo(t, c, ir) + _titulo(t, c) + _texto(t, c)
                + _lista_artigos(t, c.get("itens"), ir) + _botao(t, c, ir))
    if chave == "novidades":
        return (_titulo(t, c, 30, "center", t.suave) + _texto(t, c, t.suave)
                + _grelha(t, ps, ir, 3, t.suave) + _botao(t, c, ir, alinhar="center", fundo=t.suave))
    if chave == "promocao":
        return (_faixa(t, c) + _titulo(t, c, 24, "center") + _texto(t, c)
                + _grelha(t, ps, ir, 3) + _botao(t, c, ir, t.acento, "center"))
    if chave == "produto":
        return (_destaque_produto(t, ps[0] if ps else None, c, ir) + _titulo(t, c, 22) + _texto(t, c)
                + _grelha(t, ps[1:], ir, 3, maximo=3) + _botao(t, c, ir))
    if chave == "catalogo":
        return (_titulo(t, c, 26, "center") + _grelha(t, ps, ir, 2) + _botao(t, c, ir, alinhar="center"))
    if chave == "sazonal":
        return _imagem_topo(t, c, ir, com_texto=True) + _texto(t, c) + (
            "" if _url(c.get("imagem_topo")) else _titulo(t, c, 30, "center") + _botao(t, c, ir, alinhar="center"))
    if chave == "evento":
        return (_imagem_topo(t, c, ir) + _titulo(t, c, 28, "center") + _evento(t, c) + _texto(t, c)
                + _botao(t, c, ir, t.acento, "center"))
    if chave == "institucional":
        return _titulo(t, c, 24, cor=t.texto) + _texto(t, c) + _assinatura(t, c)
    if chave == "servicos":
        return (_titulo(t, c, 28, "center") + _itens_colunas(t, c.get("itens"), ir)
                + _botao(t, c, ir, alinhar="center"))
    if chave == "artigos":
        return _titulo(t, c) + _texto(t, c) + _lista_artigos(t, c.get("itens"), ir)
    if chave == "boas_vindas":
        return (_titulo(t, c, 30, "center", t.suave) + _texto(t, c, t.suave)
                + _itens_colunas(t, c.get("itens"), ir, t.suave) + _botao(t, c, ir, alinhar="center", fundo=t.suave))
    # relacao, e qualquer modelo desconhecido
    return _titulo(t, c, 24) + _texto(t, c) + _grelha(t, ps, ir, 3, maximo=3) + _botao(t, c, ir)


# ── O editor de blocos ────────────────────────────────────────────────────
#
# Os doze modelos são sequências fixas das peças acima. O editor deixa a
# sequência na mão de quem escreve — acrescentar, tirar, reordenar — sem lhe
# dar a paginação: cada bloco usa a mesma peça que os modelos, com as cores,
# fontes e logótipo da marca. Decisão do utilizador de 03-10-2026: blocos
# estruturados dentro da marca, não um editor livre de arrastar e largar.

def _paragrafos(texto) -> list:
    return [p.strip() for p in str(texto or "").split("\n\n") if p.strip()]


def _bloco(t: _Tema, b: dict, c: dict, ir) -> str:
    tipo = b.get("tipo")
    alinhar = "center" if b.get("alinhar") == "Centro" else "left"
    fundo = t.suave if b.get("fundo") == "Suave" else "#ffffff"
    ps = c.get("produtos") or []
    if tipo == "Título":
        return _titulo(t, {"titulo": b.get("titulo"), "subtitulo": b.get("subtitulo")}, 28, alinhar, fundo)
    if tipo == "Texto":
        return _texto(t, {"paragrafos": _paragrafos(b.get("texto"))}, fundo)
    if tipo == "Botão":
        cor = t.acento if b.get("cor_botao") == "Destaque" else None
        return _botao(t, {"cta_texto": b.get("botao_texto"), "cta_url": b.get("url")}, ir, cor, alinhar, fundo)
    if tipo == "Imagem":
        img = _url(b.get("imagem"))
        if not img:
            return ""
        ligar = f' href="{_e(ir(b["url"]))}"' if _url(b.get("url")) else ""
        return (f'<mj-section padding="0"><mj-column><mj-image src="{_e(img)}" alt=""{ligar} padding="0" '
                f'fluid-on-mobile="true" /></mj-column></mj-section>')
    if tipo == "Imagem com título":
        return _imagem_topo(t, {"imagem_topo": b.get("imagem"), "titulo": b.get("titulo"),
                                "subtitulo": b.get("subtitulo"), "cta_texto": b.get("botao_texto"),
                                "cta_url": b.get("url")}, ir, com_texto=True)
    if tipo == "Faixa de destaque":
        return _faixa(t, {"destaque": {"texto": b.get("titulo"), "subtexto": b.get("subtitulo")}})
    if tipo == "Produtos":
        colunas = 2 if str(b.get("colunas")) == "2" else 3
        return _grelha(t, ps, ir, colunas, fundo, int(b.get("maximo") or 6))
    if tipo == "Produto em destaque":
        return _destaque_produto(t, ps[0] if ps else None, {"cta_texto": b.get("botao_texto")}, ir)
    if tipo == "Vantagens em colunas":
        return _itens_colunas(t, c.get("itens"), ir, fundo)
    if tipo == "Lista de artigos":
        return _lista_artigos(t, c.get("itens"), ir)
    if tipo == "Evento":
        return _evento(t, c)
    if tipo == "Assinatura":
        return _assinatura(t, {"assinatura": b.get("texto")})
    if tipo == "Separador":
        return (f'<mj-section background-color="#ffffff" padding="8px 32px"><mj-column>'
                f'<mj-divider border-width="1px" border-color="#e3e3e3" padding="0" /></mj-column></mj-section>')
    if tipo == "Espaço":
        return ('<mj-section background-color="#ffffff" padding="0"><mj-column>'
                '<mj-spacer height="24px" /></mj-column></mj-section>')
    return ""


def blocos_do_modelo(chave: str, c: dict) -> list:
    """A sequência de um modelo como lista de blocos, cheia com o conteúdo que
    já existe — o ponto de partida do editor. Desenhada com estes blocos, a
    mensagem fica como o modelo, com pequenas diferenças de tamanho de letra."""
    tit = {"tipo": "Título", "titulo": c.get("titulo"), "subtitulo": c.get("subtitulo")}
    txt = {"tipo": "Texto", "texto": "\n\n".join(c.get("paragrafos") or [])}
    bot = {"tipo": "Botão", "botao_texto": c.get("cta_texto"), "url": c.get("cta_url")}
    img = {"tipo": "Imagem", "imagem": c.get("imagem_topo")}
    centro = {"alinhar": "Centro"}
    suave = {"fundo": "Suave"}
    seq = {
        "newsletter": [img, tit, txt, {"tipo": "Lista de artigos"}, bot],
        "novidades": [{**tit, **centro, **suave}, {**txt, **suave}, {"tipo": "Produtos", **suave}, {**bot, **centro, **suave}],
        "promocao": [{"tipo": "Faixa de destaque", "titulo": (c.get("destaque") or {}).get("texto"),
                      "subtitulo": (c.get("destaque") or {}).get("subtexto")},
                     {**tit, **centro}, txt, {"tipo": "Produtos"}, {**bot, **centro, "cor_botao": "Destaque"}],
        "produto": [{"tipo": "Produto em destaque", "botao_texto": c.get("cta_texto")}, tit, txt, {"tipo": "Produtos", "maximo": 3}, bot],
        "catalogo": [{**tit, **centro}, {"tipo": "Produtos", "colunas": "2"}, {**bot, **centro}],
        "sazonal": [{"tipo": "Imagem com título", "imagem": c.get("imagem_topo"), "titulo": c.get("titulo"),
                     "subtitulo": c.get("subtitulo"), "botao_texto": c.get("cta_texto"), "url": c.get("cta_url")}, txt],
        "evento": [img, {**tit, **centro}, {"tipo": "Evento"}, txt, {**bot, **centro, "cor_botao": "Destaque"}],
        "institucional": [tit, txt, {"tipo": "Assinatura", "texto": c.get("assinatura")}],
        "servicos": [{**tit, **centro}, {"tipo": "Vantagens em colunas"}, {**bot, **centro}],
        "artigos": [tit, txt, {"tipo": "Lista de artigos"}],
        "boas_vindas": [{**tit, **centro, **suave}, {**txt, **suave}, {"tipo": "Vantagens em colunas", **suave}, {**bot, **centro, **suave}],
    }.get(chave) or [tit, txt, {"tipo": "Produtos", "maximo": 3}, bot]
    return [{k: v for k, v in b.items() if v not in (None, "")} for b in seq]


def gerar(conteudo: dict, ident: dict, *, ir: Callable[[str], str], remover: str, motivo: str,
          legal_texto: str, pixel: Optional[str] = None, assunto: str = "",
          pre_cabecalho: str = "") -> str:
    """O HTML final da mensagem. `ir` transforma cada endereço no que é medido."""
    from mjml import mjml2html
    t = _Tema(ident)
    chave = conteudo.get("modelo") if conteudo.get("modelo") in MODELOS else "relacao"
    fontes = "".join(
        f'<mj-font name="{_e(f)}" href="https://fonts.googleapis.com/css2?family={_e(f).replace(" ", "+")}:wght@400;700&amp;display=swap" />'
        for f in {x for x in (t.fonte_titulos, t.fonte_texto) if x})
    fonte = t.familia()
    rastos = f'<mj-raw><img src="{_e(pixel)}" width="1" height="1" alt="" style="display:block;border:0" /></mj-raw>' if pixel else ""
    fonte_mjml = (
        f'<mjml lang="pt"><mj-head><mj-title>{_e(assunto)}</mj-title>'
        f'<mj-preview>{_e(pre_cabecalho)}</mj-preview>{fontes}'
        f'<mj-attributes><mj-all font-family="{fonte}" /><mj-text color="{t.texto}" />'
        f'<mj-section text-align="left" /></mj-attributes>'
        f'<mj-style>a {{ color: {t.primaria}; }} @media (max-width:480px) {{ .mj-column-per-50 {{ width:100% !important; }} }}</mj-style>'
        f'</mj-head><mj-body background-color="{t.fundo_pagina}" width="620px">'
        f'<mj-wrapper padding="20px 0" background-color="{t.fundo_pagina}">'
        + _cabecalho(t, ir)
        + ("".join(_bloco(t, b, conteudo, ir) for b in conteudo["blocos"]) if conteudo.get("blocos")
           else _corpo(chave, t, conteudo, ir))
        + _rodape(t, ident, motivo, remover, legal_texto)
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


def exemplo(chave: str) -> dict:
    """Conteúdo de exemplo para mostrar um modelo antes de haver texto."""
    produtos = [{"nome": f"Produto {n}", "preco": f"{19 + n * 10},90 €", "url": "https://exemplo.pt/p",
                 "descricao": "Descrição curta do produto."} for n in range(1, 7)]
    itens = [{"titulo": t, "texto": "Uma frase que explica a vantagem.", "url": "https://exemplo.pt/s"}
             for t in ("Rapidez", "Qualidade", "Apoio")]
    return {"modelo": chave, "titulo": MODELOS[chave]["nome"], "subtitulo": MODELOS[chave]["para"].capitalize(),
            "paragrafos": ["{{nome}}, este é um texto de exemplo para mostrar o modelo.",
                           "Na campanha a sério, este texto é escrito para a ocasião."],
            "cta_texto": "Ver mais", "cta_url": "https://exemplo.pt", "produtos": produtos, "itens": itens,
            "destaque": {"texto": "−30%", "subtexto": "Só este mês"},
            "evento": {"data": "15 de Novembro", "hora": "18h30", "local": "Lisboa"},
            "assinatura": "Com os melhores cumprimentos,\nA equipa"}


# Os nomes que o utilizador escolhe no Orbit → as chaves dos modelos.
POR_NOME = {m["nome"]: k for k, m in MODELOS.items()}
POR_NOME.update({"Comunicado": "institucional"})
