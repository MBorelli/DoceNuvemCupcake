"""Testes de regressão do laudo de qualidade (docs/LAUDO_QUALIDADE.md).

Cada teste reproduz um defeito encontrado na inspeção (DEF-xx). Antes da
correção, o teste falhava. Agora deve passar.

Executar:  python -m unittest tests.test_qualidade -v
Para simular o fuso UTC da Vercel:  TZ=UTC0 python -m unittest tests.test_qualidade -v
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from unittest import mock

from app.database import agora, get_db
from app.models import Cliente, ErroValidacao, Pedido, StatusPedido
from app.models.pagamento import GatewayPagamentoSimulado

from .test_loja import CARTAO_OK, VALIDADE, BaseTeste

ID_GIGANTE = 10 ** 20  # maior que o INTEGER de 64 bits do SQLite/PostgreSQL


def crc16_ccitt(texto: str) -> str:
    crc = 0xFFFF
    for byte in texto.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def ler_tlv(texto: str) -> dict:
    """Lê o formato EMV (ID de 2 dígitos + tamanho de 2 dígitos + valor)."""
    campos, i = {}, 0
    while i < len(texto):
        ident, tamanho = texto[i:i + 2], int(texto[i + 2:i + 4])
        campos[ident] = texto[i + 4:i + 4 + tamanho]
        i += 4 + tamanho
    return campos


class TestDefeitosLaudo(BaseTeste):
    def admin(self):
        return self.login("admin@cupcakes.com", "admin123")

    def pedido_pix(self):
        self.login()
        self.checkout([{"produto_id": 1, "quantidade": 1}])
        return self.ultimo_pedido()

    # DEF-01 ---------------------------------------------------------------
    def test_def01_id_gigante_nao_derruba_rotas_publicas(self):
        r = self.client.post("/api/carrinho", json={"itens": [{"produto_id": ID_GIGANTE, "quantidade": 1}]},
                             headers={"X-CSRF-Token": self.token()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["itens"], [])
        self.assertEqual(self.client.get(f"/produto/{ID_GIGANTE}").status_code, 404)
        self.login()
        self.assertEqual(self.client.get(f"/pedidos/{ID_GIGANTE}").status_code, 404)

    # DEF-02 ---------------------------------------------------------------
    def test_def02_preco_e_estoque_absurdos_viram_mensagem_de_erro(self):
        self.admin()
        base = {"nome": "Teste", "descricao": "x", "categoria": "Clássicos",
                "cor_cobertura": "#ffffff", "cor_forminha": "#000000", "estoque": "1", "preco": "10"}
        for campo, valor in (("preco", "NaN"), ("preco", "Infinity"), ("preco", "1e30"), ("preco", "50000,00"),
                             ("estoque", str(ID_GIGANTE))):
            with self.subTest(campo=campo, valor=valor):
                r = self.post("/admin/produtos/novo", {**base, campo: valor})
                self.assertEqual(r.status_code, 200)
                self.assertIn("alerta--erro", r.get_data(as_text=True))

    # DEF-03 ---------------------------------------------------------------
    def test_def03_horario_registrado_e_o_de_brasilia(self):
        esperado = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-3)))
        registrado = datetime.fromisoformat(agora())
        self.assertLess(abs(registrado - esperado.replace(tzinfo=None)), timedelta(minutes=1))

    # DEF-04 ---------------------------------------------------------------
    def test_def04_codigo_pix_segue_o_padrao_br_code(self):
        codigo = GatewayPagamentoSimulado().processar("pix", 12345, {}).detalhes["copia_e_cola"]
        campos = ler_tlv(codigo)  # falha se algum tamanho declarado estiver errado
        self.assertEqual(campos["54"], "123.45")
        self.assertEqual(campos["59"], "DOCE NUVEM")
        self.assertEqual(campos["63"], crc16_ccitt(codigo[:-4]))

    # DEF-05 ---------------------------------------------------------------
    def test_def05_cancelamento_concorrente_nao_gera_erro_500(self):
        pedido = self.pedido_pix()
        with self.app.app_context():
            desatualizado = Pedido.buscar_por_id(pedido.id)  # cliente abriu a página
            Pedido.buscar_por_id(pedido.id).alterar_status(StatusPedido.CANCELADO)  # outra aba cancelou
        with mock.patch.object(Pedido, "buscar_por_id", return_value=desatualizado):
            r = self.post(f"/pedidos/{pedido.id}/cancelar")
        self.assertEqual(r.status_code, 302)

    # DEF-06 ---------------------------------------------------------------
    def test_def06_login_nao_volta_para_rota_que_so_aceita_post(self):
        r = self.post("/pedidos/1/cancelar")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("cancelar", r.headers["Location"])

    # DEF-07 ---------------------------------------------------------------
    def test_def07_paginas_de_erro_em_portugues(self):
        r = self.client.get("/logout")
        self.assertEqual(r.status_code, 405)
        self.assertIn("Doce Nuvem", r.get_data(as_text=True))

        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        with mock.patch("app.controllers.vitrine_controller.Produto.listar", side_effect=RuntimeError):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 500)
        self.assertIn("Doce Nuvem", r.get_data(as_text=True))

    # DEF-08 ---------------------------------------------------------------
    def test_def08_cabecalhos_de_seguranca(self):
        h = self.client.get("/").headers
        self.assertEqual(h.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(h.get("X-Frame-Options"), "DENY")
        self.assertIn("frame-ancestors 'none'", h.get("Content-Security-Policy", ""))
        self.assertTrue(h.get("Referrer-Policy"))

    # DEF-09 ---------------------------------------------------------------
    def test_def09_curingas_da_busca_sao_literais(self):
        # "%" como texto: só o Chocolate Belga tem "%" na descrição ("chocolate 54%").
        html = self.client.get("/?q=%25").get_data(as_text=True)
        self.assertEqual(html.count('<article class="card'), 1, "a busca por '%' virou curinga")
        self.assertIn("Chocolate Belga", html)
        # "_" como texto: nenhum produto tem sublinhado.
        html = self.client.get("/?q=_").get_data(as_text=True)
        self.assertEqual(html.count('<article class="card'), 0, "a busca por '_' virou curinga")

    # DEF-10 ---------------------------------------------------------------
    def test_def10_email_duplicado_em_concorrencia_vira_mensagem(self):
        class ConexaoSemPreChecagem:
            """Simula outra requisição gravando o mesmo e-mail entre a checagem e o INSERT."""
            def __init__(self, db):
                self._db = db

            def execute(self, sql, params=()):
                if sql.startswith("SELECT 1 FROM clientes"):
                    return self._db.execute("SELECT 1 WHERE 0")
                return self._db.execute(sql, params)

            def __getattr__(self, nome):
                return getattr(self._db, nome)

        with self.app.app_context():
            falsa = ConexaoSemPreChecagem(get_db())
            with mock.patch("app.models.cliente.get_db", return_value=falsa):
                with self.assertRaises(ErroValidacao):
                    Cliente.cadastrar("Outra Pessoa", "cliente@cupcakes.com", "segredo1")

    # DEF-11 ---------------------------------------------------------------
    def test_def11_senha_do_admin_configuravel_por_variavel_de_ambiente(self):
        os.close(self.fd)
        os.unlink(self.caminho_db)
        with mock.patch.dict(os.environ, {"ADMIN_SENHA": "S3nh@-Forte-Producao"}):
            self.setUp()  # create_app() cria e popula um banco novo
        self.assertIn("E-mail ou senha incorretos", self.admin().get_data(as_text=True))
        self.assertEqual(self.login("admin@cupcakes.com", "S3nh@-Forte-Producao").status_code, 302)

    # DEF-12 ---------------------------------------------------------------
    def test_def12_soma_das_parcelas_igual_ao_total(self):
        r = GatewayPagamentoSimulado().processar(
            "cartao", 1000, {"numero": CARTAO_OK, "titular": "Maria", "validade": VALIDADE,
                             "cvv": "123", "parcelas": 3})
        d = r.detalhes
        soma = d["valor_primeira_parcela_centavos"] + d["valor_parcela_centavos"] * (d["parcelas"] - 1)
        self.assertEqual(soma, 1000)
