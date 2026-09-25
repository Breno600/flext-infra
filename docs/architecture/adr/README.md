# Mapa de decisões aplicáveis ao flext-infra

<!-- TOC START -->

- [Divergências identificadas](#divergencias-identificadas)
- [Contexto de implementação](#contexto-de-implementacao)
- [Estado corrente (reconciliado com fontes vivas em a2bd0a726)](#estado-corrente-reconciliado-com-fontes-vivas-em-a2bd0a726)

<!-- TOC END -->

Este índice aponta os responsáveis arquiteturais da estabilização de namespace e
runtime. Os ADRs de plataforma abaixo pertencem a `flext`; este repositório mantém o
código, seus testes e este mapa de navegação. O índice não substitui nem duplica o texto
das decisões.

| Referência                                                                                                                                 | Responsabilidade                                        | Aplicação nesta execução                                                                              |
| ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| [ADR-005](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/005-config-settings-constants-templates-schemas-ssot.md) | Configuração, settings, constantes, templates e schemas | Usar §§1–2 para configuração e seus responsáveis tipados; corrigir templates/SSOT antes das projeções |
| [ADR-010](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/010-unified-project-standardization-via-codegen.md)      | Padronização e descoberta semântica                     | §3b descreve descoberta nas fontes e rewiring automático; conferir a implementação e a skill canônica |
| [ADR-014](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/014-family-part-shape-rope-codemod-rules.md)             | Forma das famílias e codemods Rope                      | Alinhar órfãos, wrappers, consumidores e detecção de namespace                                        |

## Divergências identificadas

ADR-012 não é a referência de configuração dessa linha: `flext-z0zkq` já documentou a
correção para ADR-005 e os docstrings de `_settings.py`/`_config.py`. A propagação
restante está ligada a `flext-la3z5`.

ADR-005 §6 contém uma proibição histórica de AST, enquanto ADR-010 §3b e a skill
`flext-law` descrevem o circuito AST/Rope/LSP. ADR-010 §2 contém, enquanto o plano de
reconciliação de 14/09/2026 determina verbos sem seletores. Essas divergências estão
documentadas no [handoff](../../roadmap/namespace-automation-handoff-2026-09-14.md), com
as revisões consultadas e a precedência do pedido mais recente. Este índice não declara
que os ADRs de plataforma já foram alterados.

## Contexto de implementação

O plano reconstruído, as causas ainda não corrigidas e os responsáveis estão no handoff.
`flext-5fxu6.4` é o Bead principal de geração/enforcement; `flext-pwmej` cobre a
convergência dos gates; `flext-ro6mj.1` trata da capacidade correlata de
coleta/reconciliação de planos. Consulte o
[guia de recuperação](../../guides/execution-context.md) antes de reiniciar uma
varredura de contexto.

## Estado corrente (reconciliado com fontes vivas em `a2bd0a726`)

Os ADRs de plataforma acima não foram alterados desde a consulta. As divergências
listadas permanecem abertas e não devem ser silenciosamente escolhidas:

- ADR-005 §6 proíbe AST; ADR-010 §3b e a skill `flext-law` descrevem o circuito
  AST/Rope/LSP.
- ADR-010 §2 menciona verbos com seletor, enquanto o plano vigente determina verbos sem
  seletor e a remoção de `APPLY`.
- ADR-012 continua ausente deste diretório; `flext-z0zkq` documentou a referência
  histórica e determina ADR-005 §§1–2 como padrão. A propagação restante é de
  `flext-la3z5`.

A correção mais recente do operador sobrepõe esses textos: `APPLY` está exterminado em
todos os produtores e consumidores; a configuração declara `latest` e somente `make upg`
resolve e grava os `uv.lock` e `mise.lock` versionados, enquanto `setup`, `gen` e `fmt`
instalam congelados a partir deles (operador 2026-09-24); e os Beads são exclusivamente
do Gas City. Qualquer nova leitura desses ADRs deve aplicar essa precedência e reportar
o conflito no Bead owner, não resolver em silêncio.

O estado dos god modules e do defeito `_lazy_analysis` não é provado resolvido por
qualquer fonte viva. Consulte o [roadmap](../../roadmap/index.md) para a tabela corrente
e o Bead ativo. Gas City task `flext-itpd1.2` mantém o cursor da convergência documental
e `flext-5fxu6.4` mantém o owner técnico de geração/enforcement; o
[handoff de namespace e runtime](../../roadmap/namespace-automation-handoff-2026-09-14.md)
é a rota versionada de retomada. Planos locais do superprojeto são contexto de sessão e
não fazem parte do contrato standalone.
