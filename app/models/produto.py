"""Model Produto: os cupcakes exibidos na vitrine."""
import re
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ..database import get_db, id_valido
from .erros import ErroValidacao

COR_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
PRECO_MAXIMO_CENTAVOS = 1_000_000   # R$ 10.000,00
ESTOQUE_MAXIMO = 100_000


@dataclass
class Produto:
    nome: str
    descricao: str
    preco_centavos: int
    categoria: str
    cor_cobertura: str = "#f7a1c4"
    cor_forminha: str = "#8b5a3c"
    estoque: int = 0
    ativo: bool = True
    destaque: bool = False
    id: int | None = None

    # ------------------------------------------------------------------ regras
    @property
    def disponivel(self) -> bool:
        return bool(self.ativo) and self.estoque > 0

    def validar(self):
        erros = []
        if len((self.nome or "").strip()) < 3:
            erros.append("O nome do produto deve ter pelo menos 3 caracteres.")
        if not isinstance(self.preco_centavos, int) or self.preco_centavos <= 0:
            erros.append("O preço deve ser maior que zero.")
        elif self.preco_centavos > PRECO_MAXIMO_CENTAVOS:
            erros.append("O preço máximo é R$ 10.000,00.")
        if not (self.categoria or "").strip():
            erros.append("Informe a categoria.")
        if not isinstance(self.estoque, int) or self.estoque < 0:
            erros.append("O estoque não pode ser negativo.")
        elif self.estoque > ESTOQUE_MAXIMO:
            erros.append(f"O estoque máximo é {ESTOQUE_MAXIMO:,} unidades.".replace(",", "."))
        if not COR_HEX.match(self.cor_cobertura or ""):
            erros.append("Cor da cobertura inválida.")
        if not COR_HEX.match(self.cor_forminha or ""):
            erros.append("Cor da forminha inválida.")
        if erros:
            raise ErroValidacao(erros)

    @staticmethod
    def converter_preco(texto) -> int:
        """Converte '12,90', '12.90' ou 'R$ 1.234,50' para centavos (int)."""
        t = str(texto or "").replace("R$", "").replace(" ", "").strip()
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        try:
            valor = Decimal(t)
        except InvalidOperation:
            raise ErroValidacao("Preço inválido. Use o formato 12,90.") from None
        # Decimal aceita "NaN" e "Infinity", que quebravam a conversão para int.
        if not valor.is_finite() or valor * 100 > PRECO_MAXIMO_CENTAVOS:
            raise ErroValidacao("Preço inválido. Use o formato 12,90 (máximo R$ 10.000,00).")
        return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    # ------------------------------------------------------------ persistência
    @classmethod
    def _de_linha(cls, linha):
        if linha is None:
            return None
        dados = dict(linha)
        dados["ativo"] = bool(dados["ativo"])
        dados["destaque"] = bool(dados["destaque"])
        return cls(**dados)

    @classmethod
    def listar(cls, categoria=None, busca=None, incluir_inativos=False):
        sql = ["SELECT * FROM produtos WHERE 1 = 1"]
        params = []
        if not incluir_inativos:
            sql.append("AND ativo = 1")
        if categoria:
            sql.append("AND categoria = ?")
            params.append(categoria)
        if busca:
            # LOWER nos dois lados: busca sem diferenciar maiúsculas (SQLite e Postgres).
            # ESCAPE: "%" e "_" digitados pelo cliente são texto, não curingas do LIKE.
            # "!" é o caractere de escape (igual no SQLite e no PostgreSQL).
            sql.append("AND (LOWER(nome) LIKE ? ESCAPE '!' OR LOWER(descricao) LIKE ? ESCAPE '!')")
            literal = busca.lower().replace("!", "!!").replace("%", "!%").replace("_", "!_")
            termo = f"%{literal}%"
            params += [termo, termo]
        sql.append("ORDER BY destaque DESC, (estoque > 0) DESC, nome")
        return [cls._de_linha(l) for l in get_db().execute(" ".join(sql), params)]

    @classmethod
    def buscar_por_id(cls, produto_id):
        if not id_valido(produto_id):
            return None
        linha = get_db().execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
        return cls._de_linha(linha)

    @classmethod
    def buscar_varios(cls, ids) -> dict:
        ids = [i for i in ids if id_valido(i)]
        if not ids:
            return {}
        marcadores = ",".join("?" * len(ids))
        linhas = get_db().execute(f"SELECT * FROM produtos WHERE id IN ({marcadores})", ids)
        return {l["id"]: cls._de_linha(l) for l in linhas}

    @staticmethod
    def categorias():
        linhas = get_db().execute(
            "SELECT DISTINCT categoria FROM produtos WHERE ativo = 1 ORDER BY categoria"
        )
        return [l["categoria"] for l in linhas]

    def salvar(self):
        self.validar()
        db = get_db()
        valores = (
            self.nome.strip(), (self.descricao or "").strip(), self.preco_centavos,
            self.categoria.strip(), self.cor_cobertura, self.cor_forminha,
            self.estoque, int(self.ativo), int(self.destaque),
        )
        if self.id is None:
            cur = db.execute(
                """INSERT INTO produtos (nome, descricao, preco_centavos, categoria,
                       cor_cobertura, cor_forminha, estoque, ativo, destaque)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                valores,
            )
            self.id = cur.lastrowid
        else:
            db.execute(
                """UPDATE produtos SET nome = ?, descricao = ?, preco_centavos = ?,
                       categoria = ?, cor_cobertura = ?, cor_forminha = ?, estoque = ?,
                       ativo = ?, destaque = ?
                   WHERE id = ?""",
                valores + (self.id,),
            )
        db.commit()
        return self

    def to_dict(self):
        dados = asdict(self)
        dados["disponivel"] = self.disponivel
        return dados
