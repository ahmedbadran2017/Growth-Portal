"""Source Connection — controller.

Frappe requires a controller module beside every DocType JSON: on any
schema sync it calls load_doctype_module(), and a missing .py aborts
`bench migrate` for the WHOLE bench, not just this app. All 14 DocTypes
in this app shipped without one, so migrate never got past the first.

No behaviour is added here on purpose — these restore the import so the
bench can migrate. Put real validation in as each DocType needs it.
"""
from frappe.model.document import Document


class SourceConnection(Document):
	pass
