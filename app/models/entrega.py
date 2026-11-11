"""Model Entrega: endereço, cálculo de frete, prazo e rastreio."""
import re
import secrets
from dataclasses import dataclass
from datetime import date, timedelta

from ..database import get_db, hoje
from .erros import ErroValidacao

# Área de entrega própria da confeitaria (cupcakes são perecíveis, por isso a
# entrega é regional). (CEP inicial, CEP final, região, valor em centavos,
# prazo em dias úteis, frete grátis a partir de X centavos ou None)
FAIXAS_ENTREGA = [
    (1000000, 9999999, "Grande São Paulo", 790, 1, 10000),
    (11000000, 19999999, "Interior e litoral de SP", 1490, 2, None),
]

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


def somente_digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def adicionar_dias_uteis(inicio: date, dias: int) -> date:
    """Entregamos de segunda a sábado (domingo não conta)."""
    atual = inicio
    restantes = dias
    while restantes > 0:
        atual += timedelta(days=1)
        if atual.weekday() != 6:
            restantes -= 1
    return atual


@dataclass
class Frete:
    regiao: str
    valor_centavos: int
    prazo_dias: int
    gratis: bool

    @property
    def previsao(self) -> date:
        return adicionar_dias_uteis(hoje(), self.prazo_dias)

    def to_dict(self):
        return {
            "regiao": self.regiao,
            "valor_centavos": self.valor_centavos,
            "prazo_dias": self.prazo_dias,
            "gratis": self.gratis,
            "previsao": self.previsao.isoformat(),
        }


def calcular_frete(cep, subtotal_centavos=0) -> Frete:
    cep = somente_digitos(cep)
    if len(cep) != 8:
        raise ErroValidacao("CEP inválido. Informe os 8 dígitos.")
    numero = int(cep)
    for inicio, fim, regiao, valor, prazo, gratis_a_partir in FAIXAS_ENTREGA:
        if inicio <= numero <= fim:
            gratis = gratis_a_partir is not None and subtotal_centavos >= gratis_a_partir
            return Frete(regiao, 0 if gratis else valor, prazo, gratis)
    raise ErroValidacao(
        "Ainda não entregamos neste CEP. Atendemos a Grande São Paulo e o interior/litoral de SP."
    )


@dataclass
class Entrega:
    id: int
    pedido_id: int
    destinatario: str
    telefone: str
    cep: str
    logradouro: str
    numero: str
    complemento: str | None
    bairro: str
    cidade: str
    uf: str
    regiao: str
    prazo_dias: int
    previsao: str
    codigo_rastreio: str | None

    CAMPOS = ("destinatario", "telefone", "cep", "logradouro", "numero",
              "complemento", "bairro", "cidade", "uf")

    @property
    def cep_formatado(self) -> str:
        return f"{self.cep[:5]}-{self.cep[5:]}"

    @staticmethod
    def validar_endereco(dados) -> dict:
        d = {campo: str(dados.get(campo) or "").strip() for campo in Entrega.CAMPOS}
        d["cep"] = somente_digitos(d["cep"])
        d["telefone"] = somente_digitos(d["telefone"])
        d["uf"] = d["uf"].upper()

        erros = []
        if len(d["destinatario"]) < 3:
            erros.append("Informe o nome de quem vai receber o pedido.")
        if len(d["telefone"]) not in (10, 11):
            erros.append("Informe um telefone de contato com DDD.")
        if len(d["cep"]) != 8:
            erros.append("CEP inválido.")
        if not d["logradouro"]:
            erros.append("Informe a rua/avenida.")
        if not d["numero"]:
            erros.append("Informe o número do endereço.")
        if not d["bairro"]:
            erros.append("Informe o bairro.")
        if not d["cidade"]:
            erros.append("Informe a cidade.")
        if d["uf"] not in UFS:
            erros.append("Informe a UF (ex.: SP).")
        if erros:
            raise ErroValidacao(erros)
        for campo, limite in (("logradouro", 150), ("complemento", 80), ("bairro", 80),
                              ("cidade", 80), ("destinatario", 100), ("numero", 20)):
            d[campo] = d[campo][:limite]
        return d

    @classmethod
    def criar(cls, db, pedido_id, endereco: dict, frete: Frete):
        db.execute(
            """INSERT INTO entregas (pedido_id, destinatario, telefone, cep, logradouro, numero,
                   complemento, bairro, cidade, uf, regiao, prazo_dias, previsao)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pedido_id, endereco["destinatario"], endereco["telefone"], endereco["cep"],
                endereco["logradouro"], endereco["numero"], endereco["complemento"] or None,
                endereco["bairro"], endereco["cidade"], endereco["uf"], frete.regiao,
                frete.prazo_dias, frete.previsao.isoformat(),
            ),
        )

    @classmethod
    def buscar_por_pedido(cls, pedido_id):
        linha = get_db().execute("SELECT * FROM entregas WHERE pedido_id = ?", (pedido_id,)).fetchone()
        return cls(**dict(linha)) if linha else None

    @staticmethod
    def registrar_despacho(db, pedido_id) -> str:
        """Gera o código de rastreio quando o pedido sai para entrega."""
        codigo = f"DN{pedido_id:06d}{secrets.randbelow(900) + 100}BR"
        db.execute("UPDATE entregas SET codigo_rastreio = ? WHERE pedido_id = ?", (codigo, pedido_id))
        return codigo
