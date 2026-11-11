"""Utilitários de segurança compartilhados pelos controllers:
proteção CSRF, exigência de login e de perfil administrador."""
import hmac
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for


def gerar_csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def verificar_csrf():
    """Toda requisição POST precisa enviar o token (campo do formulário ou cabeçalho)."""
    if request.method != "POST":
        return
    enviado = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    esperado = session.get("_csrf") or ""
    if not esperado or not hmac.compare_digest(enviado, esperado):
        abort(400)


def destino_seguro(destino, padrao="/"):
    """Evita redirecionamento aberto: só aceita caminhos internos."""
    if destino and destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
        return destino
    return padrao


def login_obrigatorio(view):
    @wraps(view)
    def envoltorio(*args, **kwargs):
        if g.get("cliente") is None:
            flash("Entre na sua conta para continuar.", "info")
            # Só volta para páginas GET: redirecionar para uma rota que só aceita POST
            # (ex.: /pedidos/1/cancelar) terminaria em erro 405 depois do login.
            proximo = request.full_path.rstrip("?") if request.method == "GET" else None
            return redirect(url_for("auth.login", next=proximo))
        return view(*args, **kwargs)
    return envoltorio


def admin_obrigatorio(view):
    @wraps(view)
    @login_obrigatorio
    def envoltorio(*args, **kwargs):
        if not g.cliente.is_admin:
            abort(404)
        return view(*args, **kwargs)
    return envoltorio


def cabecalhos_de_seguranca(resposta):
    """Cabeçalhos HTTP de proteção aplicados a todas as respostas."""
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")          # sem MIME sniffing
    resposta.headers.setdefault("X-Frame-Options", "DENY")                    # anti-clickjacking
    resposta.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resposta


def registrar(app):
    app.before_request(verificar_csrf)
    app.after_request(cabecalhos_de_seguranca)
    app.jinja_env.globals["csrf_token"] = gerar_csrf_token
