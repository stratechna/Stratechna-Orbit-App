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
			// O Meet e o Chat entraram nesta lista a 24-09-2026: sem ela caíam na
			// rede de segurança e apareciam em «Operações», longe do Mail e do
			// Social, que são da mesma família. A rede funcionou — não se
			// perderam —, mas o sítio estava errado.
			itens: ["Frappe CRM", "Helpdesk", "Mail", "Docs", "Sign", "Events",
				"Social", "Meet", "Chat", "Wiki", "Projects",
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

	// ── Agenda ───────────────────────────────────────────────────────────────
	// Duas vistas lado a lado e não em abas: o mês responde a «quando estou
	// livre?» e o dia a «o que tenho a seguir?». Numa vista de relance, esconder
	// uma delas atrás de um clique tira-lhe a razão de existir.
	//
	// Os dois quadros desenham-se VAZIOS com a altura final e só depois se
	// enchem. Sem isso, a faixa de cima crescia quando a resposta chegasse e o
	// ecrã inteiro dava um salto — a mesma coisa que já se tinha notado quando a
	// grelha substitui a do Frappe.
	const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
		"Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];

	function quadroMes() {
		const el = document.createElement("div");
		el.className = "orbit-mes";
		const hoje = new Date();
		el.innerHTML =
			`<div class="orbit-agenda-cab">` +
			`<span class="orbit-agenda-titulo">${MESES[hoje.getMonth()]}</span>` +
			`<span class="orbit-agenda-risco"></span></div>` +
			`<div class="orbit-mes-grelha"></div>`;

		const g = el.querySelector(".orbit-mes-grelha");
		for (const d of ["S", "T", "Q", "Q", "S", "S", "D"]) {
			const c = document.createElement("span");
			c.className = "orbit-mes-dia orbit-mes-dia--cab";
			c.textContent = d;
			g.appendChild(c);
		}
		const primeiro = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
		// getDay() dá 0 ao domingo; a semana aqui começa à segunda.
		const recuo = (primeiro.getDay() + 6) % 7;
		const dias = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0).getDate();
		for (let i = 0; i < recuo; i++) {
			g.appendChild(document.createElement("span"));
		}
		for (let d = 1; d <= dias; d++) {
			const c = document.createElement("span");
			c.className = "orbit-mes-dia" + (d === hoje.getDate() ? " orbit-mes-dia--hoje" : "");
			c.dataset.dia = String(d);
			c.textContent = String(d);
			g.appendChild(c);
		}
		return el;
	}

	function quadroDia() {
		const el = document.createElement("div");
		el.className = "orbit-agenda";
		el.innerHTML =
			`<div class="orbit-agenda-cab">` +
			`<span class="orbit-agenda-titulo">${__("Hoje")}</span>` +
			`<span class="orbit-agenda-risco"></span>` +
			`<a class="orbit-agenda-marcar" href="/app/event/new">${__("Marcar reunião")}</a>` +
			`</div><div class="orbit-agenda-lista"></div>`;
		return el;
	}

	function encherAgenda(mes, dia) {
		frappe.call({ method: "orbit.agenda.resumo", type: "GET" })
			.then((r) => {
				const d = (r && r.message) || {};
				for (const n of d.ocupados || []) {
					const c = mes.querySelector(`.orbit-mes-dia[data-dia="${n}"]`);
					if (c) c.classList.add("orbit-mes-dia--ocupado");
				}
				const lista = dia.querySelector(".orbit-agenda-lista");
				lista.textContent = "";
				if (!(d.hoje || []).length) {
					const v = document.createElement("p");
					v.className = "orbit-agenda-vazio";
					// Estados diferentes, mensagens diferentes: um dia livre não
					// é a mesma coisa que o correio estar em baixo, e dizer o
					// mesmo nos dois casos escondia a avaria.
					v.textContent = d.ligado
						? __("Sem compromissos hoje.")
						: __("Agenda indisponível.");
					lista.appendChild(v);
					return;
				}
				for (const e of d.hoje) {
					const linha = document.createElement(e.meet ? "a" : "div");
					linha.className = "orbit-agenda-linha";
					if (e.meet) {
						linha.href = e.local;
						linha.target = "_blank";
					}
					linha.innerHTML =
						`<span class="orbit-agenda-hora"></span>` +
						`<span class="orbit-agenda-nome"></span>` +
						(e.meet ? `<span class="orbit-agenda-meet" title="${__("Entrar na reunião")}"></span>` : "");
					linha.querySelector(".orbit-agenda-hora").textContent =
						e.dia_inteiro ? __("dia") : e.hora;
					linha.querySelector(".orbit-agenda-nome").textContent = e.titulo;
					lista.appendChild(linha);
				}
			})
			.catch(() => {
				const lista = dia.querySelector(".orbit-agenda-lista");
				lista.innerHTML = `<p class="orbit-agenda-vazio">${__("Agenda indisponível.")}</p>`;
			});
	}

	function cabecalho() {
		const s = saudacao();
		const el = document.createElement("header");
		el.id = "orbit-saudacao";
		// A fila de pontos é o divisor da marca, o mesmo que separa secções no
		// stratechna.com. As cores são as da paleta, pela ordem em que lá estão.
		const PONTOS = ["#8a9bab", "#c8d0d8", "#5f7386", "#ea5c55", "#880000",
			"#3d5163", "#22303d"];
		el.innerHTML =
			`<div class="orbit-saudacao-texto">` +
			`<h1 class="orbit-saudacao-titulo"></h1>` +
			`<p class="orbit-saudacao-frase"></p>` +
			`<div class="orbit-saudacao-pontos" aria-hidden="true">` +
			PONTOS.map((c) => `<span style="background:${c}"></span>`).join("") +
			`</div></div>`;
		el.querySelector(".orbit-saudacao-titulo").textContent = s.titulo;
		el.querySelector(".orbit-saudacao-frase").textContent = s.frase;

		const caixa = document.createElement("div");
		caixa.className = "orbit-agenda-caixa";
		const mes = quadroMes();
		const dia = quadroDia();
		caixa.appendChild(mes);
		caixa.appendChild(dia);
		el.appendChild(caixa);
		encherAgenda(mes, dia);
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
			`<p class="orbit-rodape-frase"></p>` +
			// Seis dos componentes do Orbit são AGPL v3, e a cláusula 13 obriga a
			// oferecer o código da nossa versão a quem usa o serviço pela rede.
			// Fica por baixo de tudo e discreto — o que a licença exige é que
			// seja alcançável, não que seja vistoso.
			`<a class="orbit-rodape-licencas" href="/licencas">Licenças e código aberto</a>`;
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

	// As apps com casa própria: as que vivem fora do Frappe (link externo) e as
	// quatro que, dentro dele, são aplicações inteiras com arranque próprio.
	const APPS_PROPRIAS = new Set(["Frappe CRM", "Helpdesk", "Wiki", "Frappe HR"]);

	function eApp(icone) {
		return icone.link_type === "External" || APPS_PROPRIAS.has(icone.label);
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
		// Cada APP abre no seu próprio separador, com NOME.
		//
		// Estava incoerente: as apps de fora abriam em separador novo e as do
		// Frappe no mesmo. E `_blank` sem nome abre um separador NOVO a cada
		// clique — três cliques no Docs, três separadores iguais. Com um nome
		// por app, o primeiro clique abre e os seguintes reutilizam o que já lá
		// está, com o trabalho como estava.
		//
		// Só as apps. Os módulos do ERP (Vendas, Compras, Inventário…) são
		// páginas da MESMA aplicação e continuam a abrir aqui: um separador por
		// módulo seria uma dúzia de separadores para uma tarefa só.
		if (eApp(icone)) a.target = "orbit-" + frappe.scrub(icone.label);
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

		// Um bloco por linha, a toda a largura.
		//
		// Era uma grelha 2×2 com as colunas proporcionais ao que cada uma
		// levava. Resolvia o problema de um bloco pesado fazer crescer a
		// página, mas criava outro: com 22, 9, 7 e 9 módulos, os blocos eram
		// esticados à altura do mais alto da linha e sobravam vazios grandes —
		// mais de metade do bloco de gestão era espaço morto. E as duas colunas
		// nunca alinhavam uma com a outra.
		//
		// Empilhados, cada bloco tem a altura do que leva, todos partilham a
		// mesma grelha de colunas de símbolos, e há uma margem esquerda e uma
		// direita só. O `campo` do CSS (`auto-fill`) trata de quantos cabem por
		// linha em cada largura de ecrã.
		for (const g of grupos) {
			const el = document.createElement("div");
			el.className = "orbit-linha";
			el.appendChild(bloco(g));
			grelha.appendChild(el);
		}

		const raiz = document.createElement("div");
		raiz.id = "orbit-pagina";
		// Quantos módulos há muda o tamanho a que cabem todos num ecrã. Um
		// tenant com o Orbit inteiro tem o dobro dos módulos de um que só
		// comprou o correio e o CRM; com uma medida fixa, ou o primeiro rola ou
		// o segundo fica com símbolos perdidos no meio do branco.
		const total = grupos.reduce((s, g) => s + g.membros.length, 0);
		// A densidade era decidida pela contagem de módulos («mais de 24 =
		// apertada»). Com os blocos empilhados a altura deixa de depender só da
		// contagem — depende também de quantos cabem por linha, que muda com a
		// largura do ecrã. Passa a ser MEDIDA: desenha-se e, se a página não
		// couber, desce-se um degrau. A contagem fica como primeiro palpite,
		// para não haver um salto visível no arranque.
		porDegrau(raiz, total > 24 ? 1 : 0);
		raiz.appendChild(cabecalho());
		raiz.appendChild(grelha);
		raiz.appendChild(rodape());

		container.parentNode.insertBefore(raiz, container);
		container.classList.add("orbit-escondido");
		ajustarDensidade(raiz);
		return true;
	}

	// Se a página não cabe no ecrã, aperta. Mede-se depois de desenhar, porque
	// antes não se sabe quantos símbolos cabem por linha nesta largura.
	//
	// MEDE-SE O FUNDO DA NOSSA PÁGINA, e não o contentor que a leva.
	//
	// Duas tentativas falharam antes desta. A primeira olhava para o
	// `document.documentElement.scrollHeight`, que no desk do Frappe fica preso
	// à altura da janela — dizia sempre que cabia, com 327px a transbordar. A
	// segunda procurava o primeiro antepassado que rolasse: acertou, mas por
	// acaso — esse contentor tem 90px de `padding-bottom` próprios, que por
	// coincidência davam a mesma resposta. Num ecrã de outra altura teria
	// decidido mal.
	//
	// O fundo da nossa página contra a altura da janela é exacto, e não depende
	// de nada que o Frappe faça à volta.
	// Os degraus, do que custa menos ao que custa mais.
	//
	// A ordem é a decisão de produto que está por trás de tudo isto: este ecrã é
	// um LANÇADOR, e o que ele existe para fazer são os símbolos. Por isso
	// aperta-se primeiro o que é moldura (espaçamentos, rodapé), depois recolhe-se
	// o calendário do mês — que é orientação, e a data também está no relógio do
	// sistema — e só no fim se encolhem os símbolos, que são o que a pessoa tem
	// de acertar com o rato. Os compromissos de hoje nunca saem: não estão em
	// mais lado nenhum.
	const DEGRAUS = [
		{ densidade: "folgada", agenda: "inteira" },
		{ densidade: "apertada", agenda: "inteira" },
		{ densidade: "apertada", agenda: "recolhida" },
		{ densidade: "minima", agenda: "recolhida" },
	];

	function cabe(raiz) {
		return Math.round(raiz.getBoundingClientRect().bottom) <= window.innerHeight + 2;
	}

	function porDegrau(raiz, i) {
		raiz.dataset.densidade = DEGRAUS[i].densidade;
		raiz.dataset.agenda = DEGRAUS[i].agenda;
		raiz.dataset.degrau = String(i);
	}

	function ajustarDensidade(raiz) {
		// Um degrau por fotograma, para o browser desenhar entre cada um.
		const passo = () => {
			if (cabe(raiz)) return;
			const i = Number(raiz.dataset.degrau || 0);
			if (i >= DEGRAUS.length - 1) return;
			porDegrau(raiz, i + 1);
			requestAnimationFrame(passo);
		};
		requestAnimationFrame(passo);
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
	window.addEventListener("resize", function () {
		const raiz = document.getElementById("orbit-pagina");
		if (!raiz) return;
		// Alargar o ecrã põe mais símbolos por linha e pode voltar a caber
		// folgado; por isso tenta-se sempre o folgado primeiro.
		// Alargar ou aumentar a janela pode voltar a permitir o folgado, por
		// isso recomeça-se sempre do princípio em vez de só apertar mais.
		porDegrau(raiz, 0);
		ajustarDensidade(raiz);
	});

	if (window.frappe && frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			let n = 0;
			const r = setInterval(function () {
				if (montar() || ++n > 30) clearInterval(r);
			}, 200);
		});
	}
})();
