"""A mensagem de uma campanha para um destinatário: assunto, HTML e cabeçalhos.

Os cabeçalhos de remoção num clique (`List-Unsubscribe` + `List-Unsubscribe-Post`,
RFC 8058) são exigência da Google e da Yahoo para quem envia em volume. O Frappe
não os sabe pôr: o `email_headers` do `frappe.sendmail` acrescenta «X-» a
qualquer nome que não comece por «X-» (`EMail.add_headers`), e
`X-List-Unsubscribe` não serve a ninguém. Por isso entram directamente na
mensagem já guardada na fila (`acrescentar_cabecalhos`), que é texto MIME com os
cabeçalhos antes da primeira linha em branco.
"""

import json

import frappe
from frappe.utils import cint, get_url

from orbit.marketing import modelos

MOTIVO = {
    "consentimento": "Recebe este email porque aceitou receber as nossas comunicações.",
    "cliente": "Recebe este email porque é nosso cliente.",
    "b2b": "Recebe este email na qualidade de contacto profissional da sua empresa.",
}


def definicoes():
    return frappe.get_cached_doc("Definicoes de Marketing")


def identidade(d=None) -> dict:
    d = d or definicoes()

    def _json(v):
        try:
            return json.loads(v) if v else {}
        except ValueError:
            return {}
    return {"nome": d.marca_nome or "",
            "logotipos": {"claro": d.logo_url} if d.logo_url else {},
            "cores": {k: v for k, v in (("primaria", d.cor_primaria), ("acento", d.cor_acento)) if v},
            "fontes": {k: v for k, v in (("titulos", d.fonte_titulos), ("texto", d.fonte_texto)) if v},
            "redes": _json(d.redes), "contactos": _json(d.contactos)}


def _absoluto(u: str | None) -> str | None:
    """Os anexos do Frappe guardam caminhos («/files/x.png»). Um email abre-se
    fora do site: tem de levar o endereço completo."""
    if not u:
        return None
    return u if u.startswith(("http://", "https://")) else get_url(u)


def conteudo(c) -> dict:
    """Os campos da campanha na forma que os modelos usam."""
    return {
        "modelo": modelos.POR_NOME.get(c.modelo, "relacao"),
        "titulo": c.titulo_email, "subtitulo": c.subtitulo,
        "paragrafos": [p.strip() for p in (c.texto or "").split("\n\n") if p.strip()],
        "cta_texto": c.cta_texto, "cta_url": c.cta_url,
        "imagem_topo": _absoluto(c.imagem_topo),
        "destaque": {"texto": c.destaque_texto, "subtexto": c.destaque_subtexto} if c.destaque_texto else {},
        "evento": {"data": c.evento_data, "hora": c.evento_hora, "local": c.evento_local},
        "assinatura": c.assinatura,
        "itens": [{"titulo": i.titulo, "texto": i.texto, "url": i.url, "imagem": _absoluto(i.imagem)}
                  for i in (c.itens or [])],
        "produtos": [{"nome": p.nome, "preco": p.preco, "url": p.url, "imagem": _absoluto(p.imagem),
                      "descricao": p.descricao} for p in (c.produtos or [])],
    }


def _pessoal(texto: str | None, r: dict) -> str:
    return (texto or "").replace("{{nome}}", (r.get("nome") or "").strip())


def url_publico(metodo: str, **params) -> str:
    from urllib.parse import urlencode
    return get_url(f"/api/method/orbit.marketing.publico.{metodo}?{urlencode(params)}")


def compor(c, r: dict, token: str | None = None) -> dict:
    """Sem `token` é pré-visualização ou teste: as ligações vão directas e não
    há píxel."""
    d = definicoes()
    k = conteudo(c)
    for campo in ("titulo", "subtitulo", "assinatura"):
        if k.get(campo):
            k[campo] = _pessoal(k[campo], r)
    k["paragrafos"] = [_pessoal(p, r) for p in k["paragrafos"]]
    ligacoes = modelos.ligacoes(k)

    def ir(u):
        if not token or not u or u not in ligacoes:
            return u or "#"
        return url_publico("ir", t=token, i=ligacoes.index(u))

    remover = get_url(f"/deixar-de-receber?t={token}") if token else get_url("/deixar-de-receber")
    html = modelos.gerar(
        k, identidade(d), ir=ir, remover=remover,
        motivo=MOTIVO.get(r.get("mkt_base_legal") or "", ""),
        legal_texto=d.legal_texto or "",
        pixel=url_publico("aberto", t=token) if token and cint(d.medir_aberturas) else None,
        assunto=c.linha_assunto or "", pre_cabecalho=c.pre_cabecalho or "")
    return {"assunto": _pessoal(c.linha_assunto, r), "html": html,
            "sair_um_clique": url_publico("sair", t=token) if token else None}


def acrescentar_cabecalhos(queue_name: str, sair_um_clique: str) -> None:
    q = frappe.get_doc("Email Queue", queue_name)
    mensagem = q.message or ""
    if "List-Unsubscribe:" in mensagem:
        return
    quebra = "\r\n" if "\r\n" in mensagem.split("\n\n", 1)[0] + "\n" else "\n"
    novos = (f"List-Unsubscribe: <{sair_um_clique}>{quebra}"
             f"List-Unsubscribe-Post: List-Unsubscribe=One-Click{quebra}"
             f"Precedence: bulk{quebra}")
    q.db_set("message", novos + mensagem, update_modified=False)
