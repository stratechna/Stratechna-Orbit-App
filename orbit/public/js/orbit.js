/* Ecrã de apps do Stratechna Orbit.
 *
 * O ecrã de origem do Frappe é uma grelha única, sem hierarquia: o CRM fica ao
 * lado da Subcontratação e das Definições, e a página termina na última linha de
 * ícones. Este ficheiro dá-lhe a forma de um produto:
 *
 *   - o nome da plataforma ao lado do símbolo, na barra de cima;
 *   - uma saudação que muda com a hora do dia, na mesma voz do portal;
 *   - os módulos agrupados por função, com um título discreto em cada grupo;
 *   - o logótipo da Stratechna a fechar a página.
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

	// Os grupos, por ordem de aparição. Um módulo que não esteja em lista nenhuma
	// cai em "Mais" — assim uma app nova nunca desaparece do ecrã.
	const GRUPOS = [
		{
			titulo: "Trabalho",
			nota: "O dia-a-dia com clientes e equipa",
			itens: ["CRM", "Desk", "Mail", "Docs", "Sign", "Events", "Social", "Wiki", "Projects"],
		},
		{
			titulo: "Gestão",
			nota: "Dinheiro, contratos e obrigações",
			itens: ["Faturação", "Invoicing", "Payments", "Banking", "Taxes", "Budget",
				"Financial Reports", "Accounts Setup", "Subscription", "Share Management",
				"Accounting"],
		},
		{
			titulo: "Operações",
			nota: "O que se compra, produz e vende",
			itens: ["Selling", "Buying", "Stock", "Assets", "Manufacturing",
				"Subcontracting", "Quality", "Organização", "Organization"],
		},
		{ titulo: "Pessoas", nota: "Equipa e recursos humanos", itens: ["RH", "Frappe HR"] },
		{
			titulo: "Sistema",
			nota: "Configuração da plataforma",
			itens: ["Definições ...", "ERPNext Settings", "Framework", "Orbit", "Home",
				"My Workspaces"],
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
	function marcaNaBarra() {
		const casa = document.querySelector(".desktop-navbar .navbar-home");
		if (!casa || casa.querySelector(".orbit-marca-nome")) return;
		const nome = document.createElement("span");
		nome.className = "orbit-marca-nome";
		nome.textContent = MARCA;
		casa.appendChild(nome);
	}

	function cabecalho(container) {
		if (document.getElementById("orbit-saudacao")) return;
		const s = saudacao();
		const el = document.createElement("div");
		el.id = "orbit-saudacao";
		el.innerHTML =
			`<h1 class="orbit-saudacao-titulo"></h1>` +
			`<p class="orbit-saudacao-frase"></p>`;
		el.querySelector(".orbit-saudacao-titulo").textContent = s.titulo;
		el.querySelector(".orbit-saudacao-frase").textContent = s.frase;
		container.parentNode.insertBefore(el, container);
	}

	function rodape(container) {
		if (document.getElementById("orbit-rodape")) return;
		const el = document.createElement("footer");
		el.id = "orbit-rodape";
		el.innerHTML = `<img class="orbit-rodape-marca" src="/assets/orbit/img/stratechna.svg" alt="Stratechna">`;
		container.parentNode.insertBefore(el, container.nextSibling);
	}

	function grelha(container) {
		const icones = (frappe.boot && frappe.boot.desktop_icons) || [];
		if (!icones.length) return false;
		if (document.getElementById("orbit-grelha")) return true;

		const visiveis = icones.filter((i) => !i.hidden && !i.parent_icon);
		const usados = new Set();
		const grupos = GRUPOS.map((g) => {
			const membros = g.itens
				.map((r) => visiveis.find((i) => i.label === r))
				.filter(Boolean);
			membros.forEach((m) => usados.add(m.label));
			return { ...g, membros };
		});
		const sobras = visiveis.filter((i) => !usados.has(i.label));
		if (sobras.length) grupos.push({ titulo: "Mais", nota: "", membros: sobras });

		const raiz = document.createElement("div");
		raiz.id = "orbit-grelha";
		for (const g of grupos) {
			if (!g.membros.length) continue;
			const sec = document.createElement("section");
			sec.className = "orbit-seccao";
			const cab = document.createElement("div");
			cab.className = "orbit-seccao-cab";
			cab.innerHTML = `<span class="orbit-seccao-titulo"></span><span class="orbit-seccao-risco"></span>`;
			cab.querySelector(".orbit-seccao-titulo").textContent = g.titulo;
			if (g.nota) {
				const nota = document.createElement("span");
				nota.className = "orbit-seccao-nota";
				nota.textContent = g.nota;
				cab.appendChild(nota);
			}
			sec.appendChild(cab);

			const lista = document.createElement("div");
			lista.className = "orbit-lista";
			for (const i of g.membros) lista.appendChild(cartao(i));
			sec.appendChild(lista);
			raiz.appendChild(sec);
		}

		container.parentNode.insertBefore(raiz, container);
		container.classList.add("orbit-escondido");
		return true;
	}

	function cartao(icone) {
		const a = document.createElement("a");
		a.className = "orbit-cartao";
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

	// ── Arranque ─────────────────────────────────────────────────────────────
	function montar() {
		const container = document.querySelector(".desktop-container");
		if (!container) return false;
		marcaNaBarra();
		if (!grelha(container)) return false;
		cabecalho(document.getElementById("orbit-grelha"));
		rodape(document.getElementById("orbit-grelha"));
		return true;
	}

	let tentativas = 0;
	const relogio = setInterval(function () {
		if (montar() || ++tentativas > 60) clearInterval(relogio);
	}, 200);

	if (window.frappe && frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			let n = 0;
			const r = setInterval(function () {
				if (montar() || ++n > 30) clearInterval(r);
			}, 200);
		});
	}
})();
