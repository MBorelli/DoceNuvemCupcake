"""Model Carrinho.

O carrinho fica guardado no navegador (localStorage). O servidor nunca confia nos
preços enviados pelo cliente: ele recebe apenas [{produto_id, quantidade}] e
recalcula tudo a partir do banco, ajustando quantidades ao estoque disponível.
"""
from dataclasses import dataclass, field

from ..database import id_valido
from .produto import Produto

MAX_POR_ITEM = 50


def normalizar_itens(brutos) -> dict:
    """Converte a lista recebida em {produto_id: quantidade}, descartando lixo."""
    quantidades = {}
    if not isinstance(brutos, list):
        return quantidades
    for item in brutos:
        if not isinstance(item, dict):
            continue
        try:
            produto_id = int(item.get("produto_id"))
            quantidade = int(item.get("quantidade"))
        except (TypeError, ValueError):
            continue
        if not id_valido(produto_id) or quantidade <= 0:
            continue
        quantidades[produto_id] = min(quantidades.get(produto_id, 0) + quantidade, MAX_POR_ITEM)
    return quantidades


@dataclass
class LinhaCarrinho:
    produto: Produto
    quantidade: int

    @property
    def subtotal_centavos(self) -> int:
        return self.produto.preco_centavos * self.quantidade

    def to_dict(self):
        p = self.produto
        return {
            "produto_id": p.id,
            "nome": p.nome,
            "categoria": p.categoria,
            "preco_centavos": p.preco_centavos,
            "quantidade": self.quantidade,
            "estoque": p.estoque,
            "subtotal_centavos": self.subtotal_centavos,
            "cor_cobertura": p.cor_cobertura,
            "cor_forminha": p.cor_forminha,
        }


@dataclass
class Carrinho:
    linhas: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    @classmethod
    def montar(cls, itens_brutos):
        quantidades = normalizar_itens(itens_brutos)
        produtos = Produto.buscar_varios(quantidades.keys())
        carrinho = cls()
        for produto_id, quantidade in quantidades.items():
            produto = produtos.get(produto_id)
            if produto is None or not produto.ativo:
                carrinho._avisar(produto_id, "Um item do seu carrinho não está mais disponível e foi removido.")
                continue
            if produto.estoque <= 0:
                carrinho._avisar(produto_id, f"{produto.nome} esgotou e foi removido do carrinho.")
                continue
            if quantidade > produto.estoque:
                carrinho._avisar(
                    produto_id,
                    f"Temos apenas {produto.estoque} unidade(s) de {produto.nome}; ajustamos a quantidade.",
                )
                quantidade = produto.estoque
            carrinho.linhas.append(LinhaCarrinho(produto, quantidade))
        return carrinho

    def _avisar(self, produto_id, mensagem):
        self.avisos.append({"produto_id": produto_id, "mensagem": mensagem})

    @property
    def vazio(self) -> bool:
        return not self.linhas

    @property
    def subtotal_centavos(self) -> int:
        return sum(l.subtotal_centavos for l in self.linhas)

    @property
    def quantidade_total(self) -> int:
        return sum(l.quantidade for l in self.linhas)

    def to_dict(self):
        return {
            "itens": [l.to_dict() for l in self.linhas],
            "avisos": self.avisos,
            "subtotal_centavos": self.subtotal_centavos,
            "quantidade_total": self.quantidade_total,
        }
