class ERIApiError(Exception):
    """Exception raised for errors returned by the ITD ERI API.

    Cites: Docs/ERI API Specification_v1.1.pdf Section 5 (API Exception Details)
    """
    def __init__(
        self,
        code: str,
        desc: str,
        field_name: str | None = None,
        category: str | None = None,
        as_per_itr: object = None,
        as_computed: object = None,
        variance: object = None,
        sch_id: object = None,
    ):
        self.code = code
        self.desc = desc
        self.field_name = field_name
        # The validate/submit endpoints' errors[] entries (errCd/errFld/
        # errCtg/asPerItr/asComputed/variance/schId -- distinct from the
        # login/addClient/everify messages[] shape's code/desc/fieldName)
        # carry this extra arithmetic-mismatch detail.
        # Cites: API_SubmitFlow_v1.1.pdf Section 4.6 "Response 2: When error
        # in validation".
        self.category = category
        self.as_per_itr = as_per_itr
        self.as_computed = as_computed
        self.variance = variance
        self.sch_id = sch_id
        msg = f"[{code}] {desc}"
        if field_name:
            msg += f" (Field: {field_name})"
        if variance is not None:
            msg += f" (As-per-ITR: {as_per_itr}, As-computed: {as_computed}, Variance: {variance})"
        super().__init__(msg)
