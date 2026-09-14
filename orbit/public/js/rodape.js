// Rodapé do ecrã de apps do Orbit.
//
// O ecrã de apps do Frappe termina na grelha e deixa o resto da página vazio.
// Este ficheiro acrescenta por baixo o nome do produto, o que ele é, o logótipo
// da Stratechna e a atribuição ao Frappe e ao ERPNext.
//
// Só entra no ecrã de apps (a grelha), nunca noutras páginas do desk. E é
// idempotente: se o Frappe voltar a desenhar a grelha, o rodapé não se duplica.

(function () {
	const ID = "orbit-rodape";
	const ALVO = ".desktop-wrapper"; // o contentor da grelha (frappe/desk/page/desktop)

	function montar() {
		const grelha = document.querySelector(ALVO);
		if (!grelha || document.getElementById(ID)) return !!grelha;

		const marca = (window.frappe && frappe.boot && frappe.boot.app_data
			&& frappe.boot.app_data[0] && frappe.boot.app_data[0].app_logo_url) || "";

		const rodape = document.createElement("footer");
		rodape.id = ID;
		rodape.innerHTML = `
			<div class="orbit-rodape-nome">ORBIT</div>
			<p class="orbit-rodape-frase">
				A suite de gestão da Stratechna — CRM, suporte, faturação, documentos
				e correio, num só lugar.
			</p>
			${marca ? `<img class="orbit-rodape-marca" src="${marca}" alt="Stratechna">` : ""}
			<div class="orbit-rodape-base">Construído sobre Frappe e ERPNext · Software livre</div>
		`;
		grelha.parentNode.insertBefore(rodape, grelha.nextSibling);
		return true;
	}

	// A grelha é desenhada pelo router, depois do arranque. Tenta-se enquanto a
	// página for a do ecrã de apps, com um tecto para nunca ficar a girar.
	let tentativas = 0;
	const relogio = setInterval(function () {
		if (montar() || ++tentativas > 40) clearInterval(relogio);
	}, 250);

	// E ao navegar entre páginas dentro do desk, volta a tentar.
	if (window.frappe && frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			let n = 0;
			const r = setInterval(function () {
				if (montar() || ++n > 20) clearInterval(r);
			}, 250);
		});
	}
})();
