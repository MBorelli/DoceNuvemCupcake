"""Controller administrativo: gestão de pedidos (status/entrega) e de produtos."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..models import ErroValidacao, Pedido, Produto, StatusPedido
from .seguranca import admin_obrigatorio

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_obrigatorio
def inicio():
    return redirect(url_for("admin.pedidos"))


# ------------------------------------------------------------------ pedidos
@bp.route("/pedidos")
@admin_obrigatorio
def pedidos():
    status = request.args.get("status") or None
    if status and status not in StatusPedido.ROTULOS:
        status = None
    return render_template(
        "admin/pedidos.html",
        pedidos=Pedido.listar(status),
        status_atual=status,
        contagem=Pedido.contagem_por_status(),
    )


@bp.post("/pedidos/<int:pedido_id>/status")
@admin_obrigatorio
def alterar_status(pedido_id):
    pedido = Pedido.buscar_por_id(pedido_id)
    if pedido is None:
        abort(404)
    try:
        pedido.alterar_status(request.form.get("status"), (request.form.get("descricao") or "").strip() or None)
    except ErroValidacao as erro:
        flash(str(erro), "erro")
    else:
        flash(f"Pedido #{pedido.id} atualizado para '{pedido.rotulo_status}'.", "sucesso")
    if request.form.get("voltar_para") == "detalhe":
        return redirect(url_for("pedido.detalhe", pedido_id=pedido.id))
    return redirect(url_for("admin.pedidos", status=request.form.get("filtro") or None))


# ----------------------------------------------------------------- produtos
@bp.route("/produtos")
@admin_obrigatorio
def produtos():
    return render_template("admin/produtos.html", produtos=Produto.listar(incluir_inativos=True))


def _produto_do_formulario(produto, form):
    produto.nome = form.get("nome", "").strip()
    produto.descricao = form.get("descricao", "").strip()
    produto.categoria = form.get("categoria", "").strip()
    produto.cor_cobertura = form.get("cor_cobertura", "")
    produto.cor_forminha = form.get("cor_forminha", "")
    produto.ativo = form.get("ativo") == "on"
    produto.destaque = form.get("destaque") == "on"
    produto.preco_centavos = Produto.converter_preco(form.get("preco"))
    try:
        produto.estoque = int(form.get("estoque", "0"))
    except ValueError:
        raise ErroValidacao("Estoque deve ser um número inteiro.") from None


@bp.route("/produtos/novo", methods=["GET", "POST"])
@bp.route("/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@admin_obrigatorio
def produto_form(produto_id=None):
    if produto_id is None:
        produto = Produto(nome="", descricao="", preco_centavos=0, categoria="", estoque=0)
    else:
        produto = Produto.buscar_por_id(produto_id)
        if produto is None:
            abort(404)

    if request.method == "POST":
        try:
            _produto_do_formulario(produto, request.form)
            produto.salvar()
        except ErroValidacao as erro:
            for mensagem in erro.erros:
                flash(mensagem, "erro")
        else:
            flash(f"Produto '{produto.nome}' salvo.", "sucesso")
            return redirect(url_for("admin.produtos"))

    return render_template("admin/produto_form.html", produto=produto,
                           categorias=Produto.categorias())
