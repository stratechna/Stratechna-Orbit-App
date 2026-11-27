"""Textos e categorias do produto mudados à mão no Orbit (27-11-2026, pedido do Vítor: «o feed lê os textos e
categorias da ficha»).

Até aqui o feed da loja (sync3.py) partia da cópia do produto que o importador do portal manda (`orbit_dados_loja`) e
o espelho reescrevia o título, as descrições, as categorias e as etiquetas da ficha em cada volta — o que se mudasse
no Orbit perdia-se e nunca chegava à loja.

Agora:
* quando uma PESSOA muda um destes campos na ficha (não o espelho/importador), o campo entra em
  `orbit_campos_manuais` (um por linha);
* o espelho deixa de o escrever por cima (espelho.py);
* o feed leva para a loja o valor da ficha (sync3.py) — também os ids das categorias, pelo nome, a partir das que o
  importador já usa nesta loja.
Para devolver um campo ao importador, apaga-se a linha dele em «Editado à mão no Orbit».

A loja aplica o título e as descrições se ninguém os tiver mudado à mão no WordPress; as categorias só entram em
produtos que ainda não tenham categoria (regra da Sync3 na Suite: nunca troca categorias de um produto existente).
"""
from __future__ import annotations

import re
from html import unescape

import frappe

# campo da ficha → campo do produto no feed
CAMPOS = {"item_name": "titulo", "description": "descricao", "orbit_descricao_curta": "descricao_curta",
          "orbit_categorias_loja": "categorias_loja", "orbit_tags_loja": "tags_loja"}
LISTAS = {"orbit_categorias_loja", "orbit_tags_loja"}
CAMPO = "orbit_campos_manuais"


def lista(doc) -> set:
    return {c.strip() for c in (doc.get(CAMPO) or "").splitlines() if c.strip() in CAMPOS}


def _norm(campo, v) -> str:
    """Para comparar: o editor de texto do Frappe reembrulha o HTML ao gravar outra coisa — compara-se o texto."""
    t = unescape(re.sub(r"<[^>]+>", " ", str(v or "")))
    return re.sub(r"\s+", " ", t).strip()


def antes_de_validar(doc, method=None):
    """Item.before_validate: marca os campos que uma pessoa mudou (só nos artigos que vêm do importador)."""
    if doc.flags.get("orbit_espelho") or doc.is_new() or not doc.get("orbit_chave_importador") \
            or not doc.meta.has_field(CAMPO):
        return
    antes = doc.get_doc_before_save()
    if not antes:
        return
    marcados = lista(doc)
    for campo in CAMPOS:
        if _norm(campo, doc.get(campo)) != _norm(campo, antes.get(campo)):
            marcados.add(campo)
    doc.set(CAMPO, "\n".join(c for c in CAMPOS if c in marcados))


def no_feed(it, loja: dict, ids_categoria: dict) -> None:
    """Põe no produto do feed os campos editados à mão no Orbit."""
    for campo in [c for c in (it.get(CAMPO) or "").splitlines() if c.strip() in CAMPOS]:
        campo = campo.strip()
        chave = CAMPOS[campo]
        v = it.get(campo)
        if campo in LISTAS:
            valores = [x.strip() for x in (v or "").splitlines() if x.strip()]
            if valores != list(loja.get(chave) or []):
                loja[chave] = valores
                if campo == "orbit_categorias_loja":
                    loja["categorias_loja_ids"] = [ids_categoria[n] for n in valores if n in ids_categoria]
        elif (v or "") != (loja.get(chave) or ""):
            loja[chave] = v or None


def ids_categorias(itens) -> dict:
    """Nome da categoria → term_id na loja, pelo que o importador já manda (o nome só vale se for único)."""
    import json
    mapa, repetidos = {}, set()
    for it in itens:
        try:
            l = json.loads(it.get("orbit_dados_loja") or "{}")
        except ValueError:
            continue
        for n, i in zip(l.get("categorias_loja") or [], l.get("categorias_loja_ids") or []):
            if n in mapa and mapa[n] != i:
                repetidos.add(n)
            mapa.setdefault(n, i)
    return {n: i for n, i in mapa.items() if n not in repetidos}
