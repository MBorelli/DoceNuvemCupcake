"""Model Pedido: criação do pedido eletrônico e seu ciclo de vida.

Fluxo de status:
    aguardando_pagamento -> pago -> em_preparo -> saiu_para_entrega -> entregue
    (aguardando_pagamento | pago) -> cancelado
"""
from dataclasses import dataclass
from functools import cached_property

from ..database import agora, get_db, id_valido
from .carrinho import Carrinho
from .entrega import Entrega, calcular_frete
from .erros import ErroValidacao
from .pagamento import GatewayPagamentoSimulado, MetodoPagamento, Pagamento, StatusPagamento


class StatusPedido:
    AGUARDANDO_PAGAMENTO = "aguardando_pagamento"
    PAGO = "pago"
    EM_PREPARO = "em_preparo"
    SAIU_PARA_ENTREGA = "saiu_para_entrega"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"

    ROTULOS = {
        AGUARDANDO_PAGAMENTO: "Aguardando pagamento",
        PAGO: "Pago",
        EM_PREPARO: "Em preparo",
        SAIU_PARA_ENTREGA: "Saiu para entrega",
        ENTREGUE: "Entregue",
        CANCELADO: "Cancelado",
    }
    FLUXO = [AGUARDANDO_PAGAMENTO, PAGO, EM_PREPARO, SAIU_PARA_ENTREGA, ENTREGUE]
    TRANSICOES = {
        AGUARDANDO_PAGAMENTO: {PAGO, CANCELADO},
        PAGO: {EM_PREPARO, CANCELADO},
        EM_PREPARO: {SAIU_PARA_ENTREGA},
        SAIU_PARA_ENTREGA: {ENTREGUE},
        ENTREGUE: set(),
        CANCELADO: set(),
    }
    DESCRICOES = {
        AGUARDANDO_PAGAMENTO: "Pedido recebido. Aguardando confirmação do pagamento.",
        PAGO: "Pagamento confirmado.",
        EM_PREPARO: "Seus cupcakes estão sendo preparados.",
        SAIU_PARA_ENTREGA: "Pedido saiu para entrega.",
        ENTREGUE: "Pedido entregue. Bom apetite!",
        CANCELADO: "Pedido cancelado.",
    }

    @classmethod
    def rotulo(cls, status):
        return cls.ROTULOS.get(status, status)


@dataclass
class ItemPedido:
    produto_id: int
    nome_produto: str
    preco_unitario_centavos: int
    quantidade: int

    @property
    def subtotal_centavos(self):
        return self.preco_unitario_centavos * self.quantidade


def _registrar_historico(db, pedido_id, status, descricao):
    db.execute(
        "INSERT INTO historico_pedido (pedido_id, status, descricao, criado_em) VALUES (?, ?, ?, ?)",
        (pedido_id, status, descricao, agora()),
    )


@dataclass
class Pedido:
    id: int
    cliente_id: int
    status: str
    subtotal_centavos: int
    frete_centavos: int
    total_centavos: int
    observacoes: str | None
    criado_em: str
    cliente_nome: str | None = None
    metodo_pagamento: str | None = None
    status_pagamento: str | None = None

    _CONSULTA = """
        SELECT p.*, c.nome AS cliente_nome, pg.metodo AS metodo_pagamento,
               pg.status AS status_pagamento
          FROM pedidos p
          JOIN clientes c ON c.id = p.cliente_id
          LEFT JOIN pagamentos pg ON pg.pedido_id = p.id
    """

    # ---------------------------------------------------------------- criação
    @classmethod
    def criar(cls, cliente_id, itens, endereco, metodo_pagamento, dados_pagamento=None,
              observacoes="", gateway=None):
        """Cria o pedido de forma transacional: valida carrinho e endereço, calcula
        frete, baixa estoque, registra entrega e processa o pagamento. Qualquer falha
        (inclusive pagamento recusado) desfaz tudo."""
        carrinho = Carrinho.montar(itens)
        if carrinho.avisos:
            raise ErroValidacao([a["mensagem"] for a in carrinho.avisos]
                                + ["Revise seu carrinho antes de finalizar."])
        if carrinho.vazio:
            raise ErroValidacao("Seu carrinho está vazio.")
        if metodo_pagamento not in MetodoPagamento.TODOS:
            raise ErroValidacao("Escolha uma forma de pagamento.")

        dados_entrega = Entrega.validar_endereco(endereco)
        frete = calcular_frete(dados_entrega["cep"], carrinho.subtotal_centavos)
        total = carrinho.subtotal_centavos + frete.valor_centavos
        observacoes = (observacoes or "").strip()[:500] or None
        gateway = gateway or GatewayPagamentoSimulado()

        db = get_db()
        try:
            cur = db.execute(
                """INSERT INTO pedidos (cliente_id, status, subtotal_centavos, frete_centavos,
                       total_centavos, observacoes, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cliente_id, StatusPedido.AGUARDANDO_PAGAMENTO, carrinho.subtotal_centavos,
                 frete.valor_centavos, total, observacoes, agora()),
            )
            pedido_id = cur.lastrowid

            for linha in carrinho.linhas:
                p = linha.produto
                # Baixa atômica: só baixa se ainda houver estoque suficiente.
                baixou = db.execute(
                    "UPDATE produtos SET estoque = estoque - ? WHERE id = ? AND estoque >= ?",
                    (linha.quantidade, p.id, linha.quantidade),
                ).rowcount
                if not baixou:
                    raise ErroValidacao(f"O estoque de {p.nome} acabou de mudar. Revise seu carrinho.")
                db.execute(
                    """INSERT INTO itens_pedido (pedido_id, produto_id, nome_produto,
                           preco_unitario_centavos, quantidade)
                       VALUES (?, ?, ?, ?, ?)""",
                    (pedido_id, p.id, p.nome, p.preco_centavos, linha.quantidade),
                )

            Entrega.criar(db, pedido_id, dados_entrega, frete)
            _registrar_historico(db, pedido_id, StatusPedido.AGUARDANDO_PAGAMENTO,
                                 StatusPedido.DESCRICOES[StatusPedido.AGUARDANDO_PAGAMENTO])

            resultado = gateway.processar(metodo_pagamento, total, dados_pagamento or {})
            Pagamento.registrar(db, pedido_id, metodo_pagamento, total, resultado)
            if resultado.status == StatusPagamento.APROVADO:
                db.execute("UPDATE pedidos SET status = ? WHERE id = ?", (StatusPedido.PAGO, pedido_id))
                _registrar_historico(db, pedido_id, StatusPedido.PAGO, "Pagamento aprovado pela operadora do cartão.")
            db.commit()
        except Exception:
            db.rollback()
            raise
        return cls.buscar_por_id(pedido_id)

    # ---------------------------------------------------------- ciclo de vida
    @property
    def rotulo_status(self):
        return StatusPedido.rotulo(self.status)

    @property
    def etapa_atual(self) -> int:
        return StatusPedido.FLUXO.index(self.status) if self.status in StatusPedido.FLUXO else -1

    @property
    def proximos_status(self) -> list:
        permitidos = StatusPedido.TRANSICOES.get(self.status, set())
        ordem = StatusPedido.FLUXO + [StatusPedido.CANCELADO]
        return [s for s in ordem if s in permitidos]

    @property
    def pode_ser_cancelado_pelo_cliente(self) -> bool:
        return self.status in (StatusPedido.AGUARDANDO_PAGAMENTO, StatusPedido.PAGO)

    def alterar_status(self, novo_status, descricao=None):
        if novo_status not in StatusPedido.TRANSICOES.get(self.status, set()):
            raise ErroValidacao(
                f"Não é possível mudar o pedido de '{StatusPedido.rotulo(self.status)}' "
                f"para '{StatusPedido.rotulo(novo_status)}'."
            )
        db = get_db()
        try:
            alterou = db.execute(
                "UPDATE pedidos SET status = ? WHERE id = ? AND status = ?",
                (novo_status, self.id, self.status),
            ).rowcount
            if not alterou:
                raise ErroValidacao("O pedido foi alterado por outra pessoa. Recarregue a página.")

            if novo_status == StatusPedido.PAGO:
                Pagamento.atualizar_status(db, self.id, StatusPagamento.APROVADO)
            elif novo_status == StatusPedido.SAIU_PARA_ENTREGA:
                codigo = Entrega.registrar_despacho(db, self.id)
                descricao = descricao or f"Pedido saiu para entrega. Código de rastreio: {codigo}."
            elif novo_status == StatusPedido.CANCELADO:
                for item in self.itens:
                    db.execute("UPDATE produtos SET estoque = estoque + ? WHERE id = ?",
                               (item.quantidade, item.produto_id))
                pagamento = self.pagamento
                if pagamento:
                    Pagamento.atualizar_status(
                        db, self.id,
                        StatusPagamento.ESTORNADO if pagamento.status == StatusPagamento.APROVADO
                        else StatusPagamento.CANCELADO,
                    )

            _registrar_historico(db, self.id, novo_status, descricao or StatusPedido.DESCRICOES[novo_status])
            db.commit()
        except Exception:
            db.rollback()
            raise
        self.status = novo_status
        self.__dict__.pop("pagamento", None)
        self.__dict__.pop("entrega", None)

    # ------------------------------------------------------- relacionamentos
    @cached_property
    def itens(self):
        linhas = get_db().execute(
            """SELECT produto_id, nome_produto, preco_unitario_centavos, quantidade
                 FROM itens_pedido WHERE pedido_id = ? ORDER BY id""",
            (self.id,),
        )
        return [ItemPedido(**dict(l)) for l in linhas]

    @cached_property
    def pagamento(self):
        return Pagamento.buscar_por_pedido(self.id)

    @cached_property
    def entrega(self):
        return Entrega.buscar_por_pedido(self.id)

    @property
    def historico(self):
        return [dict(l) for l in get_db().execute(
            "SELECT status, descricao, criado_em FROM historico_pedido WHERE pedido_id = ? ORDER BY id",
            (self.id,),
        )]

    # ---------------------------------------------------------------- consultas
    @classmethod
    def buscar_por_id(cls, pedido_id):
        if not id_valido(pedido_id):
            return None
        linha = get_db().execute(cls._CONSULTA + " WHERE p.id = ?", (pedido_id,)).fetchone()
        return cls(**dict(linha)) if linha else None

    @classmethod
    def listar_por_cliente(cls, cliente_id):
        linhas = get_db().execute(cls._CONSULTA + " WHERE p.cliente_id = ? ORDER BY p.id DESC", (cliente_id,))
        return [cls(**dict(l)) for l in linhas]

    @classmethod
    def listar(cls, status=None):
        if status:
            linhas = get_db().execute(cls._CONSULTA + " WHERE p.status = ? ORDER BY p.id DESC", (status,))
        else:
            linhas = get_db().execute(cls._CONSULTA + " ORDER BY p.id DESC")
        return [cls(**dict(l)) for l in linhas]

    @staticmethod
    def contagem_por_status() -> dict:
        linhas = get_db().execute("SELECT status, COUNT(*) AS total FROM pedidos GROUP BY status")
        return {l["status"]: l["total"] for l in linhas}
