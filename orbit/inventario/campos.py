"""Campos do inventário central nos doctypes do ERPNext (21-11-2026, docs/PLANO-INVENTARIO-IMPORTADOR-ORBIT.md F1).

Só campos acrescentados (Custom Field, módulo Inventario) — nenhum ficheiro do ERPNext é alterado, por isso
sobrevivem às actualizações. Corre em cada `bench migrate` (after_migrate) e é idempotente.
"""
import frappe

ITEM = [
    {"fieldname": "orbit_sec_inventario", "fieldtype": "Section Break", "label": "Inventário central",
     "insert_after": "description", "collapsible": 1},
    {"fieldname": "orbit_fabricante", "fieldtype": "Link", "options": "Manufacturer", "label": "Fabricante",
     "insert_after": "orbit_sec_inventario", "in_standard_filter": 1,
     "description": "A marca do fabricante. A «Marca» do artigo é a do negócio (ex.: Arnox, JFusados, Shopinox)."},
    {"fieldname": "orbit_chave_importador", "fieldtype": "Data", "label": "Chave do importador",
     "insert_after": "orbit_fabricante", "read_only": 1, "no_copy": 1, "search_index": 1,
     "description": "«<id do fornecedor>:<referência>» — o produto do feed de onde este artigo vem."},
    {"fieldname": "orbit_pai_ref", "fieldtype": "Data", "label": "Produto-pai no feed",
     "insert_after": "orbit_chave_importador", "read_only": 1, "no_copy": 1},
    {"fieldname": "orbit_origem_stock", "fieldtype": "Data", "label": "Origem do stock (feed)",
     "insert_after": "orbit_pai_ref", "read_only": 1, "no_copy": 1},
    {"fieldname": "orbit_col_inventario", "fieldtype": "Column Break", "insert_after": "orbit_origem_stock"},
    {"fieldname": "orbit_comprimento", "fieldtype": "Float", "label": "Comprimento (cm)", "insert_after": "orbit_col_inventario"},
    {"fieldname": "orbit_largura", "fieldtype": "Float", "label": "Largura (cm)", "insert_after": "orbit_comprimento"},
    {"fieldname": "orbit_altura", "fieldtype": "Float", "label": "Altura (cm)", "insert_after": "orbit_largura"},
    # 27-11-2026: título, descrições, categorias e etiquetas editáveis — o que se muda à mão no Orbit vai para a loja
    # e o importador deixa de o escrever por cima (orbit/inventario/manuais.py)
    {"fieldname": "orbit_categorias_loja", "fieldtype": "Small Text", "label": "Categorias na loja",
     "insert_after": "orbit_altura", "read_only": 0, "no_copy": 1, "description": "Uma por linha, com o nome exacto da categoria da loja."},
    {"fieldname": "orbit_campos_manuais", "fieldtype": "Small Text", "label": "Editado à mão no Orbit",
     "insert_after": "orbit_categorias_loja", "no_copy": 1,
     "description": "Campos mudados aqui: o importador já não os escreve por cima e a loja recebe o valor do Orbit. Apague a linha para voltar ao importador."},
    {"fieldname": "orbit_imagens", "fieldtype": "Long Text", "label": "Imagens (endereços)",
     "insert_after": "orbit_campos_manuais", "read_only": 1, "no_copy": 1,
     "description": "Endereços alojados, um por linha — as galerias não entram nos ficheiros do Orbit."},
    {"fieldname": "orbit_dados_loja", "fieldtype": "Long Text", "label": "Produto na loja (feed)",
     "insert_after": "orbit_imagens", "hidden": 1, "read_only": 1, "no_copy": 1,
     "description": "O produto tal como o importador o leva à loja — base do feed do Orbit (F2)."},
    {"fieldname": "orbit_hash_espelho", "fieldtype": "Data", "label": "Assinatura do espelho",
     "insert_after": "orbit_dados_loja", "hidden": 1, "read_only": 1, "no_copy": 1},
]

# 23-11-2026 (Vítor: «cada ficha deve ter campos associados a cada campo do WooCommerce e do importador»): os ~50 campos
# do produto do feed passam a campos da ficha, por secções. Só de leitura enquanto o importador do portal for o mestre
# (corrige-se no importador — regra do «feed é a fonte de verdade»); preenchidos pelo espelho/importador (espelho.py).
def _c(nome, tipo, rotulo, depois, **k):
    return {"fieldname": nome, "fieldtype": tipo, "label": rotulo, "insert_after": depois, "read_only": 1, "no_copy": 1, **k}


ITEM_LOJA = [
    {"fieldname": "orbit_sec_loja", "fieldtype": "Section Break", "label": "Loja (WooCommerce)", "insert_after": "orbit_hash_espelho", "collapsible": 1},
    _c("orbit_ref_feed", "Data", "Referência (SKU)", "orbit_sec_loja", search_index=1),
    _c("orbit_ean", "Data", "GTIN / EAN", "orbit_ref_feed"),
    _c("orbit_mpn", "Data", "Referência do fabricante (MPN)", "orbit_ean"),
    _c("orbit_estado_publicacao", "Data", "Estado na loja", "orbit_mpn"),
    _c("orbit_tipo_fornecimento", "Data", "Tipo de fornecimento", "orbit_estado_publicacao"),
    _c("orbit_transporte", "Data", "Transporte", "orbit_tipo_fornecimento"),
    {"fieldname": "orbit_col_loja", "fieldtype": "Column Break", "insert_after": "orbit_transporte"},
    _c("orbit_tags_loja", "Small Text", "Etiquetas na loja", "orbit_col_loja", read_only=0),
    _c("orbit_descricao_curta", "Text Editor", "Descrição curta", "orbit_tags_loja", read_only=0),
    {"fieldname": "orbit_sec_precos", "fieldtype": "Section Break", "label": "Preços (importador)", "insert_after": "orbit_descricao_curta", "collapsible": 1},
    _c("orbit_custo", "Currency", "Custo", "orbit_sec_precos"),
    _c("orbit_preco_base", "Currency", "Preço base", "orbit_custo"),
    _c("orbit_preco_base_venda", "Currency", "Preço base de venda", "orbit_preco_base"),
    _c("orbit_preco_pvp", "Currency", "PVP", "orbit_preco_base_venda"),
    {"fieldname": "orbit_col_precos", "fieldtype": "Column Break", "insert_after": "orbit_preco_pvp"},
    _c("orbit_preco_regular", "Currency", "Preço normal na loja", "orbit_col_precos"),
    _c("orbit_preco_promocional", "Currency", "Preço promocional", "orbit_preco_regular"),
    _c("orbit_preco_congelado", "Check", "Preço congelado", "orbit_preco_promocional"),
    _c("orbit_preco_sob_consulta", "Check", "Preço sob consulta", "orbit_preco_congelado"),
    {"fieldname": "orbit_sec_stock_feed", "fieldtype": "Section Break", "label": "Stock e prazos (feed)", "insert_after": "orbit_preco_sob_consulta", "collapsible": 1},
    _c("orbit_stock_feed", "Data", "Stock no feed", "orbit_sec_stock_feed"),
    _c("orbit_estado_stock", "Data", "Estado do stock", "orbit_stock_feed"),
    _c("orbit_estado_stock_com_preco", "Data", "Estado do stock (com preço)", "orbit_estado_stock"),
    {"fieldname": "orbit_col_stock_feed", "fieldtype": "Column Break", "insert_after": "orbit_estado_stock_com_preco"},
    _c("orbit_prazo_entrega", "Data", "Prazo de entrega", "orbit_col_stock_feed"),
    _c("orbit_prazo_entrega_com_preco", "Data", "Prazo de entrega (com preço)", "orbit_prazo_entrega"),
    _c("orbit_data_reposicao", "Data", "Data de reposição", "orbit_prazo_entrega_com_preco"),
    {"fieldname": "orbit_sec_atributos", "fieldtype": "Section Break", "label": "Atributos e especificações", "insert_after": "orbit_data_reposicao", "collapsible": 1},
    _c("orbit_atributos", "Small Text", "Atributos globais", "orbit_sec_atributos"),
    _c("orbit_atributos_locais", "Small Text", "Atributos locais", "orbit_atributos"),
    _c("orbit_atributos_variacao", "Small Text", "Atributos da variação", "orbit_atributos_locais"),
    {"fieldname": "orbit_col_atributos", "fieldtype": "Column Break", "insert_after": "orbit_atributos_variacao"},
    _c("orbit_especificacoes", "Long Text", "Especificações", "orbit_col_atributos"),
    _c("orbit_o_que_vem_na_caixa", "Small Text", "O que vem na caixa", "orbit_especificacoes"),
    _c("orbit_campos_personalizados", "Small Text", "Campos personalizados", "orbit_o_que_vem_na_caixa"),
    {"fieldname": "orbit_sec_documentos", "fieldtype": "Section Break", "label": "Documentos e relacionados", "insert_after": "orbit_campos_personalizados", "collapsible": 1},
    _c("orbit_documentos", "Small Text", "Documentos (fichas, PDF)", "orbit_sec_documentos"),
    _c("orbit_medidas_rever", "Small Text", "Medidas a rever", "orbit_documentos"),
    {"fieldname": "orbit_col_documentos", "fieldtype": "Column Break", "insert_after": "orbit_medidas_rever"},
    _c("orbit_cross_sell", "Small Text", "Complementares (cross-sell)", "orbit_col_documentos"),
    _c("orbit_upsell", "Small Text", "Alternativos (upsell)", "orbit_cross_sell"),
    {"fieldname": "orbit_sec_importador", "fieldtype": "Section Break", "label": "Importador", "insert_after": "orbit_upsell", "collapsible": 1},
    _c("orbit_fornecedor_feed", "Data", "Fornecedor (feed)", "orbit_sec_importador"),
    _c("orbit_actualizado_feed", "Data", "Actualizado no importador", "orbit_fornecedor_feed"),
    {"fieldname": "orbit_col_importador", "fieldtype": "Column Break", "insert_after": "orbit_actualizado_feed"},
    _c("orbit_categoria_confirmada_ia", "Check", "Categoria confirmada pela IA", "orbit_col_importador"),
    _c("orbit_pendente_ia", "Small Text", "Por rever pela IA", "orbit_categoria_confirmada_ia"),
]

WAREHOUSE = [
    {"fieldname": "orbit_virtual", "fieldtype": "Check", "label": "Armazém virtual do fornecedor (não contabilizado)",
     "insert_after": "is_group", "read_only": 1,
     "description": "Mostra o stock do fornecedor (Oferta do fornecedor). Nunca recebe movimentos de stock."},
    {"fieldname": "orbit_fornecedor", "fieldtype": "Link", "options": "Supplier", "label": "Fornecedor",
     "insert_after": "orbit_virtual", "read_only": 1},
]

SUPPLIER = [
    {"fieldname": "orbit_sec_inventario", "fieldtype": "Section Break", "label": "Inventário central",
     "insert_after": "supplier_group", "collapsible": 1},
    {"fieldname": "orbit_importador_id", "fieldtype": "Int", "label": "Id no importador",
     "insert_after": "orbit_sec_inventario", "read_only": 1, "no_copy": 1, "search_index": 1},
    {"fieldname": "orbit_vende_com_stock", "fieldtype": "Check", "label": "Pode vender-se com o stock deste fornecedor",
     "insert_after": "orbit_importador_id", "default": "1"},
    {"fieldname": "orbit_frescura_horas", "fieldtype": "Int", "label": "Frescura máxima do stock (horas)",
     "insert_after": "orbit_vende_com_stock", "default": "12",
     "description": "Stock lido há mais tempo do que isto conta como zero (D8: 12 h por omissão)."},
    {"fieldname": "orbit_margem_stock", "fieldtype": "Int", "label": "Margem de segurança (unidades)",
     "insert_after": "orbit_frescura_horas", "default": "0",
     "description": "Mostra-se a quantidade do fornecedor menos esta margem."},
]


def garantir():
    if not frappe.db.exists("DocType", "Item"):
        return   # tenant sem ERPNext
    try:
        from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
        create_custom_fields({"Item": [{**c, "module": "Inventario"} for c in ITEM + ITEM_LOJA],
                              "Supplier": [{**c, "module": "Inventario"} for c in SUPPLIER],
                              "Warehouse": [{**c, "module": "Inventario"} for c in WAREHOUSE]}, update=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(title="orbit.inventario.campos.garantir")
