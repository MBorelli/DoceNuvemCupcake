# Laudo de Qualidade de Software: Doce Nuvem Cupcakes

| | |
|---|---|
| **Sistema avaliado** | Doce Nuvem Cupcakes, loja virtual com vitrine, pedido eletrônico, pagamento e entrega |
| **Tecnologias** | Python 3.12 + Flask (padrão MVC), HTML5/Jinja2, CSS3, JavaScript; SQLite (local) e PostgreSQL (produção na Vercel) |
| **Versão avaliada** | commit `cd2e750` ("Alterações realizadas para hospedar a aplicação na Vercel") |
| **Data da avaliação** | 10/11/2026 |
| **Disciplina** | Projeto Integrador Transdisciplinar em Engenharia de Software II |
| **Resultado** | 12 defeitos encontrados (2 de severidade alta, 4 média e 6 baixa). **Todos foram corrigidos e verificados.** Ao final, 47 de 47 testes automatizados passam. |

---

## 1. Objetivo

Avaliar a qualidade do sistema antes da publicação em produção. Este laudo:

1. identifica os defeitos de funcionamento, segurança e robustez;
2. registra a **evidência** de cada defeito, isto é, a prova de que ele existia;
3. descreve a **correção** aplicada;
4. registra a **evidência de que a correção funciona**.

## 2. Escopo

| Incluído | Não incluído |
|---|---|
| Todo o back-end (`app/models`, `app/controllers`, `app/database.py`, `app/__init__.py`) | Teste de carga e desempenho |
| Templates Jinja2 e scripts `public/static/js` | Teste em um servidor PostgreSQL real (veja a seção 8) |
| Configuração de publicação na Vercel | Teste visual em vários navegadores |
| Regras de negócio: estoque, frete, pagamento, status do pedido | Integração com um gateway de pagamento real (o gateway do projeto é simulado) |

## 3. Metodologia

Foram usadas três técnicas complementares:

1. **Inspeção de código (revisão estática).** Leitura de todos os models, controllers e scripts, buscando entradas não validadas, exceções não tratadas, condições de corrida, dependência do ambiente (relógio, sistema de arquivos) e falhas de segurança (OWASP Top 10).
2. **Testes de regressão.** Cada defeito virou um teste automatizado em [`tests/test_qualidade.py`](../tests/test_qualidade.py). O teste foi executado **antes** da correção, para provar o defeito (ele falha), e **depois**, para provar a correção (ele passa). Esse é o ciclo *vermelho → verde*.
3. **Coleta de evidências HTTP.** O script [`docs/evidencias/coletar_evidencias.py`](evidencias/coletar_evidencias.py) sobe a aplicação, executa os cenários de cada defeito e registra o que o servidor respondeu: código HTTP, cabeçalhos e valores gravados. O mesmo script foi rodado antes e depois das correções.

**Simulação do ambiente da Vercel.** Os servidores da Vercel rodam no fuso **UTC**. Todos os testes e coletas foram executados com a variável `TZ=UTC0`, que faz o processo Python usar o relógio UTC, como em produção. Sem essa simulação, o defeito DEF-03 não aparece no computador de desenvolvimento, que está no horário de Brasília.

**Como reproduzir:**

```bash
TZ=UTC0 python -m unittest tests.test_qualidade -v        # testes do laudo
TZ=UTC0 python docs/evidencias/coletar_evidencias.py      # evidências HTTP
python -m unittest -v                                      # suíte completa
```

### Critério de severidade

| Severidade | Critério |
|---|---|
| **Alta** | Compromete a segurança do sistema ou produz dados incorretos em todo o uso normal em produção |
| **Média** | Qualquer visitante consegue provocar um erro 500, ou uma funcionalidade fica inutilizável num cenário plausível |
| **Baixa** | Afeta só usabilidade, mensagens ou casos raros (concorrência, entrada do administrador), sem perda de dados |

## 4. Ambiente da avaliação

| Item | Valor |
|---|---|
| Sistema operacional | Windows 10 Pro 10.0.19045 |
| Python | 3.12.2 |
| Banco nos testes | SQLite (arquivo temporário por teste) |
| Relógio simulado | `TZ=UTC0` (igual aos servidores da Vercel) |
| Horário da coleta | 10/11/2026 às 23h17 (Brasília), que já é 11/11/2026 às 02h17 em UTC |

## 5. Resumo dos resultados

| ID | Defeito | Severidade | Antes | Depois |
|---|---|---|---|---|
| [DEF-11](#def-11--senha-padrão-do-administrador-em-produção) | Senha padrão e pública do administrador em produção | **Alta** | Admin entra com `admin123` | Senha definida por `ADMIN_SENHA` ou gerada aleatoriamente |
| [DEF-03](#def-03--data-e-hora-gravadas-no-fuso-do-servidor-utc) | Data e hora gravadas no fuso do servidor (UTC) | **Alta** | Pedido das 23h17 gravado como 02h17 do dia seguinte | Gravado como 23h17 |
| [DEF-01](#def-01--ids-muito-grandes-derrubam-rotas-públicas-erro-500) | IDs muito grandes derrubam rotas públicas | Média | HTTP 500 | HTTP 200 / 404 |
| [DEF-04](#def-04--código-pix-copia-e-cola-fora-do-padrão-br-code) | Código PIX fora do padrão BR Code | Média | Tamanhos errados e CRC aleatório | Tamanhos e CRC corretos |
| [DEF-05](#def-05--cancelamento-simultâneo-gera-erro-500) | Cancelamento simultâneo gera erro 500 | Média | HTTP 500 | Mensagem de aviso |
| [DEF-08](#def-08--ausência-de-cabeçalhos-de-segurança-http) | Ausência de cabeçalhos de segurança HTTP | Média | 4 cabeçalhos ausentes | 4 cabeçalhos presentes |
| [DEF-02](#def-02--preço-ou-estoque-absurdos-derrubam-o-cadastro-de-produto) | Preço ou estoque absurdos derrubam o cadastro de produto | Baixa | HTTP 500 | Mensagem de validação |
| [DEF-06](#def-06--login-redireciona-para-rota-que-só-aceita-post) | Login redireciona para rota que só aceita POST | Baixa | `next=/pedidos/1/cancelar` | Sem `next` |
| [DEF-07](#def-07--páginas-de-erro-405-e-500-em-inglês-e-fora-do-layout) | Páginas de erro 405 e 500 em inglês e fora do layout | Baixa | "405 Method Not Allowed" | "Erro 405 · Doce Nuvem Cupcakes" |
| [DEF-09](#def-09--caracteres--e-_-funcionam-como-curinga-na-busca) | `%` e `_` funcionam como curinga na busca | Baixa | 10 produtos | 1 e 0 produtos |
| [DEF-10](#def-10--cadastro-simultâneo-com-o-mesmo-e-mail-gera-erro-500) | Cadastro simultâneo com o mesmo e-mail gera erro 500 | Baixa | `IntegrityError` | Mensagem de validação |
| [DEF-12](#def-12--soma-das-parcelas-diferente-do-total) | Soma das parcelas diferente do total | Baixa | R$ 9,99 | R$ 10,00 |

**Execução dos testes do laudo** ([01](evidencias/01_testes_antes_da_correcao.txt) e [03](evidencias/03_testes_depois_da_correcao.txt)):

```text
ANTES:   Ran 12 tests ... FAILED (failures=7, errors=9)
DEPOIS:  Ran 12 tests ... OK
```

**Suíte completa após as correções** ([05](evidencias/05_suite_completa_depois.txt) e [06](evidencias/06_suite_completa_fuso_local.txt)):

```text
TZ=UTC0 (Vercel):   Ran 47 tests ... OK
Fuso local (BRT):   Ran 47 tests ... OK
```

Os 35 testes que já existiam continuam passando, então nenhuma funcionalidade anterior foi quebrada.

---

## 6. Defeitos encontrados, evidências e correções

### DEF-11 · Senha padrão do administrador em produção

| | |
|---|---|
| **Severidade** | Alta (segurança: OWASP A07, falhas de identificação e autenticação) |
| **Local** | `app/database.py`, função `popular()` |

**Descrição.** No primeiro acesso, o banco era populado com o administrador `admin@cupcakes.com` e a senha fixa `admin123`. Essa senha está escrita no código e no README, que são públicos no GitHub. Na Vercel, qualquer pessoa que lesse o repositório poderia entrar no painel administrativo, alterar preços, esconder produtos e mudar o status de pedidos.

**Evidência (antes).** O teste `test_def11` define a variável `ADMIN_SENHA` e mesmo assim consegue entrar com `admin123`. O login é aceito, com redirecionamento 302 para a vitrine:

```text
FAIL: test_def11_senha_do_admin_configuravel_por_variavel_de_ambiente
AssertionError: 'E-mail ou senha incorretos' not found in '<!doctype html>
<title>Redirecting...</title> ... <a href="/">/</a>
```

**Correção.** A nova função `_senha_inicial_admin()` (`app/database.py`, linha 274) segue esta ordem:

1. Se a variável de ambiente `ADMIN_SENHA` existir, usa essa senha.
2. Se estiver na Vercel sem `ADMIN_SENHA`, **gera uma senha aleatória** (`secrets.token_urlsafe`) e a mostra uma única vez nos *Runtime Logs*.
3. Só no computador local continua usando `admin123`, para facilitar a demonstração.

O README foi atualizado com a nova variável.

**Evidência (depois).** O teste passa: `admin123` é recusada e a senha da variável é aceita.

```text
test_def11_senha_do_admin_configuravel_por_variavel_de_ambiente ... ok
```

---

### DEF-03 · Data e hora gravadas no fuso do servidor (UTC)

| | |
|---|---|
| **Severidade** | Alta (dados incorretos em produção) |
| **Local** | `app/database.py` `agora()`; `app/models/entrega.py` `Frete.previsao`; `app/models/pagamento.py` (validade do PIX, vencimento do boleto, validade do cartão) |

**Descrição.** O sistema usava `datetime.now()` e `date.today()`, que devolvem a hora **do servidor**. Na Vercel, o servidor fica em UTC, 3 horas à frente de Brasília. Por isso, entre 21h e 0h:

- o pedido fica registrado **no dia seguinte** (o cliente vê "Realizado em 11/11 às 02:17");
- a **previsão de entrega** é calculada a partir do dia errado e pode pular um dia;
- o **vencimento do boleto** e a **validade do PIX** ficam deslocados;
- nas últimas 3 horas de cada mês, um cartão que vence naquele mês é **recusado como vencido**.

**Evidência (antes).** Coleta HTTP [02](evidencias/02_http_antes_da_correcao.txt), com o servidor simulado em UTC:

```text
Data/hora da coleta (Brasília): 10/11/2026 23:17:42
Relógio do processo (simulando o servidor): 11/11/2026 02:17:42
[DEF-03] Pedido criado agora - horário gravado no banco
        -> criado_em = 2026-11-11T02:17:43        ← dia e hora errados
```

```text
FAIL: test_def03_horario_registrado_e_o_de_brasilia
AssertionError: datetime.timedelta(seconds=10799, ...) not less than datetime.timedelta(seconds=60)
                 ↑ diferença de 3 horas
```

**Correção.** Foi criado o fuso fixo da loja, `FUSO_LOJA = UTC−3` (`app/database.py`, linha 137). O Brasil não tem horário de verão desde 2019. Também foram criadas as funções `agora_local()` e `hoje()`. Todos os usos de `datetime.now()` e `date.today()` foram substituídos por elas. O fuso é um deslocamento fixo, e não `ZoneInfo("America/Sao_Paulo")`, porque a base de fusos `tzdata` não existe no Windows. Isso foi confirmado durante a avaliação com `ZoneInfoNotFoundError`.

**Evidência (depois).** Coleta [04](evidencias/04_http_depois_da_correcao.txt), ainda com o servidor em UTC:

```text
Data/hora da coleta (Brasília): 10/11/2026 23:17:21
[DEF-03] Pedido criado agora - horário gravado no banco
        -> criado_em = 2026-11-10T23:17:22        ← correto
```

---

### DEF-01 · IDs muito grandes derrubam rotas públicas (erro 500)

| | |
|---|---|
| **Severidade** | Média (disponibilidade: qualquer visitante, mesmo sem login, provoca o erro) |
| **Local** | `app/models/carrinho.py` `normalizar_itens()`; `buscar_por_id()` de `Produto`, `Pedido` e `Cliente` |

**Descrição.** As rotas `/produto/<id>`, `/pedidos/<id>` e a API `/api/carrinho` aceitavam qualquer número inteiro. Um número maior que o limite do banco (por exemplo, 100000000000000000000) causava `OverflowError` no SQLite ou *integer out of range* no PostgreSQL. O resultado era **erro 500** numa rota pública.

**Evidência (antes):**

```text
[DEF-01] POST /api/carrinho com produto_id=100000000000000000000  -> HTTP 500
[DEF-01] GET /produto/100000000000000000000                       -> HTTP 500

ERROR: test_def01_id_gigante_nao_derruba_rotas_publicas
OverflowError: Python int too large to convert to SQLite INTEGER
```

**Correção.** Foi criada a função `id_valido()` (`app/database.py`, linha 157), que aceita apenas `0 < id ≤ 2.147.483.647`. Esse é o limite do tipo INTEGER do PostgreSQL, o mais restritivo entre os dois bancos. A função é usada em `normalizar_itens()` e em todos os `buscar_por_id()`. Um ID fora da faixa agora é tratado como "não encontrado".

**Evidência (depois):**

```text
[DEF-01] POST /api/carrinho com produto_id=100000000000000000000  -> HTTP 200   (carrinho vazio)
[DEF-01] GET /produto/100000000000000000000                       -> HTTP 404
```

---

### DEF-04 · Código PIX copia-e-cola fora do padrão BR Code

| | |
|---|---|
| **Severidade** | Média (o código de pagamento é inválido) |
| **Local** | `app/models/pagamento.py`, `GatewayPagamentoSimulado._pix()` |

**Descrição.** O código PIX segue o padrão EMV (BR Code), em que cada campo tem a forma **ID + tamanho + valor**. O código antigo tinha três erros:

1. O tamanho do **campo 54 (valor)** era fixo em `06`. Isso só está certo para valores com 6 caracteres, como `123.45`. Para R$ 7,90 (`7.90`, 4 caracteres), o código ficava corrompido.
2. O **campo 59 (nome)** declarava `11` caracteres, mas "DOCE NUVEM" tem 10.
3. O **campo 63 (CRC)** era gerado aleatoriamente (`secrets.token_hex(2)`), em vez do CRC16-CCITT exigido pelo Banco Central.

Mesmo num ambiente simulado, um aplicativo de banco rejeitaria esse código.

**Evidência (antes):**

```text
[DEF-04] Código PIX copia-e-cola de R$ 7,90
  -> ...530398654067.905802BR5911DOCE NUVEM6009SAO PAULO...6304311F
[DEF-04] Campo 54 (valor) e campo 59 (nome)
  -> 54 declara 06 caracteres para o valor '7.90'; 59 = '5911DOCE NUVEM'

ERROR: test_def04_codigo_pix_segue_o_padrao_br_code
ValueError: invalid literal for int() with base 10: '9S'   ← a leitura do código se perde
```

**Correção.** O código passou a ser montado com a função `_campo_emv()`, que calcula o tamanho de cada campo a partir do valor real. O CRC agora é calculado de verdade por `crc16_ccitt()` (`pagamento.py`, linha 25).

**Evidência (depois).** O teste lê o código campo a campo e confere o CRC:

```text
[DEF-04] Código PIX copia-e-cola de R$ 7,90
  -> ...530398654047.905802BR5910DOCE NUVEM6009SAO PAULO...6304F390
[DEF-04] Campo 54 (valor) e campo 59 (nome)
  -> 54 declara 04 caracteres para o valor '7.90'; 59 = '5910DOCE NUVEM'
```

---

### DEF-05 · Cancelamento simultâneo gera erro 500

| | |
|---|---|
| **Severidade** | Média |
| **Local** | `app/controllers/pedido_controller.py`, rotas `cancelar` e `simular_pagamento` |

**Descrição.** O model `Pedido.alterar_status()` já detectava corretamente quando outra pessoa tinha alterado o pedido, usando `UPDATE ... WHERE status = ?`, e lançava `ErroValidacao`. Os controllers, porém, **não tratavam essa exceção**. Exemplos: o cliente cancela em duas abas, ou o administrador muda o pedido para "Em preparo" no mesmo instante em que o cliente clica em "Cancelar". Nesses casos, o cliente recebia um erro 500.

**Evidência (antes):**

```text
ERROR: test_def05_cancelamento_concorrente_nao_gera_erro_500
  File "app\controllers\pedido_controller.py", line 86, in cancelar
    pedido.alterar_status(StatusPedido.CANCELADO, "Pedido cancelado pelo cliente.")
app.models.erros.ErroValidacao: O pedido foi alterado por outra pessoa. Recarregue a página.
```

**Correção.** As duas rotas agora capturam `ErroValidacao` e mostram a mensagem ao cliente (`pedido_controller.py`, linhas 88 e 108).

**Evidência (depois):** `test_def05_cancelamento_concorrente_nao_gera_erro_500 ... ok`. A resposta é HTTP 302 de volta ao pedido, com o aviso na tela.

---

### DEF-08 · Ausência de cabeçalhos de segurança HTTP

| | |
|---|---|
| **Severidade** | Média (segurança: OWASP A05, configuração de segurança incorreta) |
| **Local** | `app/controllers/seguranca.py` |

**Descrição.** As respostas não traziam cabeçalhos de proteção. Sem `X-Frame-Options` e `frame-ancestors`, outro site poderia carregar a loja dentro de um `<iframe>` invisível e induzir o administrador a clicar em botões, um ataque chamado *clickjacking*.

**Evidência (antes):**

```text
[DEF-08] Cabeçalho X-Content-Type-Options   -> (ausente)
[DEF-08] Cabeçalho X-Frame-Options          -> (ausente)
[DEF-08] Cabeçalho Content-Security-Policy  -> (ausente)
[DEF-08] Cabeçalho Referrer-Policy          -> (ausente)
```

**Correção.** A nova função `cabecalhos_de_seguranca()` (`seguranca.py`, linha 56) é registrada com `after_request` e se aplica a todas as respostas.

**Evidência (depois):**

```text
[DEF-08] Cabeçalho X-Content-Type-Options   -> nosniff
[DEF-08] Cabeçalho X-Frame-Options          -> DENY
[DEF-08] Cabeçalho Content-Security-Policy  -> frame-ancestors 'none'
[DEF-08] Cabeçalho Referrer-Policy          -> strict-origin-when-cross-origin
```

---

### DEF-02 · Preço ou estoque absurdos derrubam o cadastro de produto

| | |
|---|---|
| **Severidade** | Baixa (só o administrador alcança) |
| **Local** | `app/models/produto.py`, `converter_preco()` e `validar()` |

**Descrição.** A classe `Decimal` do Python aceita os textos `"NaN"` e `"Infinity"`. Esses valores quebravam a conversão para centavos. Um estoque ou preço gigante estourava o limite do banco. Em todos esses casos, o administrador via um erro 500 em vez de uma mensagem.

**Evidência (antes):**

```text
[DEF-02] Admin cadastra produto com preco=NaN                        -> HTTP 500
[DEF-02] Admin cadastra produto com preco=Infinity                   -> HTTP 500
[DEF-02] Admin cadastra produto com estoque=100000000000000000000    -> HTTP 500

ValueError: cannot convert NaN to integer
decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]
OverflowError: Python int too large to convert to SQLite INTEGER
```

**Correção.** `converter_preco()` agora recusa valores não finitos (`is_finite()`). `validar()` passou a ter limites de negócio: preço de até **R$ 10.000,00** e estoque de até **100.000** unidades.

**Evidência (depois).** Os quatro cenários retornam HTTP 200, com o formulário e a mensagem de erro. O teste também cobre um preço de R$ 50.000,00, acima do limite.

---

### DEF-06 · Login redireciona para rota que só aceita POST

| | |
|---|---|
| **Severidade** | Baixa (usabilidade) |
| **Local** | `app/controllers/seguranca.py`, `login_obrigatorio()` |

**Descrição.** Quando a sessão expira e o cliente clica em "Cancelar pedido", que é um formulário POST, o sistema manda para o login com `next=/pedidos/1/cancelar`. Depois do login, o navegador abre esse endereço com GET, e o resultado é o erro **405**.

**Evidência (antes):** `POST /pedidos/1/cancelar -> HTTP 302 Location: /login?next=/pedidos/1/cancelar`

**Correção.** O parâmetro `next` só é preenchido em requisições GET (`seguranca.py`, linha 40).

**Evidência (depois):** `POST /pedidos/1/cancelar -> HTTP 302 Location: /login`

---

### DEF-07 · Páginas de erro 405 e 500 em inglês e fora do layout

| | |
|---|---|
| **Severidade** | Baixa (usabilidade) |
| **Local** | `app/__init__.py` |

**Descrição.** Só os erros 400 e 404 tinham página própria. Os erros 405 e 500 mostravam a página padrão do Flask, em inglês e sem o layout da loja.

**Evidência (antes):** `GET /logout -> HTTP 405 - título: 405 Method Not Allowed`

**Correção.** Foram adicionados os tratadores `errorhandler(405)` e `errorhandler(500)` (`app/__init__.py`, linhas 93 e 99), que usam o template `erro.html` com mensagens em português.

**Evidência (depois):** `GET /logout -> HTTP 405 - título: Erro 405 · Doce Nuvem Cupcakes`. O teste também força uma exceção na vitrine e confere que o erro 500 aparece com o layout da loja.

---

### DEF-09 · Caracteres `%` e `_` funcionam como curinga na busca

| | |
|---|---|
| **Severidade** | Baixa |
| **Local** | `app/models/produto.py`, `Produto.listar()` |

**Descrição.** O termo digitado era colocado direto no `LIKE`. No SQL, `%` significa "qualquer texto" e `_` significa "qualquer caractere". Por isso, buscar `%` ou `_` listava a vitrine inteira. Não há risco de *SQL injection*, porque a consulta é parametrizada, mas o resultado da busca fica errado.

**Evidência (antes):**

```text
[DEF-09] Busca na vitrine pelo texto '%' (só 'Chocolate 54%' contém o símbolo) -> 10 produto(s)
[DEF-09] Busca na vitrine pelo texto '_' (nenhum produto contém o símbolo)     -> 10 produto(s)
```

**Correção.** `%`, `_` e `!` passaram a ser escapados, com a cláusula `ESCAPE '!'`. Ela funciona igual no SQLite e no PostgreSQL.

**Evidência (depois):**

```text
[DEF-09] Busca na vitrine pelo texto '%' ... -> 1 produto(s) listado(s)   (Chocolate Belga, "54%")
[DEF-09] Busca na vitrine pelo texto '_' ... -> 0 produto(s) listado(s)
```

---

### DEF-10 · Cadastro simultâneo com o mesmo e-mail gera erro 500

| | |
|---|---|
| **Severidade** | Baixa (condição de corrida) |
| **Local** | `app/models/cliente.py`, `Cliente.cadastrar()` |

**Descrição.** O cadastro primeiro verificava se o e-mail já existia e depois fazia o `INSERT`. Se duas requisições com o mesmo e-mail chegassem ao mesmo tempo, as duas passavam pela verificação. A segunda era então barrada pela restrição `UNIQUE` do banco, e o erro não era tratado, resultando em erro 500.

**Evidência (antes).** O teste simula a outra requisição gravando entre a verificação e o `INSERT`:

```text
ERROR: test_def10_email_duplicado_em_concorrencia_vira_mensagem
sqlite3.IntegrityError: UNIQUE constraint failed: clientes.email
```

**Correção.** O `INSERT` agora fica num bloco `try` que captura os erros de integridade dos dois bancos, com a função `erros_de_integridade()` (`sqlite3.IntegrityError` e `psycopg.IntegrityError`). Nesse caso, a transação é desfeita e o cliente vê a mensagem "Já existe uma conta com este e-mail".

**Evidência (depois):** `test_def10_email_duplicado_em_concorrencia_vira_mensagem ... ok`

---

### DEF-12 · Soma das parcelas diferente do total

| | |
|---|---|
| **Severidade** | Baixa |
| **Local** | `app/models/pagamento.py` `_cartao()`; `templates/pedido/detalhe.html` |

**Descrição.** O valor da parcela era calculado com `round(total / parcelas)`. Numa compra de R$ 10,00 em 3x, o pedido mostrava "3x de R$ 3,33", o que soma R$ 9,99.

**Evidência (antes):** `[DEF-12] Compra de R$ 10,00 em 3x -> parcelas somam R$ 9.99`

**Correção.** As parcelas agora são iguais, e a diferença de centavos fica na 1ª parcela. A tela mostra "1ª parcela de R$ 3,34 + 2x de R$ 3,33". Pedidos antigos, sem o novo campo, continuam sendo exibidos como antes.

**Evidência (depois):** `[DEF-12] Compra de R$ 10,00 em 3x -> parcelas somam R$ 10.00`

---

## 7. Itens verificados sem defeito

A inspeção também confirmou que estes controles **estão corretos**:

| Item | Como foi verificado |
|---|---|
| Senhas armazenadas com hash (Werkzeug PBKDF2/scrypt) | Leitura de `Cliente.cadastrar()` |
| Proteção CSRF em todos os POST (formulário e `fetch`) | Teste existente `test_post_sem_csrf_e_rejeitado` |
| SQL sempre parametrizado (sem *SQL injection*) | Busca por concatenação de entrada em SQL: nenhuma ocorrência |
| Escape de HTML nos templates (autoescape do Jinja) e no JS (`Loja.escapar`) | Revisão de todos os `innerHTML`: todo texto vindo do servidor passa por `escapar` |
| Proteção contra redirecionamento aberto no `next` | Leitura de `destino_seguro()` e teste existente |
| O preço do carrinho é recalculado no servidor | Teste existente `test_api_carrinho_recalcula_preco_e_ajusta_estoque` |
| Baixa de estoque atômica e criação de pedido transacional | Testes existentes de pagamento recusado e de cancelamento |
| Número do cartão e CVV nunca gravados | Leitura de `Pagamento.registrar()` e do formulário devolvido em caso de erro |
| Cliente não acessa pedido de outro cliente | Teste existente de controle de acesso (404) |

### Alertas analisados e descartados (falsos positivos)

O analisador de acessibilidade do editor (axe) acusou 3 avisos em `pedido/detalhe.html`. A análise mostrou que nenhum é real:

| Aviso | Motivo do descarte |
|---|---|
| "IDs must be unique: `codigo-pagamento`" | Os dois elementos estão em ramos exclusivos `{% if PIX %} … {% else %}`, e só um é gerado no HTML final |
| "`<ol>`/`<ul>` contém texto" (2 avisos) | O "texto" são as tags `{% for %}` do Jinja, que não aparecem no HTML final |

## 8. Riscos residuais e recomendações

Estes pontos **não são defeitos do código entregue**, mas devem ser considerados antes de um uso real:

| # | Risco / limitação | Recomendação |
|---|---|---|
| R1 | **O PostgreSQL real não foi testado.** O adaptador foi validado com 7 testes de conexão simulada. A instalação do `psycopg` falhou na máquina de avaliação por um bloqueio de certificado SSL da rede. | Após o deploy, fazer um pedido completo no site publicado (cadastro → pedido → pagamento → admin) |
| R2 | **Login sem limite de tentativas.** Permite ataque de força bruta contra senhas. | Bloquear temporariamente depois de N tentativas (por exemplo, com Flask-Limiter) |
| R3 | **O gateway de pagamento é simulado.** O botão "Simular confirmação do banco" é só para demonstração. | Em produção, trocar por um provedor real com confirmação via *webhook* |
| R4 | **CSP mínima** (só `frame-ancestors`). Uma CSP completa exigiria tirar os `<script>` embutidos nos templates. | Mover os scripts embutidos para arquivos `.js` e adotar `script-src 'self'` |
| R5 | **`ADMIN_SENHA` só vale na criação do banco.** Se o banco da Vercel já foi criado com `admin123`, a senha antiga continua valendo. | Recriar as tabelas no painel do Neon, ou trocar a senha, antes de divulgar o link |
| R6 | Não há recuperação de senha nem confirmação de e-mail. | Implementar numa próxima versão |

## 9. Conclusão

A avaliação encontrou **12 defeitos**:

- **2 de severidade alta.** A senha pública do administrador em produção (DEF-11) e as datas erradas por causa do fuso UTC da Vercel (DEF-03) afetariam diretamente a loja publicada.
- **4 de severidade média.** Erros 500 provocáveis por visitantes, código PIX inválido e falta de cabeçalhos de segurança.
- **6 de severidade baixa.** Usabilidade, mensagens e condições de corrida raras.

**Todos os defeitos foram corrigidos.** Cada correção é comprovada por um teste automatizado que falhava antes e passa depois, e pela comparação das respostas HTTP antes e depois. A suíte completa (**47 testes**) passa tanto no fuso da Vercel quanto no fuso local, sem regressões nas funcionalidades existentes.

**Parecer:** o sistema está **apto para publicação**, desde que a variável `ADMIN_SENHA` seja configurada na Vercel antes do primeiro acesso (R5) e que se faça o teste de fumaça no ambiente publicado (R1).

---

## Anexo: arquivos de evidência

Todos os arquivos estão em [`docs/evidencias/`](evidencias/):

| Arquivo | Conteúdo |
|---|---|
| [`01_testes_antes_da_correcao.txt`](evidencias/01_testes_antes_da_correcao.txt) | Saída completa dos 12 testes do laudo no código original, com os *tracebacks* |
| [`02_http_antes_da_correcao.txt`](evidencias/02_http_antes_da_correcao.txt) | Respostas HTTP de cada cenário no código original |
| [`03_testes_depois_da_correcao.txt`](evidencias/03_testes_depois_da_correcao.txt) | Os mesmos 12 testes após as correções (todos OK) |
| [`04_http_depois_da_correcao.txt`](evidencias/04_http_depois_da_correcao.txt) | As mesmas respostas HTTP após as correções |
| [`05_suite_completa_depois.txt`](evidencias/05_suite_completa_depois.txt) | Suíte completa (47 testes) no fuso UTC |
| [`06_suite_completa_fuso_local.txt`](evidencias/06_suite_completa_fuso_local.txt) | Suíte completa (47 testes) no fuso local |
| [`07_diff_das_correcoes.patch`](evidencias/07_diff_das_correcoes.patch) | Todas as alterações de código (formato *diff*) |
| [`coletar_evidencias.py`](evidencias/coletar_evidencias.py) | Script que gera os arquivos 02 e 04 |
| [`../tests/test_qualidade.py`](../tests/test_qualidade.py) | Testes de regressão de cada defeito (gera os arquivos 01 e 03) |

**Arquivos alterados pelas correções:** `app/__init__.py`, `app/database.py`, `app/controllers/pedido_controller.py`, `app/controllers/seguranca.py`, `app/models/carrinho.py`, `app/models/cliente.py`, `app/models/entrega.py`, `app/models/pagamento.py`, `app/models/pedido.py`, `app/models/produto.py`, `app/views/templates/pedido/detalhe.html` e `README.md`.
