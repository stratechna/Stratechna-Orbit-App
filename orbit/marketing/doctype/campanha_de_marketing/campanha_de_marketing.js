// Campanha de Marketing — os botões do ciclo, a pré-visualização e o teste.
//
// Os botões aparecem conforme o estado, para nunca se oferecer um passo que
// o servidor vai recusar. Aprovar não pede confirmação; rejeitar pede o
// motivo, porque é do motivo que se refaz.

// A pré-visualização ao vivo: cada alteração no formulário volta a desenhar
// a mensagem (com uma pausa, para não pedir ao servidor a cada tecla).
const desenhar = frappe.utils.debounce((frm) => {
	const campo = frm.get_field("como_fica");
	if (!campo) return;
	frappe.call({ method: "orbit.marketing.mensagem.previsualizar_rascunho", args: { doc: frm.doc }, freeze: false })
		.then(({ message: m }) => {
			if (!m) return;
			let quadro = campo.$wrapper.find("iframe")[0];
			if (!quadro) {
				campo.$wrapper.html(`<div class="text-muted small" data-assunto></div>
					<iframe sandbox="" style="width:100%;max-width:680px;height:900px;border:1px solid var(--border-color);border-radius:8px;background:#f2f2f0"></iframe>`);
				quadro = campo.$wrapper.find("iframe")[0];
			}
			campo.$wrapper.find("[data-assunto]").text(m.assunto ? __("Assunto") + ": " + m.assunto : __("Sem linha de assunto"));
			quadro.srcdoc = m.html;
		});
}, 700);
const CAMPOS_DA_MENSAGEM = ["rotulo", "modelo", "linha_assunto", "pre_cabecalho", "titulo_email", "subtitulo", "texto",
	"cta_texto", "cta_url", "imagem_topo", "destaque_texto", "destaque_subtexto", "evento_data", "evento_hora",
	"evento_local", "assinatura", "itens_add", "itens_remove", "produtos_add", "produtos_remove",
	"blocos_add", "blocos_remove", "blocos_move"];

frappe.ui.form.on("Campanha de Marketing", {
	...Object.fromEntries(CAMPOS_DA_MENSAGEM.map((c) => [c, desenhar])),
	refresh(frm) {
		desenhar(frm);
		if (frm.is_new()) return;
		if (frm.doc.estado === "Rascunho") {
			// O editor de blocos começa pelo modelo: a sequência dele, com o
			// texto que a campanha já tem. Substitui os blocos que houver.
			frm.add_custom_button(__("Montar a partir do modelo"), () => {
				const montar = () => frm.call("montar_blocos").then(() => {
					frappe.show_alert({ message: __("Blocos montados a partir de «{0}»", [frm.doc.modelo]), indicator: "green" });
					frm.reload_doc();
				});
				if ((frm.doc.blocos || []).length) {
					frappe.confirm(__("Os blocos actuais são substituídos pelos do modelo. Continuar?"), montar);
				} else {
					montar();
				}
			});
		}
		const passo = (metodo, args, msg) =>
			frm.call(metodo, args || {}).then(() => {
				if (msg) frappe.show_alert({ message: msg, indicator: "green" });
				frm.reload_doc();
			});

		frm.add_custom_button(__("Pré-visualizar"), () => {
			frm.call("previsualizar").then(({ message: m }) => {
				const d = new frappe.ui.Dialog({ title: m.assunto || __("Sem linha de assunto"), size: "extra-large" });
				const aviso = m.simula
					? `<div class="alert alert-warning">${__("Em simulação: nada sai.")}${m.falta.length ? " " + __("Falta") + ": " + m.falta.join("; ") + "." : ""}</div>`
					: "";
				d.$body.html(`${aviso}<iframe sandbox="" style="width:100%;height:75vh;border:0;background:#f2f2f0"></iframe>`);
				d.$body.find("iframe")[0].srcdoc = m.html;
				d.show();
			});
		});
		// O volume do mês, à vista de quem cria a campanha.
		frm.call("volume").then(({ message: v }) => {
			if (!v || !v.limite) return;
			const cor = v.usado >= v.limite ? "red" : v.usado > v.limite * 0.8 ? "orange" : "blue";
			frm.dashboard.add_indicator(__("Envios este mês: {0} de {1}", [v.usado, v.limite]), cor);
		});
		frm.add_custom_button(__("Quantos recebem"), () => {
			frm.call("contar").then(({ message: n }) =>
				frappe.msgprint(__("Se saísse agora: {0} destinatários.", [n])));
		});

		if (frm.doc.estado === "Rascunho") {
			frm.add_custom_button(__("Enviar para aprovação"), () => passo("submeter", null, __("Enviada para aprovação")), __("Ciclo"));
		}
		if (frm.doc.estado === "Para aprovação") {
			frm.add_custom_button(__("Aprovar"), () => passo("aprovar", null, __("Aprovada")), __("Ciclo"));
		}
		if (["Para aprovação", "Aprovada"].includes(frm.doc.estado)) {
			frm.add_custom_button(__("Rejeitar"), () => {
				frappe.prompt({ fieldname: "motivo", fieldtype: "Small Text", label: __("Motivo"), reqd: 1 },
					(v) => passo("rejeitar", { motivo: v.motivo }, __("Devolvida a rascunho")), __("Rejeitar"));
			}, __("Ciclo"));
		}
		if (["Rascunho", "Para aprovação", "Aprovada"].includes(frm.doc.estado)) {
			frm.add_custom_button(__("Marcar a saída"), () => {
				frappe.prompt({ fieldname: "quando", fieldtype: "Datetime", label: __("Sair em"), reqd: 1,
					default: frm.doc.agendar_para },
					(v) => passo("agendar", { quando: v.quando }, __("Saída marcada")), __("Marcar a saída"));
			}, __("Ciclo"));
			frm.add_custom_button(__("Enviar teste"), () => {
				frappe.prompt({ fieldname: "para", fieldtype: "Data", options: "Email", label: __("Para"), reqd: 1 },
					(v) => passo("enviar_teste", { para: v.para }, __("Teste enviado")), __("Enviar teste"));
			}, __("Ciclo"));
		}
		if (frm.doc.estado === "Pausada") {
			frm.add_custom_button(__("Retomar"), () => passo("retomar", null, __("Retomada")), __("Ciclo"));
		}
		if (!["Enviada", "Cancelada"].includes(frm.doc.estado)) {
			frm.add_custom_button(__("Cancelar"), () => passo("cancelar", null, __("Cancelada")), __("Ciclo"));
		}

		const cores = { "Rascunho": "gray", "Para aprovação": "orange", "Aprovada": "blue", "A enviar": "yellow", "Pausada": "red", "Enviada": "green", "Cancelada": "red" };
		frm.page.set_indicator(__(frm.doc.estado), cores[frm.doc.estado] || "gray");
		if (frm.doc.estado !== "Rascunho") frm.set_read_only();
	},
});

// As linhas das tabelas também redesenham.
frappe.ui.form.on("Item de Campanha", {
	titulo: desenhar, texto: desenhar, url: desenhar, imagem: desenhar,
});
frappe.ui.form.on("Bloco de Campanha", {
	tipo: desenhar, rotulo: desenhar, titulo: desenhar, subtitulo: desenhar, texto: desenhar, botao_texto: desenhar,
	url: desenhar, imagem: desenhar, imagem_2: desenhar, imagem_3: desenhar, alinhar: desenhar, fundo: desenhar,
	cor_botao: desenhar, colunas: desenhar, maximo: desenhar, posicao: desenhar, margens: desenhar,
});
frappe.ui.form.on("Produto de Campanha", {
	nome: desenhar, preco: desenhar, preco_antigo: desenhar, etiqueta: desenhar, url: desenhar, imagem: desenhar,
	descricao: desenhar,
});
