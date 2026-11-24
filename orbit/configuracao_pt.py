"""Opções de configuração de todas as apps do Orbit em português (24-11-2026).

Pedido do Vítor: «Verifica todas as opções de configuração em todas as apps. Tudo o que estiver em inglês tem que ser
traduzido.» As listas que o ERPNext, o HRMS e o Helpdesk instalam (plano de contas, unidades, armazéns, tipos de
ausência, cargos, papéis, estados, modos de pagamento…) vêm em inglês e muitos destes nomes são usados pelo código
das apps (ex. «All Item Groups», «Leave Without Pay», «Basic», «Material Issue», os papéis). Por isso NÃO mudam
de nome: traduzem-se.

- O tipo de documento fica «traduzido» (`translated_doctype`, por Property Setter): o Frappe mostra e procura os
  nomes pela tradução no ecrã do ERP.
- Cada nome ganha uma tradução PT-PT (registo `Translation`, língua pt). Palavras soltas que também aparecem como
  texto da interface («Open», «Default», «Second»…) não ganham tradução geral, para não trocar botões.
- A interface /orbit lê `TRAD` (`erp.traducoes`) e mostra o nome português nas listas, nas fichas, nas ligações e
  nos relatórios — também o das palavras soltas.
- O plano de contas traduz-se com o sufixo da empresa («Cost of Goods Sold - JFLDA» → «Custo das mercadorias
  vendidas - JFLDA»).
As listas do CRM que são só dados (motivos de perda, origens, setores) mudam mesmo de nome em `listas_pt.py`.
Corre em `after_migrate`; repetível.
"""
import frappe

TRAD = {
    "Mode of Payment": {"Bank Draft": "Cheque bancário", "Cash": "Numerário", "Cheque": "Cheque",
                        "Credit Card": "Cartão de crédito", "Wire Transfer": "Transferência bancária"},
    "Opportunity Type": {"Maintenance": "Manutenção", "Sales": "Vendas", "Support": "Apoio"},
    "Salutation": {"Madam": "Sr.ª", "Master": "Menino", "Miss": "Menina", "Mrs": "Sr.ª", "Mr": "Sr.", "Ms": "Sr.ª",
                   "Prof": "Prof.", "Dr": "Dr."},
    "Role": {
        "Academics User": "Utilizador académico", "Accounts Manager": "Gestor de contabilidade",
        "Accounts User": "Utilizador de contabilidade", "Administrator": "Administrador", "Agent": "Agente",
        "Agent Manager": "Gestor de agentes", "All": "Todos", "Analytics": "Análises", "Auditor": "Auditor",
        "Customer": "Cliente", "Dashboard Manager": "Gestor de painéis", "Delivery Manager": "Gestor de entregas",
        "Delivery User": "Utilizador de entregas", "Desk User": "Utilizador do ERP", "Employee": "Colaborador",
        "Employee Self Service": "Portal do colaborador", "Expense Approver": "Aprovador de despesas",
        "Fleet Manager": "Gestor de frota", "Flow User": "Utilizador de fluxos", "Fulfillment User": "Utilizador de expedição",
        "Guest": "Visitante", "HD Customer": "Cliente do Desk", "HD Customer Manager": "Gestor de clientes do Desk",
        "HR Manager": "Gestor de RH", "HR User": "Utilizador de RH", "Inbox User": "Utilizador da caixa de entrada",
        "Interviewer": "Entrevistador", "Item Manager": "Gestor de artigos",
        "Knowledge Base Contributor": "Autor da base de conhecimento", "Knowledge Base Editor": "Editor da base de conhecimento",
        "Leave Approver": "Aprovador de ausências", "Maintenance Manager": "Gestor de manutenção",
        "Maintenance User": "Utilizador de manutenção", "Manufacturing Manager": "Gestor de produção",
        "Manufacturing User": "Utilizador de produção", "Marketing Manager": "Gestor de marketing",
        "Newsletter Manager": "Gestor de newsletters", "Prepared Report User": "Utilizador de relatórios preparados",
        "Projects Manager": "Gestor de projetos", "Projects User": "Utilizador de projetos",
        "Purchase Manager": "Gestor de compras", "Purchase Master Manager": "Gestor dos dados de compras",
        "Purchase User": "Utilizador de compras", "Quality Manager": "Gestor da qualidade",
        "Report Manager": "Gestor de relatórios", "Sales Manager": "Gestor comercial",
        "Sales Master Manager": "Gestor dos dados de vendas", "Sales User": "Utilizador comercial",
        "Script Manager": "Gestor de scripts", "Stock Manager": "Gestor de stock", "Stock User": "Utilizador de stock",
        "Studio User": "Utilizador do Studio", "Supplier": "Fornecedor", "Support Team": "Equipa de apoio",
        "System Manager": "Gestor do sistema", "TP Agent": "Agente de telefonia", "TP Manager": "Gestor de telefonia",
        "Translator": "Tradutor", "Website Manager": "Gestor do site", "Wiki Approver": "Aprovador da wiki",
        "Workspace Manager": "Gestor de áreas de trabalho"},
    "Role Profile": {"Accounts": "Contabilidade", "Inventory": "Inventário", "Manufacturing": "Produção",
                     "Purchase": "Compras", "Sales": "Vendas"},
    "Party Type": {"Customer": "Cliente", "Employee": "Colaborador", "Shareholder": "Sócio/acionista", "Supplier": "Fornecedor"},
    "User Type": {"Employee Self Service": "Portal do colaborador", "System User": "Utilizador do sistema",
                  "Website User": "Utilizador do site"},
    "Email Template": {"Dispatch Notification": "Aviso de expedição", "Exit Questionnaire Notification": "Questionário de saída",
                       "Interview Feedback Reminder": "Lembrete da avaliação da entrevista", "Interview Reminder": "Lembrete de entrevista",
                       "Leave Approval Notification": "Pedido de aprovação de ausência", "Leave Status Notification": "Decisão sobre a ausência"},
    "CRM Availability Status": {"Active": "Disponível", "Away": "Ausente", "Unavailable": "Indisponível"},
    "CRM Communication Status": {"Open": "Por responder", "Replied": "Respondido"},
    "HD Agent Status": {"Active": "Disponível", "Away": "Ausente", "Unavailable": "Indisponível"},
    "HD Ticket Status": {"Open": "Aberto", "Replied": "Respondido", "Resolved": "Resolvido", "Closed": "Fechado",
                         "Paused": "Em pausa"},
    "HD Service Level Agreement": {"Standard": "Padrão"},
    "HD Ticket Feedback Option": {
        "Adequate help, bit slow": "Ajuda adequada, um pouco lenta", "Clear guidance given": "Orientação clara",
        "Delayed response time": "Resposta demorada", "Exceptional support experience": "Apoio excecional",
        "Helpful answers, reasonable wait": "Respostas úteis, espera razoável", "Instant, top-notch help": "Ajuda imediata e excelente",
        "No resolution provided": "Sem resolução", "Prompt, informative support": "Apoio rápido e esclarecedor",
        "Quick and precise solutions": "Soluções rápidas e precisas", "Response did not help": "A resposta não ajudou"},
    "HD Ticket Template": {"Default": "Predefinido"},
    "HD Ticket Priority": {"Urgent": "Urgente", "High": "Alta", "Medium": "Média", "Low": "Baixa"},
    "HD Ticket Type": {"Bug": "Erro", "Incident": "Incidente", "Question": "Pergunta", "Unspecified": "Não especificado"},
    "HD Service Holiday List": {"Default": "Predefinida"},
    "Issue Priority": {"High": "Alta", "Medium": "Média", "Low": "Baixa"},
    "Operation": {"Assembly": "Montagem"},
    "Salary Component": {"Arrear": "Retroativos", "Basic": "Vencimento base", "Income Tax": "IRS",
                         "Leave Encashment": "Pagamento de férias não gozadas"},
    "Project Type": {"External": "Externo", "Internal": "Interno", "Other": "Outro"},
    "Sales Partner Type": {"Agent": "Agente", "Channel Partner": "Parceiro de canal", "Dealer": "Concessionário",
                           "Distributor": "Distribuidor", "Implementation Partner": "Parceiro de implementação",
                           "Reseller": "Revendedor", "Retailer": "Retalhista"},
    "Industry Type": {
        "Accounting": "Contabilidade", "Advertising": "Publicidade", "Aerospace": "Aeroespacial", "Agriculture": "Agricultura",
        "Airline": "Aviação", "Apparel & Accessories": "Vestuário e acessórios", "Automotive": "Automóvel", "Banking": "Banca",
        "Biotechnology": "Biotecnologia", "Broadcasting": "Rádio e televisão", "Brokerage": "Corretagem", "Chemical": "Química",
        "Computer": "Informática", "Consulting": "Consultoria", "Consumer Products": "Bens de consumo", "Cosmetics": "Cosmética",
        "Defense": "Defesa", "Department Stores": "Grandes armazéns", "Education": "Educação", "Electronics": "Eletrónica",
        "Energy": "Energia", "Entertainment & Leisure": "Lazer e entretenimento", "Executive Search": "Recrutamento de quadros",
        "Financial Services": "Serviços financeiros", "Food, Beverage & Tobacco": "Alimentação, bebidas e tabaco",
        "Grocery": "Mercearia e supermercados", "Health Care": "Saúde", "Internet Publishing": "Edição digital",
        "Investment Banking": "Banca de investimento", "Legal": "Jurídico", "Manufacturing": "Indústria",
        "Motion Picture & Video": "Cinema e vídeo", "Music": "Música", "Newspaper Publishers": "Imprensa",
        "Online Auctions": "Leilões online", "Pension Funds": "Fundos de pensões", "Pharmaceuticals": "Farmacêutica",
        "Private Equity": "Fundos de investimento", "Publishing": "Edição", "Real Estate": "Imobiliário",
        "Retail & Wholesale": "Comércio a retalho e por grosso", "Securities & Commodity Exchanges": "Bolsas e mercados",
        "Service": "Prestação de serviços", "Soap & Detergent": "Detergentes e higiene", "Software": "Software",
        "Sports": "Desporto", "Technology": "Tecnologia", "Telecommunications": "Telecomunicações", "Television": "Televisão",
        "Transportation": "Transportes", "Venture Capital": "Capital de risco"},
    "Item Group": {"All Item Groups": "Todos os grupos de artigos", "Consumable": "Consumíveis", "Products": "Produtos",
                   "Raw Material": "Matérias-primas", "Services": "Serviços", "Sub Assemblies": "Subconjuntos"},
    "Department": {"All Departments": "Todos os departamentos"},
    "Territory": {"All Territories": "Todos os territórios", "Rest Of The World": "Resto do mundo"},
    "Sales Person": {"Sales Team": "Equipa comercial"},
    "Supplier Group": {"All Supplier Groups": "Todos os grupos de fornecedores", "Distributor": "Distribuidor",
                       "Electrical": "Material elétrico", "Hardware": "Ferragens e equipamento", "Local": "Nacional",
                       "Pharmaceutical": "Farmacêutico", "Raw Material": "Matérias-primas", "Services": "Serviços"},
    "Customer Group": {"All Customer Groups": "Todos os grupos de clientes", "Commercial": "Empresas",
                       "Government": "Estado e administração pública", "Individual": "Particulares", "Non Profit": "Sem fins lucrativos"},
    "Designation": {
        "Accountant": "Contabilista", "Administrative Assistant": "Assistente administrativo(a)",
        "Administrative Officer": "Técnico(a) administrativo(a)", "Analyst": "Analista", "Associate": "Associado(a)",
        "Business Analyst": "Analista de negócio", "Business Development Manager": "Gestor(a) de desenvolvimento de negócio",
        "Chief Executive Officer": "Diretor(a) executivo(a) (CEO)", "Chief Financial Officer": "Diretor(a) financeiro(a) (CFO)",
        "Chief Operating Officer": "Diretor(a) de operações (COO)", "Chief Technology Officer": "Diretor(a) de tecnologia (CTO)",
        "Consultant": "Consultor(a)", "Customer Service Representative": "Assistente de apoio ao cliente", "Designer": "Designer",
        "Engineer": "Engenheiro(a)", "Executive Assistant": "Assistente de direção", "Finance Manager": "Gestor(a) financeiro(a)",
        "HR Manager": "Gestor(a) de RH", "Head of Marketing and Sales": "Diretor(a) comercial e de marketing",
        "Manager": "Gestor(a)", "Managing Director": "Diretor(a)-geral", "Marketing Manager": "Gestor(a) de marketing",
        "Marketing Specialist": "Especialista de marketing", "President": "Presidente", "Product Manager": "Gestor(a) de produto",
        "Project Manager": "Gestor(a) de projeto", "Researcher": "Investigador(a)", "Sales Representative": "Comercial",
        "Secretary": "Secretário(a)", "Software Developer": "Programador(a)", "Vice President": "Vice-presidente"},
    "Warehouse": {"All Warehouses": "Todos os armazéns", "Finished Goods": "Produto acabado", "Goods In Transit": "Mercadoria em trânsito",
                  "Stores": "Armazém", "Work In Progress": "Em produção"},
    "Stock Entry Type": {
        "Disassemble": "Desmontagem", "Manufacture": "Produção", "Material Consumption for Manufacture": "Consumo para produção",
        "Material Issue": "Saída de material", "Material Receipt": "Entrada de material", "Material Transfer": "Transferência entre armazéns",
        "Material Transfer for Manufacture": "Transferência para produção", "Receive from Customer": "Receção do cliente",
        "Repack": "Reembalagem", "Return Raw Material to Customer": "Devolução de matéria-prima ao cliente",
        "Send to Subcontractor": "Envio ao subcontratado", "Subcontracting Delivery": "Entrega de subcontratação",
        "Subcontracting Return": "Devolução de subcontratação"},
    "Price List": {"Standard Buying": "Preços de compra", "Standard Selling": "Preços de venda"},
    "UTM Source": {"Advertisement": "Publicidade", "Campaign": "Campanha", "Cold Calling": "Contacto a frio",
                   "Customer's Vendor": "Fornecedor do cliente", "Exhibition": "Feira ou exposição", "Existing Customer": "Cliente existente",
                   "Mass Mailing": "Email marketing", "Reference": "Referência externa", "Supplier Reference": "Referência de fornecedor",
                   "Walk In": "Visita presencial"},
    "Workflow State": {"Approved": "Aprovado", "Pending": "Pendente", "Rejected": "Recusado"},
    "Appointment Letter Template": {"Standard Appointment Letter": "Carta de admissão (modelo)"},
    "Job Applicant Source": {"Campaign": "Campanha", "Employee Referral": "Indicação de colaborador", "Walk In": "Candidatura espontânea",
                             "Website Listing": "Anúncio no site"},
    "Offer Term": {"Annual Salary": "Remuneração anual", "Date of Joining": "Data de admissão", "Department": "Departamento",
                   "Employee Benefits": "Benefícios", "Incentives": "Incentivos", "Job Description": "Descrição de funções",
                   "Leaves per Year": "Dias de férias por ano", "Notice Period": "Pré-aviso", "Probationary Period": "Período experimental",
                   "Responsibilities": "Responsabilidades", "Stock Options": "Opções sobre ações", "Working Hours": "Horário de trabalho"},
    "Leave Type": {"Casual Leave": "Falta justificada", "Compensatory Off": "Descanso compensatório",
                   "Leave Without Pay": "Licença sem vencimento", "Privilege Leave": "Férias", "Sick Leave": "Baixa por doença"},
    "Employment Type": {"Apprentice": "Aprendiz", "Commission": "À comissão", "Contract": "Contrato a termo", "Full-time": "Tempo inteiro",
                        "Intern": "Estágio", "Part-time": "Tempo parcial", "Piecework": "À peça", "Probation": "Período experimental"},
    "Expense Claim Type": {"Calls": "Telefone", "Food": "Refeições", "Medical": "Saúde", "Others": "Outras", "Travel": "Deslocações"},
    "Activity Type": {"Communication": "Comunicação", "Execution": "Execução", "Planning": "Planeamento",
                      "Proposal Writing": "Preparação de propostas", "Research": "Pesquisa"},
    "Supplier Scorecard Standing": {"Average": "Médio", "Excellent": "Excelente", "Poor": "Fraco", "Very Poor": "Muito fraco"},
    "Supplier Scorecard Variable": {
        "# of On Time Shipments": "N.º de entregas a tempo", "Cost of Delayed Shipments": "Custo das entregas atrasadas",
        "Cost of On Time Shipments": "Custo das entregas a tempo", "RFQ Response Days": "Dias de resposta aos pedidos de cotação",
        "RFQ Total Items": "Artigos pedidos em cotação", "RFQ Total Number": "N.º de pedidos de cotação",
        "SQ Total Items": "Artigos cotados", "SQ Total Number": "N.º de cotações", "Total Accepted Amount": "Valor aceite",
        "Total Accepted Items": "Artigos aceites", "Total Cost of Shipments": "Custo total das entregas",
        "Total Days Late": "Dias de atraso", "Total Invoiced": "Total faturado", "Total Item Days": "Dias-artigo",
        "Total Ordered": "Total encomendado", "Total Received Amount": "Valor recebido", "Total Received Items": "Artigos recebidos",
        "Total Rejected Amount": "Valor rejeitado", "Total Rejected Items": "Artigos rejeitados", "Total Shipments": "N.º de entregas",
        "Total Working Days": "Dias úteis"},
    "Financial Report Template": {
        "Financial Ratios Analysis": "Rácios financeiros", "Horizontal Balance Sheet (Columnar)": "Balanço (colunas)",
        "Horizontal Profit and Loss (Columnar)": "Demonstração de resultados (colunas)", "Standard Balance Sheet (IFRS)": "Balanço (IFRS)",
        "Standard Cash Flow Statement (IFRS)": "Fluxos de caixa (IFRS)", "Standard Profit and Loss (IFRS)": "Demonstração de resultados (IFRS)"},
    "Account Category": {
        "Cash and Cash Equivalents": "Caixa e equivalentes", "Cost of Goods Sold": "Custo das mercadorias vendidas",
        "Current Tax Liabilities": "Impostos a pagar", "Finance Costs": "Gastos financeiros", "Intangible Assets": "Ativos intangíveis",
        "Investment Income": "Rendimentos de investimentos", "Long-term Borrowings": "Financiamentos de médio e longo prazo",
        "Long-term Investments": "Investimentos de longo prazo", "Long-term Provisions": "Provisões de longo prazo",
        "Operating Expenses": "Gastos operacionais", "Other Current Assets": "Outros ativos correntes",
        "Other Current Liabilities": "Outros passivos correntes", "Other Direct Costs": "Outros custos diretos",
        "Other Non-current Assets": "Outros ativos não correntes", "Other Non-current Liabilities": "Outros passivos não correntes",
        "Other Operating Income": "Outros rendimentos operacionais", "Other Payables": "Outras contas a pagar",
        "Other Receivables": "Outras contas a receber", "Reserves and Surplus": "Reservas e resultados transitados",
        "Revenue from Operations": "Vendas e prestações de serviços", "Share Capital": "Capital social",
        "Short-term Borrowings": "Financiamentos de curto prazo", "Short-term Investments": "Investimentos de curto prazo",
        "Short-term Provisions": "Provisões de curto prazo", "Stock Assets": "Inventários", "Tangible Assets": "Ativos fixos tangíveis",
        "Tax Expense": "Imposto sobre o rendimento", "Trade Payables": "Fornecedores", "Trade Receivables": "Clientes"},
    "Market Segment": {"Lower Income": "Rendimento baixo", "Middle Income": "Rendimento médio", "Upper Income": "Rendimento alto"},
    "Sales Stage": {"Identifying Decision Makers": "Identificar quem decide", "Needs Analysis": "Análise de necessidades",
                    "Negotiation/Review": "Negociação", "Perception Analysis": "Análise de perceção",
                    "Proposal/Price Quote": "Proposta / orçamento", "Prospecting": "Prospeção", "Qualification": "Qualificação",
                    "Value Proposition": "Proposta de valor"},
    "Cost Center": {"Main": "Principal"},
    "Print Heading": {"Credit Note": "Nota de crédito", "Debit Note": "Nota de débito"},
    "Item Attribute": {"Colour": "Cor", "Size": "Tamanho"},
    "UOM Category": {"Agriculture": "Agricultura", "Area": "Área", "Density": "Densidade", "Electric Current": "Corrente elétrica",
                     "Electrical Charge": "Carga elétrica", "Energy": "Energia", "Force": "Força",
                     "Frequency and Wavelength": "Frequência e comprimento de onda", "Length": "Comprimento",
                     "Magnetic Induction": "Indução magnética", "Mass": "Massa", "Power": "Potência", "Pressure": "Pressão",
                     "Speed": "Velocidade", "Temperature": "Temperatura", "Time": "Tempo", "Volume": "Volume"},
    "UOM": {
        "Abampere": "Abampere", "Acre": "Acre", "Acre (US)": "Acre (EUA)", "Ampere": "Ampere", "Ampere-Hour": "Ampere-hora",
        "Ampere-Minute": "Ampere-minuto", "Ampere-Second": "Ampere-segundo", "Are": "Are", "Area": "Área", "Arshin": "Arshin",
        "Atmosphere": "Atmosfera", "Bar": "Bar", "Barleycorn": "Grão de cevada", "Barrel (Oil)": "Barril (petróleo)",
        "Barrel(Beer)": "Barril (cerveja)", "Biot": "Biot", "Box": "Caixa", "Btu (It)": "Btu (IT)", "Btu (Mean)": "Btu (médio)",
        "Btu (Th)": "Btu (termoquímico)", "Btu/Hour": "Btu/hora", "Btu/Minutes": "Btu/minuto", "Btu/Seconds": "Btu/segundo",
        "Bushel (UK)": "Alqueire (RU)", "Bushel (US Dry Level)": "Alqueire (EUA)", "Caballeria": "Caballería",
        "Cable Length": "Comprimento de cabo", "Cable Length (UK)": "Comprimento de cabo (RU)", "Cable Length (US)": "Comprimento de cabo (EUA)",
        "Calibre": "Calibre", "Calorie (Food)": "Caloria (alimentar)", "Calorie (It)": "Caloria (IT)", "Calorie (Mean)": "Caloria (média)",
        "Calorie (Th)": "Caloria (termoquímica)", "Calorie/Seconds": "Caloria/segundo", "Carat": "Quilate", "Celsius": "Grau Celsius",
        "Cental": "Cental", "Centiarea": "Centiare", "Centigram/Litre": "Centigrama/litro", "Centilitre": "Centilitro",
        "Centimeter": "Centímetro", "Chain": "Cadeia", "Coulomb": "Coulomb", "Cubic Centimeter": "Centímetro cúbico",
        "Cubic Decimeter": "Decímetro cúbico", "Cubic Foot": "Pé cúbico", "Cubic Inch": "Polegada cúbica", "Cubic Meter": "Metro cúbico",
        "Cubic Millimeter": "Milímetro cúbico", "Cubic Yard": "Jarda cúbica", "Cup": "Chávena", "Cycle/Second": "Ciclo/segundo",
        "Day": "Dia", "Decigram/Litre": "Decigrama/litro", "Decilitre": "Decilitro", "Decimeter": "Decímetro",
        "Dekagram/Litre": "Decagrama/litro", "Dram": "Dracma", "Dyne": "Dina", "EMU Of Charge": "UEM de carga",
        "EMU of current": "UEM de corrente", "Ells (UK)": "Vara inglesa", "Ems(Pica)": "Paica", "Erg": "Erg",
        "Fahrenheit": "Grau Fahrenheit", "Faraday": "Faraday", "Fathom": "Braça", "Fluid Ounce (UK)": "Onça líquida (RU)",
        "Fluid Ounce (US)": "Onça líquida (EUA)", "Foot": "Pé", "Foot Of Water": "Pé de água", "Foot/Minute": "Pé/minuto",
        "Foot/Second": "Pé/segundo", "Furlong": "Furlong", "Gallon (UK)": "Galão (RU)", "Gallon Dry (US)": "Galão seco (EUA)",
        "Gallon Liquid (US)": "Galão líquido (EUA)", "Gamma": "Gama", "Gauss": "Gauss", "Grain": "Grão", "Grain/Cubic Foot": "Grão/pé cúbico",
        "Grain/Gallon (UK)": "Grão/galão (RU)", "Grain/Gallon (US)": "Grão/galão (EUA)", "Gram": "Grama", "Gram-Force": "Grama-força",
        "Gram/Cubic Centimeter": "Grama/centímetro cúbico", "Gram/Cubic Meter": "Grama/metro cúbico",
        "Gram/Cubic Millimeter": "Grama/milímetro cúbico", "Gram/Litre": "Grama/litro", "Hand": "Palmo", "Hectare": "Hectare",
        "Hectogram/Litre": "Hectograma/litro", "Hectometer": "Hectómetro", "Hectopascal": "Hectopascal", "Hertz": "Hertz",
        "Horsepower": "Cavalo-vapor", "Horsepower-Hours": "Cavalo-vapor-hora", "Hour": "Hora", "Hundredweight (UK)": "Quintal inglês (RU)",
        "Hundredweight (US)": "Quintal inglês (EUA)", "Iches Of Water": "Polegadas de água", "Inch": "Polegada",
        "Inch Pound-Force": "Polegada-libra-força", "Inch/Minute": "Polegada/minuto", "Inch/Second": "Polegada/segundo",
        "Inches Of Mercury": "Polegadas de mercúrio", "Joule": "Joule", "Joule/Meter": "Joule/metro", "Kelvin": "Kelvin",
        "Kiloampere": "Quiloampere", "Kilocalorie": "Quilocaloria", "Kilocoulomb": "Quilocoulomb", "Kilogram-Force": "Quilograma-força",
        "Kilogram/Cubic Centimeter": "Quilograma/centímetro cúbico", "Kilogram/Cubic Meter": "Quilograma/metro cúbico",
        "Kilogram/Litre": "Quilograma/litro", "Kilohertz": "Quilohertz", "Kilojoule": "Quilojoule", "Kilometer": "Quilómetro",
        "Kilometer/Hour": "Quilómetro/hora", "Kilopascal": "Quilopascal", "Kilopond": "Quilopond", "Kilopound-Force": "Quilolibra-força",
        "Kilowatt": "Quilowatt", "Kilowatt-Hour": "Quilowatt-hora", "Kip": "Kip", "Knot": "Nó", "Link": "Elo", "Litre": "Litro",
        "Litre-Atmosphere": "Litro-atmosfera", "Megacoulomb": "Megacoulomb", "Megagram/Litre": "Megagrama/litro", "Megahertz": "Megahertz",
        "Megajoule": "Megajoule", "Megawatt": "Megawatt", "Meter": "Metro", "Meter Of Water": "Metro de água", "Meter/Second": "Metro/segundo",
        "Microbar": "Microbar", "Microgram": "Micrograma", "Microgram/Litre": "Micrograma/litro", "Micrometer": "Micrómetro",
        "Microsecond": "Microssegundo", "Mile": "Milha", "Mile (Nautical)": "Milha náutica", "Mile/Hour": "Milha/hora",
        "Mile/Minute": "Milha/minuto", "Mile/Second": "Milha/segundo", "Milibar": "Milibar", "Milliampere": "Miliampere",
        "Millicoulomb": "Milicoulomb", "Milligram": "Miligrama", "Milligram/Cubic Centimeter": "Miligrama/centímetro cúbico",
        "Milligram/Cubic Meter": "Miligrama/metro cúbico", "Milligram/Cubic Millimeter": "Miligrama/milímetro cúbico",
        "Milligram/Litre": "Miligrama/litro", "Millihertz": "Milihertz", "Millilitre": "Mililitro", "Millimeter": "Milímetro",
        "Millimeter Of Mercury": "Milímetro de mercúrio", "Millimeter Of Water": "Milímetro de água", "Millisecond": "Milissegundo",
        "Minute": "Minuto", "Nanocoulomb": "Nanocoulomb", "Nanogram/Litre": "Nanograma/litro", "Nanohertz": "Nanohertz",
        "Nanometer": "Nanómetro", "Nanosecond": "Nanossegundo", "Newton": "Newton", "Nos": "Unidade", "Ounce": "Onça",
        "Ounce-Force": "Onça-força", "Ounce/Cubic Foot": "Onça/pé cúbico", "Ounce/Cubic Inch": "Onça/polegada cúbica",
        "Ounce/Gallon (UK)": "Onça/galão (RU)", "Ounce/Gallon (US)": "Onça/galão (EUA)", "Pair": "Par", "Parts Per Million": "Partes por milhão",
        "Pascal": "Pascal", "Peck (UK)": "Peck (RU)", "Peck (US)": "Peck (EUA)", "Percent": "Percentagem", "Pint (UK)": "Pinta (RU)",
        "Pint (US)": "Pinta (EUA)", "Pint, Dry (US)": "Pinta seca (EUA)", "Pint, Liquid (US)": "Pinta líquida (EUA)", "Pond": "Pond",
        "Pood": "Pud", "Pound": "Libra", "Pound-Force": "Libra-força", "Pound/Cubic Foot": "Libra/pé cúbico",
        "Pound/Cubic Inch": "Libra/polegada cúbica", "Pound/Cubic Yard": "Libra/jarda cúbica", "Pound/Gallon (UK)": "Libra/galão (RU)",
        "Pound/Gallon (US)": "Libra/galão (EUA)", "Poundal": "Poundal", "Psi/1000 Feet": "Psi/1000 pés", "Quart (UK)": "Quarto (RU)",
        "Quart Dry (US)": "Quarto seco (EUA)", "Quart Liquid (US)": "Quarto líquido (EUA)", "Quintal": "Quintal", "Rod": "Vara",
        "Sazhen": "Sazhen", "Second": "Segundo", "Set": "Conjunto", "Slug": "Slug", "Slug/Cubic Foot": "Slug/pé cúbico",
        "Square Centimeter": "Centímetro quadrado", "Square Foot": "Pé quadrado", "Square Inch": "Polegada quadrada",
        "Square Kilometer": "Quilómetro quadrado", "Square Meter": "Metro quadrado", "Square Mile": "Milha quadrada",
        "Square Yard": "Jarda quadrada", "Stone": "Stone", "Tablespoon (US)": "Colher de sopa (EUA)", "Teaspoon": "Colher de chá",
        "Technical Atmosphere": "Atmosfera técnica", "Tesla": "Tesla", "Ton (Long)/Cubic Yard": "Tonelada longa/jarda cúbica",
        "Ton (Short)/Cubic Yard": "Tonelada curta/jarda cúbica", "Ton-Force (UK)": "Tonelada-força (RU)",
        "Ton-Force (US)": "Tonelada-força (EUA)", "Tonne": "Tonelada", "Tonne-Force(Metric)": "Tonelada-força (métrica)", "Torr": "Torr",
        "Unit": "Unidade", "Vara": "Vara", "Versta": "Versta", "Volt-Ampere": "Volt-ampere", "Watt": "Watt", "Watt-Hour": "Watt-hora",
        "Wavelength In Gigametres": "Comprimento de onda em gigametros", "Wavelength In Kilometres": "Comprimento de onda em quilómetros",
        "Wavelength In Megametres": "Comprimento de onda em megametros", "Week": "Semana", "Yard": "Jarda",
        "Kg": "Kg", "Month": "Mês", "Year": "Ano"},
    "Sales Taxes and Charges Template": {"Portugal Tax": "IVA Portugal 23 %"},
    "Purchase Taxes and Charges Template": {"Portugal Tax": "IVA Portugal 23 %"},
    "Item Tax Template": {"Portugal Tax": "IVA Portugal 23 %"},
}

# Plano de contas genérico do ERPNext (o nome traduz-se com o sufixo « - <sigla>» de cada empresa)
CONTAS = {
    "Accounts Payable": "Contas a pagar", "Accounts Receivable": "Contas a receber", "Accrued Expenses": "Acréscimos de gastos",
    "Accumulated Depreciation": "Depreciações acumuladas", "Administrative Expenses": "Gastos administrativos",
    "Application of Funds (Assets)": "Ativo", "Asset Received But Not Billed": "Ativos recebidos por faturar",
    "Bank Accounts": "Depósitos bancários", "Bank Charges": "Comissões bancárias", "Bank Overdraft Account": "Descobertos bancários",
    "Buildings": "Edifícios", "CWIP Account": "Investimentos em curso", "Capital Equipment": "Equipamento básico",
    "Capital Stock": "Capital social", "Cash": "Caixa", "Cash In Hand": "Caixa e equivalentes", "Commission on Sales": "Comissões de vendas",
    "Cost of Goods Sold": "Custo das mercadorias vendidas", "Creditors": "Fornecedores", "Current Assets": "Ativo corrente",
    "Current Liabilities": "Passivo corrente", "Customer Advances": "Adiantamentos de clientes", "Debtors": "Clientes",
    "Depreciation": "Depreciações", "Direct Expenses": "Gastos diretos", "Direct Income": "Rendimentos diretos",
    "Dividends Paid": "Dividendos pagos", "Duties and Taxes": "Estado e outros entes públicos", "Earnest Money": "Cauções",
    "Electronic Equipment": "Equipamento eletrónico", "Employee Advances": "Adiantamentos a colaboradores",
    "Employee Benefits Obligation": "Benefícios a colaboradores", "Entertainment Expenses": "Despesas de representação",
    "Equity": "Capital próprio", "Exchange Gain/Loss": "Diferenças de câmbio", "Expense Claims": "Despesas de colaboradores",
    "Expenses": "Gastos", "Expenses Included In Asset Valuation": "Gastos incluídos no valor dos ativos",
    "Expenses Included In Valuation": "Gastos incluídos na valorização", "Fixed Assets": "Ativos fixos",
    "Freight and Forwarding Charges": "Transportes e fretes", "Furniture and Fixtures": "Mobiliário",
    "Gain/Loss on Asset Disposal": "Ganhos/perdas na alienação de ativos", "Impairment": "Imparidades", "Income": "Rendimentos",
    "Indirect Expenses": "Gastos indiretos", "Indirect Income": "Rendimentos indiretos", "Interest Expense": "Juros suportados",
    "Interest Income": "Juros obtidos", "Interest on Fixed Deposits": "Juros de depósitos a prazo", "Investments": "Investimentos",
    "Legal Expenses": "Honorários jurídicos", "Loans (Liabilities)": "Financiamentos obtidos",
    "Loans and Advances (Assets)": "Empréstimos e adiantamentos concedidos", "Long-term Provisions": "Provisões de longo prazo",
    "Marketing Expenses": "Publicidade e marketing", "Miscellaneous Expenses": "Outros gastos", "Non-Current Liabilities": "Passivo não corrente",
    "Office Equipment": "Equipamento administrativo", "Office Maintenance Expenses": "Conservação e reparação",
    "Office Rent": "Rendas e alugueres", "Opening Balance Equity": "Saldos de abertura", "Payroll Payable": "Remunerações a pagar",
    "Plants and Machineries": "Máquinas e instalações", "Postal Expenses": "Correios", "Prepaid Expenses": "Gastos a reconhecer",
    "Print and Stationery": "Material de escritório", "Retained Earnings": "Resultados transitados",
    "Revaluation Surplus": "Excedentes de revalorização", "Round Off": "Arredondamentos", "Salary": "Remunerações",
    "Sales": "Vendas", "Sales Expenses": "Gastos comerciais", "Secured Loans": "Empréstimos com garantia",
    "Securities and Deposits": "Cauções e depósitos", "Service": "Prestações de serviços",
    "Short-term Investments": "Investimentos de curto prazo", "Short-term Provisions": "Provisões de curto prazo", "Software": "Software",
    "Source of Funds (Liabilities)": "Passivo", "Stock Adjustment": "Ajustamentos de inventário", "Stock Assets": "Inventários",
    "Stock Expenses": "Gastos de inventário", "Stock In Hand": "Mercadorias em armazém", "Stock Liabilities": "Passivos de inventário",
    "Stock Received But Not Billed": "Mercadoria recebida por faturar", "Tax Assets": "Impostos a recuperar",
    "Tax Expense": "Imposto sobre o rendimento", "Telephone Expenses": "Comunicações", "Temporary Accounts": "Contas transitórias",
    "Temporary Opening": "Abertura transitória", "Travel Expenses": "Deslocações e estadas", "Unsecured Loans": "Empréstimos sem garantia",
    "Utility Expenses": "Eletricidade, água e gás", "VAT": "IVA", "Write Off": "Anulações",
}
SUFIXO = ("Account", "Warehouse", "Cost Center", "Department", "Sales Taxes and Charges Template",
          "Purchase Taxes and Charges Template", "Item Tax Template")

# Não ganham tradução GERAL (são também texto de botões e da interface); só a interface /orbit as mostra traduzidas
SOLTAS = {"Open", "Closed", "Replied", "Resolved", "Paused", "Active", "Away", "Unavailable", "Default", "Standard", "Other",
          "Others", "Set", "Second", "Minute", "Hour", "Day", "Week", "Month", "Year", "Link", "Hand", "Area", "Unit", "Pair", "Box",
          "Bar", "Rod", "Chain", "Stone", "Cup", "Grain", "Gamma", "Knot", "Pound", "Service", "Sales", "Agent", "Customer",
          "Supplier", "Employee", "Administrator", "Guest", "All", "Analytics", "Translator", "Main", "Cash", "Size", "Time",
          "Mass", "Power", "Speed", "Volume", "Force", "Energy", "Length", "Pressure", "Density", "Temperature", "Software",
          "Income", "Expenses", "Equity", "Investments", "Depreciation", "Salary", "VAT", "Kg", "Nos", "Medium", "Low",
          "High", "Urgent", "Pending", "Approved", "Rejected", "Local", "Contract", "Commission", "Internal", "External",
          "Food", "Travel", "Calls", "Medical", "Support", "Maintenance", "Question", "Incident", "Bug", "Inventory",
          "Purchase", "Accounts", "Manufacturing", "Average", "Excellent", "Poor", "Department", "Campaign", "Reference"}


def _empresas():
    return {c.abbr for c in frappe.get_all("Company", fields=["abbr"])}


def mapa() -> dict:
    """{doctype: {nome: tradução}} com os sufixos das empresas deste tenant (para a interface e as traduções)."""
    abbrs = _empresas()
    out = {}
    for dt, m in TRAD.items():
        if not frappe.db.exists("DocType", dt):
            continue
        d = dict(m)
        if dt in SUFIXO:
            for a in abbrs:
                d.update({f"{en} - {a}": f"{pt} - {a}" for en, pt in m.items()})
        out[dt] = d
    if frappe.db.exists("DocType", "Account"):
        out["Account"] = {f"{en} - {a}": f"{pt} - {a}" for en, pt in CONTAS.items() for a in abbrs}
    return out


def _traducao(en, pt):
    nome = frappe.db.get_value("Translation", {"language": "pt", "source_text": en, "context": ("in", ("", None))}, "name")
    if nome:
        frappe.db.set_value("Translation", nome, "translated_text", pt, update_modified=False)
    else:
        frappe.get_doc({"doctype": "Translation", "language": "pt", "source_text": en, "translated_text": pt}).insert(
            ignore_permissions=True)


def acertar():
    try:
        from frappe.custom.doctype.property_setter.property_setter import make_property_setter
        m = mapa()
        feitas = set()
        for dt, d in m.items():
            if not frappe.get_meta(dt).translated_doctype:
                make_property_setter(dt, None, "translated_doctype", 1, "Check", validate_fields_for_doctype=False)
            for en, pt in d.items():
                if en == pt or en in SOLTAS or en in feitas:
                    continue
                _traducao(en, pt)
                feitas.add(en)
        frappe.db.commit()
        frappe.clear_cache()
    except Exception as e:  # noqa: BLE001 — nunca deita abaixo uma migração
        frappe.db.rollback()
        frappe.log_error(f"configuracao_pt: {e}", "orbit configuração PT")
