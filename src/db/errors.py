"""Exceções tipadas da camada de banco (nada de falha silenciosa)."""


class DatabaseError(Exception):
    """Base dos erros da camada de banco."""


class DatabaseNotFoundError(DatabaseError):
    """O arquivo do banco (SQLite) não existe. A API só lê: ela nunca cria um
    banco vazio, senão serviria "nada encontrado" em silêncio."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"banco não encontrado: {path}. Rode o batch antes ou aponte DATABASE_URL."
        )


class IncompleteResultError(DatabaseError):
    """O ReportResult não tem as chaves mínimas para ser gravado."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("ReportResult incompleto, falta: " + ", ".join(missing))


class SchemaOutdatedError(DatabaseError):
    """O banco existe mas faltam colunas que os modelos exigem (schema mudou)."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            "banco desatualizado, faltam colunas: " + ", ".join(missing)
            + ". `create_all` não altera tabelas existentes: recrie o banco "
            "(até haver dado em produção; depois, Alembic)."
        )


class ReportIdentityMismatchError(DatabaseError):
    """O PDF (mesmo hash) já está gravado com outra (empresa, tipo, período).
    É aviso, não insert: a identificação do mesmo arquivo mudou entre execuções."""

    def __init__(self, file_hash: str, existing: tuple, new: tuple):
        self.file_hash = file_hash
        self.existing = existing   # (empresa, tipo, período) gravados
        self.new = new             # (empresa, tipo, período) desta execução
        super().__init__(
            f"PDF {file_hash[:12]}… já gravado como {existing}, "
            f"mas identificado agora como {new}"
        )


class StorageConstraintError(DatabaseError):
    """Violação de UNIQUE/CHECK/FK ao gravar (IntegrityError com mensagem clara).
    Quem chamou deve fazer rollback da sessão."""


class CompanyConflictError(DatabaseError):
    """CNPJ, ticker e nome apontam para empresas diferentes (ou o CNPJ diverge)."""


class ReportNotFoundError(DatabaseError):
    """Não existe relatório com este id."""

    def __init__(self, report_id: int):
        self.report_id = report_id
        super().__init__(f"relatório {report_id} não encontrado")


class InvalidCnpjError(DatabaseError):
    """CNPJ que, sem máscara, não tem 14 dígitos."""

    def __init__(self, raw: str):
        self.raw = raw
        super().__init__(f"CNPJ inválido (esperado 14 dígitos): {raw!r}")
