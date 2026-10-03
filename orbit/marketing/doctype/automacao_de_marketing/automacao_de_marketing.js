// Automação de Marketing — o ciclo, e a pré-visualização com produtos de
// exemplo (os mais vendidos), porque o que cada pessoa recebe é escolhido
// para ela no momento.

frappe.ui.form.on("Automacao de Marketing", {
	refresh(frm) {
		if (frm.is_new()) return;
		const passo = (m, a, msg) => frm.call(m, a || {}).then(() => {
			if (msg) frappe.show_alert({ message: msg, indicator: "green" });
			frm.reload_doc();
		});
		frm.add_custom_button(__("Pré-visualizar"), () => frm.call("previsualizar").then(({ message: m }) => {
			const d = new frappe.ui.Dialog({ title: m.assunto, size: "extra-large" });
			d.$body.html('<iframe sandbox="" style="width:100%;height:75vh;border:0;background:#f2f2f0"></iframe>');
			d.$body.find("iframe")[0].srcdoc = m.html;
			d.show();
		}));
		const e = frm.doc.estado;
		if (e === "Rascunho") frm.add_custom_button(__("Enviar para aprovação"), () => passo("submeter", null, __("Enviada para aprovação")), __("Ciclo"));
		if (e === "Para aprovação") {
			frm.add_custom_button(__("Aprovar e activar"), () => passo("aprovar", null, __("Activa")), __("Ciclo"));
			frm.add_custom_button(__("Rejeitar"), () => frappe.prompt({ fieldname: "motivo", fieldtype: "Small Text", label: __("Motivo"), reqd: 1 },
				(v) => passo("rejeitar", { motivo: v.motivo }), __("Rejeitar")), __("Ciclo"));
		}
		if (e === "Activa") frm.add_custom_button(__("Pausar"), () => passo("pausar", null, __("Pausada")), __("Ciclo"));
		if (e === "Pausada") {
			frm.add_custom_button(__("Retomar"), () => passo("retomar", null, __("Activa")), __("Ciclo"));
			frm.add_custom_button(__("Devolver a rascunho para editar"), () => passo("editar"), __("Ciclo"));
		}
		const cores = { "Rascunho": "gray", "Para aprovação": "orange", "Activa": "green", "Pausada": "red" };
		frm.page.set_indicator(__(e), cores[e] || "gray");
		if (e !== "Rascunho") frm.set_read_only();
	},
});
