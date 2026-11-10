/* Propostas comerciais no Orçamento (orbit/propostas, 10-11-2026).
 *
 * «Adicionar por referência»: escreve-se a referência, o Orbit procura no catálogo da conta (portal) e na loja
 * da marca; à falta, há um botão para procurar na internet (gasta créditos de IA). O que vem fica num
 * formulário para rever — descrição, características, imagem (trocar ou carregar), preço, observações,
 * transporte e montagem — e só depois entra no Orçamento como linha (ou como alternativa a uma linha).
 */
frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;
		frm.add_custom_button(__("Adicionar por referência"), () => orbitPorReferencia(frm));
	},
	orbit_marca(frm) {
		// a marca escolhe a série e os textos: na proposta nova, preenche já os que estão vazios
		if (!frm.doc.orbit_marca || !frm.is_new()) return;
		frappe.db.get_doc("Brand", frm.doc.orbit_marca).then((m) => {
			const serie = (m.orbit_serie || "").toUpperCase();
			const opcoes = (frm.fields_dict.naming_series.df.options || "").split("\n");
			const alvo = opcoes.find((o) => serie && o.includes(`-${serie}-`));
			if (alvo) frm.set_value("naming_series", alvo);
			["orbit_garantia", "orbit_pagamento", "orbit_prazo", "orbit_texto_intro"].forEach((c) => {
				if (!frm.doc[c] && m[c]) frm.set_value(c, m[c]);
			});
			if (m.orbit_validade_dias && frm.doc.transaction_date)
				frm.set_value("valid_till", frappe.datetime.add_days(frm.doc.transaction_date, m.orbit_validade_dias));
			if (frappe.model.can_read("Letter Head")) {
				frappe.db.exists("Letter Head", `Timbre ${m.name}`).then((e) => e && frm.set_value("letter_head", `Timbre ${m.name}`));
			}
		});
	},
});

function orbitCaracteristicasTexto(lista) {
	return (lista || []).map((c) => (c[0] ? `${c[0]}: ${c[1]}` : c[1])).join("\n");
}

function orbitPorReferencia(frm) {
	const principais = (frm.doc.items || []).filter((l) => !l.orbit_de && !l.is_alternative && l.item_code);
	const d = new frappe.ui.Dialog({
		title: __("Adicionar por referência"),
		size: "large",
		fields: [
			{ fieldname: "referencia", fieldtype: "Data", label: __("Referência"), reqd: 1 },
			// A acção vai no próprio campo (`click`): um botão escondido não tem $input até aparecer, e ligar-lhe
			// o clique por $input.on rebentava antes de a janela abrir (10-11-2026, «não abre nenhuma janela»).
			{ fieldname: "procurar", fieldtype: "Button", label: __("Procurar"), click: () => procurar() },
			{ fieldname: "estado", fieldtype: "HTML" },
			{ fieldname: "internet", fieldtype: "Button", label: __("Procurar na internet (gasta créditos de IA)"), hidden: 1,
			  click: () => internet() },
			{ fieldname: "sec1", fieldtype: "Section Break", label: __("Produto"), hidden: 1 },
			{ fieldname: "titulo", fieldtype: "Data", label: __("Designação"), reqd: 1 },
			{ fieldname: "descricao", fieldtype: "Small Text", label: __("Descrição curta") },
			{ fieldname: "caracteristicas", fieldtype: "Small Text", label: __("Características (uma por linha, «Nome: valor»)") },
			{ fieldname: "col1", fieldtype: "Column Break" },
			{ fieldname: "imagem", fieldtype: "Attach Image", label: __("Imagem") },
			{ fieldname: "ver_imagem", fieldtype: "HTML" },
			{ fieldname: "sec2", fieldtype: "Section Break", label: __("Na proposta"), hidden: 1 },
			{ fieldname: "qtd", fieldtype: "Float", label: __("Quantidade"), default: 1, reqd: 1 },
			{ fieldname: "preco", fieldtype: "Currency", label: __("Preço unitário (sem IVA)"), reqd: 1 },
			{ fieldname: "preco_nota", fieldtype: "HTML" },
			{ fieldname: "col2", fieldtype: "Column Break" },
			{ fieldname: "transporte", fieldtype: "Currency", label: __("Transporte desta linha") },
			{ fieldname: "montagem", fieldtype: "Currency", label: __("Montagem desta linha") },
			{ fieldname: "col3", fieldtype: "Column Break" },
			{ fieldname: "alternativa_de", fieldtype: "Select", label: __("Alternativa à linha"),
			  options: [""].concat(principais.map((l) => `${l.idx} — ${l.item_code}`)),
			  description: __("Uma alternativa aparece na proposta mas não entra no total.") },
			{ fieldname: "observacoes", fieldtype: "Small Text", label: __("Observações") },
		],
		primary_action_label: __("Adicionar à proposta"),
		primary_action: (v) => orbitAdicionar(frm, d, v),
	});
	let fonte = "";
	const mostrar = (produto) => {
		["sec1", "sec2"].forEach((f) => d.set_df_property(f, "hidden", 0));
		if (!produto) {
			d.fields_dict.estado.$wrapper.html(`<p class="text-muted">${__("Não encontrada no catálogo nem na loja da marca. Pode preencher à mão ou procurar na internet.")}</p>`);
			d.set_df_property("internet", "hidden", 0);
			return;
		}
		fonte = produto.fonte || "";
		const aviso = produto.a_confirmar ? ` <b style="color:#8a5a00">${__("a confirmar")}</b>` : "";
		d.fields_dict.estado.$wrapper.html(`<p>${__("Encontrada em")}: <b>${frappe.utils.escape_html(fonte)}</b>${aviso}` +
			(produto.url ? ` · <a href="${encodeURI(produto.url)}" target="_blank" rel="noopener">${__("ver a página")}</a>` : "") + `</p>`);
		d.set_df_property("internet", "hidden", produto.a_confirmar ? 1 : 0);
		d.set_values({
			titulo: produto.titulo || "", descricao: produto.descricao || "",
			caracteristicas: orbitCaracteristicasTexto(produto.caracteristicas),
			preco: produto.preco || d.get_value("preco") || 0,
		});
		const img = (produto.imagens || [])[0];
		d.orbit_imagem_url = img || null;
		d.fields_dict.ver_imagem.$wrapper.html(img ? `<img src="${encodeURI(img)}" style="max-width:160px;max-height:160px;border:1px solid var(--border-color)">` +
			`<p class="text-muted small">${__("Imagem encontrada. Para usar outra, carregue-a acima.")}</p>` : "");
		d.fields_dict.preco_nota.$wrapper.html(produto.preco_nota ? `<p class="text-muted small">${frappe.utils.escape_html(produto.preco_nota)}</p>` : "");
	};
	const procurar = () => {
		const ref = d.get_value("referencia");
		if (!ref) return;
		d.fields_dict.estado.$wrapper.html(`<p class="text-muted">${__("A procurar…")}</p>`);
		frappe.call({ method: "orbit.propostas.referencia.procurar", args: { referencia: ref, marca: frm.doc.orbit_marca || null } })
			.then((r) => mostrar(r.message && r.message.produto));
	};
	const internet = () => {
		const ref = d.get_value("referencia");
		if (!ref) return;
		d.fields_dict.estado.$wrapper.html(`<p class="text-muted">${__("A procurar na internet… (pode levar um minuto)")}</p>`);
		frappe.call({ method: "orbit.propostas.referencia.procurar_internet", args: { referencia: ref, marca: frm.doc.orbit_marca || null } })
			.then((r) => {
				const p = r.message && r.message.produto;
				if (!p) d.fields_dict.estado.$wrapper.html(`<p class="text-muted">${__("Também não se encontrou na internet. Preencha à mão.")}</p>`);
				else mostrar(p);
			});
	};
	d.show();
}

function orbitAdicionar(frm, d, v) {
	frappe.call({
		method: "orbit.propostas.referencia.gravar_artigo",
		args: { dados: {
			referencia: v.referencia, titulo: v.titulo, descricao: v.descricao, caracteristicas: v.caracteristicas,
			imagem: v.imagem || d.orbit_imagem_url || null, marca: frm.doc.orbit_marca || null,
			fonte: (d.fields_dict.estado.$wrapper.text() || "").replace(/^.*?:\s*/, "").split("·")[0].trim(),
		} },
		freeze: true,
	}).then(async (r) => {
		const a = r.message;
		let linha;
		const idxMae = v.alternativa_de ? parseInt(v.alternativa_de, 10) : null;
		if (idxMae) {
			// a alternativa tem de ficar logo a seguir à linha principal (e às outras alternativas dela)
			let pos = idxMae;
			const linhas = frm.doc.items || [];
			while (linhas[pos] && linhas[pos].is_alternative) pos++;
			linha = frm.add_child("items");
			const lista = frm.doc.items;
			lista.splice(lista.indexOf(linha), 1);
			lista.splice(pos, 0, linha);
			lista.forEach((l, i) => (l.idx = i + 1));
		} else {
			linha = frm.add_child("items");
		}
		await frappe.model.set_value(linha.doctype, linha.name, "item_code", a.item_code);
		// o ERPNext vai buscar os dados do artigo (e o preço da tabela, 0) — esperar, senão escrevia por cima
		await new Promise((res) => frappe.after_ajax(res));
		await frappe.model.set_value(linha.doctype, linha.name, {
			qty: v.qtd || 1, rate: v.preco || 0, item_name: a.item_name, description: a.description, image: a.image,
			orbit_caracteristicas: a.orbit_caracteristicas, orbit_observacoes: v.observacoes || "",
			orbit_transporte: v.transporte || 0, orbit_montagem: v.montagem || 0, is_alternative: idxMae ? 1 : 0,
			orbit_fonte: a.orbit_fonte || "",
		});
		frm.refresh_field("items");
		d.hide();
		frappe.show_alert({ message: __("Linha adicionada: {0}", [a.item_code]), indicator: "green" });
	});
}
