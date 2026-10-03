// Os doze modelos com a marca do cliente. Cada cartão abre uma campanha nova
// já com esse modelo escolhido.
frappe.pages["modelos-de-email"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Modelos de email"), single_column: true });
	const $grelha = $(`<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;padding:8px 0"></div>`)
		.appendTo(page.main);
	frappe.call("orbit.marketing.page.modelos_de_email.modelos_de_email.galeria").then(({ message }) => {
		for (const m of message || []) {
			const $c = $(`<div class="frappe-card" style="padding:0;overflow:hidden;cursor:pointer">
				<div style="height:340px;overflow:hidden;background:#f2f2f0;pointer-events:none">
					<iframe sandbox="" style="width:620px;height:1100px;border:0;transform:scale(.45);transform-origin:0 0"></iframe>
				</div>
				<div style="padding:10px 12px"><b></b><div class="text-muted small"></div></div>
			</div>`);
			$c.find("iframe")[0].srcdoc = m.html;
			$c.find("b").text(m.nome);
			$c.find(".text-muted").text(m.para);
			$c.on("click", () => frappe.new_doc("Campanha de Marketing", { modelo: m.nome }));
			$grelha.append($c);
		}
	});
};
