"""Testes automatizados da loja.

Executar na raiz do projeto:
    python -m unittest -v
"""
import json
import os
import re
import tempfile
import unittest
from datetime import date

from app import create_app
from app.database import get_db
from app.models import ErroValidacao, Pedido, Produto, StatusPedido, calcular_frete
from app.models.pagamento import luhn_valido

CARTAO_OK = "4111 1111 1111 1111"
CARTAO_RECUSADO = "4000 0000 0000 0002"
VALIDADE = f"12/{(date.today().year + 2) % 100:02d}"

ENDERECO = {
    "destinatario": "Maria Teste", "telefone": "(11) 98888-7777", "cep": "01310-100",
    "logradouro": "Av. Paulista", "numero": "1000", "complemento": "", "bairro": "Bela Vista",
    "cidade": "São Paulo", "uf": "SP",
}


class BaseTeste(unittest.TestCase):
    def setUp(self):
        self.fd, self.caminho_db = tempfile.mkstemp(suffix=".sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": self.caminho_db, "DATABASE_URL": None,
                               "SECRET_KEY": "teste"})
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.fd)
        os.unlink(self.caminho_db)

    # ----------------------------------------------------------- utilitários
    def token(self):
        with self.client.session_transaction() as sessao:
            sessao.setdefault("_csrf", "token-teste")
            return sessao["_csrf"]

    def post(self, url, dados=None, **kwargs):
        dados = dict(dados or {})
        dados["csrf_token"] = self.token()
        return self.client.post(url, data=dados, **kwargs)

    def login(self, email="cliente@cupcakes.com", senha="cliente123"):
        return self.post("/login", {"email": email, "senha": senha})

    def estoque(self, produto_id):
        with self.app.app_context():
            return Produto.buscar_por_id(produto_id).estoque

    def checkout(self, itens, metodo="pix", **extra):
        dados = {**ENDERECO, "carrinho": json.dumps(itens), "metodo_pagamento": metodo, **extra}
        return self.post("/checkout", dados)

    def ultimo_pedido(self):
        with self.app.app_context():
            pedidos = Pedido.listar()
            return pedidos[0] if pedidos else None


class TestRegrasDeNegocio(BaseTeste):
    def test_luhn(self):
        self.assertTrue(luhn_valido("4111111111111111"))
        self.assertFalse(luhn_valido("4111111111111112"))

    def test_frete_grande_sp(self):
        frete = calcular_frete("01310-100", 5000)
        self.assertEqual(frete.valor_centavos, 790)
        self.assertEqual(frete.prazo_dias, 1)

    def test_frete_gratis_acima_de_100_reais(self):
        self.assertTrue(calcular_frete("01310100", 10000).gratis)
        self.assertEqual(calcular_frete("01310100", 10000).valor_centavos, 0)

    def test_frete_interior(self):
        self.assertEqual(calcular_frete("13010-000", 50000).valor_centavos, 1490)

    def test_cep_fora_da_area(self):
        with self.assertRaises(ErroValidacao):
            calcular_frete("20040-020")  # Rio de Janeiro

    def test_converter_preco(self):
        self.assertEqual(Produto.converter_preco("12,90"), 1290)
        self.assertEqual(Produto.converter_preco("R$ 1.234,50"), 123450)
        self.assertEqual(Produto.converter_preco("9.5"), 950)


class TestVitrineECarrinho(BaseTeste):
    def test_vitrine_lista_produtos(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Red Velvet", resposta.get_data(as_text=True))

    def test_filtro_por_categoria(self):
        html = self.client.get("/?categoria=Frutas").get_data(as_text=True)
        self.assertIn("Limão Siciliano", html)
        self.assertNotIn("Chocolate Belga", html)

    def test_pagina_produto(self):
        self.assertEqual(self.client.get("/produto/1").status_code, 200)
        self.assertEqual(self.client.get("/produto/9999").status_code, 404)

    def test_api_carrinho_recalcula_preco_e_ajusta_estoque(self):
        resposta = self.client.post(
            "/api/carrinho",
            json={"itens": [{"produto_id": 1, "quantidade": 2}, {"produto_id": 4, "quantidade": 999},
                            {"produto_id": 10, "quantidade": 1}]},
            headers={"X-CSRF-Token": self.token()},
        )
        dados = resposta.get_json()
        itens = {i["produto_id"]: i for i in dados["itens"]}
        self.assertEqual(itens[1]["subtotal_centavos"], 2 * 1290)
        self.assertEqual(itens[4]["quantidade"], 25)  # limitado ao estoque
        self.assertNotIn(10, itens)  # Pistache esgotado
        self.assertEqual(len(dados["avisos"]), 2)

    def test_api_frete(self):
        self.assertTrue(self.client.get("/api/frete?cep=01310100&subtotal=1000").get_json()["ok"])
        self.assertEqual(self.client.get("/api/frete?cep=123").status_code, 422)


class TestAutenticacao(BaseTeste):
    def test_cadastro_e_login(self):
        resposta = self.post("/cadastro", {
            "nome": "Ana Souza", "email": "ana@exemplo.com", "telefone": "11977776666",
            "senha": "segredo1", "confirmacao": "segredo1",
        })
        self.assertEqual(resposta.status_code, 302)
        self.post("/logout")
        self.assertEqual(self.login("ana@exemplo.com", "segredo1").status_code, 302)

    def test_email_duplicado(self):
        resposta = self.post("/cadastro", {
            "nome": "Outro", "email": "cliente@cupcakes.com", "senha": "123456", "confirmacao": "123456",
        })
        self.assertIn("Já existe uma conta", resposta.get_data(as_text=True))

    def test_senha_errada(self):
        self.assertIn("incorretos", self.login(senha="errada").get_data(as_text=True))

    def test_checkout_exige_login(self):
        resposta = self.client.get("/checkout")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.headers["Location"])

    def test_post_sem_csrf_e_rejeitado(self):
        resposta = self.client.post("/login", data={"email": "x", "senha": "y"})
        self.assertEqual(resposta.status_code, 400)


class TestPedidoPagamentoEntrega(BaseTeste):
    def setUp(self):
        super().setUp()
        self.login()

    def test_pedido_pix_baixa_estoque_e_aguarda_pagamento(self):
        estoque_antes = self.estoque(1)
        resposta = self.checkout([{"produto_id": 1, "quantidade": 3}], "pix")
        self.assertEqual(resposta.status_code, 302)
        pedido = self.ultimo_pedido()
        self.assertEqual(pedido.status, StatusPedido.AGUARDANDO_PAGAMENTO)
        self.assertEqual(pedido.subtotal_centavos, 3 * 1290)
        self.assertEqual(pedido.frete_centavos, 790)
        self.assertEqual(pedido.total_centavos, 3 * 1290 + 790)
        self.assertEqual(self.estoque(1), estoque_antes - 3)

        html = self.client.get(f"/pedidos/{pedido.id}").get_data(as_text=True)
        self.assertIn("Pague com PIX", html)

        self.post(f"/pedidos/{pedido.id}/simular-pagamento")
        self.assertEqual(self.ultimo_pedido().status, StatusPedido.PAGO)

    def test_cartao_aprovado_marca_pedido_como_pago(self):
        self.checkout([{"produto_id": 2, "quantidade": 10}], "cartao",
                      cartao_numero=CARTAO_OK, cartao_titular="MARIA TESTE",
                      cartao_validade=VALIDADE, cartao_cvv="123", cartao_parcelas="2")
        pedido = self.ultimo_pedido()
        self.assertEqual(pedido.status, StatusPedido.PAGO)
        self.assertEqual(pedido.frete_centavos, 0)  # 10 × 11,90 ≥ R$ 100 → frete grátis
        with self.app.app_context():
            detalhes = Pedido.buscar_por_id(pedido.id).pagamento.detalhes
        self.assertEqual(detalhes["final"], "1111")
        self.assertNotIn("4111111111111111", json.dumps(detalhes))  # número completo nunca é salvo

    def test_cartao_recusado_nao_cria_pedido_nem_baixa_estoque(self):
        estoque_antes = self.estoque(2)
        resposta = self.checkout([{"produto_id": 2, "quantidade": 1}], "cartao",
                                 cartao_numero=CARTAO_RECUSADO, cartao_titular="MARIA",
                                 cartao_validade=VALIDADE, cartao_cvv="123", cartao_parcelas="1")
        self.assertEqual(resposta.status_code, 422)
        self.assertIn("recusada", resposta.get_data(as_text=True))
        self.assertIsNone(self.ultimo_pedido())
        self.assertEqual(self.estoque(2), estoque_antes)

    def test_cartao_invalido(self):
        resposta = self.checkout([{"produto_id": 2, "quantidade": 1}], "cartao",
                                 cartao_numero="1234 5678 9012 3456", cartao_titular="X",
                                 cartao_validade="13/20", cartao_cvv="1", cartao_parcelas="9")
        html = resposta.get_data(as_text=True)
        self.assertIn("Número do cartão inválido", html)
        self.assertIsNone(self.ultimo_pedido())

    def test_cep_fora_da_area_bloqueia_pedido(self):
        resposta = self.checkout([{"produto_id": 1, "quantidade": 1}], "pix", cep="20040-020")
        self.assertIn("Ainda não entregamos", resposta.get_data(as_text=True))
        self.assertIsNone(self.ultimo_pedido())

    def test_estoque_insuficiente_bloqueia_pedido(self):
        resposta = self.checkout([{"produto_id": 4, "quantidade": 26}], "pix")
        self.assertIn("Temos apenas 25", resposta.get_data(as_text=True))
        self.assertIsNone(self.ultimo_pedido())

    def test_carrinho_vazio(self):
        resposta = self.checkout([], "pix")
        self.assertIn("carrinho está vazio", resposta.get_data(as_text=True))

    def test_cancelamento_devolve_estoque(self):
        estoque_antes = self.estoque(3)
        self.checkout([{"produto_id": 3, "quantidade": 5}], "boleto")
        pedido = self.ultimo_pedido()
        self.assertEqual(self.estoque(3), estoque_antes - 5)
        self.post(f"/pedidos/{pedido.id}/cancelar")
        self.assertEqual(self.ultimo_pedido().status, StatusPedido.CANCELADO)
        self.assertEqual(self.estoque(3), estoque_antes)

    def test_fluxo_completo_de_entrega_pelo_admin(self):
        self.checkout([{"produto_id": 1, "quantidade": 1}], "pix")
        pedido_id = self.ultimo_pedido().id
        self.post("/logout")
        self.login("admin@cupcakes.com", "admin123")

        # Transição inválida (pular etapas) é recusada.
        self.post(f"/admin/pedidos/{pedido_id}/status", {"status": StatusPedido.ENTREGUE})
        self.assertEqual(self.ultimo_pedido().status, StatusPedido.AGUARDANDO_PAGAMENTO)

        for status in (StatusPedido.PAGO, StatusPedido.EM_PREPARO,
                       StatusPedido.SAIU_PARA_ENTREGA, StatusPedido.ENTREGUE):
            self.post(f"/admin/pedidos/{pedido_id}/status", {"status": status})
            self.assertEqual(self.ultimo_pedido().status, status)

        with self.app.app_context():
            pedido = Pedido.buscar_por_id(pedido_id)
            self.assertRegex(pedido.entrega.codigo_rastreio, r"^DN\d{9}BR$")
            self.assertEqual(len(pedido.historico), 5)

        html = self.client.get("/admin/pedidos").get_data(as_text=True)
        self.assertIn(f"#{pedido_id}", html)


class TestPermissoes(BaseTeste):
    def test_cliente_nao_acessa_admin(self):
        self.login()
        self.assertEqual(self.client.get("/admin/pedidos").status_code, 404)

    def test_cliente_nao_ve_pedido_de_outro(self):
        self.login()
        self.checkout([{"produto_id": 1, "quantidade": 1}], "pix")
        pedido_id = self.ultimo_pedido().id
        self.post("/logout")
        self.post("/cadastro", {"nome": "Intruso Silva", "email": "intruso@exemplo.com",
                                "senha": "123456", "confirmacao": "123456"})
        self.assertEqual(self.client.get(f"/pedidos/{pedido_id}").status_code, 404)

    def test_admin_cadastra_produto(self):
        self.login("admin@cupcakes.com", "admin123")
        resposta = self.post("/admin/produtos/novo", {
            "nome": "Café com Canela", "descricao": "Teste", "categoria": "Especiais",
            "preco": "13,50", "estoque": "12", "cor_cobertura": "#c8a27a",
            "cor_forminha": "#5a3220", "ativo": "on",
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("Café com Canela", self.client.get("/").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
