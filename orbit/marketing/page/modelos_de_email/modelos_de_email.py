"""Os doze modelos, desenhados com a marca deste tenant e um texto de exemplo.
Escolhe-se a ver, não pelo nome."""

import frappe

from orbit.marketing import mensagem, modelos


@frappe.whitelist()
def galeria() -> list[dict]:
    d = mensagem.definicoes()
    ident = mensagem.identidade(d)
    saida = []
    for chave, m in modelos.MODELOS.items():
        html = modelos.gerar(modelos.exemplo(chave), ident, ir=lambda u: u or "#", remover="#",
                             motivo=mensagem.MOTIVO["consentimento"], legal_texto=d.legal_texto or "",
                             assunto=m["nome"], pre_cabecalho=m["para"])
        saida.append({"chave": chave, "nome": m["nome"], "para": m["para"], "html": html})
    return saida
