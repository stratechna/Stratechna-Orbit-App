"""Propostas comerciais por cima do Orçamento (Quotation) do ERPNext — 10-11-2026.

Pedido da JF (Arnox, JFusados, Shopinox): proposta com logótipo da marca, texto de introdução, produtos com
imagem/referência/características/observações, alternativas que não somam, transporte e montagem por produto
ou no total, IVA à parte, validade/garantia/pagamento/prazo por omissão da marca, rodapé com os dados da marca
e as condições comerciais da marca como página anexa. O documento continua a ser o Orçamento: passa a
Encomenda e Fatura como qualquer outro.

* `instalar.py`  — campos (Brand, Quotation, Quotation Item), artigos de serviço e o modelo de impressão.
* `regras.py`    — antes de validar: marca → série/timbre/textos, linhas de transporte e montagem, IVA.
* `referencia.py` — «Adicionar por referência»: catálogo do portal → site da marca → internet (IA).
* `proposta.html` — o modelo de impressão «Proposta Orbit» (wkhtmltopdf: só tabelas, nada de grid/flex).

Plano: docs/PLANO-PROPOSTAS-ORBIT.md (stratechna-work).
"""
