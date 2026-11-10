"""Filtros e variáveis globais disponíveis em todos os templates."""
from datetime import date, datetime

from ..models import MetodoPagamento, StatusPagamento, StatusPedido


def brl(centavos) -> str:
    """1290 -> 'R$ 12,90'"""
    valor = f"{(centavos or 0) / 100:,.2f}"
    return "R$ " + valor.replace(",", "X").replace(".", ",").replace("X", ".")


def data_hora(iso) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y às %H:%M")


def data_br(iso) -> str:
    if not iso:
        return ""
    return date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")


def telefone(numero) -> str:
    n = numero or ""
    if len(n) == 11:
        return f"({n[:2]}) {n[2:7]}-{n[7:]}"
    if len(n) == 10:
        return f"({n[:2]}) {n[2:6]}-{n[6:]}"
    return n


def registrar(app):
    app.jinja_env.filters.update(brl=brl, data_hora=data_hora, data_br=data_br, telefone=telefone)
    app.jinja_env.globals.update(
        StatusPedido=StatusPedido,
        StatusPagamento=StatusPagamento,
        MetodoPagamento=MetodoPagamento,
        rotulo_status=StatusPedido.rotulo,
    )
