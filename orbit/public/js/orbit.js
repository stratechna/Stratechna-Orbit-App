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

// 22-11-2026: dentro do /orbit (moldura da mesma origem) a secretária mostra só o conteúdo — sem a barra de cima nem a
// barra lateral do Frappe, que já são da interface.
try { if (window.self !== window.top && window.top.location.pathname.indexOf("/orbit") === 0) document.documentElement.classList.add("orbit-embutida"); } catch (e) {}

(function () {
	const MARCA = "Stratechna Orbit";

	// Os grupos, empilhados a toda a largura pela ordem em que estão aqui.
	// (O campo `linha` é o que restou da disposição em duas colunas e já não é
	// lido; fica porque é o que diz a ordem de leitura pretendida.)
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
			// O Marketing entrou a 03-10-2026, ao lado do Social: as duas são
			// a forma de o cliente falar com quem já o conhece.
			// A linha que divide o RH entre este grupo e «Gestão» é a mesma que
			// divide os dois grupos: aqui ficam as PESSOAS (quem entra, quem
			// falta, quem faz turnos, como corre o trabalho de cada um); o
			// dinheiro que delas decorre — salários, despesas, impostos e
			// benefícios — é obrigação da casa e vai para «Gestão», ao lado da
			// facturação e dos pagamentos. Quem trata de uma coisa raramente
			// trata da outra.
			// As Propostas (10-11-2026) ficam logo a seguir ao CRM: é de lá que nascem.
			itens: ["Frappe CRM", "Propostas", "Helpdesk", "Mail", "Docs", "Sign", "Events",
				"Social", "Marketing", "Meet", "Chat", "Wiki", "Projects",
				"Frappe HR", "HR Setup", "Recruitment", "Leaves",
				"Performance", "Tenure", "Shift & Attendance"],
		},
		{
			linha: 1,
			titulo: "Gestão",
			nota: "Dinheiro, contratos e obrigações",
			itens: ["Invoicing", "Payments", "Banking", "Taxes", "Budget",
				"Financial Reports", "Accounts Setup", "Account Setup", "Subscription",
				"Share Management", "Accounting",
				"Payroll", "Expenses", "Tax & Benefits"],
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
		const ola = __({ manha: "Bom dia", tarde: "Boa tarde", noite: "Boa noite" }[periodo]);
		const lista = FRASES[periodo];
		const nome = (frappe.boot && frappe.boot.user && frappe.boot.user.first_name) || "";
		return {
			titulo: nome ? `${ola}, ${nome}.` : `${ola}.`,
			frase: __(lista[Math.floor(Math.random() * lista.length)]),
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
	// 18-10-2026: meses e dias na língua da pessoa (Intl), não escritos à mão em português.
	const LINGUA = (frappe.boot && frappe.boot.lang) || "pt";
	const LOCALE = { pt: "pt-PT", en: "en-GB", es: "es-ES", fr: "fr-FR" }[LINGUA.slice(0, 2)] || LINGUA;
	const maiuscula = (t) => t.charAt(0).toLocaleUpperCase(LOCALE) + t.slice(1);
	const MESES = Array.from({ length: 12 }, (_, m) =>
		maiuscula(new Intl.DateTimeFormat(LOCALE, { month: "long" }).format(new Date(2026, m, 1))));
	// 05-01-2026 é uma segunda-feira: daí a semana começar à segunda.
	const DIAS = Array.from({ length: 7 }, (_, d) =>
		maiuscula(new Intl.DateTimeFormat(LOCALE, { weekday: "narrow" }).format(new Date(2026, 0, 5 + d))));

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
		for (const d of DIAS) {
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

	// «Marcar reunião» (02-11-2026, Vítor): com o Booking, é lá que se marca — com cliente, sala
	// do Meet, confirmação e o evento de volta na agenda. O formulário de Evento do Frappe só
	// fechava as horas de quem o criava. Sem o Booking, fica o evento simples.
	function enderecoMarcar() {
		const apps = (frappe.boot && frappe.boot.orbit_apps) || {};
		const icones = (frappe.boot && frappe.boot.desktop_icons) || [];
		const booking = icones.find((i) => i.label === "Booking");
		const destino = booking && ((frappe.utils.get_route_for_icon && frappe.utils.get_route_for_icon(booking)) || booking.link);
		if (destino && /^https:\/\//.test(destino) && (apps.activas || []).includes("booking")) {
			return { href: destino.replace(/\/+$/, "") + "/?nova=1", fora: true };
		}
		return { href: "/app/event/new", fora: false };
	}

	function quadroDia() {
		const el = document.createElement("div");
		const marcar = enderecoMarcar();
		el.className = "orbit-agenda";
		el.innerHTML =
			`<div class="orbit-agenda-cab">` +
			`<span class="orbit-agenda-titulo">${__("Hoje")}</span>` +
			`<span class="orbit-agenda-risco"></span>` +
			`<a class="orbit-agenda-marcar" href="${marcar.href}"${marcar.fora ? ' target="_blank" rel="noopener"' : ""}>${__("Marcar reunião")}</a>` +
			`</div><div class="orbit-agenda-lista"></div>`;
		return el;
	}

	// ── Compromissos de um dia do mês, ao passar o rato ──────────────────────
	// Uma caixa só, presa ao <body> com posição fixa: dentro do quadro do mês
	// ficava cortada pela margem do cartão e por cima da faixa da saudação. Sai
	// ao rolar porque deixaria de estar ao lado do dia a que se refere.
	const MAX_NA_CAIXA = 6;
	let caixaDia = null;

	function esconderDia() {
		if (caixaDia) caixaDia.hidden = true;
	}
	window.addEventListener("scroll", esconderDia, { passive: true });
	if (frappe.router && frappe.router.on) frappe.router.on("change", esconderDia);

	function mostrarDia(celula, eventos) {
		if (!caixaDia) {
			caixaDia = document.createElement("div");
			caixaDia.className = "orbit-mes-caixa";
			caixaDia.setAttribute("role", "tooltip");
			document.body.appendChild(caixaDia);
		}
		const hoje = new Date();
		const data = new Date(hoje.getFullYear(), hoje.getMonth(), Number(celula.dataset.dia));
		caixaDia.textContent = "";
		const cab = document.createElement("div");
		cab.className = "orbit-mes-caixa-data";
		cab.textContent = maiuscula(new Intl.DateTimeFormat(LOCALE,
			{ weekday: "long", day: "numeric", month: "long" }).format(data));
		caixaDia.appendChild(cab);
		for (const e of eventos.slice(0, MAX_NA_CAIXA)) {
			const linha = document.createElement("div");
			linha.className = "orbit-agenda-linha";
			linha.innerHTML = `<span class="orbit-agenda-hora"></span><span class="orbit-agenda-nome"></span>`;
			linha.querySelector(".orbit-agenda-hora").textContent = e.dia_inteiro ? __("dia") : e.hora;
			linha.querySelector(".orbit-agenda-nome").textContent = e.titulo;
			caixaDia.appendChild(linha);
		}
		if (eventos.length > MAX_NA_CAIXA) {
			const mais = document.createElement("div");
			mais.className = "orbit-mes-caixa-mais";
			mais.textContent = __("and {0} more", [eventos.length - MAX_NA_CAIXA]);
			caixaDia.appendChild(mais);
		}
		caixaDia.hidden = false;
		// Por baixo do dia, alinhada ao centro; se não couber em baixo vai para
		// cima, e nunca sai pelas margens da janela.
		const r = celula.getBoundingClientRect();
		const w = caixaDia.offsetWidth, h = caixaDia.offsetHeight;
		let x = r.left + r.width / 2 - w / 2;
		x = Math.max(8, Math.min(x, window.innerWidth - w - 8));
		let y = r.bottom + 6;
		if (y + h > window.innerHeight - 8) y = r.top - h - 6;
		caixaDia.style.left = `${Math.round(x)}px`;
		caixaDia.style.top = `${Math.round(y)}px`;
	}

	function encherAgenda(mes, dia) {
		frappe.call({ method: "orbit.agenda.resumo", type: "GET" })
			.then((r) => {
				const d = (r && r.message) || {};
				window.__orbitAgenda = d;
				document.dispatchEvent(new CustomEvent("orbit-agenda", { detail: d }));
				for (const [n, eventos] of Object.entries(d.dias || {})) {
					const c = mes.querySelector(`.orbit-mes-dia[data-dia="${n}"]`);
					if (!c || !eventos.length) continue;
					c.classList.add("orbit-mes-dia--ocupado");
					c.tabIndex = 0;
					c.addEventListener("mouseenter", () => mostrarDia(c, eventos));
					c.addEventListener("focus", () => mostrarDia(c, eventos));
					c.addEventListener("mouseleave", esconderDia);
					c.addEventListener("blur", esconderDia);
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
				reavaliar();
			})
			.catch(() => {
				const lista = dia.querySelector(".orbit-agenda-lista");
				lista.innerHTML = `<p class="orbit-agenda-vazio">${__("Agenda indisponível.")}</p>`;
				reavaliar();
			});
	}

	function cabecalho() {
		const s = saudacao();
		const el = document.createElement("header");
		el.id = "orbit-saudacao";
		// A fila de pontos é o divisor da marca, o mesmo que separa secções no
		// stratechna.com.
		//
		// A primeira versão usava a paleta INTEIRA, cinzentos e ardósias
		// incluídos — e sobre a faixa escura os tons escuros desapareciam
		// contra o fundo. Ficavam quatro pontos a ler-se e três buracos, e
		// parecia aleatório em vez de desenhado. Agora é uma família só: o
		// acento a esbater-se, que é o que sobrevive a um fundo escuro, com o
		// último vazado como no divisor do site.
		// Sete pontos, com os das pontas VAZADOS — é o ritmo do divisor do site.
		// A variação fica toda dentro do vermelho da marca, e nenhum tom desce
		// ao escuro: sobre a faixa de ardósia, um vermelho escurecido é
		// indistinguível do fundo, e foi isso que fez a primeira fila parecer
		// aleatória. Do pálido ao cheio e outra vez ao pálido, simétrico.
		const PONTOS = ["", "#f7b3af", "#ea5c55", "#d4544e", "#ea5c55",
			"#f7b3af", ""];
		el.innerHTML =
			`<div class="orbit-saudacao-texto">` +
			`<h1 class="orbit-saudacao-titulo"></h1>` +
			`<p class="orbit-saudacao-frase"></p>` +
			`<div class="orbit-saudacao-pontos" aria-hidden="true">` +
			PONTOS.map((c) => c
				? `<span style="background:${c}"></span>`
				: `<span class="orbit-ponto-vazado"></span>`).join("") +
			`</div></div>` +
			// A marca da empresa muda-se para aqui, do rodapé. Na faixa escura
			// é a versão para fundo escuro — a regra da casa é a marca variar
			// com o fundo, não o fundo variar com a marca. Por baixo, as
			// ligações que sobraram do rodapé.
			`<div class="orbit-saudacao-marca">` +
			`<img src="/assets/orbit/img/stratechna-marca-escura.svg" alt="Stratechna">` +
			`<a href="/licencas">${__("Licenças e código aberto")}</a>` +
			`</div>`;
		el.querySelector(".orbit-saudacao-titulo").textContent = s.titulo;
		el.querySelector(".orbit-saudacao-frase").textContent = s.frase;
		return el;
	}

	// A agenda, agora em coluna à direita dos blocos.
	//
	// Estava deitada dentro da faixa, ao lado da saudação, e era ela que lhe
	// dava 185px de altura. Em coluna, a faixa fica a uma linha de marca, e os
	// ~145px que se libertam voltam para os símbolos, que estavam pequenos de
	// mais. O custo é a largura: a coluna leva 300px que os blocos deixam de
	// ter. Compensa — a altura é o recurso escasso neste ecrã, não a largura.
	function colunaAgenda() {
		const el = document.createElement("aside");
		el.className = "orbit-agenda-caixa";
		const mes = quadroMes();
		const dia = quadroDia();
		el.appendChild(mes);
		el.appendChild(dia);
		encherAgenda(mes, dia);
		return el;
	}

	// O rodapé deixou de existir como faixa própria.
	//
	// Tinha dois logótipos, uma frase de apresentação e uma ligação — 179px
	// para dizer coisas que ninguém lê num ecrã que se usa todos os dias, e a
	// competir em peso com os próprios módulos. A marca da empresa subiu para a
	// faixa escura, onde tem contraste e onde já se olha; a ligação às licenças
	// foi com ela; a frase saiu, porque quem está dentro do produto não precisa
	// que lhe expliquem o que ele é; e o logótipo do Orbit saiu porque já está
	// na barra de cima, ao lado do nome.

	function bloco(g) {
		const sec = document.createElement("section");
		sec.className = "orbit-bloco";
		sec.innerHTML =
			`<div class="orbit-bloco-cab">` +
			`<span class="orbit-bloco-titulo"></span>` +
			`<span class="orbit-bloco-risco"></span>` +
			`<span class="orbit-bloco-nota"></span>` +
			`</div>`;
		sec.querySelector(".orbit-bloco-titulo").textContent = __(g.titulo);
		sec.querySelector(".orbit-bloco-nota").textContent = g.nota ? __(g.nota) : "";

		const lista = document.createElement("div");
		lista.className = "orbit-lista";
		for (const i of g.membros) lista.appendChild(i.__virtual ? cartaoApp(i) : cartao(i));
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
	// Regra da marca (14-09-2026): os produtos vendidos à parte não se traduzem — em nenhuma língua.
	// Pelo `__()` o fr.po do Frappe dava «Courrier», «Documentation», «Événements» (18-10-2026).
	// «Frappe CRM» e «Helpdesk» passam pelo tradutor de propósito: é lá que ficam «CRM» e «Desk».
	const PRODUTOS = new Set(["CRM", "Desk", "Mail", "Docs", "Sign", "Events", "Social", "Wiki", "Meet", "Chat"]);
	const nomeVisivel = (rotulo) => (PRODUTOS.has(rotulo) ? rotulo : __(rotulo));

	function eApp(icone) {
		return icone.link_type === "External" || APPS_PROPRIAS.has(icone.label);
	}

	/* ── 22-11-2026 (Vítor, maqueta docs/orbit-interface/apps/): uma app por área ─────────────────────────────
	 * Com a interface nova ligada no tenant, os blocos passam a Trabalho · Pessoas · Gestão · Operações · Sistema. O
	 * primeiro cartão de cada bloco (a vermelho) é a app — abre-a no seu separador; os outros abrem essa app já na
	 * secção (o separador da app é reutilizado). O resto da página (saudação, fundos, logótipos) fica como estava. */
	const NOMES_APP = { crm: "CRM", desk: "Desk", marketing: "Marketing", projetos: "Projetos", rh: "RH", gestao: "Gestão", operacoes: "Operações", admin: "Administração" };
	const novaLigada = () => !!(frappe.boot.orbit_apps && frappe.boot.orbit_apps.interface_nova);
	const APP_DO_ICONE = {
		"Frappe CRM": ["crm", ""], "Helpdesk": ["desk", ""], "Marketing": ["marketing", ""], "Sign": ["crm", "#/assinaturas"],
		"Projects": ["projetos", ""], "Frappe HR": ["rh", ""],
		"HR Setup": ["rh", "#/definicoes"], "Recruitment": ["rh"], "Leaves": ["rh"], "Performance": ["rh"], "Tenure": ["rh"],
		"Shift & Attendance": ["rh"], "Payroll": ["rh"], "Expenses": ["rh"], "Tax & Benefits": ["rh"],
		"Invoicing": ["gestao"], "Payments": ["gestao"], "Banking": ["gestao"], "Taxes": ["gestao"], "Budget": ["gestao"],
		"Financial Reports": ["gestao"], "Accounts Setup": ["gestao", "#/definicoes"], "Account Setup": ["gestao", "#/definicoes"],
		"Subscription": ["gestao"], "Share Management": ["gestao"], "Accounting": ["gestao"],
		"Selling": ["operacoes"], "Buying": ["operacoes"], "Stock": ["operacoes"], "Assets": ["operacoes"], "Manufacturing": ["operacoes"],
		"Subcontracting": ["operacoes"], "Quality": ["operacoes"], "Organization": ["operacoes"],
		"ERPNext Settings": ["admin"], "Users": ["admin"], "Website": ["admin"], "Integrations": ["admin"], "Automation": ["admin"],
		"Data": ["admin"], "Email": ["admin"], "Printing": ["admin"], "System": ["admin"],
	};
	// A app inteira (sem secção): o cartão leva-a ao ecrã inicial dela.
	const E_APP = { "Frappe CRM": 1, "Helpdesk": 1, "Marketing": 1, "Projects": 1, "Frappe HR": 1 };
	function destinoNovo(icone) {
		if (!novaLigada()) return null;
		const m = APP_DO_ICONE[icone.label];
		if (!m) return null;
		let hash = m[1];
		// Módulos do ERP com barra lateral própria abrem dentro da app, nessa barra.
		if (hash === undefined) hash = icone.link_type === "Workspace Sidebar" && icone.link_to ? "#/erp-m/" + encodeURIComponent(icone.link_to) : "";
		return { app: m[0], url: "/orbit?app=" + m[0] + (hash || ""), seccao: !E_APP[icone.label] };
	}
	// Os cartões das apps que não têm ícone próprio na secretária (Gestão, Operações, Administração).
	function cartaoApp(v) {
		const a = document.createElement("a");
		a.className = "orbit-cartao orbit-cartao--app";
		a.href = "/orbit?app=" + v.__virtual;
		a.target = "orbit-" + v.__virtual;
		a.title = v.label;
		a.innerHTML = (v.__img ? `<img class="orbit-cartao-img" alt="">` : `<span class="orbit-cartao-vazio"></span>`) + `<span class="orbit-cartao-nome"></span>`;
		if (v.__img) a.querySelector(".orbit-cartao-img").src = v.__img;
		a.querySelector(".orbit-cartao-nome").textContent = v.label;
		return a;
	}
	const GRUPOS_NOVOS = [
		{ titulo: "Trabalho", nota: "Clientes, equipa e o dia-a-dia",
			itens: ["Frappe CRM", "Helpdesk", "Projects", "Mail", "Docs", "Sign", "Meet", "Chat", "Wiki", "Booking", "Marketing", "Events", "Social"] },
		{ titulo: "Pessoas", nota: "Recursos humanos",
			itens: ["Frappe HR", "Recruitment", "Leaves", "Performance", "Tenure", "Shift & Attendance", "Payroll", "Expenses", "Tax & Benefits", "HR Setup"] },
		{ titulo: "Gestão", nota: "Dinheiro, contratos e obrigações", app: ["gestao", "Gestão", "Accounting"],
			itens: ["Invoicing", "Payments", "Banking", "Taxes", "Budget", "Financial Reports", "Subscription", "Share Management", "Accounting", "Accounts Setup", "Account Setup"] },
		{ titulo: "Operações", nota: "O que se compra, produz e vende", app: ["operacoes", "Operações", "Stock"],
			itens: ["Propostas", "Selling", "Buying", "Stock", "Assets", "Manufacturing", "Subcontracting", "Quality", "Organization"] },
		{ titulo: "Sistema", nota: "Configuração da plataforma · só administradores", app: ["admin", "Administração", "System"],
			itens: ["ERPNext Settings", "Users", "Website", "Integrations", "Automation", "Data", "Email", "Printing", "System", "Support", "Home", "My Workspaces"] },
	];

	function cartao(icone) {
		const fechada = inactiva(icone);
		const a = document.createElement("a");
		a.className = fechada ? "orbit-cartao orbit-cartao--fechada" : "orbit-cartao";
		if (fechada) {
			const portal = (frappe.boot.orbit_apps && frappe.boot.orbit_apps.portal) || "#";
			a.href = portal;
			a.target = "_blank";
			a.title = __("{0} — não subscrito. Clique para subscrever.", [nomeVisivel(icone.label)]);
			a.innerHTML =
				`<img class="orbit-cartao-img" alt="">` +
				`<span class="orbit-cartao-nome"></span>` +
				`<span class="orbit-cartao-selo">${__("Subscrever")}</span>`;
			const url = frappe.utils.get_desktop_icon(icone.label, frappe.boot.desktop_icon_style);
			const fonte = (icone.icon_type !== "Folder" && url) || icone.logo_url || icone.icon_image;
			if (fonte) a.querySelector(".orbit-cartao-img").src = fonte;
			a.querySelector(".orbit-cartao-nome").textContent = nomeVisivel(icone.label);
			return a;
		}
		a.href = frappe.utils.get_route_for_icon(icone) || "#";
		const destino = destinoNovo(icone);
		if (destino) {
			a.href = destino.url;
			a.target = "orbit-" + destino.app;
			if (!destino.seccao) a.classList.add("orbit-cartao--app");
			a.title = nomeVisivel(icone.label);
			const url = frappe.utils.get_desktop_icon(icone.label, frappe.boot.desktop_icon_style);
			const fonte = (icone.icon_type !== "Folder" && url) || icone.logo_url || icone.icon_image;
			a.innerHTML = (fonte ? `<img class="orbit-cartao-img" alt="">` : `<span class="orbit-cartao-vazio"></span>`) +
				`<span class="orbit-cartao-nome"></span>` + (destino.seccao ? `<span class="orbit-cartao-app"></span>` : "");
			if (fonte) a.querySelector(".orbit-cartao-img").src = fonte;
			a.querySelector(".orbit-cartao-nome").textContent = nomeVisivel(icone.label);
			if (destino.seccao) a.querySelector(".orbit-cartao-app").textContent = NOMES_APP[destino.app] + " ›";
			return a;
		}
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
		a.title = nomeVisivel(icone.label);

		const url = frappe.utils.get_desktop_icon(icone.label, frappe.boot.desktop_icon_style);
		const fonte = (icone.icon_type !== "Folder" && url) || icone.logo_url || icone.icon_image;
		a.innerHTML =
			(fonte ? `<img class="orbit-cartao-img" alt="">` : `<span class="orbit-cartao-vazio"></span>`) +
			`<span class="orbit-cartao-nome"></span>`;
		if (fonte) a.querySelector(".orbit-cartao-img").src = fonte;
		a.querySelector(".orbit-cartao-nome").textContent = nomeVisivel(icone.label);
		return a;
	}

	/* ── Página inicial com análises (22-11-2026) ─────────────────────────────────────────────────────────────
	 * Os números vêm todos de `orbit.inicio.resumo` (já filtrados: dinheiro só para gestão/contas). Cada bloco
	 * desenha-se com o que houver — um tenant sem faturação mostra os negócios ganhos no lugar dela, sem buracos. */
	const PERIODOS = [["hoje", "Hoje"], ["semana", "Semana"], ["mes", "Mês"], ["ano", "Ano"]];
	const CHAVE_PERIODO = "orbit-inicio-periodo";
	const CHAVE_USO = "orbit-inicio-uso";
	const esc = (t) => frappe.utils.escape_html(t == null ? "" : String(t));
	function eur(v) {
		const n = Number(v || 0);
		return new Intl.NumberFormat(LOCALE, { style: "currency", currency: "EUR",
			maximumFractionDigits: Math.abs(n) >= 100 ? 0 : 2 }).format(n);
	}
	const num = (v) => new Intl.NumberFormat(LOCALE).format(Number(v || 0));
	function periodoGuardado() {
		try { const p = localStorage.getItem(CHAVE_PERIODO); return PERIODOS.some((x) => x[0] === p) ? p : "mes"; }
		catch (e) { return "mes"; }
	}
	function cabSec(titulo, extra) {
		return `<div class="oi-cab"><b>${esc(__(titulo))}</b><i></i>${extra || ""}</div>`;
	}
	// 23-11-2026: ao passar o rato, cada barra mostra o seu total (e o mês, quando se sabe)
	function spark(serie, fmt, rotulos) {
		const v = (serie || []).map(Number);
		const max = Math.max(1, ...v);
		const f = fmt || num;
		return `<div class="oi-spark">${v.map((x, i) => `<i class="${i === v.length - 1 ? "u" : ""}" data-v="${esc((rotulos && rotulos[i] ? rotulos[i] + " · " : "") + f(x))}" style="height:${Math.max(6, Math.round(100 * x / max))}%"></i>`).join("")}</div>`;
	}
	function delta(atual, anterior, rotulo) {
		if (!anterior) return `<div class="oi-d oi-neutro">${esc(__("sem termo de comparação"))}</div>`;
		const p = Math.round(100 * (atual - anterior) / anterior);
		return `<div class="oi-d ${p >= 0 ? "oi-sobe" : "oi-desce"}">${p >= 0 ? "▲" : "▼"} ${Math.abs(p)} % ${esc(rotulo || "")}</div>`;
	}
	const NOME_PERIODO = { hoje: "face a ontem", semana: "face à semana passada", mes: "face ao mês passado", ano: "face ao ano passado" };
	const TITULO_PERIODO = { hoje: "hoje", semana: "esta semana", mes: "este mês", ano: "este ano" };

	function kpis(d) {
		const p = d.periodo, out = [];
		const f = d.faturacao, c = d.crm, k = d.desk;
		if (f) {
			out.push(`<div class="oi-cartao oi-kpi"><div class="oi-t">${esc(__("Faturado"))} ${esc(__(TITULO_PERIODO[p]))}<span>${esc(f.fonte)}</span></div>` +
				`<div class="oi-v">${eur(f.faturado)}</div>${delta(f.faturado, f.anterior, __(NOME_PERIODO[p]))}${spark(f.meses.map((m) => m.valor), eur, f.meses.map((m) => MESES_CURTOS(m.mes)))}</div>`);
			out.push(`<div class="oi-cartao oi-kpi"><div class="oi-t">${esc(__("Por receber"))}<span>${f.por_receber_n} ${esc(__("faturas"))}</span></div>` +
				`<div class="oi-v">${eur(f.por_receber)}</div>` +
				`<div class="oi-d ${f.vencido ? "oi-desce" : "oi-neutro"}">${f.vencido ? esc(__("Vencido")) + " " + eur(f.vencido) + " · " + f.vencidas.length + " " + esc(__("faturas")) : esc(__("Nada vencido"))}</div>` +
				`${spark(f.meses.map((m) => m.valor), eur, f.meses.map((m) => MESES_CURTOS(m.mes)))}</div>`);
		}
		if (c) {
			out.push(`<a class="oi-cartao oi-kpi" href="/crm/deals" target="orbit-frappe_crm"><div class="oi-t">${esc(__("Negócios em aberto"))}<span>CRM</span></div>` +
				`<div class="oi-v">${num(c.abertos)}${c.abertos_valor != null ? ` <small>· ${eur(c.abertos_valor)}</small>` : ""}</div>` +
				`<div class="oi-d oi-neutro">${num(c.ganhos)} ${esc(__("ganhos"))} ${esc(__(TITULO_PERIODO[p]))}${c.ganhos_valor != null && c.ganhos ? " · " + eur(c.ganhos_valor) : ""}</div>${spark(c.serie)}</a>`);
			if (!f) out.push(`<a class="oi-cartao oi-kpi" href="/crm/deals" target="orbit-frappe_crm"><div class="oi-t">${esc(__("Negócios ganhos"))} ${esc(__(TITULO_PERIODO[p]))}<span>CRM</span></div>` +
				`<div class="oi-v">${num(c.ganhos)}${c.ganhos_valor != null && c.ganhos ? ` <small>· ${eur(c.ganhos_valor)}</small>` : ""}</div>` +
				`${delta(c.ganhos, c.ganhos_anterior, __(NOME_PERIODO[p]))}${spark(c.serie)}</a>`);
		}
		if (k) {
			out.push(`<a class="oi-cartao oi-kpi" href="/helpdesk/tickets" target="orbit-helpdesk"><div class="oi-t">${esc(__("Atendimento"))}<span>Desk</span></div>` +
				`<div class="oi-v">${num(k.abertos)} <small>${esc(__("abertos"))}</small></div>` +
				`<div class="oi-d ${k.fora_prazo ? "oi-desce" : "oi-neutro"}">${num(k.fora_prazo)} ${esc(__("fora do prazo"))}${k.primeira_resposta_h != null ? " · " + esc(__("1.ª resposta")) + " " + num(k.primeira_resposta_h) + " h" : ""}</div>${spark(k.serie)}</a>`);
		}
		if (c && c.taxa_ganho != null && out.length < 4) {
			out.push(`<div class="oi-cartao oi-kpi"><div class="oi-t">${esc(__("Taxa de ganho"))}<span>${esc(__("12 meses"))}</span></div>` +
				`<div class="oi-v">${c.taxa_ganho} %</div><div class="oi-d oi-neutro">${esc(__("negócios ganhos sobre fechados"))}</div></div>`);
		}
		return out.slice(0, 4);
	}

	const MESES_CURTOS = (iso) => new Intl.DateTimeFormat(LOCALE, { month: "short" }).format(new Date(iso + "-15")).replace(".", "");
	function grafico(d) {
		const f = d.faturacao;
		if (f) {
			const desp = d.despesas || [];
			const max = Math.max(1, ...f.meses.map((m) => m.valor), ...desp.map((m) => m.valor));
			const barras = f.meses.map((m, i) => `<div><b style="height:${Math.round(110 * m.valor / max)}px" data-v="${esc(MESES_CURTOS(m.mes) + " · " + eur(m.valor))}"></b>` +
				(desp[i] ? `<b class="e" style="height:${Math.round(110 * desp[i].valor / max)}px" data-v="${esc(__("Despesas") + " · " + eur(desp[i].valor))}"></b>` : "") + `</div>`).join("");
			const ult = f.meses[f.meses.length - 1].valor - (desp.length ? desp[desp.length - 1].valor : 0);
			return `<div class="oi-cartao"><header><h3>${esc(__(desp.length ? "Faturação e despesas" : "Faturação"))}</h3><small>${esc(__("últimos 6 meses"))}</small></header>` +
				`<div class="oi-graf"><div class="oi-barras">${barras}</div><div class="oi-meses">${f.meses.map((m) => `<span>${esc(MESES_CURTOS(m.mes))}</span>`).join("")}</div>` +
				`<div class="oi-legenda"><span><i class="oi-l1"></i>${esc(__("Faturado"))}</span>${desp.length ? `<span><i class="oi-l2"></i>${esc(__("Despesas"))}</span>` : ""}` +
				`<span class="oi-dir">${esc(__(desp.length ? "Margem do mês" : "Este mês"))} <b>${eur(ult)}</b></span></div></div></div>`;
		}
		const c = d.crm, k = d.desk;
		if (!c && !k) return "";
		const a = (c && c.serie) || [], b = (k && k.serie) || [];
		const n = Math.max(a.length, b.length), max = Math.max(1, ...a, ...b);
		const hoje = new Date();
		const meses = Array.from({ length: n }, (_, i) => { const x = new Date(hoje.getFullYear(), hoje.getMonth() - (n - 1 - i), 15); return x.toISOString().slice(0, 7); });
		const barras = meses.map((_, i) => `<div>${c ? `<b style="height:${Math.round(110 * (a[i] || 0) / max)}px" data-v="${esc(MESES_CURTOS(meses[i]) + " · " + (a[i] || 0) + " " + __("negócios"))}"></b>` : ""}${k ? `<b class="e" style="height:${Math.round(110 * (b[i] || 0) / max)}px" data-v="${esc(MESES_CURTOS(meses[i]) + " · " + (b[i] || 0) + " " + __("pedidos"))}"></b>` : ""}</div>`).join("");
		return `<div class="oi-cartao"><header><h3>${esc(__("Entradas por mês"))}</h3><small>${esc(__("últimos {0} meses", [n]))}</small></header>` +
			`<div class="oi-graf"><div class="oi-barras">${barras}</div><div class="oi-meses">${meses.map((m) => `<span>${esc(MESES_CURTOS(m))}</span>`).join("")}</div>` +
			`<div class="oi-legenda">${c ? `<span><i class="oi-l1"></i>${esc(__("Negócios novos"))}</span>` : ""}${k ? `<span><i class="oi-l2"></i>${esc(__("Pedidos no Desk"))}</span>` : ""}</div></div></div>`;
	}

	function funil(c) {
		if (!c || !c.funil.length) return "";
		const max = Math.max(1, ...c.funil.map((e) => c.abertos_valor != null ? e.valor : e.n));
		const linhas = c.funil.map((e) => {
			const base = c.abertos_valor != null ? e.valor : e.n;
			return `<div class="oi-etapa"><span>${esc(e.etapa)}</span><div class="oi-b"><i style="width:${Math.max(e.n ? 4 : 0, Math.round(100 * base / max))}%"></i></div>` +
				`<span>${e.n}${e.valor != null && e.n ? " · " + eur(e.valor) : ""}</span></div>`;
		}).join("");
		const taxa = c.taxa_ganho != null ? `<div class="oi-etapa oi-taxa"><span>${esc(__("Taxa de ganho"))}</span><div class="oi-b"><i class="v" style="width:${c.taxa_ganho}%"></i></div><span>${c.taxa_ganho} %</span></div>` : "";
		return `<a class="oi-cartao" href="/crm/deals" target="orbit-frappe_crm"><header><h3>${esc(__("Funil de vendas"))}</h3><small>${esc(__(c.abertos_valor != null ? "valor em aberto" : "negócios em aberto"))}</small></header><div class="oi-funil">${linhas}${taxa}</div></a>`;
	}

	function atencao(lista) {
		const corpo = (lista || []).length
			? lista.map((a) => `<${a.ligacao ? `a href="${esc(a.ligacao)}"` : "div"} class="oi-linha"><div class="oi-c">${esc(a.titulo)}<small>${esc(a.nota)}</small></div><span class="oi-etq oi-${esc(a.tom)}">${esc(__(a.selo))}</span></${a.ligacao ? "a" : "div"}>`).join("")
			: `<p class="oi-vazio">${esc(__("Nada pendente. Bom trabalho."))}</p>`;
		return `<div class="oi-cartao"><header><h3>${esc(__("A precisar de atenção"))}</h3><small>${(lista || []).length || ""}</small></header>${corpo}</div>`;
	}

	const IC_DIA = {
		tarefas: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m8 12 3 3 5-6"/>',
		reunioes: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
		atribuidos: '<path d="M5 15a7 7 0 1 1 14 0"/><path d="M5 15v2M19 15v2"/>',
		horas: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
	};
	function cartaoDia(ic, valor, texto, extra, href) {
		const tag = href ? `a href="${href}"` : "div";
		return `<${tag} class="oi-cartao oi-dia" data-dia="${ic}"><span class="oi-ic"><svg viewBox="0 0 24 24">${IC_DIA[ic]}</svg></span>` +
			`<div class="oi-dia-t"><b>${valor}</b><small>${texto}</small>${extra || ""}</div></${href ? "a" : "div"}>`;
	}
	function reunioesTexto(d) {
		const hoje = (d && d.hoje) || [];
		const agora = new Date(), seg = new Date(agora); seg.setDate(agora.getDate() - ((agora.getDay() + 6) % 7));
		let semana = 0;
		for (const [n, ev] of Object.entries((d && d.dias) || {})) {
			const dt = new Date(agora.getFullYear(), agora.getMonth(), Number(n));
			if (dt >= new Date(seg.getFullYear(), seg.getMonth(), seg.getDate()) && dt < new Date(seg.getFullYear(), seg.getMonth(), seg.getDate() + 7)) semana += ev.length;
		}
		return { valor: hoje.length, texto: `${esc(__(hoje.length === 1 ? "reunião hoje" : "reuniões hoje"))} · ${semana} ${esc(__("esta semana"))}` };
	}
	function meuDia(d) {
		const m = d.meu_dia || {}, k = d.desk;
		const cartoes = [];
		if (m.abertas != null) cartoes.push(cartaoDia("tarefas", m.atrasadas || m.hoje || 0,
			m.atrasadas ? `${esc(__("tarefas atrasadas"))} · ${m.hoje} ${esc(__("para hoje"))}` : `${esc(__("tarefas para hoje"))} · ${m.abertas} ${esc(__("abertas"))}`, "", "/app/todo?status=Open&allocated_to=" + encodeURIComponent(frappe.session.user)));
		const r = reunioesTexto(window.__orbitAgenda);
		cartoes.push(cartaoDia("reunioes", r.valor, r.texto));
		if (k) cartoes.push(cartaoDia("atribuidos", k.meus, esc(__("pedidos atribuídos a mim")), "", "/helpdesk/tickets"));
		if (m.horas != null) {
			const pc = Math.min(100, Math.round(100 * m.horas / (m.horas_objetivo || 40)));
			cartoes.push(cartaoDia("horas", `${num(Math.round(m.horas * 10) / 10)} h`, `${esc(__("registadas esta semana"))} · ${esc(__("objetivo"))} ${m.horas_objetivo} h`,
				`<div class="oi-prog"><i style="width:${pc}%"></i></div>`, "/app/timesheet"));
		}
		const hoje = maiuscula(new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long" }).format(new Date()));
		return cabSec("O meu dia", `<small>${esc(hoje)}</small>`) + `<div class="oi-grelha oi-n${cartoes.length}">${cartoes.join("")}</div>`;
	}

	function actividade(lista) {
		if (!(lista || []).length) return "";
		const rel = (q) => {
			const s = (Date.now() - new Date(q.replace(" ", "T")).getTime()) / 1000;
			if (s < 3600) return __("há {0} min", [Math.max(1, Math.round(s / 60))]);
			if (s < 86400) return __("há {0} h", [Math.round(s / 3600)]);
			const d = Math.round(s / 86400);
			return d === 1 ? __("ontem") : __("há {0} dias", [d]);
		};
		return cabSec("Atividade recente") + `<div class="oi-cartao">` + lista.map((a) =>
			`<a class="oi-linha" href="${esc(a.ligacao || "#")}"><div class="oi-c">${esc(a.texto)}<small>${esc(rel(a.quando))} · ${esc(a.app)}${a.valor != null ? " · " + eur(a.valor) : ""}</small></div>` +
			(a.selo ? `<span class="oi-etq oi-${a.selo === "Lead" ? "azul" : "verde"}">${esc(__(a.selo))}</span>` : "") + `</a>`).join("") + `</div>`;
	}

	function desenharNegocio(el, d, aoMudar) {
		const ks = kpis(d);
		const g = grafico(d), fu = funil(d.crm), at = atencao(d.atencao);
		if (!ks.length && !g && !fu) { el.innerHTML = ""; return; }
		const tabs = `<div class="oi-tabs">${PERIODOS.map(([k, n]) => `<button type="button" data-p="${k}" class="${k === d.periodo ? "on" : ""}">${esc(__(n))}</button>`).join("")}</div>`;
		el.className = "oi-sec";
		el.innerHTML = cabSec("O negócio", tabs) +
			`<div class="oi-grelha oi-n${ks.length}">${ks.join("")}</div>` +
			`<div class="oi-graficos">${g}${fu}${at}</div>`;
		el.querySelectorAll(".oi-tabs button").forEach((b) => b.addEventListener("click", () => aoMudar(b.dataset.p)));
	}

	// 23-11-2026 (Vítor): nada na página inicial leva aos ecrãs antigos — CRM clássico, lista de ToDo, ERP do Frappe.
	const NOVO_CRM = { deals: ["negocios", "negocio"], leads: ["leads", "lead"], contacts: ["contactos", "contacto"], organizations: ["empresas", "empresa"] };
	const NOVO_APP = { "sales-invoice": ["gestao", "Sales Invoice"], "purchase-invoice": ["gestao", "Purchase Invoice"], "item": ["operacoes", "Item"],
		"timesheet": null, "todo": null, "expense-claim": ["rh", "Expense Claim"] };
	function urlNova(u) {
		let m = /^\/crm\/(deals|leads|contacts|organizations)(?:\/([^?#]+))?/.exec(u || "");
		if (m) return "/orbit#/" + (m[2] ? NOVO_CRM[m[1]][1] + "/" + m[2] : NOVO_CRM[m[1]][0]);
		if (/^\/app\/todo/.test(u)) return "/orbit#/tarefas";
		if (/^\/app\/timesheet/.test(u)) return "/orbit?app=projetos#/tempo";
		m = /^\/app\/([a-z-]+)(?:\/([^?#]+))?/.exec(u || "");
		if (m && NOVO_APP[m[1]]) return `/orbit?app=${NOVO_APP[m[1]][0]}#/erp/${encodeURIComponent(NOVO_APP[m[1]][1])}` + (m[2] ? "/" + m[2] : "");
		return null;
	}
	function reescrever(el) {
		if (!novaLigada() || !el) return;
		el.querySelectorAll("a[href]").forEach((a) => { const n = urlNova(a.getAttribute("href")); if (n) { a.setAttribute("href", n); a.removeAttribute("target"); } });
	}

	function encherInicio(z) {
		const carregar = (periodo) => {
			z.negocio.classList.add("oi-a-carregar");
			frappe.call({ method: "orbit.inicio.resumo", args: { periodo }, type: "GET" }).then((r) => {
				const d = (r && r.message) || {};
				z.negocio.classList.remove("oi-a-carregar");
				desenharNegocio(z.negocio, d, (p) => { try { localStorage.setItem(CHAVE_PERIODO, p); } catch (e) { /* sem armazenamento */ } carregar(p); });
				z.dia.className = "oi-sec";
				z.dia.innerHTML = meuDia(d);
				z.act.innerHTML = actividade(d.atividade);
				[z.negocio, z.dia, z.act].forEach(reescrever);
				z.ultimo = d;
			}).catch(() => z.negocio.classList.remove("oi-a-carregar"));
		};
		document.addEventListener("orbit-agenda", () => { if (z.ultimo) { z.dia.innerHTML = meuDia(z.ultimo); reescrever(z.dia); } });
		carregar(periodoGuardado());
	}

	// As apps num só bloco: as mais usadas por esta pessoa à frente (contadas neste browser), as outras por baixo
	// com a área como título discreto. Sem uso registado ainda, à frente vão as apps de cada área (as de contorno).
	function lerUso() { try { return JSON.parse(localStorage.getItem(CHAVE_USO) || "{}"); } catch (e) { return {}; } }
	function contarUso(rotulo) {
		const u = lerUso(); u[rotulo] = (u[rotulo] || 0) + 1;
		try { localStorage.setItem(CHAVE_USO, JSON.stringify(u)); } catch (e) { /* sem armazenamento */ }
	}
	function appsNumBloco(grupos) {
		const sec = document.createElement("section");
		sec.className = "oi-sec oi-apps";
		sec.innerHTML = cabSec("As suas apps", `<small>${esc(__("as mais usadas primeiro"))}</small>`);
		const caixa = document.createElement("div");
		caixa.className = "oi-cartao oi-apps-caixa";
		const todos = [];
		for (const g of grupos) for (const m of g.membros) todos.push([g, m]);
		const uso = lerUso();
		const fechada = (m) => !m.__virtual && inactiva(m);
		const usadas = todos.filter(([, m]) => !fechada(m) && uso[m.label]).sort((a, b) => uso[b[1].label] - uso[a[1].label]);
		const base = todos.filter(([, m]) => !fechada(m) && (m.__virtual || E_APP[m.label] || ["Mail", "Docs", "Meet", "Chat"].includes(m.label)));
		const fav = [];
		for (const x of usadas.concat(base)) { if (!fav.includes(x[1]) && fav.length < 9) fav.push(x[1]); }
		const fila = document.createElement("div");
		fila.className = "orbit-lista oi-fav";
		for (const m of fav) fila.appendChild(m.__virtual ? cartaoApp(m) : cartao(m));
		caixa.appendChild(fila);
		for (const g of grupos) {
			const resto = g.membros.filter((m) => !fav.includes(m));
			if (!resto.length) continue;
			const t = document.createElement("div");
			t.className = "oi-grupo";
			t.textContent = __(g.titulo);
			caixa.appendChild(t);
			const l = document.createElement("div");
			l.className = "orbit-lista";
			for (const m of resto) l.appendChild(m.__virtual ? cartaoApp(m) : cartao(m));
			caixa.appendChild(l);
		}
		caixa.addEventListener("click", (e) => {
			const a = e.target.closest(".orbit-cartao");
			const nome = a && a.querySelector(".orbit-cartao-nome");
			if (nome && !a.classList.contains("orbit-cartao--fechada")) {
				const m = todos.find(([, x]) => (x.__virtual ? x.label : nomeVisivel(x.label)) === nome.textContent);
				if (m) contarUso(m[1].label);
			}
		});
		sec.appendChild(caixa);
		return sec;
	}

	function pagina(container) {
		const icones = (frappe.boot && frappe.boot.desktop_icons) || [];
		if (!icones.length) return false;
		// O Frappe pode voltar a desenhar a grelha dele (ao regressar ao ecrã de
		// apps) num contentor novo, sem a nossa classe: escondem-se todos, não só
		// o primeiro, ou a grelha de origem aparece repetida por baixo da nossa.
		if (document.getElementById("orbit-pagina")) {
			document.querySelectorAll(".desktop-container").forEach((c) => c.classList.add("orbit-escondido"));
			return true;
		}

		const visiveis = icones.filter((i) => !i.hidden && !i.parent_icon);
		const usados = new Set();
		const grupos = (novaLigada() ? GRUPOS_NOVOS : GRUPOS).map((g) => {
			const membros = g.itens
				.map((r) => visiveis.find((i) => i.label === r))
				.filter(Boolean);
			membros.forEach((m) => usados.add(m.label));
			// 22-11-2026: a app do bloco à cabeça (Gestão, Operações, Administração não têm ícone próprio).
			if (g.app && membros.length) {
				// 25-11-2026: o mesmo desenho do seletor de apps (icons/apps/<app>.svg) — antes dependia do 1.º módulo visível
				membros.unshift({ __virtual: g.app[0], label: g.app[1], __img: "/assets/orbit/icons/apps/" + g.app[0] + ".svg" });
			}
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

		// 22-11-2026 (Vítor, maqueta docs/orbit-interface/inicio/): com a interface nova, por baixo da faixa vêm
		// «O negócio», «O meu dia» e, em baixo, as apps num só bloco ao lado da agenda e da atividade. A faixa e o
		// símbolo de fundo ficam como estavam (claro e escuro); a página passa a rolar, por isso não há degraus.
		if (novaLigada()) {
			raiz.dataset.inicio = "nova";
			porDegrau(raiz, 0);
			const corpoN = document.createElement("div");
			corpoN.id = "orbit-corpo";
			corpoN.className = "oi";
			const negocio = document.createElement("div");
			const dia = document.createElement("div");
			corpoN.appendChild(negocio);
			corpoN.appendChild(dia);
			const baixo = document.createElement("div");
			baixo.className = "oi-baixo";
			baixo.appendChild(appsNumBloco(grupos));
			const lado = document.createElement("div");
			lado.className = "oi-lado";
			lado.appendChild(colunaAgenda());
			const act = document.createElement("section");
			act.className = "oi-sec oi-actividade";
			lado.appendChild(act);
			baixo.appendChild(lado);
			corpoN.appendChild(baixo);
			raiz.appendChild(corpoN);
			container.parentNode.insertBefore(raiz, container);
			document.querySelectorAll(".desktop-container").forEach((c) => c.classList.add("orbit-escondido"));
			encherInicio({ negocio, dia, act });
			return true;
		}

		// Duas colunas por baixo da faixa: os blocos à esquerda, a agenda à
		// direita. A agenda é uma coluna e não uma faixa porque a altura é o
		// recurso escasso deste ecrã — deitada, custava 185px a toda a largura;
		// de pé, não custa altura nenhuma, porque os blocos são mais altos do
		// que ela.
		const corpo = document.createElement("div");
		corpo.id = "orbit-corpo";
		corpo.appendChild(grelha);
		corpo.appendChild(colunaAgenda());
		raiz.appendChild(corpo);

		container.parentNode.insertBefore(raiz, container);
		document.querySelectorAll(".desktop-container").forEach((c) => c.classList.add("orbit-escondido"));
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
		if (raiz.dataset.inicio === "nova") return; // a página com análises rola; não se aperta
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

	// Recomeça do primeiro degrau e desce só o que for preciso.
	//
	// Tem de haver um recomeço — e não só «apertar mais» — porque a página pode
	// passar a caber: a janela cresce, ou o conteúdo encolhe. Foi o que
	// aconteceu com a agenda: ela chega por pedido ao servidor DEPOIS de a
	// página estar desenhada, e a medição feita antes disso escolhia um degrau
	// a mais do que o necessário — o ecrã ficava com os símbolos no tamanho
	// mínimo quando o degrau anterior chegava perfeitamente.
	function reavaliar() {
		const raiz = document.getElementById("orbit-pagina");
		if (!raiz || raiz.dataset.inicio === "nova") return;
		porDegrau(raiz, 0);
		ajustarDensidade(raiz);
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
	// Ao arrastar o canto da janela o `resize` dispara dezenas de vezes por
	// segundo, e cada chamada arrancaria a sua própria descida de degraus.
	// Espera-se que a pessoa pare.
	let relogioReavaliar = null;
	window.addEventListener("resize", function () {
		clearTimeout(relogioReavaliar);
		relogioReavaliar = setTimeout(reavaliar, 120);
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

// Entrada única: ao sair do desk vai-se directo ao formulário do Orbit (?nativo=1) — a sessão central já foi
// terminada no servidor (entrada_unica.ao_sair), não vale a pena perguntar ao portal (18-10-2026: dois ecrãs).
// E, ao abrir o desk, se a entrada foi pelo formulário e a ponte para o portal ficou por fazer, faz-se agora.
(function () {
	function ligar() {
		if (!window.frappe || !frappe.app || frappe.app.__orbit_saida) { return false; }
		var original = frappe.app.redirect_to_login && frappe.app.redirect_to_login.bind(frappe.app);
		frappe.app.redirect_to_login = function () {
			fetch("/api/method/orbit.entrada_unica.automatica", { credentials: "same-origin" })
				.then(function (r) { return r.json(); })
				.then(function (d) {
					if (d.message && d.message.auto) { window.location.replace("/login?nativo=1"); }
					else if (original) { original(); }
				})
				.catch(function () { if (original) { original(); } });
		};
		frappe.app.__orbit_saida = true;
		if (frappe.boot && frappe.boot.orbit_ligar_portal) { window.location.replace(frappe.boot.orbit_ligar_portal); }
		return true;
	}
	if (!ligar()) {
		var n = 0, t = setInterval(function () { if (ligar() || ++n > 50) { clearInterval(t); } }, 200);
	}
})();

// Assistência Stratechna (21-10-2026): um administrador do portal entrou neste Orbit como suporte@stratechna.pt
// (entrada_unica._assistencia). Aviso fixo com o nome de quem está; minimiza-se num ícone (Vítor, 21-10) e fica
// minimizado nas páginas seguintes. «Sair da assistência» fecha só esta sessão e volta ao portal (a sessão do
// portal continua).
(function () {
	var CHAVE = "orbit_assistencia_minimizada";
	function lerMin() { try { return localStorage.getItem(CHAVE) === "1"; } catch (e) { return false; } }
	function gravarMin(v) { try { localStorage.setItem(CHAVE, v ? "1" : "0"); } catch (e) { /* sem armazenamento */ } }
	function aviso() {
		if (!window.frappe || !frappe.boot) { return false; }
		var q = frappe.boot.orbit_assistencia;
		if (!q || document.getElementById("orbit-assistencia")) { return true; }
		var nome = q.nome || q.email;
		var d = document.createElement("div");
		d.id = "orbit-assistencia";
		d.setAttribute("role", "status");
		var cor = "#b45309";
		var base = "position:fixed;z-index:1060;color:#fff;background:" + cor + ";box-shadow:0 4px 16px rgba(0,0,0,.25);";
		var barra = base + "left:50%;bottom:14px;transform:translateX(-50%);display:flex;gap:10px;align-items:center;" +
			"padding:6px 6px 6px 16px;border-radius:999px;font-size:13px;line-height:1.3;max-width:calc(100vw - 32px)";
		var icone = base + "right:16px;bottom:16px;width:40px;height:40px;border-radius:50%;display:flex;" +
			"align-items:center;justify-content:center;cursor:pointer;padding:0;border:0";
		// boia (lucide life-buoy), em linha: sem pedidos nem bibliotecas
		var svg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
			'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/>' +
			'<path d="m4.93 4.93 4.24 4.24"/><path d="m14.83 9.17 4.24-4.24"/><path d="m14.83 14.83 4.24 4.24"/>' +
			'<path d="m9.17 14.83-4.24 4.24"/><circle cx="12" cy="12" r="4"/></svg>';
		function desenhar() {
			d.innerHTML = "";
			if (lerMin()) {
				d.style.cssText = icone;
				d.title = "Em assistência — " + nome + " (Stratechna). Clique para mostrar.";
				d.setAttribute("aria-label", d.title);
				d.setAttribute("tabindex", "0");
				d.innerHTML = svg;
				d.onclick = function () { gravarMin(false); desenhar(); };
				d.onkeydown = function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); d.onclick(); } };
				return;
			}
			d.style.cssText = barra;
			d.removeAttribute("title"); d.removeAttribute("tabindex"); d.onclick = null; d.onkeydown = null;
			var t = document.createElement("span");
			t.textContent = "Em assistência — " + nome + " (Stratechna)";
			t.style.cssText = "white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
			var b = document.createElement("button");
			b.type = "button";
			b.textContent = "Sair da assistência";
			b.style.cssText = "border:0;border-radius:999px;padding:4px 12px;background:#fff;color:" + cor + ";font-weight:600;cursor:pointer;white-space:nowrap";
			b.onclick = function () {
				b.disabled = true;
				fetch("/api/method/logout", { method: "POST", credentials: "same-origin",
					headers: { "X-Frappe-CSRF-Token": frappe.csrf_token || "" } })
					.finally(function () { window.location.replace("https://portal.stratechna.com/"); });
			};
			var m = document.createElement("button");
			m.type = "button";
			m.title = "Minimizar";
			m.setAttribute("aria-label", "Minimizar o aviso de assistência");
			m.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" ' +
				'stroke-linecap="round" aria-hidden="true"><path d="M5 12h14"/></svg>';
			m.style.cssText = "border:0;background:transparent;color:#fff;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer";
			m.onclick = function () { gravarMin(true); desenhar(); };
			d.appendChild(t); d.appendChild(b); d.appendChild(m);
		}
		desenhar();
		document.body.appendChild(d);
		return true;
	}
	if (!aviso()) {
		var n = 0, t = setInterval(function () { if (aviso() || ++n > 50) { clearInterval(t); } }, 200);
	}
})();

/* 24-11-2026 (Vítor: «orbit.stratechna.com não deixa criar app»): a secretária do Frappe (`/app`), onde se cai depois
 * de entrar, não indica manifesto nem ícone — o Chrome não oferecia «Instalar app» e o iPhone gravava sem o ícone do
 * Orbit. Pomos aqui o mesmo manifesto e ícone que a entrada, a página inicial e a interface /orbit já levam
 * (orbit/interface/push.py). */
(function () {
	try {
		var h = document.head;
		// 25-11-2026 (Vítor: barra azul na app instalada): a secretária do Frappe traz `theme-color` azul e o Chrome pinta
		// com ela a barra da janela — passa sempre ao grafite do Orbit, com ou sem manifesto nosso
		if ( h ) {
			var tc = document.querySelectorAll( 'meta[name="theme-color"]' );
			if ( tc.length ) { tc.forEach( function ( m ) { m.setAttribute( 'content', '#161a1d' ); } ); }
			else { var m = document.createElement( 'meta' ); m.setAttribute( 'name', 'theme-color' ); m.setAttribute( 'content', '#161a1d' ); h.appendChild( m ); }
		}
		if ( ! h || document.querySelector( 'link[rel="manifest"]' ) ) { return; }
		var junta = function ( tag, attrs ) { var e = document.createElement( tag ); for ( var k in attrs ) { e.setAttribute( k, attrs[ k ] ); } h.appendChild( e ); };
		junta( 'link', { rel: 'manifest', href: '/api/method/orbit.interface.push.manifesto' } );
		if ( ! document.querySelector( 'link[rel="apple-touch-icon"]' ) ) { junta( 'link', { rel: 'apple-touch-icon', href: '/assets/orbit/pwa/orbit-180.png?v=4' } ); }
		junta( 'meta', { name: 'apple-mobile-web-app-title', content: 'Orbit' } );
		junta( 'meta', { name: 'apple-mobile-web-app-capable', content: 'yes' } );
		junta( 'meta', { name: 'mobile-web-app-capable', content: 'yes' } );
		if ( ! document.querySelector( 'meta[name="theme-color"]' ) ) { junta( 'meta', { name: 'theme-color', content: '#161a1d' } ); }
	} catch ( e ) {}
}());
