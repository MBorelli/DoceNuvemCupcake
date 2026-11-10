"""Controller do carrinho e da API de frete (consumidos via JavaScript)."""
from flask import Blueprint, jsonify, render_template, request

from ..models import Carrinho, ErroValidacao, calcular_frete

bp = Blueprint("carrinho", __name__)


@bp.route("/carrinho")
def pagina():
    return render_template("carrinho/carrinho.html")


@bp.post("/api/carrinho")
def validar():
    """Recebe [{produto_id, quantidade}] e devolve o carrinho com preços e
    estoque oficiais do servidor."""
    dados = request.get_json(silent=True) or {}
    return jsonify(Carrinho.montar(dados.get("itens")).to_dict())


@bp.get("/api/frete")
def frete():
    try:
        subtotal = max(int(request.args.get("subtotal", 0)), 0)
    except ValueError:
        subtotal = 0
    try:
        resultado = calcular_frete(request.args.get("cep", ""), subtotal)
    except ErroValidacao as erro:
        return jsonify(ok=False, erro=str(erro)), 422
    return jsonify(ok=True, **resultado.to_dict())
