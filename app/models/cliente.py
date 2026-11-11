"""Model Cliente: cadastro e autenticação."""
import re
from dataclasses import dataclass

from werkzeug.security import check_password_hash, generate_password_hash

from ..database import agora, erros_de_integridade, get_db, id_valido
from .erros import ErroValidacao

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Cliente:
    id: int
    nome: str
    email: str
    telefone: str | None
    is_admin: bool
    criado_em: str

    @property
    def primeiro_nome(self) -> str:
        return self.nome.split()[0] if self.nome else ""

    @classmethod
    def _de_linha(cls, linha):
        if linha is None:
            return None
        return cls(
            id=linha["id"], nome=linha["nome"], email=linha["email"],
            telefone=linha["telefone"], is_admin=bool(linha["is_admin"]),
            criado_em=linha["criado_em"],
        )

    @classmethod
    def buscar_por_id(cls, cliente_id):
        if not id_valido(cliente_id):
            return None
        linha = get_db().execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
        return cls._de_linha(linha)

    @classmethod
    def cadastrar(cls, nome, email, senha, telefone="", confirmacao=None):
        nome = (nome or "").strip()
        email = (email or "").strip().lower()
        telefone = re.sub(r"\D", "", telefone or "")
        senha = senha or ""

        erros = []
        if len(nome) < 3:
            erros.append("Informe seu nome completo.")
        if not EMAIL.match(email):
            erros.append("Informe um e-mail válido.")
        if len(senha) < 6:
            erros.append("A senha deve ter pelo menos 6 caracteres.")
        if confirmacao is not None and senha != confirmacao:
            erros.append("As senhas não conferem.")
        if telefone and len(telefone) not in (10, 11):
            erros.append("O telefone deve ter DDD + número.")

        db = get_db()
        if not erros and db.execute("SELECT 1 FROM clientes WHERE email = ?", (email,)).fetchone():
            erros.append("Já existe uma conta com este e-mail.")
        if erros:
            raise ErroValidacao(erros)

        try:
            cur = db.execute(
                """INSERT INTO clientes (nome, email, senha_hash, telefone, is_admin, criado_em)
                   VALUES (?, ?, ?, ?, 0, ?)""",
                (nome, email, generate_password_hash(senha), telefone or None, agora()),
            )
            db.commit()
        except erros_de_integridade():
            # Dois cadastros com o mesmo e-mail ao mesmo tempo: a checagem acima passou
            # para os dois, mas o UNIQUE do banco barra o segundo.
            db.rollback()
            raise ErroValidacao("Já existe uma conta com este e-mail.") from None
        return cls.buscar_por_id(cur.lastrowid)

    @classmethod
    def autenticar(cls, email, senha):
        linha = get_db().execute(
            "SELECT * FROM clientes WHERE email = ?", ((email or "").strip().lower(),)
        ).fetchone()
        if linha and check_password_hash(linha["senha_hash"], senha or ""):
            return cls._de_linha(linha)
        return None
