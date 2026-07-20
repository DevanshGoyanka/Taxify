class ERIApiError(Exception):
    """Exception raised for errors returned by the ITD ERI API.
    
    Cites: Docs/ERI API Specification_v1.1.pdf Section 5 (API Exception Details)
    """
    def __init__(self, code: str, desc: str, field_name: str | None = None):
        self.code = code
        self.desc = desc
        self.field_name = field_name
        msg = f"[{code}] {desc}"
        if field_name:
            msg += f" (Field: {field_name})"
        super().__init__(msg)
