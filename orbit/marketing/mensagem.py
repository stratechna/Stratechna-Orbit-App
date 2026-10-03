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


def conteudo(c, dados: dict | None = None) -> dict:
    """Os campos de uma campanha ou automação na forma que os modelos usam.
    `dados` é o que é só de um destinatário (os produtos que ELE comprou, a
    encomenda DELE) — por cima do conteúdo comum. Lê-se com `.get` porque a
    automação não tem todos os campos da campanha."""
    g = c.get
    k = {
        "modelo": modelos.POR_NOME.get(g("modelo"), "relacao"),
        "titulo": g("titulo_email"), "subtitulo": g("subtitulo"),
        "paragrafos": [p.strip() for p in (g("texto") or "").split("\n\n") if p.strip()],
        "cta_texto": g("cta_texto"), "cta_url": g("cta_url"),
        "imagem_topo": _absoluto(g("imagem_topo")),
        "destaque": {"texto": g("destaque_texto"), "subtexto": g("destaque_subtexto")} if g("destaque_texto") else {},
        "evento": {"data": g("evento_data"), "hora": g("evento_hora"), "local": g("evento_local")},
        "assinatura": g("assinatura"),
        "itens": [{"titulo": i.titulo, "texto": i.texto, "url": i.url, "imagem": _absoluto(i.imagem)}
                  for i in (g("itens") or [])],
        "produtos": [{"nome": p.nome, "preco": p.preco, "url": p.url, "imagem": _absoluto(p.imagem),
                      "descricao": p.descricao} for p in (g("produtos") or [])],
    }
    if dados:
        if dados.get("produtos") is not None:
            k["produtos"] = dados["produtos"]
        if dados.get("cta_url"):
            k["cta_url"] = dados["cta_url"]
    return k


def _pessoal(texto: str | None, r: dict) -> str:
    return (texto or "").replace("{{nome}}", (r.get("nome") or "").strip())


def url_publico(metodo: str, **params) -> str:
    from urllib.parse import urlencode
    return get_url(f"/api/method/orbit.marketing.publico.{metodo}?{urlencode(params)}")


def compor(c, r: dict, token: str | None = None, dados: dict | None = None) -> dict:
    """Sem `token` é pré-visualização ou teste: as ligações vão directas e não
    há píxel."""
    d = definicoes()
    k = conteudo(c, dados)
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


@frappe.whitelist()
def previsualizar_rascunho(doc) -> dict:
    """A pré-visualização do que está no formulário, gravado ou não — é o que
    deixa ver a campanha a montar-se enquanto se escreve."""
    frappe.has_permission("Campanha de Marketing", "read", throw=True)
    dados = json.loads(doc) if isinstance(doc, str) else dict(doc)
    dados["doctype"] = "Campanha de Marketing"
    c = frappe.get_doc(dados)
    r = compor(c, {"nome": "Maria", "mkt_base_legal": "consentimento"})
    return {"assunto": r["assunto"], "html": r["html"]}
