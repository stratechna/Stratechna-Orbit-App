/* Ecrã de apps do Stratechna Orbit.
 *
 * O ecrã de origem do Frappe é uma grelha única, sem hierarquia: o CRM fica ao
 * lado da Subcontratação e das Definições, e a página termina na última linha de
 * ícones. Este ficheiro dá-lhe a forma de um produto:
 *
 *   - o nome da plataforma ao lado do símbolo, na barra de cima;
 *   - uma saudação que muda com a hora do dia, na mesma voz do portal;
 *   - os módulos em blocos, para a página caber num ecrã sem rolar;
 *   - o rodapé com a marca do produto, a frase e o logótipo da empresa.
 *
 * Decisão a assumir: a grelha é redesenhada por nós a partir de
 * `frappe.boot.desktop_icons`, em vez de tentarmos reorganizar a que o Frappe
 * desenha. Reorganizar a deles obrigaria a mexer nas linhas que o layout deles
 * calcula, e partia-se a cada actualização. Em troca, perde-se o modo de edição
 * do ecrã de apps — que num produto fechado não faz falta.
 *
 * Se algum dia esta grelha falhar, a do Frappe continua lá por baixo: basta não
 * lhe chamar `esconder()`.
 */

(function () {
	const MARCA = "Stratechna Orbit";

	// A frase do rodapé. Nomeia o que lá está dentro em vez de dizer «suite de
	// produtividade», que toda a gente diz e não quer dizer nada.
	const FRASE_RODAPE =
		"A suite de gestão da Stratechna — CRM, suporte, faturação, documentos " +
		"e correio, num só lugar.";

	// Os grupos, em duas linhas: em cima os dois grandes, lado a lado; em baixo
	// os dois pequenos, que só dão uma linha de símbolos e por isso levam blocos
	// mais baixos. A largura de cada bloco da linha de baixo é proporcional ao
	// que tem lá dentro, para a linha fechar de ponta a ponta como a de cima.
	//
	// Os nomes aqui são os RÓTULOS do `Desktop Icon`, não o que se lê no ecrã: o
	// CRM chama-se «Frappe CRM» e o Desk chama-se «Helpdesk» na base de dados, e
	// é a tradução que lhes dá o nome curto à frente do utilizador. Escrever aqui
	// o nome traduzido foi o que atirou os dois para fora do sítio, com o ecrã a
	// mostrar um bloco solto no fim — parecia decisão, era engano.
	//
	// Um módulo que não esteja em lista nenhuma cai em «Operações», para que uma
	// app nova nunca desapareça do ecrã.
	const GRUPOS = [
		{
			linha: 1,
			titulo: "Trabalho",
			nota: "Clientes, equipa e o dia-a-dia",
			// Os módulos do RH ficam com a app do RH. Estiveram em «Operações» e
			// lia-se mal: o ícone do RH num bloco e o processamento salarial
			// noutro, quando um se abre a partir do outro.
			itens: ["Frappe CRM", "Helpdesk", "Mail", "Docs", "Sign", "Events",
				"Social", "Wiki", "Projects",
				"Frappe HR", "HR Setup", "Recruitment", "Leaves", "Payroll",
				"Expenses", "Performance", "Tenure", "Shift & Attendance",
				"Tax & Benefits"],
		},
		{
			linha: 1,
			titulo: "Gestão",
			nota: "Dinheiro, contratos e obrigações",
			itens: ["Invoicing", "Payments", "Banking", "Taxes", "Budget",
				"Financial Reports", "Accounts Setup", "Account Setup", "Subscription",
				"Share Management", "Accounting"],
		},
		{
			linha: 2,
			titulo: "Operações",
			nota: "O que se compra, produz e vende",
			itens: ["Selling", "Buying", "Stock", "Assets", "Manufacturing",
				"Subcontracting", "Quality", "Organization"],
		},
		{
			linha: 2,
			titulo: "Sistema",
			nota: "Configuração da plataforma",
			itens: ["ERPNext Settings", "Users", "Website", "Integrations",
				"Automation", "Data", "Email", "Printing", "System", "Support",
				"Home", "My Workspaces"],
		},
	];

	// ── Saudação ─────────────────────────────────────────────────────────────
	// Mesma voz do portal: cumprimento pela hora, seguido de uma frase curta.
	const FRASES = {
		manha: [
			"O café ainda está quente — vamos a isso.",
			"Hoje é um bom dia para fazer coisas boas.",
			"Começar cedo é meio caminho andado.",
			"A agenda não se gere sozinha, mas quase.",
			"Outro dia, outra oportunidade de fazer bem feito.",
		],
		tarde: [
			"A tarde ainda tem muito para dar.",
			"Metade do dia feito, a melhor metade começa agora.",
			"O pico da produtividade está aí — aproveite.",
			"Um passo de cada vez ainda é andar para a frente.",
			"Feito é sempre melhor que perfeito.",
		],
		noite: [
			"O trabalho bem feito não precisa de pressa.",
			"Ainda a postos? Que seja por pouco tempo.",
			"Amanhã também é dia — mas se é agora, force.",
			"As melhores decisões tomam-se com a cabeça descansada.",
			"Nenhum email foi alguma vez tão urgente quanto parecia.",
		],
	};

	function saudacao() {
		const h = new Date().getHours();
		const periodo = h >= 6 && h < 13 ? "manha" : h >= 13 && h < 20 ? "tarde" : "noite";
		const ola = { manha: "Bom dia", tarde: "Boa tarde", noite: "Boa noite" }[periodo];
		const lista = FRASES[periodo];
		const nome = (frappe.boot && frappe.boot.user && frappe.boot.user.first_name) || "";
		return {
			titulo: nome ? `${ola}, ${nome}.` : `${ola}.`,
			frase: lista[Math.floor(Math.random() * lista.length)],
		};
	}

	// ── Peças ────────────────────────────────────────────────────────────────
	// A página mede-se contra o ecrã, e para isso precisa de saber quanto ocupa a
	// barra de cima. Medida, não adivinhada: um valor fixo deixava a página uns
	// pixéis mais alta do que o ecrã e punha barra de rolamento numa página que
	// devia caber inteira.
	function medirTopo() {
		const barra = document.querySelector(".desktop-navbar") ||
			document.querySelector(".navbar");
		const h = barra ? Math.round(barra.getBoundingClientRect().height) : 60;
		document.documentElement.style.setProperty("--orbit-topo", h + "px");
	}

	function marcaNaBarra() {
		const casa = document.querySelector(".desktop-navbar .navbar-home");
		if (!casa || casa.querySelector(".orbit-marca-nome")) return;
		const nome = document.createElement("span");
		nome.className = "orbit-marca-nome";
		nome.textContent = MARCA;
		casa.appendChild(nome);
	}

	function cabecalho() {
		const s = saudacao();
		const el = document.createElement("header");
		el.id = "orbit-saudacao";
		el.innerHTML =
			`<h1 class="orbit-saudacao-titulo"></h1>` +
			`<p class="orbit-saudacao-frase"></p>`;
		el.querySelector(".orbit-saudacao-titulo").textContent = s.titulo;
		el.querySelector(".orbit-saudacao-frase").textContent = s.frase;
		return el;
	}

	// O rodapé responde a três coisas pedidas depois de o ver no ecrã: a marca do
	// produto tinha ficado pequena de mais, faltava o logótipo da empresa e
	// faltava a frase que estava na versão anterior.
	function rodape() {
		const el = document.createElement("footer");
		el.id = "orbit-rodape";
		el.innerHTML =
			`<div class="orbit-rodape-marcas">` +
			`<img class="orbit-rodape-produto" src="/assets/orbit/img/stratechna.svg" alt="${MARCA}">` +
			`<span class="orbit-rodape-risco"></span>` +
			`<img class="orbit-rodape-empresa orbit-so-claro" src="/assets/orbit/img/stratechna-marca.svg" alt="Stratechna">` +
			`<img class="orbit-rodape-empresa orbit-so-escuro" src="/assets/orbit/img/stratechna-marca-escura.svg" alt="Stratechna">` +
			`</div>` +
			`<p class="orbit-rodape-frase"></p>`;
		el.querySelector(".orbit-rodape-frase").textContent = FRASE_RODAPE;
		return el;
	}

	function bloco(g) {
		const sec = document.createElement("section");
		sec.className = "orbit-bloco";
		sec.innerHTML =
			`<div class="orbit-bloco-cab">` +
			`<span class="orbit-bloco-titulo"></span>` +
			`<span class="orbit-bloco-risco"></span>` +
			`<span class="orbit-bloco-nota"></span>` +
			`</div>`;
		sec.querySelector(".orbit-bloco-titulo").textContent = g.titulo;
		sec.querySelector(".orbit-bloco-nota").textContent = g.nota || "";

		const lista = document.createElement("div");
		lista.className = "orbit-lista";
		for (const i of g.membros) lista.appendChild(cartao(i));
		sec.appendChild(lista);
		return sec;
	}

	// As apps que o cliente não subscreveu não desaparecem: ficam a cinzento e
	// levam ao portal. Esconder deixava o cliente sem saber que existem e a nós
	// sem a venda; e como a grelha é o catálogo, o catálogo tem de estar todo lá.
	//
	// Isto é a VISTA. Quem não tem a app não a tem mesmo — as do Frappe nem
	// sequer estão instaladas no site, e as de fora não estão aprovisionadas.
	// O cinzento não é o cadeado.
	function inactiva(icone) {
		const m = (frappe.boot && frappe.boot.orbit_apps && frappe.boot.orbit_apps.inactivas) || {};
		return m[icone.label] || null;
	}

	function cartao(icone) {
		const fechada = inactiva(icone);
		const a = document.createElement("a");
		a.className = fechada ? "orbit-cartao orbit-cartao--fechada" : "orbit-cartao";
		if (fechada) {
			const portal = (frappe.boot.orbit_apps && frappe.boot.orbit_apps.portal) || "#";
			a.href = portal;
			a.target = "_blank";
			a.title = __("{0} — não subscrito. Clique para subscrever.", [__(icone.label)]);
			a.innerHTML =
				`<img class="orbit-cartao-img" alt="">` +
				`<span class="orbit-cartao-nome"></span>` +
				`<span class="orbit-cartao-selo">${__("Subscrever")}</span>`;
			const url = frappe.utils.get_desktop_icon(icone.label, frappe.boot.desktop_icon_style);
			const fonte = (icone.icon_type !== "Folder" && url) || icone.logo_url || icone.icon_image;
			if (fonte) a.querySelector(".orbit-cartao-img").src = fonte;
			a.querySelector(".orbit-cartao-nome").textContent = __(icone.label);
			return a;
		}
		a.href = frappe.utils.get_route_for_icon(icone) || "#";
		if (icone.link_type === "External") a.target = "_blank";
		a.title = __(icone.label);

		const url = frappe.utils.get_desktop_icon(icone.label, frappe.boot.desktop_icon_style);
		const fonte = (icone.icon_type !== "Folder" && url) || icone.logo_url || icone.icon_image;
		a.innerHTML =
			(fonte ? `<img class="orbit-cartao-img" alt="">` : `<span class="orbit-cartao-vazio"></span>`) +
			`<span class="orbit-cartao-nome"></span>`;
		if (fonte) a.querySelector(".orbit-cartao-img").src = fonte;
		a.querySelector(".orbit-cartao-nome").textContent = __(icone.label);
		return a;
	}

	function pagina(container) {
		const icones = (frappe.boot && frappe.boot.desktop_icons) || [];
		if (!icones.length) return false;
		if (document.getElementById("orbit-pagina")) return true;

		const visiveis = icones.filter((i) => !i.hidden && !i.parent_icon);
		const usados = new Set();
		const grupos = GRUPOS.map((g) => {
			const membros = g.itens
				.map((r) => visiveis.find((i) => i.label === r))
				.filter(Boolean);
			membros.forEach((m) => usados.add(m.label));
			return { ...g, membros };
		}).filter((g) => g.membros.length);

		// O que não está em lista nenhuma junta-se a «Operações» em vez de abrir
		// um bloco «Mais» só para si. A rede de segurança mantém-se — um módulo
		// novo continua a aparecer sem ninguém mexer aqui —, mas deixa de haver
		// um bloco sem nome próprio a desequilibrar a linha de baixo.
		const sobras = visiveis.filter((i) => !usados.has(i.label));
		if (sobras.length) {
			const operacoes = grupos.find((g) => g.titulo === "Operações");
			if (operacoes) operacoes.membros.push(...sobras);
			// Se «Operações» não tiver nenhum módulo visível, nem sequer existe
			// na lista — e aí as sobras precisam de sítio, ou desapareciam do
			// ecrã, que é exactamente o que isto existe para evitar.
			else grupos.push({ linha: 2, titulo: "Operações",
				nota: "O que se compra, produz e vende", membros: sobras });
		}

		const grelha = document.createElement("div");
		grelha.id = "orbit-grelha";

		const linhas = [1, 2].map((n) => grupos.filter((g) => g.linha === n)).filter((l) => l.length);

		// As colunas são as mesmas em todas as linhas — para um bloco de baixo
		// ficar exactamente por baixo do de cima — mas a largura de cada coluna
		// é proporcional ao que essa coluna leva no total. A coluna dos módulos
		// de trabalho carrega mais do dobro da de gestão, e com colunas iguais
		// ficava com mais uma linha de símbolos do que o resto: a página crescia
		// por causa de um bloco só.
		const peso = [];
		for (const linha of linhas) {
			linha.forEach((g, i) => {
				peso[i] = (peso[i] || 0) + g.membros.length;
			});
		}
		// O mínimo impede que uma coluna com um módulo fique fina de mais para o
		// próprio título do bloco.
		const colunas = peso.map((n) => `minmax(0, ${Math.max(n, 4)}fr)`).join(" ");

		for (const linha of linhas) {
			const el = document.createElement("div");
			el.className = "orbit-linha";
			el.style.gridTemplateColumns = colunas;
			for (const g of linha) el.appendChild(bloco(g));
			grelha.appendChild(el);
		}

		const raiz = document.createElement("div");
		raiz.id = "orbit-pagina";
		// Quantos módulos há muda o tamanho a que cabem todos num ecrã. Um
		// tenant com o Orbit inteiro tem o dobro dos módulos de um que só
		// comprou o correio e o CRM; com uma medida fixa, ou o primeiro rola ou
		// o segundo fica com símbolos perdidos no meio do branco.
		const total = grupos.reduce((s, g) => s + g.membros.length, 0);
		raiz.dataset.densidade = total > 24 ? "apertada" : "folgada";
		raiz.appendChild(cabecalho());
		raiz.appendChild(grelha);
		raiz.appendChild(rodape());

		container.parentNode.insertBefore(raiz, container);
		container.classList.add("orbit-escondido");
		return true;
	}

	// ── Arranque ─────────────────────────────────────────────────────────────
	function montar() {
		const container = document.querySelector(".desktop-container");
		if (!container) return false;
		marcaNaBarra();
		const feito = pagina(container);
		if (feito) medirTopo();
		return feito;
	}

	let tentativas = 0;
	const relogio = setInterval(function () {
		if (montar() || ++tentativas > 60) clearInterval(relogio);
	}, 200);

	window.addEventListener("resize", medirTopo);

	if (window.frappe && frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			let n = 0;
			const r = setInterval(function () {
				if (montar() || ++n > 30) clearInterval(r);
			}, 200);
		});
	}
})();
