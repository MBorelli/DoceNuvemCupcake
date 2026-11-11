# Doce Nuvem Cupcakes — Loja virtual

Sistema web de uma loja virtual de cupcakes. Ele cobre a **vitrine virtual**, o **pedido eletrônico**, o **pagamento** e a **entrega**.

- **Front-end:** HTML5 (templates Jinja2), CSS3 e JavaScript puro (sem frameworks)
- **Back-end:** Python 3 + Flask, organizado no padrão **MVC (Model–View–Controller)**
- **Banco de dados:** SQLite no desenvolvimento local; PostgreSQL em produção (Vercel + Neon). As tabelas são criadas automaticamente
- **Hospedagem:** Vercel (veja [Publicação na Vercel](#publicação-na-vercel))

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

São 47 testes. Eles cobrem as regras de frete, o algoritmo de Luhn, o carrinho, o cadastro e o login, o pedido com PIX, cartão e boleto, o pagamento recusado (o pedido é desfeito por completo), o cancelamento com devolução de estoque, o fluxo de entrega pelo administrador, as permissões de acesso, a proteção CSRF e a tradução de SQL para o PostgreSQL. Os 12 testes de `tests/test_qualidade.py` reproduzem os defeitos corrigidos no [laudo de qualidade](docs/LAUDO_QUALIDADE.md).

---

## Publicação na Vercel

Na Vercel, a aplicação roda como uma *Vercel Function*. O sistema de arquivos é somente leitura e cada instância tem o seu, então **os dados precisam ficar num banco PostgreSQL externo**. Localmente, o sistema continua usando SQLite.

1. **Importe o repositório** em [vercel.com/new](https://vercel.com/new). A Vercel detecta o Flask pelo `pyproject.toml` (`entrypoint = "run:app"`). Não é preciso configurar build nem output.
2. **Crie o banco:** no projeto, abra **Storage → Create Database → Neon (Postgres)** e conecte-o ao projeto. A integração cria a variável `DATABASE_URL` automaticamente. O plano gratuito é suficiente.
3. **Defina a chave secreta** em **Settings → Environment Variables**:
   - `SECRET_KEY` = um valor aleatório e longo. Para gerar um: `python -c "import secrets; print(secrets.token_hex(32))"`
   - `ADMIN_SENHA` = a senha do administrador (`admin@cupcakes.com`) criado no primeiro acesso
4. **Faça um novo deploy** (Deployments → Redeploy) para que as variáveis passem a valer.

As tabelas e os dados de demonstração (produtos e contas de teste) são criados sozinhos no primeiro acesso.

| Variável       | Obrigatória | Para que serve |
|----------------|-------------|----------------|
| `SECRET_KEY`   | sim (na Vercel) | Assina o cookie de sessão. Sem ela, a aplicação não inicia na Vercel |
| `DATABASE_URL` | recomendada | URL do PostgreSQL. `POSTGRES_URL` também é aceita |
| `ADMIN_SENHA`  | recomendada | Senha do admin criado no primeiro acesso. Sem ela, na Vercel, é gerada uma senha aleatória que aparece uma única vez nos *Runtime Logs* |

> **Sem banco configurado**, a aplicação ainda abre, mas usa SQLite em `/tmp`. Pedidos e cadastros somem quando a instância é reciclada e não são compartilhados entre instâncias. Serve só para uma demonstração rápida.

> **Senha do administrador:** na Vercel, a senha pública `admin123` não é mais usada. Defina `ADMIN_SENHA` **antes do primeiro acesso**, porque ela só vale na criação do banco. Se o banco já foi criado com `admin123`, apague as tabelas no painel do Neon e faça um novo deploy. A conta `cliente@cupcakes.com` / `cliente123` continua existindo para demonstração.

---

## Arquitetura MVC

```
ProjetoIntegrador/
├── run.py                        # ponto de entrada (também usado pela Vercel)
├── pyproject.toml                # dependências + entrypoint da Vercel
├── requirements.txt
├── public/static/                # ── VIEW: CSS e JS (servidos pela CDN da Vercel)
│   ├── css/style.css
│   └── js/carrinho.js            #    carrinho (localStorage), vitrine, máscaras
│       js/checkout.js            #    frete por CEP, ViaCEP, validação do cartão
├── app/
│   ├── __init__.py               # fábrica da aplicação (create_app)
│   ├── database.py               # SQLite (local) ou PostgreSQL (produção), esquema e dados iniciais
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
│       └── templates/            #    HTML (Jinja2)
└── tests/
    ├── test_loja.py
    └── test_postgres_adaptador.py
```

Os arquivos CSS e JS fazem parte da camada View, mas ficam em `public/static/` porque a Vercel só serve arquivos estáticos dessa pasta.

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
