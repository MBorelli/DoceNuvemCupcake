"""Camada Model: entidades, regras de negócio e persistência."""
from .carrinho import Carrinho
from .cliente import Cliente
from .entrega import Entrega, calcular_frete
from .erros import ErroPagamento, ErroValidacao
from .pagamento import MetodoPagamento, Pagamento, StatusPagamento
from .pedido import Pedido, StatusPedido
from .produto import Produto

__all__ = [
    "Carrinho", "Cliente", "Entrega", "calcular_frete", "ErroPagamento", "ErroValidacao",
    "MetodoPagamento", "Pagamento", "StatusPagamento", "Pedido", "StatusPedido", "Produto",
]
