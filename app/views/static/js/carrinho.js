/* =========================================================================
   carrinho.js — carrinho de compras no navegador (localStorage) e
   utilitários compartilhados (Loja.*). Carregado em todas as páginas.
   ========================================================================= */
(function () {
  "use strict";

  var CHAVE = "docenuvem:carrinho";
  var MAX_POR_ITEM = 50;

  // ------------------------------------------------------------ armazenamento
  function ler() {
    try {
      var dados = JSON.parse(localStorage.getItem(CHAVE));
      return dados && typeof dados === "object" ? dados : {};
    } catch (e) {
      return {};
    }
  }

  function gravar(dados) {
    try { localStorage.setItem(CHAVE, JSON.stringify(dados)); } catch (e) { /* modo privado */ }
    atualizarContador();
  }

  var Carrinho = {
    itens: function () {
      var dados = ler();
      return Object.keys(dados).map(function (id) {
        return { produto_id: Number(id), quantidade: Number(dados[id]) };
      }).filter(function (i) { return i.produto_id > 0 && i.quantidade > 0; });
    },
    quantidade: function (id) { return Number(ler()[id] || 0); },
    quantidadeTotal: function () {
      return this.itens().reduce(function (s, i) { return s + i.quantidade; }, 0);
    },
    adicionar: function (id, qtd) {
      var dados = ler();
      dados[id] = Math.min((Number(dados[id]) || 0) + qtd, MAX_POR_ITEM);
      gravar(dados);
    },
    definir: function (id, qtd) {
      var dados = ler();
      if (qtd > 0) dados[id] = Math.min(qtd, MAX_POR_ITEM); else delete dados[id];
      gravar(dados);
    },
    remover: function (id) { this.definir(id, 0); },
    substituir: function (itens) {
      var dados = {};
      itens.forEach(function (i) { dados[i.produto_id] = i.quantidade; });
      gravar(dados);
    },
    limpar: function () { gravar({}); }
  };

  // --------------------------------------------------------------- utilitários
  var Loja = {
    brl: function (centavos) {
      return (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    },
    dataBR: function (iso) {
      var p = String(iso).slice(0, 10).split("-");
      return p[2] + "/" + p[1] + "/" + p[0];
    },
    escapar: function (texto) {
      var div = document.createElement("div");
      div.textContent = texto == null ? "" : String(texto);
      return div.innerHTML;
    },
    csrf: function () {
      var meta = document.querySelector('meta[name="csrf-token"]');
      return meta ? meta.content : "";
    },
    postJSON: function (url, corpo) {
      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": Loja.csrf() },
        body: JSON.stringify(corpo)
      }).then(function (r) {
        if (!r.ok) throw new Error("Falha na comunicação com o servidor (" + r.status + ").");
        return r.json();
      });
    },
    /** Valida o carrinho no servidor (preços/estoque oficiais) e sincroniza o localStorage. */
    validarCarrinho: function () {
      return Loja.postJSON("/api/carrinho", { itens: Carrinho.itens() }).then(function (dados) {
        Carrinho.substituir(dados.itens);
        return dados;
      });
    },
    /** Mesmo desenho do macro cupcake() em templates/macros.html. */
    cupcake: function (cobertura, forminha, classe) {
      var cor = /^#[0-9a-fA-F]{6}$/;
      cobertura = cor.test(cobertura) ? cobertura : "#f7a1c4";
      forminha = cor.test(forminha) ? forminha : "#8b5a3c";
      return '<svg class="cupcake ' + (classe || "") + '" viewBox="0 0 120 120" aria-hidden="true" focusable="false">' +
        '<ellipse cx="60" cy="110" rx="30" ry="4" fill="rgba(74,44,42,.12)"/>' +
        '<path d="M30 64h60l-8 44H38z" fill="' + forminha + '"/>' +
        '<path d="M44 64l3 44M60 64v44M76 64l-3 44" stroke="rgba(255,255,255,.3)" stroke-width="3"/>' +
        '<path d="M24 66c-9-1-9-14 1-16-3-11 9-18 18-13 2-11 16-15 24-7 8-7 22-2 21 10 10-1 15 12 7 17 5 7-1 11-6 9z" fill="' + cobertura + '" stroke="rgba(74,44,42,.15)" stroke-width="1.5"/>' +
        '<path d="M36 50c6 3 14 3 20 0M64 44c6 3 14 3 20 0" stroke="rgba(255,255,255,.55)" stroke-width="3" fill="none" stroke-linecap="round"/>' +
        '<circle cx="62" cy="24" r="8" fill="#d62246"/>' +
        '<path d="M63 16c2-6 6-9 11-10" stroke="#5b8c3a" stroke-width="2.5" fill="none" stroke-linecap="round"/>' +
        '<circle cx="59" cy="21" r="2.4" fill="rgba(255,255,255,.65)"/>' +
        "</svg>";
    },
    toast: function (mensagem) {
      var el = document.getElementById("toast");
      if (!el) return;
      el.textContent = mensagem;
      el.classList.add("toast--visivel");
      clearTimeout(Loja._toastTimer);
      Loja._toastTimer = setTimeout(function () { el.classList.remove("toast--visivel"); }, 2600);
    },
    mascaras: {
      cep: function (v) {
        v = v.replace(/\D/g, "").slice(0, 8);
        return v.length > 5 ? v.slice(0, 5) + "-" + v.slice(5) : v;
      },
      telefone: function (v) {
        v = v.replace(/\D/g, "").slice(0, 11);
        if (v.length <= 2) return v;
        if (v.length <= 6) return "(" + v.slice(0, 2) + ") " + v.slice(2);
        if (v.length <= 10) return "(" + v.slice(0, 2) + ") " + v.slice(2, 6) + "-" + v.slice(6);
        return "(" + v.slice(0, 2) + ") " + v.slice(2, 7) + "-" + v.slice(7);
      }
    }
  };

  window.Carrinho = Carrinho;
  window.Loja = Loja;

  // ---------------------------------------------------------------- contador
  function atualizarContador() {
    var total = Carrinho.quantidadeTotal();
    document.querySelectorAll("[data-contador-carrinho]").forEach(function (el) {
      el.textContent = total;
      el.hidden = total === 0;
    });
  }

  // ------------------------------------------------- botões "Adicionar"
  document.addEventListener("click", function (ev) {
    var botao = ev.target.closest("[data-adicionar]");
    if (!botao) return;
    var id = Number(botao.dataset.adicionar);
    var estoque = Number(botao.dataset.estoque || MAX_POR_ITEM);
    var campo = botao.dataset.qtd ? document.querySelector(botao.dataset.qtd) : null;
    var qtd = campo ? Math.max(1, parseInt(campo.value, 10) || 1) : 1;
    var jaNoCarrinho = Carrinho.quantidade(id);
    var limite = Math.min(estoque, MAX_POR_ITEM);

    if (jaNoCarrinho >= limite) {
      Loja.toast("Você já tem todas as unidades disponíveis no carrinho.");
      return;
    }
    qtd = Math.min(qtd, limite - jaNoCarrinho);
    Carrinho.adicionar(id, qtd);
    Loja.toast(qtd + "× " + botao.dataset.nome + " no carrinho 🧁");
    botao.classList.add("pulsar");
    setTimeout(function () { botao.classList.remove("pulsar"); }, 400);
  });

  // ----------------------------------- seletor de quantidade da página produto
  document.addEventListener("click", function (ev) {
    var botao = ev.target.closest(".seletor-qtd__botao[data-passo]");
    if (!botao) return;
    var campo = botao.parentElement.querySelector("input");
    var max = Number(campo.max || MAX_POR_ITEM);
    var valor = (parseInt(campo.value, 10) || 1) + Number(botao.dataset.passo);
    campo.value = Math.max(1, Math.min(max, valor));
  });

  // ----------------------------------------------------- copiar código PIX
  document.addEventListener("click", function (ev) {
    var botao = ev.target.closest("[data-copiar]");
    if (!botao) return;
    var campo = document.querySelector(botao.dataset.copiar);
    campo.select();
    var copiar = navigator.clipboard ? navigator.clipboard.writeText(campo.value) : Promise.reject();
    copiar.catch(function () { document.execCommand("copy"); }).finally(function () {
      Loja.toast("Código copiado!");
    });
  });

  // ------------------------------------------------- confirmação de envio
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (form.dataset.confirmar && !window.confirm(form.dataset.confirmar)) ev.preventDefault();
  });

  // -------------------------------------------------------------- máscaras
  document.addEventListener("input", function (ev) {
    var tipo = ev.target.dataset && ev.target.dataset.mascara;
    if (tipo && Loja.mascaras[tipo]) ev.target.value = Loja.mascaras[tipo](ev.target.value);
  });

  // ------------------------------------------- filtro instantâneo da vitrine
  function ligarFiltroVitrine() {
    var campo = document.querySelector("[data-filtro-vitrine]");
    var grade = document.querySelector("[data-grade-vitrine]");
    if (!campo || !grade) return;
    var semResultado = document.querySelector("[data-sem-resultado]");
    campo.addEventListener("input", function () {
      var termo = campo.value.trim().toLowerCase();
      var visiveis = 0;
      grade.querySelectorAll(".card").forEach(function (card) {
        var mostrar = !termo || card.dataset.busca.indexOf(termo) !== -1;
        card.hidden = !mostrar;
        if (mostrar) visiveis++;
      });
      if (semResultado) semResultado.hidden = visiveis > 0;
    });
  }

  // ------------------------------------------------------- página carrinho
  function paginaCarrinho(raiz) {
    var urlCheckout = raiz.dataset.urlCheckout;
    var urlVitrine = raiz.dataset.urlVitrine;

    function vazio(avisos) {
      raiz.innerHTML = htmlAvisos(avisos) +
        '<section class="vazio"><p class="vazio__icone" aria-hidden="true">🧁</p>' +
        "<p>Seu carrinho está vazio.</p>" +
        '<a class="botao" href="' + urlVitrine + '">Escolher cupcakes</a></section>';
    }

    function htmlAvisos(avisos) {
      return (avisos || []).map(function (a) {
        return '<div class="alerta alerta--aviso">' + Loja.escapar(a.mensagem) + "</div>";
      }).join("");
    }

    function render(dados) {
      if (!dados.itens.length) return vazio(dados.avisos);
      var linhas = dados.itens.map(function (i) {
        return '<li class="carrinho__item">' +
          Loja.cupcake(i.cor_cobertura, i.cor_forminha) +
          "<div><h3><a href=\"/produto/" + i.produto_id + '">' + Loja.escapar(i.nome) + "</a></h3>" +
          "<p>" + Loja.brl(i.preco_centavos) + " cada</p>" +
          '<button class="remover" type="button" data-acao="remover" data-id="' + i.produto_id + '">Remover</button></div>' +
          '<div class="seletor-qtd seletor-qtd--pequeno">' +
          '<button type="button" class="seletor-qtd__botao" data-acao="menos" data-id="' + i.produto_id + '" aria-label="Diminuir">−</button>' +
          '<input type="number" readonly value="' + i.quantidade + '" aria-label="Quantidade de ' + Loja.escapar(i.nome) + '">' +
          '<button type="button" class="seletor-qtd__botao" data-acao="mais" data-id="' + i.produto_id + '" aria-label="Aumentar"' +
          (i.quantidade >= Math.min(i.estoque, MAX_POR_ITEM) ? " disabled" : "") + ">+</button>" +
          "</div>" +
          '<span class="carrinho__subtotal">' + Loja.brl(i.subtotal_centavos) + "</span>" +
          "</li>";
      }).join("");

      raiz.innerHTML = htmlAvisos(dados.avisos) +
        '<div class="carrinho">' +
        '<ul class="carrinho__lista">' + linhas + "</ul>" +
        '<aside class="painel resumo">' +
        "<h2>Resumo</h2>" +
        '<dl class="resumo__totais">' +
        "<div><dt>Itens</dt><dd>" + dados.quantidade_total + "</dd></div>" +
        '<div class="resumo__total"><dt>Subtotal</dt><dd>' + Loja.brl(dados.subtotal_centavos) + "</dd></div>" +
        "</dl>" +
        '<p class="dica">Frete calculado no próximo passo. Grátis na Grande SP acima de R$ 100,00.</p>' +
        '<a class="botao botao--largo" href="' + urlCheckout + '">Finalizar pedido</a>' +
        '<a class="link-voltar" href="' + urlVitrine + '">← Continuar comprando</a>' +
        "</aside></div>";
    }

    function carregar() {
      if (!Carrinho.itens().length) return vazio();
      Loja.validarCarrinho().then(render).catch(function (erro) {
        raiz.innerHTML = '<div class="alerta alerta--erro">' + Loja.escapar(erro.message) + "</div>";
      });
    }

    raiz.addEventListener("click", function (ev) {
      var botao = ev.target.closest("[data-acao]");
      if (!botao) return;
      var id = Number(botao.dataset.id);
      var atual = Carrinho.quantidade(id);
      if (botao.dataset.acao === "mais") Carrinho.definir(id, atual + 1);
      if (botao.dataset.acao === "menos") Carrinho.definir(id, atual - 1);
      if (botao.dataset.acao === "remover") Carrinho.remover(id);
      carregar();
    });

    carregar();
  }

  // ------------------------------------------------------------ inicialização
  document.addEventListener("DOMContentLoaded", function () {
    if (document.body.hasAttribute("data-limpar-carrinho")) {
      Carrinho.limpar();
      // Remove o ?novo=1 da URL para não limpar de novo ao recarregar.
      history.replaceState(null, "", location.pathname);
    }
    atualizarContador();
    ligarFiltroVitrine();
    var raiz = document.getElementById("carrinho-app");
    if (raiz) paginaCarrinho(raiz);
  });

  // Mantém o contador sincronizado entre abas.
  window.addEventListener("storage", function (ev) { if (ev.key === CHAVE) atualizarContador(); });
})();
