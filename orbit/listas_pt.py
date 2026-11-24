"""Listas do CRM em português (24-11-2026, pedido do Vítor: «isto também deve ser traduzido»).

Os motivos de perda, as origens e os setores que o Frappe CRM instala vêm em inglês e são dados (o nome é o
próprio texto). Aqui mudam de nome com `rename_doc` — os negócios e leads que já os usam acompanham — e, quando
já existe a versão portuguesa (ex. «Advertisement» e «Publicidade»), juntam-se nela. Só mexe nos nomes ingleses
de origem; o que cada tenant escreveu fica. Corre em `after_migrate`.
Fases, estados das leads, tipos e prioridades dos tickets NÃO mudam de nome (o CRM e o Desk usam os nomes
ingleses no código): mostram-se em português pelos rótulos (`orbit.interface.api._PT`).
"""
import frappe

MOTIVOS = {  # inglês → (português, descrição)
    "Budget Constraints": ("Sem orçamento", "O cliente não tinha orçamento para avançar."),
    "Competition": ("Concorrência", "O cliente escolheu um produto ou serviço da concorrência."),
    "Long Sales Cycle": ("Processo demasiado longo", "O processo de venda demorou demasiado e o interesse perdeu-se."),
    "Missing Features": ("Faltam funcionalidades", "O cliente sentiu que faltavam funcionalidades de que precisava."),
    "No Decision-Maker": ("Sem poder de decisão", "O contacto não era quem decidia e não foi possível avançar."),
    "Other": ("Outro", ""),
    "Poor Fit": ("Não se adequa", "O produto ou serviço não se adequava ao cliente."),
    "Pricing": ("Preço", "O cliente achou o preço demasiado alto ou pouco competitivo."),
    "Unresponsive Prospect": ("Sem resposta", "O cliente deixou de responder aos seguimentos."),
}
ORIGENS = {
    "WebSite Visit": "Visita ao site", "Web Form": "Formulário do site", "Website": "Site",
    "Walk In": "Visita presencial", "Campaign": "Campanha", "Customer's Vendor": "Fornecedor do cliente",
    "Mass Mailing": "Email marketing", "Supplier Reference": "Referência de fornecedor", "Exhibition": "Feira ou exposição",
    "Cold Calling": "Contacto a frio", "Advertisement": "Publicidade", "Reference": "Referência externa",
    "Existing Customer": "Cliente existente", "Email": "Email", "-Outro-": "Outro",
    "Alias de e-mail de venda": "Endereço de email de vendas",
}
SETORES = {
    "Nonprofit": "Sem fins lucrativos", "Telecom": "Telecomunicações", "Telecommunications": "Telecomunicações",
    "Travel": "Viagens e turismo", "Media": "Comunicação social", "Retail": "Comércio a retalho",
    "Food & Beverage": "Alimentação e bebidas", "Food": "Alimentação e bebidas", "Logistics": "Logística",
    "Finance": "Serviços financeiros", "Financial Services": "Serviços financeiros", "Marketing": "Marketing",
    "Healthcare": "Saúde", "Health Care": "Saúde", "Semiconductors": "Semicondutores", "SaaS": "Software como serviço (SaaS)",
    "Ecommerce": "Comércio eletrónico", "CRM": "CRM", "ERP": "ERP", "Venture Capital": "Capital de risco",
    "Transportation": "Transportes", "Television": "Televisão", "Technology": "Tecnologia", "Sports": "Desporto",
    "Software": "Software", "Soap & Detergent": "Detergentes e higiene", "Service": "Prestador de serviços",
    "Securities & Commodity Exchanges": "Bolsas e mercados", "Retail & Wholesale": "Comércio a retalho e por grosso",
    "Real Estate": "Imobiliário", "Publishing": "Edição", "Private Equity": "Fundos de investimento",
    "Pharmaceuticals": "Farmacêutica", "Pension Funds": "Fundos de pensões", "Online Auctions": "Leilões online",
    "Newspaper Publishers": "Imprensa", "Music": "Música", "Motion Picture & Video": "Cinema e vídeo",
    "Manufacturing": "Indústria", "Legal": "Jurídico", "Investment Banking": "Banca de investimento",
    "Internet Publishing": "Edição digital", "Grocery": "Mercearia e supermercados", "Beverage & Tobacco": "Bebidas e tabaco",
    "Entertainment & Leisure, Executive Search": "Lazer e entretenimento", "Energy": "Energia", "Electronics": "Eletrónica",
    "Education": "Educação", "Department Stores": "Grandes armazéns", "Defense": "Defesa", "Cosmetics": "Cosmética",
    "Consumer Products": "Bens de consumo", "Consulting": "Consultoria", "Computer": "Informática", "Chemical": "Química",
    "Brokerage": "Corretagem", "Broadcasting": "Rádio e televisão", "Biotechnology": "Biotecnologia", "Banking": "Banca",
    "Automotive": "Automóvel", "Apparel & Accessories": "Vestuário e acessórios", "Airline": "Aviação",
    "Agriculture": "Agricultura", "Aerospace": "Aeroespacial", "Advertising": "Publicidade", "Accounting": "Contabilidade",
}


def _mudar(dt, en, pt, campo):
    if en == pt or not frappe.db.exists(dt, en):
        return
    if frappe.db.exists(dt, pt):
        frappe.rename_doc(dt, en, pt, merge=True, force=True)
    else:
        frappe.rename_doc(dt, en, pt, force=True)
        frappe.db.set_value(dt, pt, campo, pt, update_modified=False)


def acertar():
    for dt, mapa, campo in (("CRM Lost Reason", {k: v[0] for k, v in MOTIVOS.items()}, "lost_reason"),
                            ("CRM Lead Source", ORIGENS, "source_name"), ("CRM Industry", SETORES, "industry")):
        if not frappe.db.exists("DocType", dt):
            continue
        for en, pt in mapa.items():
            try:
                _mudar(dt, en, pt, campo)
                frappe.db.commit()
            except Exception as e:  # noqa: BLE001 — nunca deita abaixo uma migração
                frappe.db.rollback()
                frappe.log_error(f"listas_pt {dt} {en}: {e}", "orbit listas PT")
    if frappe.db.exists("DocType", "CRM Lost Reason"):
        for en, (pt, desc) in MOTIVOS.items():
            if desc and frappe.db.exists("CRM Lost Reason", pt):
                atual = frappe.db.get_value("CRM Lost Reason", pt, "description") or ""
                if not atual or atual.startswith("The prospect") or atual.startswith("The sales"):
                    frappe.db.set_value("CRM Lost Reason", pt, "description", desc, update_modified=False)
        frappe.db.commit()
