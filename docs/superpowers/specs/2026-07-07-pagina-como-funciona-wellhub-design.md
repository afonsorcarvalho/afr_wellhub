# Página educativa "Como funciona o Wellhub"

Data: 2026-07-07
Módulo: `afr_wellhub`

## Objetivo

Página pública e educativa que explica ao colaborador toda a jornada do
benefício Wellhub — desde receber a elegibilidade pela empresa até realizar o
primeiro check-in numa academia. **Puramente educativa**: não processa
inscrição nem pagamento (isso vive no formulário existente
`/afr_wellhub/inscricao`); apenas explica e, no fim, encaminha o colaborador
para lá.

## Escopo

Fluxo escolhido (opção B do brainstorm): o colaborador **se inscreve primeiro
neste portal** e depois a empresa o cadastra no Wellhub oficial. A página
educativa reflete essa ordem e aponta "já se inscreveu? agora baixe o app".

Fora de escopo: integração com API Wellhub, mecânica de cobrança Asaas,
qualquer estado ou lógica de negócio na página.

## Arquitetura

Três alterações, todas em arquivos existentes do módulo, reusando o design
system `wh-portal` já presente.

1. **Template** — novo `portal_wellhub_como_funciona` em
   `views/portal_wellhub_templates.xml`.
   - Chama `t-call="website.layout"` e `t-call="afr_wellhub.wh_icon_sprite"`.
   - Usa classes `wh-portal`, `wh-hero`, `wh-card`, `wh-btn-primary`,
     `wh-steps`, `wh-tips` já definidas. Ícones do sprite SVG existente.
   - Sem contexto dinâmico obrigatório (conteúdo estático). Se algum valor for
     útil (ex.: preço mínimo, nome da empresa), pode vir do controller, mas não
     é requisito.

2. **Controller** — nova rota em `controllers/portal_wellhub.py`, classe
   `AfrWellhubPortal`.
   - `@http.route('/afr_wellhub/como-funciona', type='http', auth='public',
     website=True, sitemap=True)`.
   - Método simples que retorna
     `request.render('afr_wellhub.portal_wellhub_como_funciona', {})`.
   - Sem POST, sem CSRF, sem estado, sem efeitos colaterais.

3. **Menu** — novo `website.menu` em `data/website_menu.xml`.
   - Nome "Como funciona", url `/afr_wellhub/como-funciona`,
     `parent_id` = `website.main_menu`, `sequence` 54 (antes de "Inscrição
     Wellhub" em 55).

## Seções de conteúdo (dentro do template)

1. **Hero** — título "Como funciona o Wellhub" + subtítulo introdutório.
2. **O que é** — streaming de academias: 1 mensalidade única, acesso a 100k+
   academias/estúdios + apps de bem-estar (meditação, terapia, nutrição).
3. **Jornada em passos** (cards numerados, `wh-steps`):
   elegibilidade pela empresa → inscrição neste portal → confirmação por
   e-mail e pagamento → empresa cadastra no Wellhub → baixar o app →
   criar conta / confirmar a empresa → escolher plano.
4. **Primeiro check-in** (mini-guia, `wh-tips`): abrir o app → botão check-in
   (canto inferior) → locais próximos por GPS → escolher a atividade →
   confirmar perto do local. Nota: check-in fora da janela / sem comparecer
   bloqueia outro local no mesmo dia.
5. **Além da academia** — aulas ao vivo, meditação, terapia, nutrição, apps
   parceiros; check-in internacional; planos família (variam por empregador).
6. **FAQ curto** — sem taxa de adesão; cancelamento a qualquer momento sem
   multa; possibilidade de pausar; cobrança mensal na data de ativação.
7. **CTA final** — "Pronto para começar? → Fazer inscrição", botão
   `wh-btn-primary` linkando `/afr_wellhub/inscricao`.

## Fontes dos fatos Wellhub

- https://wellhub.com/pt-br/employees/
- https://analisatech.com.br/checkin-no-wellhub/
- https://wellhub.com/pt-br/recursos/b2b-como-funciona-wellhub/

## Testes / verificação

Módulo não tem suíte de testes automatizados para portal. Verificação manual:
1. Upgrade do módulo no container `web` (`-u afr_wellhub`).
2. Abrir `http://localhost:8099/afr_wellhub/como-funciona` — página renderiza,
   sem erro, layout `wh-portal` consistente com a inscrição.
3. Item "Como funciona" aparece no menu do site, antes de "Inscrição Wellhub".
4. CTA final leva a `/afr_wellhub/inscricao`.
5. Responsivo mobile (cards/steps empilham).

## Riscos / notas

- Conteúdo estático → baixo risco. Maior atenção: consistência visual com o
  design system existente e responsividade dos cards de passos.
- `sequence` do menu: confirmar que 54 posiciona antes de 55 sem colidir com
  outros itens do site.
