"""Controller da vitrine virtual: listagem e detalhe dos cupcakes."""
from flask import Blueprint, abort, render_template, request

from ..models import Produto

bp = Blueprint("vitrine", __name__)


@bp.route("/")
def index():
    categoria = request.args.get("categoria") or None
    busca = (request.args.get("q") or "").strip()
    produtos = Produto.listar(categoria=categoria, busca=busca or None)
    return render_template(
        "vitrine/index.html",
        produtos=produtos,
        categorias=Produto.categorias(),
        categoria_atual=categoria,
        busca=busca,
    )


@bp.route("/produto/<int:produto_id>")
def produto(produto_id):
    produto = Produto.buscar_por_id(produto_id)
    if produto is None or not produto.ativo:
        abort(404)
    relacionados = [p for p in Produto.listar(categoria=produto.categoria) if p.id != produto.id][:3]
    return render_template("vitrine/produto.html", produto=produto, relacionados=relacionados)
