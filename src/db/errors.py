"""Exceções tipadas da camada de banco (nada de falha silenciosa)."""


class DatabaseError(Exception):
    """Base dos erros da camada de banco."""


class IncompleteResultError(DatabaseError):
    """O ReportResult não tem as chaves mínimas para ser gravado."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("ReportResult incompleto, falta: " + ", ".join(missing))
