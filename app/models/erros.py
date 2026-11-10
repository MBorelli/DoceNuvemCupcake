"""Exceções de domínio usadas pelos models e tratadas pelos controllers."""


class ErroValidacao(Exception):
    """Violação de regra de negócio ou dado inválido. Carrega uma ou mais mensagens
    que podem ser exibidas diretamente ao usuário."""

    def __init__(self, erros):
        if isinstance(erros, str):
            erros = [erros]
        self.erros = list(erros)
        super().__init__(" ".join(self.erros))


class ErroPagamento(Exception):
    """O provedor de pagamento recusou a transação."""
