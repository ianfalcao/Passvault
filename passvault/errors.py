"""Erros que podem ser apresentados ao usuário sem revelar dados."""


class ErroPassVault(Exception):
    """Erro de domínio com mensagem pública."""


class VaultCorrupted(ErroPassVault):
    """Formato do cofre inválido."""

    def __init__(self) -> None:
        super().__init__("Cofre corrompido ou formato incompatível.")


class InvalidMasterPassword(ErroPassVault):
    """A autenticação do conteúdo falhou."""

    def __init__(self) -> None:
        super().__init__("Senha mestra incorreta ou cofre corrompido.")


class ErroArmazenamento(ErroPassVault):
    """Falha ao acessar um arquivo."""


class SemCofre(ErroArmazenamento):
    """Cofre ausente."""


class InstanciaAberta(ErroArmazenamento):
    """Outra instância controla o cofre."""


class SessaoBloqueada(ErroPassVault):
    """Operação exige desbloqueio."""


class DadosInvalidos(ErroPassVault):
    """Entrada inválida."""


class LegacyParseError(ErroPassVault):
    """Arquivo legado ilegível ou com estrutura inválida."""
