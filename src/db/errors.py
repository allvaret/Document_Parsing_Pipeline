"""Exceções tipadas da camada de banco (nada de falha silenciosa)."""


class DatabaseError(Exception):
    """Base dos erros da camada de banco."""


class IncompleteResultError(DatabaseError):
    """O ReportResult não tem as chaves mínimas para ser gravado."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("ReportResult incompleto, falta: " + ", ".join(missing))


class CompanyConflictError(DatabaseError):
    """CNPJ, ticker e nome apontam para empresas diferentes (ou o CNPJ diverge)."""


class InvalidCnpjError(DatabaseError):
    """CNPJ que, sem máscara, não tem 14 dígitos."""

    def __init__(self, raw: str):
        self.raw = raw
        super().__init__(f"CNPJ inválido (esperado 14 dígitos): {raw!r}")
