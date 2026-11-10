"""Controller de autenticação: cadastro, login e logout de clientes."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..models import Cliente, ErroValidacao
from .seguranca import destino_seguro

bp = Blueprint("auth", __name__)


@bp.before_app_request
def carregar_cliente_logado():
    cliente_id = session.get("cliente_id")
    g.cliente = Cliente.buscar_por_id(cliente_id) if cliente_id else None


def _iniciar_sessao(cliente):
    session.clear()
    session["cliente_id"] = cliente.id


@bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    destino = destino_seguro(request.values.get("next"), url_for("vitrine.index"))
    if g.cliente:
        return redirect(destino)
    form = {}
    if request.method == "POST":
        form = request.form
        try:
            cliente = Cliente.cadastrar(
                nome=form.get("nome"), email=form.get("email"), senha=form.get("senha"),
                telefone=form.get("telefone"), confirmacao=form.get("confirmacao"),
            )
        except ErroValidacao as erro:
            for mensagem in erro.erros:
                flash(mensagem, "erro")
        else:
            _iniciar_sessao(cliente)
            flash(f"Bem-vindo(a), {cliente.primeiro_nome}! Sua conta foi criada.", "sucesso")
            return redirect(destino)
    return render_template("auth/cadastro.html", form=form, proximo=destino)


@bp.route("/login", methods=["GET", "POST"])
def login():
    destino = destino_seguro(request.values.get("next"), url_for("vitrine.index"))
    if g.cliente:
        return redirect(destino)
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "")
        cliente = Cliente.autenticar(email, request.form.get("senha"))
        if cliente:
            _iniciar_sessao(cliente)
            flash(f"Olá, {cliente.primeiro_nome}!", "sucesso")
            return redirect(destino)
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("auth/login.html", email=email, proximo=destino)


@bp.post("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("vitrine.index"))
