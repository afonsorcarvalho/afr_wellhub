# Reenvio de E-mail de Ativação — Portal Wellhub

**Data:** 2026-05-26  
**Módulo:** `afr_wellhub`  
**Status:** Aprovado

---

## Contexto

Após o colaborador preencher o formulário de inscrição, recebe e-mail com link de ativação (48h). Se o e-mail não chegar (spam, erro de digitação, expiração), não havia self-service para reenvio — só o admin podia reenviar pelo backend.

---

## Objetivo

Permitir que o próprio colaborador solicite reenvio do link de ativação diretamente pelo portal, sem depender do administrador.

---

## Fluxo

```
/afr_wellhub/inscricao (POST)
  └── inscricao_done
        └── link "Não recebi o e-mail"
              └── GET /afr_wellhub/inscricao/reenviar
                    └── form (campo: email)
                          └── POST /afr_wellhub/inscricao/reenviar
                                ├── busca: email ilike + signup_pending=True + company_id do site
                                ├── encontrou → renova token 48h + reenvia e-mail de ativação
                                └── não encontrou → silencioso (mesmo tempo de resposta)
                                      └── sempre retorna página com mensagem genérica
```

---

## Componentes

### 1. Controller — `controllers/portal_wellhub.py`

**GET `/afr_wellhub/inscricao/reenviar`**
- `auth="public"`, `website=True`
- Renderiza `afr_wellhub.portal_wellhub_reenviar_form`
- Contexto: `{"error": None, "done": False}`

**POST `/afr_wellhub/inscricao/reenviar`**
- `auth="public"`, `website=True`, `csrf=True`
- Valida email (normalização com `email_normalize`)
- Busca `wellhub.collaborator` sudo: `[("email", "=ilike", email_norm), ("signup_pending", "=", True), ("company_id", "=", company.id)]` limit=1
- Se encontrar:
  - Grava novo `signup_token` + `signup_token_expiry` (48h) com `afr_wellhub_skip_asaas_sync=True`
  - Envia `mail_template_wellhub_signup_activation`
- Se não encontrar: noop (sem erro, sem diferença de timing visível)
- Sempre renderiza `afr_wellhub.portal_wellhub_reenviar_done` com mensagem genérica

### 2. Templates — `views/portal_wellhub_templates.xml`

**`portal_wellhub_reenviar_form`**
- Layout `website.layout` com classe `wh-portal` (CSS existente)
- Hero section (compacto)
- Card com campo email + botão submit
- Exibe erro de validação se email inválido

**`portal_wellhub_reenviar_done`**
- Mesma estrutura do `inscricao_done`
- Mensagem: *"Se houver uma inscrição pendente para esse e-mail, enviaremos o link de ativação em instantes. Verifique também spam e promoções."*
- Link de volta ao site

**`inscricao_done` (alteração)**
- Adicionar link no rodapé do card: *"Não recebeu o e-mail? → Reenviar link de ativação"*
- Href: `/afr_wellhub/inscricao/reenviar`

---

## Segurança

- **Mensagem genérica** em todos os casos — não revela se e-mail existe no sistema
- **Timing uniforme** — mesmo fluxo de resposta independente de encontrar ou não
- **CSRF** no POST
- **Rate limit implícito:** sem mecanismo extra (aceitável para MVP)
- Token gerado com `secrets.token_urlsafe(32)` (já existente)
- Busca limitada à empresa do website atual (multi-empresa seguro)

---

## Reutilização

Sem novos modelos ou métodos no model. Reutiliza:
- `_portal_new_signup_token()`
- `_portal_signup_token_expiry_string()`
- `mail_template_wellhub_signup_activation`
- CSS `wh-portal` existente

---

## Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `controllers/portal_wellhub.py` | +2 rotas (GET + POST `/reenviar`) |
| `views/portal_wellhub_templates.xml` | +2 templates + link em `inscricao_done` |

---

## Fora de Escopo

- Rate limiting por IP ou email
- Contador de tentativas
- Expiração do token mais curta para reenvios
