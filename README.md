# Doce Nuvem Cupcakes — Loja virtual

Sistema web de uma loja virtual de cupcakes. Ele cobre a **vitrine virtual**, o **pedido eletrônico**, o **pagamento** e a **entrega**.

- **Front-end:** HTML5 (templates Jinja2), CSS3 e JavaScript puro (sem frameworks)
- **Back-end:** Python 3 + Flask, organizado no padrão **MVC (Model–View–Controller)**
- **Banco de dados:** SQLite, criado automaticamente na primeira execução

## Como executar

```bash
pip install -r requirements.txt
python run.py
```

Depois acesse **http://127.0.0.1:5000**.

O banco (`instance/cupcakes.sqlite3`) é criado e populado sozinho na primeira execução. Para apagar tudo e recomeçar com os dados de demonstração:

```bash
flask --app run reset-db
```

### Contas de demonstração

| Perfil        | E-mail                 | Senha        |
|---------------|------------------------|--------------|
| Cliente       | cliente@cupcakes.com   | cliente123   |
| Administrador | admin@cupcakes.com     | admin123     |

### Dados de teste para pagamento (ambiente simulado)

| Situação           | Cartão                | Validade        | CVV |
|--------------------|-----------------------|-----------------|-----|
| Aprovado           | 4111 1111 1111 1111   | qualquer futura | 123 |
| Recusado (sem saldo) | 4000 0000 0000 0002 | qualquer futura | 123 |

Pedidos pagos com PIX ou boleto ficam em *Aguardando pagamento*. Na tela do pedido, o botão **"Simular confirmação do banco"** faz o papel da confirmação que, em produção, chegaria automaticamente pelo provedor de pagamento.

### CEPs para testar a entrega

| CEP         | Região                      | Frete                               | Prazo       |
|-------------|-----------------------------|-------------------------------------|-------------|
| 01310-100   | Grande São Paulo            | R$ 7,90 (grátis acima de R$ 100,00) | 1 dia útil  |
| 13010-000   | Interior e litoral de SP    | R$ 14,90                            | 2 dias úteis |
| 20040-020   | Fora da área (RJ)           | pedido bloqueado                    | —           |

### Testes automatizados

```bash
python -m unittest -v
```

São 28 testes. Eles cobrem as regras de frete, o algoritmo de Luhn, o carrinho, o cadastro e o login, o pedido com PIX, cartão e boleto, o pagamento recusado (o pedido é desfeito por completo), o cancelamento com devolução de estoque, o fluxo de entrega pelo administrador, as permissões de acesso e a proteção CSRF.

---

## Arquitetura MVC

```
ProjetoIntegrador/
├── run.py                        # ponto de entrada
├── requirements.txt
├── app/
│   ├── __init__.py               # fábrica da aplicação (create_app)
│   ├── database.py               # conexão SQLite, esquema e dados iniciais
│   │
│   ├── models/                   # ── MODEL: regras de negócio + persistência
│   │   ├── produto.py            #    cupcakes da vitrine
│   │   ├── cliente.py            #    cadastro e autenticação (senha com hash)
│   │   ├── carrinho.py           #    recalcula preços/estoque a partir do banco
│   │   ├── pedido.py             #    criação transacional + ciclo de vida (status)
│   │   ├── pagamento.py          #    gateway simulado: PIX, cartão, boleto
│   │   ├── entrega.py            #    endereço, frete por CEP, prazo, rastreio
│   │   └── erros.py              #    exceções de domínio
│   │
│   ├── controllers/              # ── CONTROLLER: rotas HTTP (Blueprints)
│   │   ├── vitrine_controller.py #    /  e  /produto/<id>
│   │   ├── carrinho_controller.py#    /carrinho, /api/carrinho, /api/frete
│   │   ├── pedido_controller.py  #    /checkout, /pedidos, cancelar, pagar
│   │   ├── auth_controller.py    #    /cadastro, /login, /logout
│   │   ├── admin_controller.py   #    /admin/pedidos, /admin/produtos
│   │   └── seguranca.py          #    CSRF, login_obrigatorio, admin_obrigatorio
│   │
│   └── views/                    # ── VIEW: apresentação
│       ├── helpers.py            #    filtros (R$, datas, telefone)
│       ├── templates/            #    HTML (Jinja2)
│       └── static/
│           ├── css/style.css
│           └── js/carrinho.js    #    carrinho (localStorage), vitrine, máscaras
│               js/checkout.js    #    frete por CEP, ViaCEP, validação do cartão
└── tests/test_loja.py
```

**Fluxo de uma requisição:** o navegador chama uma rota. O **Controller** lê os dados da requisição e aciona o **Model**, onde ficam todas as regras (estoque, frete, pagamento, transições de status). Em seguida, o Controller escolhe a **View** (template) que vai mostrar o resultado. Os controllers não têm SQL, e os templates não têm regra de negócio.

## Funcionalidades

### Vitrine virtual
- Cupcakes listados por categoria, com busca no servidor e filtro instantâneo em JavaScript
- Página de detalhe com seletor de quantidade e sugestões de sabores relacionados
- Selos de "Mais pedido" e "Esgotado"; produtos ocultos não aparecem na vitrine

### Pedido eletrônico
- Carrinho guardado no navegador (`localStorage`), com contador no topo sincronizado entre abas
- O servidor **nunca confia no preço enviado pelo navegador**: recebe apenas `produto_id` e `quantidade` e recalcula tudo a partir do banco
- A criação do pedido é **transacional**. Se qualquer etapa falhar (estoque, endereço ou pagamento recusado), nada é gravado
- A baixa de estoque é atômica (`UPDATE ... WHERE estoque >= ?`), o que impede vender mais unidades do que existem

### Pagamento
- PIX (código "copia e cola"), cartão de crédito (até 3x sem juros) e boleto
- O cartão é validado no front-end, para melhorar a experiência, e de novo no back-end: algoritmo de Luhn, validade, CVV e bandeira
- **O número completo do cartão e o CVV nunca são armazenados.** O sistema guarda apenas a bandeira, os 4 últimos dígitos e o número de parcelas
- O gateway é simulado. Para usar um provedor real (Mercado Pago, PagSeguro, Stripe...), basta trocar a classe `GatewayPagamentoSimulado` por outra com o mesmo método `processar()`

### Entrega
- Frete e prazo calculados pelo CEP (entrega regional, porque o produto é perecível), com frete grátis na Grande SP acima de R$ 100,00
- Endereço preenchido automaticamente pelo serviço ViaCEP; se o serviço falhar, o cliente digita normalmente
- Previsão de entrega em dias úteis (de segunda a sábado)
- Linha do tempo do pedido: *Aguardando pagamento → Pago → Em preparo → Saiu para entrega → Entregue*
- Código de rastreio gerado quando o pedido sai para entrega, com histórico de cada mudança de status
- O cliente pode cancelar enquanto o pedido não entrou em preparo. Nesse caso, o estoque é devolvido e o pagamento é estornado

### Painel administrativo
- Pedidos filtrados por status, com avanço de etapa direto na lista. Só são permitidas as transições válidas
- Cadastro e edição de cupcakes (preço, estoque, categoria, cores da ilustração com pré-visualização, visibilidade e destaque)

### Segurança
- Senhas armazenadas com hash (Werkzeug)
- Token CSRF em todos os formulários e requisições POST
- Controle de acesso: o cliente só vê os próprios pedidos, e o painel é restrito ao administrador
- Proteção contra redirecionamento aberto no parâmetro `next` do login
- Consultas SQL parametrizadas, sem risco de SQL injection
