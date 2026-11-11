"""Conexão com o banco de dados, criação das tabelas e dados iniciais.

Dois bancos são suportados, com a mesma interface para os models:
  * SQLite     -> desenvolvimento local e testes (padrão)
  * PostgreSQL -> produção na Vercel (quando DATABASE_URL está definida)

Os models escrevem SQL com placeholders "?" e usam cursor.lastrowid, como no
sqlite3. A classe ConexaoPostgres traduz isso para o psycopg (driver do Postgres).
"""
import logging
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    telefone    TEXT,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    criado_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS produtos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT    NOT NULL,
    descricao       TEXT    NOT NULL DEFAULT '',
    preco_centavos  INTEGER NOT NULL CHECK (preco_centavos > 0),
    categoria       TEXT    NOT NULL,
    cor_cobertura   TEXT    NOT NULL DEFAULT '#f7a1c4',
    cor_forminha    TEXT    NOT NULL DEFAULT '#8b5a3c',
    estoque         INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0),
    ativo           INTEGER NOT NULL DEFAULT 1,
    destaque        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pedidos (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id         INTEGER NOT NULL REFERENCES clientes(id),
    status             TEXT    NOT NULL,
    subtotal_centavos  INTEGER NOT NULL,
    frete_centavos     INTEGER NOT NULL,
    total_centavos     INTEGER NOT NULL,
    observacoes        TEXT,
    criado_em          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id                INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    produto_id               INTEGER NOT NULL REFERENCES produtos(id),
    nome_produto             TEXT    NOT NULL,
    preco_unitario_centavos  INTEGER NOT NULL,
    quantidade               INTEGER NOT NULL CHECK (quantidade > 0)
);

CREATE TABLE IF NOT EXISTS pagamentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id       INTEGER NOT NULL UNIQUE REFERENCES pedidos(id) ON DELETE CASCADE,
    metodo          TEXT    NOT NULL,
    status          TEXT    NOT NULL,
    valor_centavos  INTEGER NOT NULL,
    transacao_id    TEXT    NOT NULL,
    detalhes        TEXT    NOT NULL DEFAULT '{}',
    criado_em       TEXT    NOT NULL,
    atualizado_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS entregas (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id        INTEGER NOT NULL UNIQUE REFERENCES pedidos(id) ON DELETE CASCADE,
    destinatario     TEXT    NOT NULL,
    telefone         TEXT    NOT NULL,
    cep              TEXT    NOT NULL,
    logradouro       TEXT    NOT NULL,
    numero           TEXT    NOT NULL,
    complemento      TEXT,
    bairro           TEXT    NOT NULL,
    cidade           TEXT    NOT NULL,
    uf               TEXT    NOT NULL,
    regiao           TEXT    NOT NULL,
    prazo_dias       INTEGER NOT NULL,
    previsao         TEXT    NOT NULL,
    codigo_rastreio  TEXT
);

CREATE TABLE IF NOT EXISTS historico_pedido (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id   INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    status      TEXT    NOT NULL,
    descricao   TEXT    NOT NULL,
    criado_em   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_itens_pedido ON itens_pedido(pedido_id);
CREATE INDEX IF NOT EXISTS idx_historico_pedido ON historico_pedido(pedido_id);
"""

TABELAS = ["historico_pedido", "entregas", "pagamentos", "itens_pedido", "pedidos", "produtos", "clientes"]

# (nome, descrição, preço em centavos, categoria, cobertura, forminha, estoque, destaque)
PRODUTOS_INICIAIS = [
    ("Red Velvet", "Massa aveludada de cacau com cobertura de cream cheese e raspas de chocolate branco.",
     1290, "Clássicos", "#f6ece4", "#b3202d", 30, 1),
    ("Chocolate Belga", "Massa de chocolate 54% com ganache cremosa e granulado belga.",
     1190, "Clássicos", "#5a3220", "#3b2314", 40, 1),
    ("Baunilha com Morango", "Massa de baunilha de Madagascar, recheio de geleia artesanal e buttercream de morango.",
     1090, "Frutas", "#f7a1c4", "#f2d7b6", 35, 0),
    ("Limão Siciliano", "Massa cítrica com recheio de curd de limão e merengue maçaricado.",
     1150, "Frutas", "#f6e27a", "#9ccc65", 25, 0),
    ("Maracujá", "Massa leve com recheio de mousse de maracujá e calda da fruta.",
     1190, "Frutas", "#f9c74f", "#e76f51", 20, 0),
    ("Brigadeiro", "O clássico brasileiro: massa de chocolate, recheio e cobertura de brigadeiro gourmet.",
     1190, "Brasileiros", "#4a2a1a", "#f7a1c4", 40, 1),
    ("Doce de Leite", "Massa de baunilha com recheio de doce de leite mineiro e cobertura caramelizada.",
     1250, "Brasileiros", "#d9a066", "#8b5a3c", 25, 0),
    ("Paçoca", "Massa de amendoim com recheio cremoso de paçoca e farofa crocante.",
     1150, "Brasileiros", "#c9a27e", "#7a5230", 18, 0),
    ("Cookies & Cream", "Massa de chocolate com pedaços de biscoito e cobertura de creme de baunilha.",
     1390, "Especiais", "#eeeeee", "#222222", 22, 1),
    ("Pistache", "Massa de pistache com recheio de creme de pistache siciliano.",
     1490, "Especiais", "#a8c97f", "#6b8e4e", 0, 0),
]


# Horário de Brasília (UTC-3, sem horário de verão desde 2019). Os servidores da
# Vercel rodam em UTC; sem isso, pedidos feitos após as 21h ficariam com a data
# do dia seguinte. Offset fixo para não depender da base tzdata (ausente no Windows).
FUSO_LOJA = timezone(timedelta(hours=-3), "BRT")

# Maior id aceito: limite do INTEGER do PostgreSQL (32 bits). Ids maiores que isso
# derrubavam a consulta com OverflowError (SQLite) ou "out of range" (Postgres).
ID_MAXIMO = 2 ** 31 - 1


def agora_local() -> datetime:
    """Data e hora atuais no fuso da loja (sem tzinfo, como o resto do banco)."""
    return datetime.now(FUSO_LOJA).replace(tzinfo=None)


def agora() -> str:
    return agora_local().isoformat(timespec="seconds")


def hoje() -> date:
    return agora_local().date()


def id_valido(valor) -> bool:
    return isinstance(valor, int) and 0 < valor <= ID_MAXIMO


def erros_de_integridade() -> tuple:
    """Exceções de violação de UNIQUE/CHECK nos dois bancos suportados."""
    erros = [sqlite3.IntegrityError]
    try:
        import psycopg
        erros.append(psycopg.IntegrityError)
    except ImportError:
        pass
    return tuple(erros)


# --------------------------------------------------------------- PostgreSQL
class CursorPostgres:
    """Expõe o resultado do psycopg com a mesma interface do cursor do sqlite3."""

    def __init__(self, cursor, retorna_id):
        self._cursor = cursor
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.fetchone()["id"] if retorna_id else None

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class ConexaoPostgres:
    """Adaptador: placeholders "?" -> "%s", lastrowid via RETURNING id,
    linhas como dicionários (acesso por nome da coluna)."""

    ID_SQLITE = "INTEGER PRIMARY KEY AUTOINCREMENT"
    ID_POSTGRES = "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"

    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row

        # prepare_threshold=None: compatível com o pool de conexões (PgBouncer) do Neon.
        self._con = psycopg.connect(url, row_factory=dict_row, prepare_threshold=None)

    @staticmethod
    def traduzir(sql, com_parametros=True):
        if com_parametros:
            sql = sql.replace("%", "%%").replace("?", "%s")
        return sql

    def execute(self, sql, params=()):
        params = tuple(params)
        sql = self.traduzir(sql, bool(params))
        retorna_id = sql.lstrip().upper().startswith("INSERT") and "RETURNING" not in sql.upper()
        if retorna_id:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        return CursorPostgres(self._con.execute(sql, params or None), retorna_id)

    def executemany(self, sql, sequencia):
        with self._con.cursor() as cur:
            cur.executemany(self.traduzir(sql), list(sequencia))

    def executescript(self, script):
        script = script.replace(self.ID_SQLITE, self.ID_POSTGRES)
        for comando in script.split(";"):
            if comando.strip():
                self._con.execute(comando)

    def bloquear_inicializacao(self):
        """Evita que duas instâncias criem tabelas/dados iniciais ao mesmo tempo
        (cold start simultâneo na Vercel). O lock é liberado no commit."""
        self._con.execute("SELECT pg_advisory_xact_lock(724531)")

    def commit(self):
        self._con.commit()

    def rollback(self):
        self._con.rollback()

    def close(self):
        self._con.close()


# ----------------------------------------------------------------- conexão
def _conectar():
    url = current_app.config.get("DATABASE_URL")
    if url:
        return ConexaoPostgres(url)
    conexao = sqlite3.connect(current_app.config["DATABASE"])
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def get_db():
    """Retorna a conexão da requisição atual (uma por requisição)."""
    if "db" not in g:
        g.db = _conectar()
    return g.db


def close_db(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def criar_tabelas(db):
    if isinstance(db, ConexaoPostgres):
        db.bloquear_inicializacao()
    db.executescript(SCHEMA)


def _senha_inicial_admin() -> str:
    """Senha do admin criado no primeiro acesso. Em produção, defina ADMIN_SENHA;
    na Vercel, sem ela, é gerada uma senha aleatória (mostrada uma vez no log)
    para que a senha pública de demonstração nunca dê acesso ao painel."""
    senha = os.environ.get("ADMIN_SENHA")
    if senha:
        return senha
    if os.environ.get("VERCEL"):
        senha = secrets.token_urlsafe(12)
        logging.getLogger(__name__).warning(
            "ADMIN_SENHA não definida. Senha gerada para admin@cupcakes.com: %s", senha)
        return senha
    return "admin123"


def popular(db):
    """Insere produtos e usuários de demonstração se o banco estiver vazio."""
    if db.execute("SELECT COUNT(*) AS total FROM produtos").fetchone()["total"] == 0:
        db.executemany(
            """INSERT INTO produtos (nome, descricao, preco_centavos, categoria,
                   cor_cobertura, cor_forminha, estoque, destaque)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            PRODUTOS_INICIAIS,
        )
    if db.execute("SELECT COUNT(*) AS total FROM clientes").fetchone()["total"] == 0:
        db.executemany(
            """INSERT INTO clientes (nome, email, senha_hash, telefone, is_admin, criado_em)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                ("Administrador da Loja", "admin@cupcakes.com",
                 generate_password_hash(_senha_inicial_admin()), "11999990000", 1, agora()),
                ("Cliente Demonstração", "cliente@cupcakes.com",
                 generate_password_hash("cliente123"), "11988887777", 0, agora()),
            ],
        )
    db.commit()


def init_db():
    db = get_db()
    criar_tabelas(db)
    popular(db)


def resetar_db():
    db = get_db()
    for tabela in TABELAS:
        db.execute(f"DROP TABLE IF EXISTS {tabela}")
    db.commit()
    init_db()


def init_app(app):
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def comando_init_db():
        """Cria as tabelas e insere dados iniciais (se ainda não existirem)."""
        init_db()
        click.echo("Banco de dados inicializado.")

    @app.cli.command("reset-db")
    def comando_reset_db():
        """Apaga TODOS os dados e recria o banco com os dados de demonstração."""
        resetar_db()
        click.echo("Banco de dados recriado.")

    with app.app_context():
        init_db()
