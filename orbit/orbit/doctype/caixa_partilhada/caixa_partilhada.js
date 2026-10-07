// A lista de caixas vem do servidor de correio, pelo portal.
//
// **O campo não é de texto livre.** Escrever o endereço à mão deixava criar
// mapeamentos para caixas que não existem — o erro só aparecia mais tarde, na
// sincronização, longe de quem o cometeu.
frappe.ui.form.on('Caixa Partilhada', {
  refresh(frm) {
    frm.set_query('caixa', () => ({
      query: 'orbit.orbit.doctype.caixa_partilhada.caixa_partilhada.caixas_existentes',
    }));
    frm.set_df_property(
      'senha_original', 'description',
      frm.is_new()
        ? 'A senha com que se entra nesta caixa. Confirmada e esquecida — não fica guardada.'
        : 'Só é pedida quando se dá acesso a mais alguém. Tirar acesso não precisa dela.');
  },
});
