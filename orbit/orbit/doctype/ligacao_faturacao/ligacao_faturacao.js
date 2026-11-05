// Ligação a um programa de faturação certificado (DP8, 05-11-2026)
frappe.ui.form.on("Ligacao Faturacao", {
	refresh(frm) {
		if (frm.is_new()) return;
		const chamar = (metodo, msg) => frappe.call({
			method: `orbit.faturacao.ligacao.${metodo}`, args: { ligacao: frm.doc.name }, freeze: true,
			freeze_message: msg,
		}).then((r) => { frm.reload_doc(); if (r.message) frappe.msgprint({ title: "Resultado", message: `<pre>${frappe.utils.escape_html(JSON.stringify(r.message, null, 2))}</pre>`, wide: true }); });
		frm.add_custom_button("Testar ligação", () => chamar("testar", "A falar com o programa…"));
		frm.add_custom_button("Ler opções do programa", () => chamar("ler_opcoes", "A ler séries, taxas e métodos…"));
		frm.add_custom_button("Ensaiar (rascunho)", () => chamar("ensaiar", "A criar e apagar um rascunho…"));
	},
});
