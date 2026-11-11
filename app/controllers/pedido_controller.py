"""Controller de pedidos: checkout (pedido + pagamento + entrega) e acompanhamento."""
import json

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..models import (
    Entrega, ErroPagamento, ErroValidacao, MetodoPagamento, Pedido, StatusPagamento, StatusPedido,
)
from ..models.pagamento import MAX_PARCELAS
from .seguranca import login_obrigatorio

bp = Blueprint("pedido", __name__)


def _pedido_do_cliente(pedido_id):
    pedido = Pedido.buscar_por_id(pedido_id)
    if pedido is None or (pedido.cliente_id != g.cliente.id and not g.cliente.is_admin):
        abort(404)
    return pedido


@bp.route("/checkout", methods=["GET", "POST"])
@login_obrigatorio
def checkout():
    if request.method == "GET":
        form = {"destinatario": g.cliente.nome, "telefone": g.cliente.telefone or "",
                "metodo_pagamento": MetodoPagamento.PIX}
        return render_template("pedido/checkout.html", form=form, max_parcelas=MAX_PARCELAS)

    form = request.form.to_dict()
    try:
        itens = json.loads(form.get("carrinho") or "[]")
    except ValueError:
        itens = []

    try:
        pedido = Pedido.criar(
            cliente_id=g.cliente.id,
            itens=itens,
            endereco={campo: form.get(campo) for campo in Entrega.CAMPOS},
            metodo_pagamento=form.get("metodo_pagamento"),
            dados_pagamento={
                "numero": form.get("cartao_numero"),
                "titular": form.get("cartao_titular"),
                "validade": form.get("cartao_validade"),
                "cvv": form.get("cartao_cvv"),
                "parcelas": form.get("cartao_parcelas"),
            },
            observacoes=form.get("observacoes"),
        )
    except ErroValidacao as erro:
        for mensagem in erro.erros:
            flash(mensagem, "erro")
    except ErroPagamento as erro:
        flash(f"Pagamento não aprovado: {erro} Tente outro cartão ou outra forma de pagamento.", "erro")
    else:
        flash("Pedido realizado com sucesso! Obrigado pela compra.", "sucesso")
        return redirect(url_for("pedido.detalhe", pedido_id=pedido.id, novo=1))

    # Nunca devolvemos número do cartão/CVV para a página.
    form.pop("cartao_numero", None)
    form.pop("cartao_cvv", None)
    return render_template("pedido/checkout.html", form=form, max_parcelas=MAX_PARCELAS), 422


@bp.route("/pedidos")
@login_obrigatorio
def lista():
    return render_template("pedido/lista.html", pedidos=Pedido.listar_por_cliente(g.cliente.id))


@bp.route("/pedidos/<int:pedido_id>")
@login_obrigatorio
def detalhe(pedido_id):
    pedido = _pedido_do_cliente(pedido_id)
    return render_template("pedido/detalhe.html", pedido=pedido, novo=request.args.get("novo") == "1")


@bp.post("/pedidos/<int:pedido_id>/cancelar")
@login_obrigatorio
def cancelar(pedido_id):
    pedido = _pedido_do_cliente(pedido_id)
    if not pedido.pode_ser_cancelado_pelo_cliente:
        flash("Este pedido não pode mais ser cancelado (já está em preparo).", "erro")
        return redirect(url_for("pedido.detalhe", pedido_id=pedido.id))
    try:
        pedido.alterar_status(StatusPedido.CANCELADO, "Pedido cancelado pelo cliente.")
    except ErroValidacao as erro:  # o status mudou entre abrir a página e clicar
        flash(str(erro), "erro")
    else:
        flash("Pedido cancelado. Se o pagamento já tinha sido aprovado, ele será estornado.", "info")
    return redirect(url_for("pedido.detalhe", pedido_id=pedido.id))


@bp.post("/pedidos/<int:pedido_id>/simular-pagamento")
@login_obrigatorio
def simular_pagamento(pedido_id):
    """Ambiente de demonstração: simula a confirmação do banco para PIX/boleto
    (em produção isso chegaria por webhook do provedor de pagamento)."""
    pedido = _pedido_do_cliente(pedido_id)
    pagamento = pedido.pagamento
    if (pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO or not pagamento
            or pagamento.status != StatusPagamento.PENDENTE):
        flash("Não há pagamento pendente para este pedido.", "erro")
    else:
        try:
            pedido.alterar_status(StatusPedido.PAGO, f"Pagamento via {pagamento.rotulo_metodo} confirmado.")
        except ErroValidacao as erro:
            flash(str(erro), "erro")
        else:
            flash("Pagamento confirmado! Já vamos preparar seus cupcakes.", "sucesso")
    return redirect(url_for("pedido.detalhe", pedido_id=pedido.id))
