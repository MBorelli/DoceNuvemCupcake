"""Fábrica da aplicação Flask.

Organização em MVC:
    app/models/       -> Model: regras de negócio e acesso a dados (SQLite)
    app/views/        -> View: templates Jinja2 (HTML)
    public/static/    -> View: CSS/JS (fica em public/ porque a Vercel serve
                         essa pasta direto pela CDN)
    app/controllers/  -> Controller: rotas que recebem a requisição, chamam
                         os models e escolhem a view a ser renderizada

Variáveis de ambiente:
    SECRET_KEY    chave de assinatura da sessão (obrigatória na Vercel)
    DATABASE_URL  URL do PostgreSQL (ou POSTGRES_URL); sem ela usa SQLite
"""
import os

from flask import Flask, render_template

from . import database
from .controllers import seguranca
from .views import helpers

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NA_VERCEL = bool(os.environ.get("VERCEL"))


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="views/templates",
        static_folder=os.path.join(RAIZ_PROJETO, "public", "static"),
        static_url_path="/static",
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE_URL=os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL"),
        # Na Vercel só /tmp aceita escrita (e é temporário): SQLite lá serve apenas de demonstração.
        DATABASE=os.path.join("/tmp" if NA_VERCEL else app.instance_path, "cupcakes.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=NA_VERCEL,
        LOJA_NOME="Doce Nuvem Cupcakes",
    )
    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        if NA_VERCEL:
            raise RuntimeError(
                "Defina a variável de ambiente SECRET_KEY em Settings > Environment Variables na Vercel."
            )
        app.config["SECRET_KEY"] = "dev-chave-local-nao-use-em-producao"

    if NA_VERCEL and not app.config["DATABASE_URL"]:
        app.logger.warning(
            "DATABASE_URL não definida: usando SQLite em /tmp. Os dados serão PERDIDOS "
            "a cada nova instância. Conecte um banco Postgres (ex.: Neon) ao projeto."
        )
    if not app.config["DATABASE_URL"]:
        os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)

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

    @app.errorhandler(405)
    def metodo_nao_permitido(_erro):
        return render_template(
            "erro.html", codigo=405, mensagem="Esta ação não pode ser acessada diretamente pelo endereço.",
        ), 405

    @app.errorhandler(500)
    def erro_interno(_erro):
        return render_template(
            "erro.html", codigo=500,
            mensagem="Ocorreu um erro inesperado. Tente novamente em instantes.",
        ), 500

    return app
