# Reenvio de E-mail de Ativação — Portal Wellhub

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar página de reenvio de e-mail de ativação no portal Wellhub, acessível pelo link "Não recebi o e-mail" na página pós-inscrição.

**Architecture:** Duas novas rotas HTTP públicas no controller existente (`GET` exibe form, `POST` processa reenvio com mensagem genérica). Dois novos templates XML reutilizando o CSS `wh-portal` existente. Link adicionado ao template `inscricao_done`.

**Tech Stack:** Odoo 18, Python (`odoo.http`), QWeb XML templates, CSS existente `wh-portal`.

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `controllers/portal_wellhub.py` | Modificar | +2 rotas: GET/POST `/afr_wellhub/inscricao/reenviar` |
| `views/portal_wellhub_templates.xml` | Modificar | +2 templates (`reenviar_form`, `reenviar_done`) + link em `inscricao_done` |

---

## Task 1: Rotas GET + POST `/reenviar` no controller

**Files:**
- Modify: `controllers/portal_wellhub.py` — adicionar ao final da classe `AfrWellhubPortal`

- [ ] **Step 1: Adicionar rota GET**

Ao final da classe `AfrWellhubPortal` (após o método `wellhub_inscricao_ativar`), adicionar:

```python
@http.route(
    "/afr_wellhub/inscricao/reenviar",
    type="http",
    auth="public",
    website=True,
    methods=["GET"],
)
def wellhub_inscricao_reenviar_get(self, **kwargs):
    return request.render(
        "afr_wellhub.portal_wellhub_reenviar_form",
        {"error": None},
    )
```

- [ ] **Step 2: Adicionar rota POST**

Logo após o método GET, adicionar:

```python
@http.route(
    "/afr_wellhub/inscricao/reenviar",
    type="http",
    auth="public",
    website=True,
    methods=["POST"],
    csrf=True,
)
def wellhub_inscricao_reenviar_post(self, **post):
    email_raw = (post.get("email") or "").strip()
    email_norm = email_normalize(email_raw, strict=False)
    if not email_norm:
        return request.render(
            "afr_wellhub.portal_wellhub_reenviar_form",
            {"error": _("Informe um e-mail válido.")},
        )
    Collab = request.env["wellhub.collaborator"].sudo()
    company = self._wellhub_company()
    collab = Collab.search(
        [
            ("email", "=ilike", email_norm),
            ("signup_pending", "=", True),
            ("company_id", "=", company.id),
        ],
        limit=1,
    )
    if collab:
        try:
            collab.with_context(afr_wellhub_skip_asaas_sync=True).write(
                {
                    "signup_token": Collab._portal_new_signup_token(),
                    "signup_token_expiry": Collab._portal_signup_token_expiry_string(),
                }
            )
            template = request.env.ref(
                "afr_wellhub.mail_template_wellhub_signup_activation",
                raise_if_not_found=False,
            )
            if template:
                template.sudo().send_mail(collab.id, force_send=True)
        except Exception:
            _logger.exception("Wellhub reenvio: falha ao renovar token ou enviar e-mail.")
    # Sempre retorna mensagem genérica (não revela se e-mail existe)
    return request.render(
        "afr_wellhub.portal_wellhub_reenviar_done",
        {},
    )
```

- [ ] **Step 3: Verificar imports**

O arquivo já importa `email_normalize`, `_`, `http`, `request`, `_logger`. Confirmar no topo do arquivo:

```python
from odoo.tools.mail import email_normalize
from odoo import _, http
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)
```

Se algum faltar, adicionar. (Provavelmente todos já existem.)

- [ ] **Step 4: Commit**

```bash
git add controllers/portal_wellhub.py
git commit -m "feat(wellhub): add resend activation email routes GET/POST /reenviar"
```

---

## Task 2: Templates XML — form e resultado

**Files:**
- Modify: `views/portal_wellhub_templates.xml` — adicionar antes da tag `</odoo>` de fechamento

- [ ] **Step 1: Adicionar template `portal_wellhub_reenviar_form`**

Inserir antes do `</odoo>` final:

```xml
<template id="portal_wellhub_reenviar_form" name="Wellhub: reenviar e-mail de ativação">
    <t t-call="website.layout">
        <div id="wrap" class="oe_structure wh-portal">
            <t t-call="afr_wellhub.wh_icon_sprite"/>
            <section class="wh-hero wh-hero--compact" aria-label="Reenviar e-mail de ativação">
                <div class="wh-hero__inner">
                    <span class="wh-hero__badge">
                        <svg aria-hidden="true" focusable="false" width="14" height="14"><use href="#wh-i-mail"/></svg>
                        Reenviar confirmação
                    </span>
                    <h1 class="wh-hero__title">Reenviar link de ativação</h1>
                    <p class="wh-hero__subtitle">Informe o e-mail cadastrado e enviaremos um novo link de confirmação.</p>
                </div>
            </section>

            <section class="wh-main">
                <div class="wh-main__inner">
                    <div class="wh-success-card" style="max-width: 480px;">
                        <div t-if="error" class="wh-alert wh-alert--danger" role="alert">
                            <span class="wh-alert__icon" aria-hidden="true">
                                <svg><use href="#wh-i-x"/></svg>
                            </span>
                            <div class="wh-alert__body"><t t-out="error"/></div>
                        </div>

                        <form action="/afr_wellhub/inscricao/reenviar" method="post" class="wh-form" novalidate="novalidate">
                            <input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>

                            <div class="wh-field" data-wh-field="email" data-wh-status="idle">
                                <div class="wh-field__control">
                                    <span class="wh-field__icon" aria-hidden="true">
                                        <svg><use href="#wh-i-mail"/></svg>
                                    </span>
                                    <input type="email" class="wh-field__input" id="wh_reenviar_email"
                                           name="email" required="required"
                                           autocomplete="email" inputmode="email"
                                           placeholder=" "
                                           aria-describedby="wh_reenviar_email_feedback"/>
                                    <label class="wh-field__label" for="wh_reenviar_email">E-mail cadastrado</label>
                                    <span class="wh-field__status" aria-hidden="true">
                                        <span class="wh-field__status-valid"><svg><use href="#wh-i-check"/></svg></span>
                                        <span class="wh-field__status-invalid"><svg><use href="#wh-i-x"/></svg></span>
                                    </span>
                                </div>
                                <small id="wh_reenviar_email_feedback" class="wh-field__feedback" aria-live="polite">
                                    O mesmo e-mail usado no cadastro.
                                </small>
                            </div>

                            <button type="submit" class="wh-btn-primary" style="margin-top: 8px;">
                                <span class="wh-btn-primary__icon-idle" aria-hidden="true">
                                    <svg width="20" height="20"><use href="#wh-i-arrow-right"/></svg>
                                </span>
                                <span class="wh-btn-primary__label-idle">Reenviar link</span>
                            </button>
                        </form>

                        <p style="text-align:center; margin-top: 20px; font-size: 0.88rem;">
                            <a href="/afr_wellhub/inscricao" style="color: var(--wh-primary);">← Voltar ao cadastro</a>
                        </p>
                    </div>
                </div>
            </section>
        </div>
    </t>
</template>
```

- [ ] **Step 2: Adicionar template `portal_wellhub_reenviar_done`**

Imediatamente após o template anterior, ainda antes de `</odoo>`:

```xml
<template id="portal_wellhub_reenviar_done" name="Wellhub: reenvio solicitado">
    <t t-call="website.layout">
        <div id="wrap" class="oe_structure wh-portal">
            <t t-call="afr_wellhub.wh_icon_sprite"/>
            <section class="wh-hero wh-hero--compact" aria-label="Reenvio solicitado">
                <div class="wh-hero__inner">
                    <span class="wh-hero__badge">
                        <svg aria-hidden="true" focusable="false" width="14" height="14"><use href="#wh-i-check"/></svg>
                        Solicitação enviada
                    </span>
                    <h1 class="wh-hero__title">Verifique o seu e-mail</h1>
                    <p class="wh-hero__subtitle">Se houver inscrição pendente, o link foi reenviado.</p>
                </div>
            </section>

            <section class="wh-main">
                <div class="wh-main__inner">
                    <div class="wh-success-card" style="max-width: 560px;">
                        <div class="wh-success-card__icon" aria-hidden="true">
                            <svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
                                <circle class="wh-success-draw-ring" cx="28" cy="28" r="26"/>
                                <path class="wh-success-draw-check" d="m16 28 8 8 16-18"/>
                            </svg>
                        </div>
                        <h2 class="wh-success-card__title">Solicitação recebida</h2>
                        <p class="wh-success-card__body">
                            Se houver uma inscrição pendente para esse e-mail, enviaremos o link de ativação em instantes.
                            Verifique a <strong>caixa de entrada</strong>, <strong>spam</strong> e <strong>promoções</strong>.
                        </p>

                        <ol class="wh-tips" aria-label="Próximos passos">
                            <li class="wh-tips__item">
                                <span class="wh-tips__num">1</span>
                                <p class="wh-tips__text">Aguarde alguns minutos e verifique o <strong>e-mail cadastrado</strong>.</p>
                            </li>
                            <li class="wh-tips__item">
                                <span class="wh-tips__num">2</span>
                                <p class="wh-tips__text">Cheque também <strong>spam</strong> e <strong>promoções</strong>.</p>
                            </li>
                            <li class="wh-tips__item">
                                <span class="wh-tips__num">3</span>
                                <p class="wh-tips__text"><strong>Clique no link</strong> recebido para ativar a inscrição.</p>
                            </li>
                        </ol>

                        <a class="wh-btn-secondary" href="/">
                            <svg width="16" height="16" aria-hidden="true" style="transform: rotate(180deg);"><use href="#wh-i-arrow-right"/></svg>
                            Voltar ao site
                        </a>
                    </div>
                </div>
            </section>
        </div>
    </t>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add views/portal_wellhub_templates.xml
git commit -m "feat(wellhub): add resend activation email templates"
```

---

## Task 3: Link "Não recebi o e-mail" no template `inscricao_done`

**Files:**
- Modify: `views/portal_wellhub_templates.xml` — template `portal_wellhub_inscricao_done`

- [ ] **Step 1: Adicionar link após botão "Voltar ao site"**

Localizar no template `portal_wellhub_inscricao_done` o botão:

```xml
<a class="wh-btn-secondary" href="/">
    <svg width="16" height="16" aria-hidden="true" style="transform: rotate(180deg);"><use href="#wh-i-arrow-right"/></svg>
    Voltar ao site
</a>
```

Substituir por:

```xml
<a class="wh-btn-secondary" href="/">
    <svg width="16" height="16" aria-hidden="true" style="transform: rotate(180deg);"><use href="#wh-i-arrow-right"/></svg>
    Voltar ao site
</a>

<p style="margin-top: 20px; font-size: 0.88rem; color: var(--wh-ink-500);">
    Não recebeu o e-mail?
    <a href="/afr_wellhub/inscricao/reenviar" style="color: var(--wh-primary); font-weight: 600;">
        Reenviar link de ativação →
    </a>
</p>
```

- [ ] **Step 2: Upgrade do módulo no container**

```bash
cd /home/afonso/docker/odoo18_teste
docker compose exec web odoo -c /etc/odoo/odoo.conf -d <BANCO> -u afr_wellhub --stop-after-init
```

- [ ] **Step 3: Verificar fluxo completo manualmente**

1. Acesse `http://localhost:8099/afr_wellhub/inscricao`
2. Preencha o formulário com dados válidos → submit
3. Na página `inscricao_done`, verificar link "Reenviar link de ativação" aparece
4. Clicar no link → abre `/afr_wellhub/inscricao/reenviar` com formulário
5. Submeter com email existente (pendente) → página `reenviar_done` com mensagem genérica
6. Verificar e-mail reenviado (log Odoo ou caixa de entrada)
7. Submeter com email inexistente → mesma página `reenviar_done` (sem erro, sem revelar)

- [ ] **Step 4: Commit e push**

```bash
git add views/portal_wellhub_templates.xml
git commit -m "feat(wellhub): add 'resend activation email' link on inscricao_done page"
git push origin main
```
