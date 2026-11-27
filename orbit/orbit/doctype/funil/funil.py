from frappe.model.document import Document


class Funil(Document):
    def validate(self):
        from orbit.funis import validar_funil
        validar_funil(self)
