/** Máscaras do formulário público de inscrição Wellhub (telefone BR e CPF). */
/** Reprodução do vídeo promocional: autoplay com som só após gesto do utilizador (política dos browsers). */
(function () {
    "use strict";

    function digitsOnly(s) {
        return (s || "").replace(/\D/g, "");
    }

    function applyPhoneMask(el) {
        var d = digitsOnly(el.value).slice(0, 11);
        if (d.length === 0) {
            el.value = "";
            return;
        }
        if (d.length <= 2) {
            el.value = "(" + d;
            return;
        }
        if (d.length <= 6) {
            el.value = "(" + d.slice(0, 2) + ") " + d.slice(2);
            return;
        }
        if (d.length <= 10) {
            el.value =
                "(" +
                d.slice(0, 2) +
                ") " +
                d.slice(2, 6) +
                "-" +
                d.slice(6, 10);
            return;
        }
        el.value =
            "(" +
            d.slice(0, 2) +
            ") " +
            d.slice(2, 7) +
            "-" +
            d.slice(7, 11);
    }

    function applyCEPMask(el) {
        var d = digitsOnly(el.value).slice(0, 8);
        if (d.length <= 5) {
            el.value = d;
            return;
        }
        el.value = d.slice(0, 5) + "-" + d.slice(5);
    }

    // ViaCEP: https://viacep.com.br/ws/{cep}/json/
    // Resposta: { cep, logradouro, complemento, bairro, localidade, uf, ... }
    // Erro: { erro: true } (CEP inexistente) ou HTTP 400 (formato inválido).
    function lookupCEP(cep, callbacks) {
        var digits = digitsOnly(cep);
        if (digits.length !== 8) {
            return;
        }
        var url = "https://viacep.com.br/ws/" + digits + "/json/";
        if (typeof fetch !== "function") {
            return;
        }
        callbacks = callbacks || {};
        if (callbacks.onStart) callbacks.onStart();
        fetch(url, { method: "GET", mode: "cors" })
            .then(function (resp) {
                if (!resp.ok) {
                    throw new Error("HTTP " + resp.status);
                }
                return resp.json();
            })
            .then(function (data) {
                if (data && data.erro) {
                    if (callbacks.onNotFound) callbacks.onNotFound();
                    return;
                }
                if (callbacks.onFound) callbacks.onFound(data);
            })
            .catch(function () {
                if (callbacks.onError) callbacks.onError();
            });
    }

    function bindCEPLookup() {
        var cepInput = document.getElementById("wh_postal_code");
        if (!cepInput) {
            return;
        }
        var streetInput = document.getElementById("wh_street");
        var cityInput = document.getElementById("wh_city");
        var ufInput = document.getElementById("wh_state_uf");
        var numberInput = document.getElementById("wh_street_number");
        var cepField = cepInput.closest(".wh-field");
        var feedback = cepField ? cepField.querySelector(".wh-field__feedback") : null;
        var defaultMsg = feedback ? feedback.textContent : "";

        cepInput.setAttribute("maxlength", "9");
        cepInput.setAttribute("inputmode", "numeric");

        function setMsg(state, msg) {
            if (cepField) cepField.setAttribute("data-wh-status", state);
            if (feedback) feedback.textContent = msg;
        }

        function fillIfEmpty(input, val) {
            if (!input || !val) return;
            if (!input.value || !input.value.trim()) {
                input.value = val;
            }
        }

        function fillAlways(input, val) {
            if (!input || !val) return;
            input.value = val;
        }

        function triggerLookup() {
            var d = digitsOnly(cepInput.value);
            if (d.length !== 8) {
                if (d.length === 0) setMsg("idle", defaultMsg);
                return;
            }
            lookupCEP(d, {
                onStart: function () {
                    setMsg("idle", "Buscando endereço…");
                },
                onFound: function (data) {
                    fillAlways(streetInput, data.logradouro || "");
                    fillAlways(cityInput, data.localidade || "");
                    if (ufInput && data.uf) {
                        ufInput.value = data.uf;
                    }
                    setMsg("valid", "Endereço preenchido. Confirme número e complemento.");
                    if (numberInput && (!numberInput.value || !numberInput.value.trim())) {
                        numberInput.focus();
                    }
                },
                onNotFound: function () {
                    setMsg("invalid", "CEP não encontrado. Preencha o endereço manualmente.");
                },
                onError: function () {
                    setMsg("idle", "Não foi possível consultar o CEP. Preencha manualmente.");
                }
            });
        }

        cepInput.addEventListener("input", function () {
            applyCEPMask(cepInput);
            if (digitsOnly(cepInput.value).length === 8) {
                triggerLookup();
            }
        });
        cepInput.addEventListener("blur", function () {
            applyCEPMask(cepInput);
            triggerLookup();
        });
    }

    function applyCPFMask(el) {
        var d = digitsOnly(el.value).slice(0, 11);
        if (d.length === 0) {
            el.value = "";
            return;
        }
        if (d.length <= 3) {
            el.value = d;
            return;
        }
        if (d.length <= 6) {
            el.value = d.slice(0, 3) + "." + d.slice(3);
            return;
        }
        if (d.length <= 9) {
            el.value =
                d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
            return;
        }
        el.value =
            d.slice(0, 3) +
            "." +
            d.slice(3, 6) +
            "." +
            d.slice(6, 9) +
            "-" +
            d.slice(9, 11);
    }

    function bind() {
        var phone = document.getElementById("wh_phone");
        var cpf = document.getElementById("wh_cpf");
        if (phone) {
            phone.setAttribute("maxlength", "16");
            phone.setAttribute("autocomplete", "tel");
            phone.setAttribute("inputmode", "tel");
            phone.addEventListener("input", function () {
                applyPhoneMask(phone);
            });
            phone.addEventListener("blur", function () {
                applyPhoneMask(phone);
            });
        }
        if (cpf) {
            cpf.setAttribute("maxlength", "14");
            cpf.setAttribute("inputmode", "numeric");
            cpf.addEventListener("input", function () {
                applyCPFMask(cpf);
            });
            cpf.addEventListener("blur", function () {
                applyCPFMask(cpf);
            });
        }
        bindCEPLookup();
        bindPromoVideoSoundUnlock();
        wireReactiveValidation();
    }

    /**
     * Autoplay com som (muted=false). Se o browser bloquear, o primeiro clique/tecla/toque
     * dispara play() de novo (gesto do utilizador permite áudio).
     */
    function bindPromoVideoSoundUnlock() {
        var video = document.getElementById("wh_promo_video");
        if (!video) {
            return;
        }
        function removeGestureListeners(fn) {
            document.removeEventListener("click", fn, true);
            document.removeEventListener("keydown", fn, true);
            document.removeEventListener("touchstart", fn, true);
        }
        function playWithSound() {
            video.muted = false;
            video.volume = 1;
            return video.play();
        }
        function onUserGesture() {
            removeGestureListeners(onUserGesture);
            var p = playWithSound();
            if (p !== undefined && typeof p.catch === "function") {
                p.catch(function () {});
            }
        }
        document.addEventListener("click", onUserGesture, true);
        document.addEventListener("keydown", onUserGesture, true);
        document.addEventListener("touchstart", onUserGesture, true);
        var initial = playWithSound();
        if (initial !== undefined && typeof initial.then === "function") {
            initial
                .then(function () {
                    removeGestureListeners(onUserGesture);
                })
                .catch(function () {});
        }
    }

    // ─── Validação reativa ──────────────────────────────────────────────────
    // Espelha o server: `_cpf_digits_valid` / `_br_phone_digits_valid` em
    // addons/afr_wellhub/controllers/portal_wellhub.py.

    function debounce(fn, ms) {
        var t;
        var wait = ms || 220;
        return function () {
            var ctx = this;
            var args = arguments;
            clearTimeout(t);
            t = setTimeout(function () {
                fn.apply(ctx, args);
            }, wait);
        };
    }

    function validateName(v) {
        var s = (v || "").trim();
        if (s.length < 2) {
            return { valid: false, message: "Informe o nome completo." };
        }
        return { valid: true, message: "" };
    }

    function validateEmail(v) {
        var s = (v || "").trim();
        if (!s) {
            return { valid: false, message: "Informe um e-mail." };
        }
        var re = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
        if (!re.test(s)) {
            return { valid: false, message: "E-mail inválido." };
        }
        return { valid: true, message: "E-mail válido." };
    }

    function validatePhone(v) {
        var d = digitsOnly(v);
        if (d.length !== 10 && d.length !== 11) {
            return { valid: false, message: "Telefone com 10 (fixo) ou 11 (celular) dígitos." };
        }
        var ddd = parseInt(d.slice(0, 2), 10);
        if (isNaN(ddd) || ddd < 11 || ddd > 99) {
            return { valid: false, message: "DDD inválido (esperado 11–99)." };
        }
        return { valid: true, message: "Telefone válido." };
    }

    function validateCPF(v) {
        var d = digitsOnly(v);
        if (d.length !== 11) {
            return { valid: false, message: "CPF deve ter 11 dígitos." };
        }
        if (d === d[0].repeat(11)) {
            return { valid: false, message: "CPF inválido." };
        }
        var i;
        var s1 = 0;
        for (i = 0; i < 9; i++) {
            s1 += parseInt(d.charAt(i), 10) * (10 - i);
        }
        var r1 = s1 % 11;
        var d1 = r1 < 2 ? 0 : 11 - r1;
        if (d1 !== parseInt(d.charAt(9), 10)) {
            return { valid: false, message: "CPF inválido (dígito verificador)." };
        }
        var s2 = 0;
        for (i = 0; i < 10; i++) {
            s2 += parseInt(d.charAt(i), 10) * (11 - i);
        }
        var r2 = s2 % 11;
        var d2 = r2 < 2 ? 0 : 11 - r2;
        if (d2 !== parseInt(d.charAt(10), 10)) {
            return { valid: false, message: "CPF inválido (dígito verificador)." };
        }
        return { valid: true, message: "CPF válido." };
    }

    var VALIDATORS = {
        name: { el: null, fn: validateName, idleMsg: "" },
        email: { el: null, fn: validateEmail, idleMsg: "Será usado para o link de confirmação." },
        phone: { el: null, fn: validatePhone, idleMsg: "10 dígitos (fixo) ou 11 (celular)." },
        cpf: { el: null, fn: validateCPF, idleMsg: "Validação pelos dígitos verificadores." }
    };

    function setFieldStatus(fieldEl, state, msg) {
        if (!fieldEl) {
            return;
        }
        fieldEl.setAttribute("data-wh-status", state);
        var input = fieldEl.querySelector(".wh-field__input");
        if (input) {
            if (state === "invalid") {
                input.setAttribute("aria-invalid", "true");
            } else {
                input.removeAttribute("aria-invalid");
            }
        }
        var fb = fieldEl.querySelector(".wh-field__feedback");
        if (fb && typeof msg === "string") {
            fb.textContent = msg;
        }
    }

    function recomputeProgress(form) {
        var keys = Object.keys(VALIDATORS);
        var validCount = 0;
        keys.forEach(function (k) {
            var entry = VALIDATORS[k];
            if (!entry.el) return;
            if (entry.el.getAttribute("data-wh-status") === "valid") {
                validCount += 1;
            }
        });
        var total = keys.length;
        var pct = Math.round((validCount / total) * 100);
        form.style.setProperty("--wh-progress", pct + "%");
        // Cor do bar por faixa: rose (início) → violeta (meio) → verde (fim).
        var color;
        if (validCount === total) {
            color = "var(--wh-success)";
        } else if (validCount >= Math.ceil(total / 2)) {
            color = "var(--wh-accent)";
        } else {
            color = "var(--wh-primary)";
        }
        form.style.setProperty("--wh-progress-color", color);
        var counter = form.querySelector(".wh-progress__count");
        if (counter) {
            counter.textContent = String(validCount);
        }
        var btn = form.querySelector(".wh-btn-primary");
        if (btn && btn.getAttribute("data-state") === "idle") {
            btn.disabled = validCount !== total;
        }
    }

    function evaluateField(key, form, opts) {
        var entry = VALIDATORS[key];
        if (!entry || !entry.el) return;
        var input = entry.el.querySelector(".wh-field__input");
        if (!input) return;
        var val = input.value;
        var fieldIsEmpty = !val || !val.trim();
        // Estado idle para campos vazios ainda não tocados (não polui o visual).
        if (fieldIsEmpty && !opts.forceInvalid && !input.dataset.whTouched) {
            setFieldStatus(entry.el, "idle", entry.idleMsg);
        } else {
            var res = entry.fn(val);
            setFieldStatus(entry.el, res.valid ? "valid" : "invalid", res.message || (res.valid ? "" : entry.idleMsg));
        }
        recomputeProgress(form);
    }

    function wireReactiveValidation() {
        var form = document.querySelector(".wellhub_portal_inscricao_form");
        if (!form) return;

        var mapping = {
            name: "wh_name",
            email: "wh_email",
            phone: "wh_phone",
            cpf: "wh_cpf"
        };

        Object.keys(mapping).forEach(function (key) {
            var input = document.getElementById(mapping[key]);
            if (!input) return;
            var fieldEl = input.closest(".wh-field");
            if (!fieldEl) return;
            VALIDATORS[key].el = fieldEl;

            var debounced = debounce(function () {
                evaluateField(key, form, {});
            }, 220);

            // `input` é adicionado DEPOIS das máscaras (ordem FIFO) — garante que
            // aplicamos a validação já com o valor formatado.
            input.addEventListener("input", debounced);
            input.addEventListener("blur", function () {
                input.dataset.whTouched = "1";
                evaluateField(key, form, {});
            });
        });

        // Hidratação inicial: se o servidor devolveu valores, já pinta o estado.
        Object.keys(mapping).forEach(function (key) {
            var input = document.getElementById(mapping[key]);
            if (!input) return;
            if (input.value && input.value.trim()) {
                input.dataset.whTouched = "1";
                evaluateField(key, form, {});
            }
        });
        recomputeProgress(form);

        // Intercepta submit: se inválido, shake + foco; se válido, estado loading.
        form.addEventListener("submit", function (ev) {
            var pendingFirst = null;
            Object.keys(mapping).forEach(function (key) {
                var entry = VALIDATORS[key];
                if (!entry.el) return;
                var input = document.getElementById(mapping[key]);
                input.dataset.whTouched = "1";
                var res = entry.fn(input.value);
                setFieldStatus(entry.el, res.valid ? "valid" : "invalid", res.message);
                if (!res.valid) {
                    entry.el.classList.remove("is-shake");
                    // reflow para reexecutar a animação
                    void entry.el.offsetWidth;
                    entry.el.classList.add("is-shake");
                    if (!pendingFirst) {
                        pendingFirst = input;
                    }
                }
            });
            recomputeProgress(form);

            if (pendingFirst) {
                ev.preventDefault();
                pendingFirst.focus();
                return;
            }

            var btn = form.querySelector(".wh-btn-primary");
            if (btn) {
                btn.setAttribute("data-state", "loading");
                btn.disabled = true;
            }
            // Submit segue normalmente (fluxo server-side preservado).
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
