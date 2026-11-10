"""Fábrica da aplicação Flask.

Organização em MVC:
    app/models/       -> Model: regras de negócio e acesso a dados (SQLite)
    app/views/        -> View: templates Jinja2 (HTML) + arquivos estáticos (CSS/JS)
    app/controllers/  -> Controller: rotas que recebem a requisição, chamam
                         os models e escolhem a view a ser renderizada
"""
import os

from flask import Flask, render_template

from . import database
from .controllers import seguranca
from .views import helpers


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="views/templates",
        static_folder="views/static",
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-troque-esta-chave-em-producao"),
        DATABASE=os.path.join(app.instance_path, "cupcakes.sqlite3"),
        LOJA_NOME="Doce Nuvem Cupcakes",
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    database.init_app(app)
    helpers.registrar(app)
    seguranca.registrar(app)

    from .controllers import (
        admin_controller,
        auth_controller,
        carrinho_controller,
        pedido_controller,
        vitrine_controller,
    )

    app.register_blueprint(auth_controller.bp)
    app.register_blueprint(vitrine_controller.bp)
    app.register_blueprint(carrinho_controller.bp)
    app.register_blueprint(pedido_controller.bp)
    app.register_blueprint(admin_controller.bp)

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return render_template("erro.html", codigo=404, mensagem="Página não encontrada."), 404

    @app.errorhandler(400)
    def requisicao_invalida(_erro):
        return render_template(
            "erro.html",
            codigo=400,
            mensagem="Requisição inválida. Recarregue a página e tente novamente.",
        ), 400

    return app
