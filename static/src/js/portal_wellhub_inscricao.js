/** Máscaras do formulário público de inscrição Wellhub (telefone BR e CPF). */
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
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
