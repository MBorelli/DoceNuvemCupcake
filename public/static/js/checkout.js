/* =========================================================================
   checkout.js — resumo do pedido, cálculo de frete por CEP, preenchimento
   de endereço (ViaCEP) e validações do pagamento antes do envio.
   As mesmas regras são revalidadas no servidor (o JS só melhora a UX).
   ========================================================================= */
(function () {
  "use strict";

  var form = document.getElementById("form-checkout");
  if (!form) return;

  var el = {
    itens: document.getElementById("resumo-itens"),
    avisos: document.getElementById("resumo-avisos"),
    subtotal: document.getElementById("resumo-subtotal"),
    frete: document.getElementById("resumo-frete"),
    total: document.getElementById("resumo-total"),
    freteInfo: document.getElementById("frete-info"),
    cep: document.getElementById("cep"),
    botao: document.getElementById("botao-finalizar"),
    carrinho: document.getElementById("campo-carrinho"),
    cartaoNumero: document.getElementById("cartao-numero"),
    cartaoValidade: document.getElementById("cartao-validade"),
    bandeira: document.getElementById("bandeira"),
    parcelas: document.getElementById("parcelas")
  };

  var estado = { subtotal: 0, frete: null, carrinhoOk: false, ultimoCep: "" };

  function digitos(v) { return String(v || "").replace(/\D/g, ""); }

  // ---------------------------------------------------------------- resumo
  function carregarResumo() {
    if (!Carrinho.itens().length) {
      el.itens.innerHTML = '<li>Seu carrinho está vazio. <a href="/">Ir para a vitrine</a></li>';
      el.botao.disabled = true;
      return;
    }
    Loja.validarCarrinho().then(function (dados) {
      el.avisos.innerHTML = dados.avisos.map(function (a) {
        return '<div class="alerta alerta--aviso">' + Loja.escapar(a.mensagem) + "</div>";
      }).join("");
      if (!dados.itens.length) {
        el.itens.innerHTML = '<li>Seu carrinho está vazio. <a href="/">Ir para a vitrine</a></li>';
        el.botao.disabled = true;
        return;
      }
      el.itens.innerHTML = dados.itens.map(function (i) {
        return '<li class="resumo__item">' + Loja.cupcake(i.cor_cobertura, i.cor_forminha) +
          "<span>" + Loja.escapar(i.nome) + "<small>" + i.quantidade + " × " + Loja.brl(i.preco_centavos) + "</small></span>" +
          "<strong>" + Loja.brl(i.subtotal_centavos) + "</strong></li>";
      }).join("");
      estado.subtotal = dados.subtotal_centavos;
      estado.carrinhoOk = true;
      atualizarTotais();
      if (digitos(el.cep.value).length === 8) calcularFrete(true);
    }).catch(function (erro) {
      el.itens.innerHTML = '<li class="alerta alerta--erro">' + Loja.escapar(erro.message) + "</li>";
    });
  }

  function atualizarTotais() {
    el.subtotal.textContent = Loja.brl(estado.subtotal);
    if (estado.frete) {
      el.frete.textContent = estado.frete.gratis ? "Grátis" : Loja.brl(estado.frete.valor_centavos);
      el.total.textContent = Loja.brl(estado.subtotal + estado.frete.valor_centavos);
    } else {
      el.frete.textContent = "informe o CEP";
      el.total.textContent = Loja.brl(estado.subtotal);
    }
    atualizarParcelas();
  }

  function atualizarParcelas() {
    if (!el.parcelas) return;
    var total = estado.subtotal + (estado.frete ? estado.frete.valor_centavos : 0);
    Array.prototype.forEach.call(el.parcelas.options, function (opt) {
      var n = Number(opt.value);
      opt.textContent = n + "x de " + Loja.brl(Math.round(total / n)) + " sem juros";
    });
  }

  // ----------------------------------------------------------------- frete
  function mostrarInfoFrete(texto, tipo) {
    el.freteInfo.textContent = texto;
    el.freteInfo.className = "frete-info" + (tipo ? " frete-info--" + tipo : "");
  }

  function calcularFrete(forcar) {
    var cep = digitos(el.cep.value);
    if (cep.length !== 8) {
      estado.frete = null;
      estado.ultimoCep = "";
      mostrarInfoFrete("Informe o CEP para calcular frete e prazo.");
      atualizarTotais();
      return;
    }
    if (cep === estado.ultimoCep && !forcar) return;
    estado.ultimoCep = cep;
    mostrarInfoFrete("Calculando frete…");

    fetch("/api/frete?cep=" + cep + "&subtotal=" + estado.subtotal)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          estado.frete = d;
          mostrarInfoFrete(
            d.regiao + " · entrega até " + Loja.dataBR(d.previsao) + (d.gratis ? " · frete grátis! 🎉" : ""),
            "ok"
          );
        } else {
          estado.frete = null;
          mostrarInfoFrete(d.erro, "erro");
        }
        atualizarTotais();
      })
      .catch(function () {
        estado.frete = null;
        mostrarInfoFrete("Não foi possível calcular o frete agora.", "erro");
        atualizarTotais();
      });

    preencherEndereco(cep);
  }

  /** Autopreenchimento opcional pelo serviço público ViaCEP. Se falhar
   *  (sem internet, CEP inexistente), o cliente digita normalmente. */
  function preencherEndereco(cep) {
    fetch("https://viacep.com.br/ws/" + cep + "/json/")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.erro) return;
        var mapa = { logradouro: d.logradouro, bairro: d.bairro, cidade: d.localidade, uf: d.uf };
        Object.keys(mapa).forEach(function (id) {
          var campo = document.getElementById(id);
          if (campo && !campo.value && mapa[id]) campo.value = mapa[id];
        });
        if (d.logradouro) document.getElementById("numero").focus();
      })
      .catch(function () { /* opcional */ });
  }

  el.cep.addEventListener("input", function () { calcularFrete(false); });

  // ------------------------------------------------------------- pagamento
  function metodoSelecionado() {
    var marcado = form.querySelector('input[name="metodo_pagamento"]:checked');
    return marcado ? marcado.value : "";
  }

  function alternarPaineis() {
    var metodo = metodoSelecionado();
    form.querySelectorAll("[data-painel-pagamento]").forEach(function (painel) {
      var ativo = painel.dataset.painelPagamento === metodo;
      painel.hidden = !ativo;
      // Campos de cartão desabilitados não são enviados ao servidor.
      painel.querySelectorAll("input, select").forEach(function (c) { c.disabled = !ativo; });
    });
  }
  form.querySelectorAll('input[name="metodo_pagamento"]').forEach(function (r) {
    r.addEventListener("change", alternarPaineis);
  });

  function luhn(numero) {
    var soma = 0;
    for (var i = 0; i < numero.length; i++) {
      var d = Number(numero[numero.length - 1 - i]);
      if (i % 2 === 1) { d *= 2; if (d > 9) d -= 9; }
      soma += d;
    }
    return numero.length >= 13 && soma % 10 === 0;
  }

  function bandeira(n) {
    if (/^(4011|4312|4389|4514|4576|5041|5066|5067|509|6277|6362|6363|650|6516|6550)/.test(n)) return "Elo";
    if (/^4/.test(n)) return "Visa";
    if (/^(5[1-5]|2[2-7])/.test(n)) return "Mastercard";
    if (/^3[47]/.test(n)) return "American Express";
    return "";
  }

  if (el.cartaoNumero) {
    el.cartaoNumero.addEventListener("input", function () {
      var n = digitos(el.cartaoNumero.value).slice(0, 19);
      el.cartaoNumero.value = n.replace(/(\d{4})(?=\d)/g, "$1 ");
      el.bandeira.textContent = bandeira(n);
      el.cartaoNumero.classList.toggle("invalido", n.length >= 13 && !luhn(n));
    });
    el.cartaoValidade.addEventListener("input", function () {
      var v = digitos(el.cartaoValidade.value).slice(0, 4);
      el.cartaoValidade.value = v.length > 2 ? v.slice(0, 2) + "/" + v.slice(2) : v;
    });
  }

  // ------------------------------------------------------------------ envio
  form.addEventListener("submit", function (ev) {
    var erros = [];
    if (!estado.carrinhoOk || !Carrinho.itens().length) erros.push("Seu carrinho está vazio.");
    if (!estado.frete) erros.push("Informe um CEP válido dentro da nossa área de entrega.");
    if (!metodoSelecionado()) erros.push("Escolha uma forma de pagamento.");
    if (metodoSelecionado() === "cartao" && !luhn(digitos(el.cartaoNumero.value))) {
      erros.push("Confira o número do cartão.");
    }
    if (erros.length) {
      ev.preventDefault();
      el.avisos.innerHTML = erros.map(function (e) {
        return '<div class="alerta alerta--erro">' + Loja.escapar(e) + "</div>";
      }).join("");
      el.avisos.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    el.carrinho.value = JSON.stringify(Carrinho.itens());
    el.botao.disabled = true;
    el.botao.textContent = "Processando pagamento…";
  });

  // Aplica máscara ao CEP/telefone já preenchidos (ex.: após erro de validação).
  form.querySelectorAll("[data-mascara]").forEach(function (c) {
    c.value = Loja.mascaras[c.dataset.mascara](c.value);
  });

  alternarPaineis();
  carregarResumo();
})();
