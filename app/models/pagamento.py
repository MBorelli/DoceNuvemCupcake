"""Model Pagamento.

O gateway é SIMULADO (ambiente acadêmico). Em produção, a classe
GatewayPagamentoSimulado seria substituída por uma integração com um provedor real
(Mercado Pago, PagSeguro, Stripe...), mantendo a mesma interface `processar()`.

Por segurança, o número completo do cartão e o CVV NUNCA são gravados: guardamos
apenas bandeira, últimos 4 dígitos, titular e parcelas.
"""
import json
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..database import agora, get_db
from .erros import ErroPagamento, ErroValidacao


class MetodoPagamento:
    PIX = "pix"
    CARTAO = "cartao"
    BOLETO = "boleto"
    ROTULOS = {PIX: "PIX", CARTAO: "Cartão de crédito", BOLETO: "Boleto bancário"}
    TODOS = tuple(ROTULOS)


class StatusPagamento:
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    ESTORNADO = "estornado"
    CANCELADO = "cancelado"
    ROTULOS = {PENDENTE: "Pendente", APROVADO: "Aprovado", ESTORNADO: "Estornado", CANCELADO: "Cancelado"}


MAX_PARCELAS = 3
# Cartão de teste que o gateway simulado sempre recusa.
CARTAO_TESTE_RECUSADO = "4000000000000002"


def luhn_valido(numero: str) -> bool:
    """Algoritmo de Luhn (dígito verificador de cartões)."""
    if not numero.isdigit():
        return False
    total = 0
    for i, digito in enumerate(int(c) for c in reversed(numero)):
        if i % 2 == 1:
            digito *= 2
            if digito > 9:
                digito -= 9
        total += digito
    return total % 10 == 0


def detectar_bandeira(numero: str) -> str:
    if re.match(r"^(4011|4312|4389|4514|4576|5041|5066|5067|509|6277|6362|6363|650|6516|6550)", numero):
        return "Elo"
    if numero.startswith("4"):
        return "Visa"
    if re.match(r"^(5[1-5]|2[2-7])", numero):
        return "Mastercard"
    if re.match(r"^3[47]", numero):
        return "American Express"
    return "Cartão"


@dataclass
class ResultadoPagamento:
    status: str
    transacao_id: str
    detalhes: dict


class GatewayPagamentoSimulado:
    def processar(self, metodo, valor_centavos, dados) -> ResultadoPagamento:
        if metodo == MetodoPagamento.PIX:
            return self._pix(valor_centavos)
        if metodo == MetodoPagamento.BOLETO:
            return self._boleto()
        if metodo == MetodoPagamento.CARTAO:
            return self._cartao(valor_centavos, dados or {})
        raise ErroValidacao("Escolha uma forma de pagamento.")

    @staticmethod
    def _pix(valor_centavos):
        txid = "PIX" + secrets.token_hex(8).upper()
        valor = f"{valor_centavos / 100:.2f}"
        codigo = (
            "00020126360014BR.GOV.BCB.PIX0114DOCENUVEM-DEMO"
            f"5204000053039865406{valor}5802BR5911DOCE NUVEM6009SAO PAULO"
            f"62{len(txid) + 4:02d}05{len(txid):02d}{txid}6304{secrets.token_hex(2).upper()}"
        )
        expira = datetime.now() + timedelta(minutes=30)
        return ResultadoPagamento(
            StatusPagamento.PENDENTE, txid,
            {"copia_e_cola": codigo, "expira_em": expira.isoformat(timespec="minutes")},
        )

    @staticmethod
    def _boleto():
        numeros = "".join(str(secrets.randbelow(10)) for _ in range(47))
        linha = (f"{numeros[0:5]}.{numeros[5:10]} {numeros[10:15]}.{numeros[15:21]} "
                 f"{numeros[21:26]}.{numeros[26:32]} {numeros[32]} {numeros[33:47]}")
        vencimento = date.today() + timedelta(days=3)
        return ResultadoPagamento(
            StatusPagamento.PENDENTE, "BOL" + secrets.token_hex(6).upper(),
            {"linha_digitavel": linha, "vencimento": vencimento.isoformat()},
        )

    @staticmethod
    def _cartao(valor_centavos, dados):
        numero = re.sub(r"\D", "", str(dados.get("numero") or ""))
        titular = str(dados.get("titular") or "").strip()
        validade = str(dados.get("validade") or "").strip()
        cvv = re.sub(r"\D", "", str(dados.get("cvv") or ""))

        erros = []
        if not (13 <= len(numero) <= 19) or not luhn_valido(numero):
            erros.append("Número do cartão inválido.")
        if len(titular) < 3:
            erros.append("Informe o nome impresso no cartão.")
        m = re.fullmatch(r"(\d{2})\s*/\s*(\d{2}|\d{4})", validade)
        if not m:
            erros.append("Validade do cartão inválida (use MM/AA).")
        else:
            mes, ano = int(m.group(1)), int(m.group(2))
            ano = ano + 2000 if ano < 100 else ano
            hoje = date.today()
            if not 1 <= mes <= 12:
                erros.append("Mês de validade inválido.")
            elif (ano, mes) < (hoje.year, hoje.month):
                erros.append("Cartão vencido.")
        if len(cvv) not in (3, 4):
            erros.append("CVV inválido.")
        try:
            parcelas = int(dados.get("parcelas") or 1)
        except (TypeError, ValueError):
            parcelas = 0
        if not 1 <= parcelas <= MAX_PARCELAS:
            erros.append(f"Parcelamento permitido: de 1 a {MAX_PARCELAS} vezes.")
        if erros:
            raise ErroValidacao(erros)

        if numero == CARTAO_TESTE_RECUSADO:
            raise ErroPagamento("Transação recusada pelo emissor do cartão (saldo insuficiente).")

        return ResultadoPagamento(
            StatusPagamento.APROVADO, "CC" + secrets.token_hex(8).upper(),
            {
                "bandeira": detectar_bandeira(numero),
                "final": numero[-4:],
                "titular": titular.upper()[:60],
                "parcelas": parcelas,
                "valor_parcela_centavos": round(valor_centavos / parcelas),
            },
        )


@dataclass
class Pagamento:
    id: int
    pedido_id: int
    metodo: str
    status: str
    valor_centavos: int
    transacao_id: str
    detalhes: dict
    criado_em: str
    atualizado_em: str

    @property
    def rotulo_metodo(self):
        return MetodoPagamento.ROTULOS.get(self.metodo, self.metodo)

    @property
    def rotulo_status(self):
        return StatusPagamento.ROTULOS.get(self.status, self.status)

    @property
    def pendente(self):
        return self.status == StatusPagamento.PENDENTE

    @classmethod
    def registrar(cls, db, pedido_id, metodo, valor_centavos, resultado: ResultadoPagamento):
        momento = agora()
        db.execute(
            """INSERT INTO pagamentos (pedido_id, metodo, status, valor_centavos, transacao_id,
                   detalhes, criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pedido_id, metodo, resultado.status, valor_centavos, resultado.transacao_id,
             json.dumps(resultado.detalhes, ensure_ascii=False), momento, momento),
        )

    @classmethod
    def buscar_por_pedido(cls, pedido_id):
        linha = get_db().execute("SELECT * FROM pagamentos WHERE pedido_id = ?", (pedido_id,)).fetchone()
        if not linha:
            return None
        dados = dict(linha)
        dados["detalhes"] = json.loads(dados["detalhes"] or "{}")
        return cls(**dados)

    @staticmethod
    def atualizar_status(db, pedido_id, novo_status):
        db.execute(
            "UPDATE pagamentos SET status = ?, atualizado_em = ? WHERE pedido_id = ?",
            (novo_status, agora(), pedido_id),
        )
