"""Montagem do feed do importador — porte fiel do portal para Python puro.

21-11-2026, F5.2 do docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md (§12): o que
acontece DEPOIS da normalização — item do feed por produto, documentos
alojados, fusão por EAN e por referência entre fornecedores (conteúdo do mais
rico, parte comercial do mais barato com stock) e relacionados (matnr ou
recurso por categoria/marca/preço).

Origem: portal `app/routers/importador.py`, `_gerar_feed_para_conta_sync`
(~6208–6580) e auxiliares: `_obter_definicoes_globais`/`_resolver_publicacao`
(~228–270), `_custo_numerico`/`_ha_stock` (~5672–5745),
`_sem_ligacoes_para_fora` (~5749–5772), `_construir_item_feed` (~5774–5952),
`_nucleo_ean`, `CAMPOS_COMERCIAIS_FUSAO`, `_mesma_marca`, `_riqueza_dados`,
`_fundir_grupo`, `_aplicar_precedencia_entre_fornecedores` (~5957–6190),
`_mapa_documentos_alojados`/`_documentos_publicaveis`/`TIPOS_DOCUMENTO_PT`
(~6871–6915). Cada bloco cita a linha de origem («portal ~NNNN»). Só
biblioteca-padrão; nada de frappe nem sqlalchemy.

Devolve só a lista `produtos` de uma passagem completa sem filtros —
`_gerar_feed_para_conta_sync(db, conta, None, None, conta={})["produtos"]`.
O invólucro (nome da conta, `definicoes_atributos`, listas dos selectores,
pesquisa/paginação do /preview-feed) fica de fora.

Forma das entradas
------------------

`produtos`: lista de dicts, uma por linha de `importador_produtos_normalizados`
dos fornecedores da conta (pode trazer fornecedores que não vão ao feed — são
ignorados aqui, como no `WHERE` do portal ~6261). Colunas lidas:

    fornecedor_id (int), produto_ref (str), ean, mpn (str|None),
    dados (dict), campos_personalizados, atributos, atributos_locais,
    atributos_variacao, campos_confirmados_ia (dict|None),
    documentos, categorias_loja, categorias_loja_ids, tags_loja,
    pendente_ia (list|None), categoria_valor, produto_pai_ref,
    tipo_fornecimento, prazo_entrega, transporte, origem_stock (str|None),
    preco_pvp, preco_regular, preco_promocional (Decimal|float|str|None),
    preco_congelado (bool),
    actualizado_em, dados_actualizado_em (datetime — sai `.isoformat()` —
        ou texto já em ISO, que passa como está; None → None)

    ORDEM: a lista tem de vir pela ordem de `ORDER BY produto_ref` da base de
    origem (no portal, collation en_US.utf8 — diferente da ordem do Python).
    O feed não reordena: a ordem decide a ordem de saída, o «último ganha» de
    um `_matnr_interno` repetido e os empates da fusão (dois fornecedores com
    a mesma prioridade e a mesma riqueza de dados — fica o primeiro). O índice
    dos relacionados (portal ~6329, `ORDER BY fornecedor_id, produto_ref`)
    obtém-se daqui com uma ordenação estável por fornecedor_id.

`fornecedores`: {fornecedor_id: {"nome": str, "estado": str, "na_loja": bool,
    "prioridade": int|None, "config": dict|None}} — todos os da conta; entram
    no feed os que têm estado <> 'inactivo' e na_loja (portal ~6236).

`definicoes`: a linha de `importador_definicoes_conta` da conta (só se lêem
    estado_publicacao_default, publicar_sem_imagem_default,
    estado_stock_zero_default; o que faltar vale o `_FALLBACK` do portal), mais:
      "documentos_alojados": [(fornecedor_id, url_origem, url_local), ...] —
          as linhas de `importador_documentos_alojados` com estado = 'ok'
          (portal ~6871; filtra-se aqui pelos fornecedores com produtos);
      "portal_base_url": o PORTAL_BASE_URL do portal (omissão
          "https://portal.stratechna.com"), para completar os documentos já
          alojados no portal.

`agora`: hora da passagem. A lista `produtos` do portal não depende da hora
    (só o invólucro tem `gerado_em`); fica na assinatura para o chamador do
    Orbit e para quando a frescura do stock entrar (F5.2+).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from .motor import _como_lista, _sem_acentos_minusculas

# ── Definições de publicação (portal ~228–270) ──────────────────────────────
_DEFINICOES_GLOBAIS_FALLBACK = {
    "estado_publicacao_default": "publicado",
    "publicar_sem_imagem_default": False,
    "estado_stock_zero_default": "sob_encomenda",
    "usar_pvp_recomendado": False,
    "atributos_so_activos": False,
}

PORTAL_BASE_URL = "https://portal.stratechna.com"  # portal ~7331 (os.getenv no portal)


def _resolver_publicacao(config_fornecedor: dict, globais: dict) -> dict:
    # portal ~252: cascata fornecedor -> conta -> fallback fixo
    pub = (config_fornecedor or {}).get("publicacao") or {}
    estado_publicacao = pub.get("estado_publicacao") or globais.get(
        "estado_publicacao_default", _DEFINICOES_GLOBAIS_FALLBACK["estado_publicacao_default"]
    )
    publicar_sem_imagem = pub.get("publicar_sem_imagem")
    if publicar_sem_imagem is None:
        publicar_sem_imagem = globais.get(
            "publicar_sem_imagem_default", _DEFINICOES_GLOBAIS_FALLBACK["publicar_sem_imagem_default"]
        )
    estado_stock_zero = pub.get("estado_stock_zero") or globais.get(
        "estado_stock_zero_default", _DEFINICOES_GLOBAIS_FALLBACK["estado_stock_zero_default"]
    )
    return {
        "estado_publicacao": estado_publicacao,
        "publicar_sem_imagem": bool(publicar_sem_imagem),
        "estado_stock_zero": estado_stock_zero,
    }


# ── Stock (portal ~5672–5745) ───────────────────────────────────────────────
def _custo_numerico(item: dict) -> Optional[float]:
    # portal ~5672
    v = item.get("custo")
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


_ROTULOS_SEM_STOCK = (
    "indisponivel", "nao disponivel", "sem stock", "esgotado", "fora de stock", "sob consulta",
    "consulta", "encomenda", "out of stock", "unavailable", "not available", "upon request", "agotado", "sin stock",
)
_ROTULOS_COM_STOCK = (
    "em stock", "disponivel", "stock limitado", "stock disponivel", "com stock",
    "in stock", "available", "delivery from stock", "en stock", "disponible",
)


def _ha_stock(valor):
    """Há stock? True / False / None (desconhecido). portal ~5692.

    Número puro → > 0; texto com números → soma do 1.º número de cada parte
    separada por | ; / («Lisboa: 10-99 | Porto: 5» = 15); texto sem números →
    rótulos negativos primeiro, depois afirmativos, o resto é «nada»; vazio
    ou None → desconhecido (o feed trata-o como em stock)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto == "":
        return None
    try:
        return float(texto.replace(",", ".")) > 0
    except (TypeError, ValueError):
        pass
    numeros = re.findall(r"\d+(?:[.,]\d+)?", texto)
    if not numeros:
        rotulo = _sem_acentos_minusculas(texto)
        if any(t in rotulo for t in _ROTULOS_SEM_STOCK):
            return False
        if any(t in rotulo for t in _ROTULOS_COM_STOCK):
            return True
        return False
    total = 0.0
    for parte in re.split(r"[|;/]", texto):
        ns = re.findall(r"\d+(?:[.,]\d+)?", parte)
        if ns:
            total += float(ns[0].replace(",", "."))
    return total > 0


# ── Descrições sem ligações para fora (portal ~5749–5772) ───────────────────
_LIGACOES_PERMITIDAS = ("youtube.com", "youtu.be", "stratechna.com", "stratechna.pt")
_RE_LI_LIGACAO = re.compile(r"<li\b[^>]*>\s*<a\b[^>]*href=[\"'](https?://[^\"']+)[\"'][^>]*>.*?</a>\s*</li>", re.S | re.I)
_RE_LIGACAO = re.compile(r"<a\b[^>]*href=[\"'](https?://[^\"']+)[\"'][^>]*>(.*?)</a>", re.S | re.I)
_RE_LISTA_VAZIA = re.compile(r"<ul\b[^>]*>\s*(?:<li\b[^>]*>\s*</li>\s*)*</ul>|<li\b[^>]*>\s*</li>", re.S | re.I)


def _ligacao_permitida(url: str) -> bool:
    h = (urlparse(url).hostname or "").lower()
    return any(h == d or h.endswith("." + d) for d in _LIGACOES_PERMITIDAS)


def _sem_ligacoes_para_fora(html: Optional[str]) -> Optional[str]:
    if not html or "href" not in html:
        return html
    novo = _RE_LI_LIGACAO.sub(lambda m: m.group(0) if _ligacao_permitida(m.group(1)) else "", html)
    novo = _RE_LIGACAO.sub(lambda m: m.group(0) if _ligacao_permitida(m.group(1)) else m.group(2), novo)
    while True:
        seguinte = _RE_LISTA_VAZIA.sub("", novo)
        if seguinte == novo:
            break
        novo = seguinte
    return novo.strip() if novo != html else html


def _iso(v: Any) -> Optional[str]:
    # portal: `p["actualizado_em"].isoformat() if p["actualizado_em"] else None`
    if not v:
        return None
    return v.isoformat() if isinstance(v, datetime) else str(v)


def _float(v: Any) -> Optional[float]:
    # portal: `float(p["preco_x"]) if p["preco_x"] is not None else None` (numeric → Decimal)
    return float(v) if v is not None else None


# ── Item do feed (portal ~5774–5952) ────────────────────────────────────────
def _construir_item_feed(p: dict, pub: dict) -> dict:
    dados = p.get("dados") or {}
    item = {
        "fornecedor_id": p["fornecedor_id"],
        "fornecedor_nome": p["fornecedor_nome"],
        "ref": p["produto_ref"],
        "ean": p.get("ean"),
        "mpn": p.get("mpn"),
        "titulo": dados.get("titulo"),
        "descricao_curta": _sem_ligacoes_para_fora(dados.get("descricao_curta")),
        "descricao": _sem_ligacoes_para_fora(dados.get("descricao")),
        "custo": dados.get("custo"),
        # portal ~5795: sem Preço Base quando o custo sai do preço de venda
        "preco_base": None if dados.get("custo_de_venda") else dados.get("preco_base", dados.get("custo")),
        "preco_base_venda": dados.get("preco_base_venda"),
        "marca": dados.get("marca"),
        "stock": dados.get("stock"),
        "peso": dados.get("peso"),
        "medidas_rever": dados.get("medidas_rever") or [],
        "dimensoes": dados.get("dimensoes"),
        "comprimento": dados.get("comprimento"),
        "largura": dados.get("largura"),
        "altura": dados.get("altura"),
        "imagem_url": dados.get("imagem_url"),
        "imagens_secundarias": _como_lista(dados.get("imagens_secundarias")),
        "especificacoes": dados.get("especificacoes") or [],
        "o_que_vem_na_caixa": dados.get("o_que_vem_na_caixa"),
        "produto_pai_ref": p.get("produto_pai_ref"),
        "atributos_variacao": p.get("atributos_variacao") or {},
        "tipo_fornecimento": p.get("tipo_fornecimento"),
        "prazo_entrega": p.get("prazo_entrega"),
        "transporte": p.get("transporte"),
        "origem_stock": p.get("origem_stock"),
        "campos_personalizados": p.get("campos_personalizados") or {},
        "atributos": p.get("atributos") or {},
        "atributos_locais": p.get("atributos_locais") or {},
        "documentos": p.get("documentos") or [],
        "categorias_loja": p.get("categorias_loja") or [],
        "categorias_loja_ids": p.get("categorias_loja_ids") or [],
        "tags_loja": p.get("tags_loja") or [],
        "categoria_confirmada_ia": bool((p.get("campos_confirmados_ia") or {}).get("categoria")),
        "campos_confirmados_ia": p.get("campos_confirmados_ia") or {},
        # interno: categoria de origem para o recurso dos relacionados (sai no fim)
        "_categoria_valor_tmp": p.get("categoria_valor"),
        "preco_pvp": _float(p.get("preco_pvp")),
        "preco_regular": _float(p.get("preco_regular")),
        "preco_promocional": _float(p.get("preco_promocional")),
        "preco_congelado": p.get("preco_congelado"),
        "pendente_ia": p.get("pendente_ia") or [],
        "actualizado_em": _iso(p.get("actualizado_em")),
        "dados_actualizado_em": _iso(p.get("dados_actualizado_em")),
    }
    # portal ~5847: hora da última mexida nas imagens, só quando existe
    if dados.get("imagens_corrigidas_em"):
        item["imagens_corrigidas_em"] = dados["imagens_corrigidas_em"]

    # portal ~5853: relacionados em bruto (matnr), resolvidos no fim
    item["_matnr_interno_tmp"] = dados.get("_matnr_interno")
    item["_crosssell_matnr_tmp"] = dados.get("relacionados_crosssell") or []
    item["_upsell_matnr_tmp"] = dados.get("relacionados_upsell") or []

    # portal ~5865: publicação — sem imagem (e sem licença para isso) = rascunho
    tem_imagem = bool(item["imagem_url"])
    try:
        preco_valido = item["preco_regular"] is not None and float(item["preco_regular"]) > 0
    except (TypeError, ValueError):
        preco_valido = False
    if not tem_imagem and not pub.get("publicar_sem_imagem"):
        item["estado_publicacao"] = "rascunho"
    else:
        item["estado_publicacao"] = pub.get("estado_publicacao", "publicado")
    item["preco_sob_consulta"] = not preco_valido
    tem_stock = _ha_stock(item["stock"])
    # portal ~5893: sem quantidade, manda o que o fornecedor diz da disponibilidade
    _disponib = _sem_acentos_minusculas(str(item.get("tipo_fornecimento") or ""))
    so_por_encomenda = any(t in _disponib for t in ("encomenda", "order", "request", "pedido"))
    if "delivery from stock" in _disponib or "em stock" in _disponib:
        so_por_encomenda = False
    if not preco_valido:
        item["estado_stock"] = "sob_encomenda"
    elif tem_stock is None and so_por_encomenda:
        item["estado_stock"] = "sob_encomenda"
    elif tem_stock is None or tem_stock:
        item["estado_stock"] = "instock"
    else:
        item["estado_stock"] = pub.get("estado_stock_zero", "sob_encomenda")

    # portal ~5912: código morto no portal — o item nunca tem «ausente_desde»
    # (não está entre as chaves acima). Portado como está para não divergir;
    # ver a nota da §12 do plano.
    if item.get("ausente_desde"):
        item["estado_stock"] = "esgotado"
        item["fora_do_feed"] = True

    # portal ~5924: estado e prazo que o produto teria COM preço válido
    if item.get("ausente_desde"):
        estado_com_preco = "esgotado"
    elif tem_stock is None and so_por_encomenda:
        estado_com_preco = "sob_encomenda"
    elif tem_stock is None or tem_stock:
        estado_com_preco = "instock"
    else:
        estado_com_preco = pub.get("estado_stock_zero", "sob_encomenda")
    item["estado_stock_com_preco"] = estado_com_preco
    item["prazo_entrega_com_preco"] = item.get("prazo_entrega") if estado_com_preco == "instock" else None

    # portal ~5942: prazo só com stock
    if item["estado_stock"] != "instock":
        item["prazo_entrega"] = None

    # portal ~5947: data de reposição só a quem não pode comprar agora
    data_rep = (dados.get("data_reposicao") or "").strip() if isinstance(dados.get("data_reposicao"), str) else None
    item["data_reposicao"] = data_rep if (data_rep and item["estado_stock"] != "instock") else None
    return item


# ── Documentos alojados (portal ~6871–6915) ─────────────────────────────────
TIPOS_DOCUMENTO_PT = {
    "data sheet": "Ficha Técnica", "datasheet": "Ficha Técnica", "technical sheet": "Ficha Técnica",
    "ficha tecnica": "Ficha Técnica", "ficha técnica": "Ficha Técnica", "scheda tecnica": "Ficha Técnica",
    "installation manual": "Manual de Instalação", "manual de instalacion": "Manual de Instalação",
    "manual de instalación": "Manual de Instalação", "user manual": "Manual de Utilização",
    "manual de usuario": "Manual de Utilização", "manual de uso": "Manual de Utilização",
    "manuale d'uso": "Manual de Utilização", "exploded view": "Vista Explodida",
    "despiece": "Vista Explodida", "spare parts": "Peças de Substituição",
    "documento reciclaje": "Documento de Reciclagem", "catalogue": "Catálogo", "brochure": "Catálogo",
    "declaration of conformity": "Declaração de Conformidade",
}


def _mapa_documentos_alojados(alojados: Iterable, fornecedor_ids: Iterable[int]) -> Dict[str, str]:
    # portal ~6871: SELECT url_origem, url_local ... estado='ok' AND fornecedor_id = ANY(:ids)
    ids = set(fornecedor_ids)
    if not ids:
        return {}
    return {url_origem: url_local for (fid, url_origem, url_local) in (alojados or []) if fid in ids}


def _documentos_publicaveis(documentos, mapa: Dict[str, str], portal_base_url: str) -> list:
    # portal ~6882: troca o URL de origem pela cópia alojada; sem cópia, sai
    saida = []
    for d in documentos or []:
        if not isinstance(d, dict):
            continue
        url = (d.get("url") or "").strip()
        if not url:
            continue
        if url.startswith("/api/v1/importador/docs/"):
            saida.append({**d, "url": f"{portal_base_url}{url}"})
        elif url.startswith(f"{portal_base_url}/api/v1/importador/docs/"):
            saida.append(d)
        elif url in mapa:
            saida.append({**d, "url": mapa[url], "url_origem": url,
                          "tipo": TIPOS_DOCUMENTO_PT.get((d.get("tipo") or "").strip().lower(), d.get("tipo"))})
    return saida


# ── Fusão entre fornecedores (portal ~5957–6190) ────────────────────────────
LIMITE_RELACIONADOS_RECURSO = 4  # portal ~5957


def _nucleo_ean(valor) -> str:
    """Só os dígitos, sem zeros à cabeça nem à cauda (portal ~5960): a Depau
    publica 952050695630 onde a TD SYNNEX publica 095205069563."""
    digitos = "".join(c for c in str(valor or "") if c.isdigit())
    return digitos.strip("0")


# portal ~5971: o que acompanha o fornecedor mais barato na fusão
CAMPOS_COMERCIAIS_FUSAO = (
    "fornecedor_id", "fornecedor_nome", "ref", "custo", "preco_base", "stock",
    "preco_pvp", "preco_regular", "preco_promocional", "preco_congelado",
    "estado_stock", "estado_stock_com_preco", "prazo_entrega", "prazo_entrega_com_preco",
    "data_reposicao", "tipo_fornecimento", "origem_stock", "transporte",
)


def _marca_normalizada(valor) -> str:
    return re.sub(r"[^a-z0-9]", "", str(valor or "").lower())


def _mesma_marca(itens: list) -> bool:
    # portal ~5983: todas com marca, uma começa pela outra («HP» / «HP INC»)
    marcas = [_marca_normalizada(i.get("marca")) for i in itens]
    if not all(marcas):
        return False
    curta = min(marcas, key=len)
    return len(curta) >= 2 and all(m.startswith(curta) for m in marcas)


def _riqueza_dados(item: dict) -> float:
    # portal ~6052: imagem > galeria > texto > atributos/documentos > marca
    def _txt(v):
        return len(re.sub(r"<[^>]+>", "", v)) if isinstance(v, str) else 0
    pontos = 1000.0 if item.get("imagem_url") else 0.0
    galeria = item.get("imagens_secundarias")
    pontos += 100 * (len(galeria) if isinstance(galeria, list) else 0)
    pontos += min(_txt(item.get("descricao")), 5000) / 5
    pontos += min(_txt(item.get("descricao_curta")), 1000) / 5
    pontos += 20 * (len(item.get("atributos") or {}) + len(item.get("atributos_locais") or {}))
    pontos += 50 * len(item.get("documentos") or [])
    pontos += 50 if item.get("marca") else 0
    return pontos


def _fundir_grupo(itens: list, prioridade_por_fornecedor: Dict[int, int], exigir_ean_igual: bool = False) -> list:
    """portal ~6068: uma só linha quando a fusão é de confiança, senão todas."""
    if len(itens) == 1:
        return itens
    # portal ~6084: chave repetida dentro do MESMO fornecedor não funde (Tefcold)
    por_fornecedor: Dict[int, int] = {}
    for item in itens:
        por_fornecedor[item["fornecedor_id"]] = por_fornecedor.get(item["fornecedor_id"], 0) + 1
    if any(n > 1 for n in por_fornecedor.values()):
        return itens
    if exigir_ean_igual:
        # portal ~6089: pela referência só com EAN que confirme ou a mesma marca
        nucleos = {n for n in (_nucleo_ean(i.get("ean")) for i in itens) if n}
        ean_confirma = len(nucleos) == 1 and all((i.get("ean") or "").strip() for i in itens)
        if not ean_confirma and not _mesma_marca(itens):
            return itens

    def _prioridade(i):
        return prioridade_por_fornecedor.get(i["fornecedor_id"], 999999)
    # portal ~6113: conteúdo do mais rico; a prioridade só desempata
    base = max(itens, key=lambda i: (_riqueza_dados(i), -_prioridade(i)))

    # portal ~6119: parte comercial do mais barato com stock; sem stock, o mais barato
    def _mais_barato(candidatos):
        melhor, custo_melhor = None, None
        for item in sorted(candidatos, key=_prioridade):
            c = _custo_numerico(item)
            if c is not None and (custo_melhor is None or c < custo_melhor):
                melhor, custo_melhor = item, c
        return melhor
    com_stock = [i for i in itens if i.get("estado_stock") == "instock"]
    mais_barato = _mais_barato(com_stock) or _mais_barato(itens) or base

    vencedor = dict(base)
    if mais_barato is not base:
        for campo in CAMPOS_COMERCIAIS_FUSAO:
            if campo in mais_barato:
                vencedor[campo] = mais_barato[campo]
        vencedor["dados_de_fornecedor_id"] = base["fornecedor_id"]
        vencedor["dados_de_fornecedor_nome"] = base["fornecedor_nome"]
    # portal ~6136: identidades absorvidas ficam na linha que sobrevive
    absorvidos = list(vencedor.get("fundidos") or [])
    for i in itens:
        for identidade in ([{"fornecedor_id": i["fornecedor_id"], "ref": i["ref"]}]
                           + list(i.get("fundidos") or [])):
            if (identidade["fornecedor_id"] != vencedor["fornecedor_id"]
                    or identidade["ref"] != vencedor["ref"]):
                if identidade not in absorvidos:
                    absorvidos.append(identidade)
    vencedor["fundidos"] = absorvidos
    return [vencedor]


def _aplicar_precedencia_entre_fornecedores(produtos: list, prioridade_por_fornecedor: Dict[int, int]) -> list:
    """portal ~6154: duas passagens — por EAN e depois pela referência (esta
    só funde com EAN que confirme ou a mesma marca). Linhas sem chave seguem
    à frente, pela ordem em que vieram; depois os grupos, pela ordem da 1.ª
    aparição de cada chave."""
    def agrupar(itens: list, chave, exigir_ean_igual: bool = False) -> list:
        grupos: Dict[str, list] = {}
        soltos: list = []
        for item in itens:
            k = chave(item)
            if not k:
                soltos.append(item)
                continue
            grupos.setdefault(k, []).append(item)
        saida = list(soltos)
        for grupo in grupos.values():
            saida.extend(_fundir_grupo(grupo, prioridade_por_fornecedor, exigir_ean_igual))
        return saida

    por_ean = agrupar(produtos, lambda i: (i.get("ean") or "").strip())
    return agrupar(por_ean, lambda i: (i.get("ref") or "").strip(), exigir_ean_igual=True)


# ── Feed completo (portal ~6208–6580) ───────────────────────────────────────
def fornecedores_do_feed(fornecedores: Dict[int, dict]) -> List[int]:
    """Ids dos fornecedores que vão ao feed, pela ordem do portal ~6236
    (`ORDER BY COALESCE(prioridade, 999999), nome` — o nome compara-se aqui
    com a ordem do Python; só desempata a lista de fornecedores, que não
    mexe na lista de produtos)."""
    ids = [fid for fid, f in fornecedores.items()
           if (f.get("estado") or "") != "inactivo" and f.get("na_loja")]
    ids.sort(key=lambda fid: (fornecedores[fid].get("prioridade") if fornecedores[fid].get("prioridade") is not None
                              else 999999, fornecedores[fid].get("nome") or ""))
    return ids


def gerar_feed(produtos: List[dict], fornecedores: Dict[int, dict], definicoes: dict, *,
               agora: Optional[datetime] = None) -> List[dict]:
    """A lista `produtos` do feed da conta (ver a docstring do módulo)."""
    definicoes = definicoes or {}
    ids = fornecedores_do_feed(fornecedores)
    if not ids:
        return []  # portal ~6252
    ids_set = set(ids)
    # portal ~6244: publicação resolvida por fornecedor
    publicacao_por_fornecedor = {fid: _resolver_publicacao(fornecedores[fid].get("config") or {}, definicoes)
                                 for fid in ids}

    # portal ~6261: linhas dos fornecedores do feed, pela ordem dada (ORDER BY produto_ref)
    linhas = [p for p in produtos if p["fornecedor_id"] in ids_set]

    itens = []
    for p in linhas:
        p = dict(p, fornecedor_nome=fornecedores[p["fornecedor_id"]].get("nome"))
        itens.append(_construir_item_feed(p, publicacao_por_fornecedor.get(p["fornecedor_id"], {})))
    # portal ~6292: só documentos com cópia no portal
    mapa_docs = _mapa_documentos_alojados(definicoes.get("documentos_alojados"), {i["fornecedor_id"] for i in itens})
    base_url = definicoes.get("portal_base_url") or PORTAL_BASE_URL
    for item in itens:
        item["documentos"] = _documentos_publicaveis(item.get("documentos"), mapa_docs, base_url)

    prioridade_por_fornecedor = {fid: (fornecedores[fid].get("prioridade")
                                       if fornecedores[fid].get("prioridade") is not None else 999999)
                                 for fid in ids}
    itens = _aplicar_precedencia_entre_fornecedores(itens, prioridade_por_fornecedor)

    # portal ~6329: índice do catálogo inteiro (ORDER BY fornecedor_id, produto_ref)
    # — ordenação estável por fornecedor da lista que já vem por produto_ref.
    indice_rows = []
    for p in sorted(linhas, key=lambda r: r["fornecedor_id"]):
        dados = p.get("dados") or {}
        matnr = dados.get("_matnr_interno")
        marca = dados.get("marca")
        indice_rows.append({
            "fornecedor_id": p["fornecedor_id"],
            "produto_ref": p["produto_ref"],
            # `dados->>'chave'` devolve texto (ou NULL para JSON null / ausente)
            "matnr": _texto_json(matnr),
            "categoria_valor": p.get("categoria_valor"),
            "categorias_loja_ids": p.get("categorias_loja_ids"),
            "marca": _texto_json(marca),
            "preco_pvp": p.get("preco_pvp"),
        })

    matnr_por_fornecedor: Dict[int, Dict[str, str]] = {}
    refs_por_fornecedor: Dict[int, set] = {}
    for r in indice_rows:
        fid = r["fornecedor_id"]
        if r["matnr"]:
            matnr_por_fornecedor.setdefault(fid, {})[str(r["matnr"])] = r["produto_ref"]
        refs_por_fornecedor.setdefault(fid, set()).add(r["produto_ref"])
    for it in itens:
        it.pop("_matnr_interno_tmp", None)

    def _resolver_relacionado(fid: int, valor: str) -> Optional[str]:
        # portal ~6347: primeiro o matnr, depois o próprio produto_ref
        tabela = matnr_por_fornecedor.get(fid, {})
        if valor in tabela:
            return tabela[valor]
        if valor in refs_por_fornecedor.get(fid, set()):
            return valor
        return None

    # portal ~6360: relacionados dados pelo fornecedor, só dentro do mesmo fornecedor
    for it in itens:
        crosssell_matnr = it.pop("_crosssell_matnr_tmp", [])
        upsell_matnr = it.pop("_upsell_matnr_tmp", [])
        item_ref = it["ref"]
        it["cross_sell_refs"] = [
            r for m in crosssell_matnr
            for r in [_resolver_relacionado(it["fornecedor_id"], m)]
            if r and r != item_ref
        ]
        it["upsell_refs"] = [
            r for m in upsell_matnr
            for r in [_resolver_relacionado(it["fornecedor_id"], m)]
            if r and r != item_ref
        ]

    # portal ~6410: recurso por categoria (da loja ∩ do fornecedor), marca e preço
    _por_categoria_loja: Dict[tuple, list] = {}
    _por_categoria: Dict[tuple, list] = {}
    for r in indice_rows:
        for cid in (r["categorias_loja_ids"] or []):
            _por_categoria_loja.setdefault((r["fornecedor_id"], str(cid)), []).append(r)
        if r["categoria_valor"]:
            _por_categoria.setdefault((r["fornecedor_id"], r["categoria_valor"]), []).append(r)

    def _candidatos_de(it) -> list:
        # portal ~6418
        fid = it["fornecedor_id"]
        ids_loja = {str(c) for c in (it.get("categorias_loja_ids") or [])}
        cat_forn = it.get("_categoria_valor_tmp")
        do_fornecedor = _por_categoria.get((fid, cat_forn), []) if cat_forn else []
        if not ids_loja:
            return list(do_fornecedor)
        vistos: Dict[str, dict] = {}
        partilha: Dict[str, int] = {}
        for cid in sorted(ids_loja):
            for c in _por_categoria_loja.get((fid, cid), []):
                ref = c["produto_ref"]
                vistos[ref] = c
                partilha[ref] = partilha.get(ref, 0) + 1
        if not vistos:
            return list(do_fornecedor)
        refs_forn = {c["produto_ref"] for c in do_fornecedor}
        if refs_forn:
            ambas = [r for r in vistos if r in refs_forn]
            if ambas:
                ambas.sort(key=lambda r: (-partilha[r], r))
                return [vistos[r] for r in ambas]
        return [vistos[r] for r in sorted(partilha, key=lambda r: (-partilha[r], r))]

    def _preco(r) -> Optional[float]:
        try:
            return float(r["preco_pvp"]) if r["preco_pvp"] is not None else None
        except (TypeError, ValueError):
            return None

    for it in itens:
        # portal ~6475
        if it["cross_sell_refs"] and it["upsell_refs"]:
            continue
        candidatos = _candidatos_de(it)
        if not candidatos or len(candidatos) < 2:
            continue
        marca_it = (it.get("marca") or "").strip().lower()
        try:
            preco_it = float(it.get("preco_regular")) if it.get("preco_regular") is not None else None
        except (TypeError, ValueError):
            preco_it = None

        if not it["cross_sell_refs"]:
            # cross-sell: mesma categoria, marca diferente, preço próximo
            alternativas = [
                c for c in candidatos
                if c["produto_ref"] != it["ref"]
                and (c["marca"] or "").strip().lower() != marca_it
            ]
            alternativas.sort(key=lambda c: (abs((_preco(c) or preco_it) - preco_it) if preco_it else 0, c["produto_ref"]))
            it["cross_sell_refs"] = [c["produto_ref"] for c in alternativas[:LIMITE_RELACIONADOS_RECURSO]]
            if it["cross_sell_refs"]:
                it["relacionados_por_recurso"] = True

        if not it["upsell_refs"] and preco_it and marca_it:
            # upsell: mesma categoria, MESMA marca, entre 1,15× e 3× o preço
            acima = [
                c for c in candidatos
                if c["produto_ref"] != it["ref"]
                and (c["marca"] or "").strip().lower() == marca_it
                and (_preco(c) or 0) >= preco_it * 1.15
                and (_preco(c) or 0) <= preco_it * 3.0
            ]
            acima.sort(key=lambda c: (_preco(c) or 0, c["produto_ref"]))
            it["upsell_refs"] = [c["produto_ref"] for c in acima[:LIMITE_RELACIONADOS_RECURSO]]
            if it["upsell_refs"]:
                it["relacionados_por_recurso"] = True

    for it in itens:
        it.pop("_categoria_valor_tmp", None)
    return itens


def _texto_json(v: Any) -> Optional[str]:
    """O que o PostgreSQL devolve em `dados->>'chave'`: None para ausente ou
    JSON null, o texto tal qual para strings, e a forma JSON para o resto
    (números, booleanos — `true`/`false` —, listas e objectos)."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _num_json(v)
    import json
    # jsonb: «, » e «: » como separadores, chaves por ordem de jsonb (tamanho, depois bytes)
    return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))


def _num_json(v) -> str:
    # números do jsonb: inteiros como estão, decimais na forma curta (12.5);
    # o `json.loads` do psycopg2 dá int/float, e repr(float) volta ao texto original.
    return str(v) if isinstance(v, int) else repr(v)
