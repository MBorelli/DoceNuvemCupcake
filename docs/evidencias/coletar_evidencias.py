"""Coleta as evidências HTTP do laudo de qualidade.

Sobe a aplicação com um banco SQLite temporário, executa os cenários de cada
defeito e imprime o que o servidor respondeu.

Uso (na raiz do projeto):
    TZ=UTC0 python docs/evidencias/coletar_evidencias.py
(TZ=UTC0 simula o relógio dos servidores da Vercel, que rodam em UTC.)
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app  # noqa: E402
from app.models.pagamento import GatewayPagamentoSimulado  # noqa: E402

GIGANTE = 10 ** 20


def linha(defeito, cenario, resultado):
    print(f"[{defeito}] {cenario}\n        -> {resultado}")


def main():
    fd, caminho = tempfile.mkstemp(suffix=".sqlite3")
    app = create_app({"TESTING": False, "PROPAGATE_EXCEPTIONS": False, "DATABASE": caminho,
                      "DATABASE_URL": None, "SECRET_KEY": "evidencias"})
    app.logger.disabled = True
    c = app.test_client()

    def token():  # o login limpa a sessão (e o token CSRF); regrava antes de cada POST
        with c.session_transaction() as s:
            s["_csrf"] = "tk"
        return "tk"

    def post(url, dados=None, **kw):
        return c.post(url, data={**(dados or {}), "csrf_token": token()}, **kw)

    print("Data/hora da coleta (Brasília):",
          datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M:%S"))
    print("Relógio do processo (simulando o servidor):", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    print("=" * 78)

    r = c.post("/api/carrinho", json={"itens": [{"produto_id": GIGANTE, "quantidade": 1}]},
               headers={"X-CSRF-Token": token()})
    linha("DEF-01", f"POST /api/carrinho com produto_id={GIGANTE}", f"HTTP {r.status_code}")
    r = c.get(f"/produto/{GIGANTE}")
    linha("DEF-01", f"GET /produto/{GIGANTE}", f"HTTP {r.status_code}")

    post("/login", {"email": "admin@cupcakes.com", "senha": "admin123"})
    base = {"nome": "Teste", "descricao": "x", "categoria": "Clássicos", "cor_cobertura": "#ffffff",
            "cor_forminha": "#000000", "estoque": "1", "preco": "10"}
    for campo, valor in (("preco", "NaN"), ("preco", "Infinity"), ("estoque", str(GIGANTE))):
        r = post("/admin/produtos/novo", {**base, campo: valor})
        linha("DEF-02", f"Admin cadastra produto com {campo}={valor}", f"HTTP {r.status_code}")
    post("/logout")

    post("/login", {"email": "cliente@cupcakes.com", "senha": "cliente123"})
    endereco = {"destinatario": "Maria Teste", "telefone": "11988887777", "cep": "01310100",
                "logradouro": "Av. Paulista", "numero": "1000", "bairro": "Bela Vista",
                "cidade": "São Paulo", "uf": "SP"}
    r = post("/checkout", {**endereco, "metodo_pagamento": "pix",
                           "carrinho": json.dumps([{"produto_id": 1, "quantidade": 1}])})
    with app.app_context():
        from app.models import Pedido
        pedido = Pedido.listar()[0]
        linha("DEF-03", "Pedido criado agora - horário gravado no banco",
              f"criado_em = {pedido.criado_em}")
    post("/logout")

    codigo = GatewayPagamentoSimulado().processar("pix", 790, {}).detalhes["copia_e_cola"]
    linha("DEF-04", "Código PIX copia-e-cola de R$ 7,90", codigo)
    i = codigo.index("54")
    linha("DEF-04", "Campo 54 (valor) e campo 59 (nome)",
          f"54 declara {codigo[i + 2:i + 4]} caracteres para o valor {codigo[i + 4:i + 8]!r}; "
          f"59 = {codigo[codigo.index('59', i):codigo.index('59', i) + 14]!r}")

    r = post("/pedidos/1/cancelar")
    linha("DEF-06", "Visitante sem login envia POST /pedidos/1/cancelar",
          f"HTTP {r.status_code} Location: {r.headers.get('Location')}")

    r = c.get("/logout")
    linha("DEF-07", "GET /logout (rota só aceita POST)",
          f"HTTP {r.status_code} - título: {r.get_data(as_text=True).split('<title>')[1].split('</title>')[0]}")

    h = c.get("/").headers
    for nome in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy", "Referrer-Policy"):
        linha("DEF-08", f"Cabeçalho {nome}", h.get(nome, "(ausente)"))

    html = c.get("/?q=%25").get_data(as_text=True)
    linha("DEF-09", "Busca na vitrine pelo texto '%' (só 'Chocolate 54%' contém o símbolo)",
          f"{html.count('<article class=\"card')} produto(s) listado(s)")
    html = c.get("/?q=_").get_data(as_text=True)
    linha("DEF-09", "Busca na vitrine pelo texto '_' (nenhum produto contém o símbolo)",
          f"{html.count('<article class=\"card')} produto(s) listado(s)")

    r = GatewayPagamentoSimulado().processar(
        "cartao", 1000, {"numero": "4111111111111111", "titular": "Maria", "validade": "12/30",
                         "cvv": "123", "parcelas": 3}).detalhes
    primeira = r.get("valor_primeira_parcela_centavos", r["valor_parcela_centavos"])
    soma = primeira + r["valor_parcela_centavos"] * 2
    linha("DEF-12", "Compra de R$ 10,00 em 3x", f"parcelas somam R$ {soma / 100:.2f}")

    os.close(fd)
    os.unlink(caminho)


if __name__ == "__main__":
    main()
