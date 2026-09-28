# Handoff: automação de namespace e runtime do flext-infra

> Historical evidence only. This plan records an earlier execution context and its
> command examples are not current workspace guidance. Use the root `AGENTS.md` and
> `make help` for the active contract.

<!-- TOC START -->

- [1. Pedido, prioridade e limite desta entrega](#1-pedido-prioridade-e-limite-desta-entrega)
- [2. Plano de execução reconstruído e confronto com o resultado](#2-plano-de-execucao-reconstruido-e-confronto-com-o-resultado)
- [3. Documentos e decisões aplicáveis](#3-documentos-e-decisoes-aplicaveis)
- [4. Crítica da execução](#4-critica-da-execucao)
  - [4.1 A principal prioridade não dirigiu as mudanças](#41-a-principal-prioridade-nao-dirigiu-as-mudancas)
  - [4.2 O automatizador foi aplicado antes de provar seus contratos](#42-o-automatizador-foi-aplicado-antes-de-provar-seus-contratos)
  - [4.3 Houve reparações estruturais manuais não reproduzíveis](#43-houve-reparacoes-estruturais-manuais-nao-reproduziveis)
  - [4.4 A mutabilidade foi tratada como grafia de tipo](#44-a-mutabilidade-foi-tratada-como-grafia-de-tipo)
  - [4.5 A evidência foi fragmentada e ficou atrás do código](#45-a-evidencia-foi-fragmentada-e-ficou-atras-do-codigo)
  - [4.6 Gates diferentes estão respondendo perguntas diferentes](#46-gates-diferentes-estao-respondendo-perguntas-diferentes)
  - [4.7 A retomada inicialmente perguntou pelo plano errado](#47-a-retomada-inicialmente-perguntou-pelo-plano-errado)
  - [4.8 A compatibilidade foi investigada tarde demais](#48-a-compatibilidade-foi-investigada-tarde-demais)
- [5. O que foi preservado no código](#5-o-que-foi-preservado-no-codigo)
- [6. Evidências executáveis e suas limitações](#6-evidencias-executaveis-e-suas-limitacoes)
- [7. Beads relacionados e uso correto](#7-beads-relacionados-e-uso-correto)
- [8. Sequência concreta de retomada](#8-sequencia-concreta-de-retomada)
  - [8.1 Confirmar o estado e reproduzir a primeira falha](#81-confirmar-o-estado-e-reproduzir-a-primeira-falha)
  - [8.2 Corrigir a automação na ordem das dependências](#82-corrigir-a-automacao-na-ordem-das-dependencias)
  - [8.3 Recuperar a validação funcional](#83-recuperar-a-validacao-funcional)
  - [8.4 Critérios de aceite antes da integração](#84-criterios-de-aceite-antes-da-integracao)
- [9. Limite de encerramento deste handoff](#9-limite-de-encerramento-deste-handoff)

<!-- TOC END -->

> **Historical handoff.** This document preserves evidence from 2026-09-14/15; it is not
> the current execution queue. Resume from Gas City Bead `flext-5fxu6.4` and its active
> children, including the documentation slice `flext-5fxu6.4.28`, then apply the newest
> root `AGENTS.md`, ADRs, and branch-matched `flext-law`. Historical authorization for
> administrative merge or acceptance with red custom gates is superseded: current work
> requires the normal reviewed no-ff landing path and the active Bead's zero-warning
> gates.

**Atualização da retomada:** o operador passou a exigir estabilização e PRs integrados,
mantendo este handoff disponível durante o trabalho. O encerramento somente como WIP
descrito no registro original foi superado. Em `check`, o aceite exigido pelo operador é
Ruff, Mypy, Pyright e Pyrefly sem erros; os gates customizados podem permanecer
vermelhos, com evidência explícita. Testes, build e o runtime trabalhado continuam
obrigatórios. Essa exceção não declara os defeitos customizados resolvidos nem autoriza
desativar seus detectores.

**Instruções mais recentes do operador:** integrar por `merge --admin --merge` nas
branches de integração, comprovar geração/runtime também em `ai-hub` e `cosmos-main`, e
exterminar o contrato `APPLY` em todos os projetos. A exceção de simulação encontrada
nas orientações desses consumidores está superada; nenhuma forma ou deve permanecer como
interface suportada. A autorização administrativa é registrada como autorização do
operador, não como aprovação independente nem como evidência de testes aprovados.

**Correção posterior:** exterminar também `uv.lock` e `mise.lock`, incluindo geração e
leitura em setup/deps/build/audit/release; consumir os tips Git das branches declaradas
e publicar tudo nas branches de integração. Provisionamento e atualização são
exclusivamente por `make setup`. O agente consultou o help do uv para pesquisar o
responsável; nenhuma instalação manual foi executada. A migração completa para execução
sem lock ainda está pendente: o template atual executa `uv sync`/`uv lock`, e o
modernizer e release ainda leem o lock.

**Fechamento e testes:** a última instrução exige concluir esta execução e parar após
integrar, provar runtime e atualizar/fechar os Beads afetados. Revalidar testes pela
interface pública: eliminar fake/mock, acesso privado e asserções que só congelam a
implementação; preservar a cobertura de comportamento válido. O runtime define o
contrato, incluindo ambiente, geração e consumidores. `flext-c4k44` registra esse
trabalho. Todas as chamadas de Beads usam `direnv exec` no checkout do rig e o banco
central já mantido pelo Gas City. Não inicializar outro banco nem interpretar uma
leitura de metadata como prova de conectividade.

**Correção de autoridade (2026-09-17):** esta tabela e o corpo deste documento são
evidência histórica da execução de 14/09/2026. O estado corrente é `flext-infra` em
`0.12.0-dev@a2bd0a7262a0eab84bd7e4c27f8bdd10de0d247a` (superprojeto `676ae7aa3c`).
Nenhum SHA desta tabela é ancestral da tip atual — `5eb47cd21`, `758467a6a`,
`ee9e5e018`, `7b0b89c59`, `4cb1f038c` e `cb312a46b` são todos superseditos ou fora da
árvore de integração. A leitura viva substitui cada linha abaixo onde fontes atuais
discordarem. O CRG citado aqui não existe no checkout atual; o único CRG válido é da
worktree `rope-modernize`, construído em `469b26b4e` (ancestral da tip). O defeito
`_lazy_analysis` em `codegen/_conform/execute.py:376/598` permanece não resolvido e os
god modules (`_models/config.py` 3.342 LOC, `codegen/conform.py` 2.996 LOC) estão
inalterados. Recupere pelos Gas City tasks `flext-itpd1.2` (cursor
documental/governança) e `flext-5fxu6.4` (owner técnico), por este handoff versionado e
por `docs/guides/execution-context.md`. Planos locais da workspace são evidência de
sessão, não autoridade standalone.

| Contexto para retomada imediata         | Estado observado                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Checkpoint da continuação               | [PR #734](https://github.com/flext-sh/flext-infra/pull/734), Draft, branch `fix/workspace-hygiene-0.12.0`, tip publicado `5eb47cd2106ace4dc2a62818f84d107459a0f79f`. Preserva `cb312a46b` (produtores de Beads e revalidação de testes) e o guia de ativação automática. Os jobs CI desse Draft aparecem SKIPPED; isso não constitui aceite. O remoto de integração já contém `712624c9d`, inclusive o checkpoint `cb312a46b`, por contribuição concorrente                                                                                                                             |
| Última suíte concluída                  | `make test`, cwd flext-infra, exit 2; recibo `20260915T021753.505056Z-2111735/suite-outcome.json`: retorno bruto -15, `timed_out=true`, nenhum sinal encaminhado. Dois workers, 2.305 casos selecionados, execução interrompida em aproximadamente 10%. A rodada anterior `20260915T020045.360053Z-1956983` também terminou exit 2, retorno bruto -9 e timeout. Nenhuma suíte completa verde                                                                                                                                                                                            |
| Causa comum confirmada em setup         | Os eventos de `real_detector_project` preservam stdout/stderr de `make setup`: construção do infra local falha porque `flext-api/pyproject.toml` conserva uma tabela vazia `tool.uv.workspace` dentro do workspace composto. O responsável foi corrigido em `ee9e5e018`; a projeção dos demais membros ainda precisa convergir pelo gerador. Não alterar fixtures para esconder esse defeito de ambiente                                                                                                                                                                                |
| Correção de relatórios em validação     | `RunCommand.reports_dir_path` usava `Path.cwd()` e sobrescrevia o relatório do chamador em checks de outro repositório. Agora usa `repository_root`. O teste público existente executa Ruff real em dois projetos, confere o destino e preserva um relatório do chamador; caso `artifacts/check` PASS na rodada acima. Isso não certifica o restante da suíte. Bead `flext-9oljq` atualizado via direnv, exit 0                                                                                                                                                                         |
| Beads central e recuperação nativa      | Sem override manual de porta, `direnv exec <flext-rig> bd context --json` e `direnv exec <flext-rig> bd show flext-c4k44 --json` retornaram exit 0: banco flext, modo server, identidade preservada. Uma leitura posterior falhou com connection refused; `gc doctor` confirmou runtime Dolt indisponível e indicou `gc start`. Esse comando, via direnv no city, retornou exit 0; novas leituras de contexto e de `flext-9oljq` retornaram exit 0. Nenhum banco substituto, cópia de dados, porta manual ou segundo servidor foi criado. `gc doctor` completo ainda não recebeu aceite |
| Branch e PR de entrega                  | GitHub confirma [PR #732 MERGED](https://github.com/flext-sh/flext-infra/pull/732), `mergedAt=2026-09-15T00:44:57Z`, mergeCommit informado pela API `758467a6a`. O remoto contém o merge de dois pais `b82eefa3e7e00241eaeba7bd663809a47b58d169` e avançou até `ee9e5e018`. A continuação na branch existente `fix/workspace-hygiene-0.12.0` absorveu esse tip por merge no-ff `7b0b89c59`, exit 0; mudanças posteriores aguardam validação e publicação                                                                                                                                |
| Handoff e reparos publicados            | `4cb1f038c0bc6988acb87bd0e5c84335ba38dba7`, push exit 0; inclui guia de contexto, mapa de ADRs, skill e reparos de escopo/ordem da automação                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Último checkpoint antes do merge        | `a895de0c9`, preserva a projeção standalone após setup                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Base consultada                         | Fetch atualizado exit 0 nos três repositórios. Infra `origin/0.12.0-dev=b82eefa3e`; `git merge --no-ff origin/0.12.0-dev` exit 0, `Already up to date`. Em ai-hub, `git merge --no-ff origin/dev` também exit 0, `Already up to date`. Adotar sempre a composição corrente, preservando trabalho concorrente                                                                                                                                                                                                                                                                            |
| Composição preservada                   | Merge no-ff `d0b32d7d6`, publicado com push exit 0, absorve `origin/bugfix/stabilize-0.12.0` em `8b03723cb`, que reúne os PRs #723, #724 e #730; os 80 arquivos conflitantes foram reconciliados                                                                                                                                                                                                                                                                                                                                                                                        |
| Reconciliação                           | Fontes Python de `src`/`tests` parsearam; nenhum nome de teste dos dois lados conflitantes foi perdido; métodos da fixture antiga existem no novo responsável. Isso não substitui execução dos testes.                                                                                                                                                                                                                                                                                                                                                                                  |
| Runtime medido antes do merge           | `make status`: exit 0, perfil standalone no checkout; `make setup`: exit 0, 160 pacotes resolvidos, instalação local de `flext-infra==0.12.0`; recibo efetivo `uv 0.12.10`                                                                                                                                                                                                                                                                                                                                                                                                              |
| Outra contribuição a avaliar            | [PR #733](https://github.com/flext-sh/flext-infra/pull/733), `flext-ro6mj.1`, inclui coletor, transação e alterações sobre os mesmos responsáveis de codemod/docs; ainda não incorporada neste merge                                                                                                                                                                                                                                                                                                                                                                                    |
| Atualização remota posterior            | Fetch exit 0: a branch do PR #731 avançou até `ec9813edd`, incluindo reparo de diagnóstico Mypy e fixtures. Esse complemento e o PR #733 ainda precisam ser reconciliados                                                                                                                                                                                                                                                                                                                                                                                                               |
| Aceite ainda não obtido                 | A suíte não completou; a validação integrada dos consumidores e a integração das mudanças posteriores ao PR #732 continuam pendentes                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Check mais recente desta execução       | `make check`, exit 2, relatório observado em 2026-09-15T01:12:23Z: Ruff/lint 0, Mypy 0, Pyrefly 0; Pyright retornou -2 com KeyboardInterrupt, causa não determinada. Total 387: namespace 382, LOC 3, censo 1 e uma falha da ferramenta Pyright. A rodada anterior de 00:08:11Z tinha os quatro analisadores verdes, mas não certifica o estado atual. O arquivo de relatório compartilhado foi depois sobrescrito por testes de fixture; não usar seu conteúdo atual para reclassificar esta rodada                                                                                    |
| Automação realmente exercitada          | `stabilize-mod-local.log`, exit 2 às 23:30:07Z: publicou o aninhamento de `_models/mise_toolchain.py`; a segunda passagem teve zero alterações semânticas. Terminou por ausência de progresso com 16 findings de detecção (14 ambiente, 2 ancestry), sem falso verde.                                                                                                                                                                                                                                                                                                                   |
| Causa de escopo e custo                 | Rope promovia a chamada do membro para o superprojeto: 632 diretórios/4.737 módulos, 115,81 s. Após retirar a promoção no responsável de descoberta, a nova execução abriu o próprio infra: 54 diretórios/921 módulos, 1,35 s. A publicação semântica concluiu; o comando permaneceu vermelho pelos findings de detecção.                                                                                                                                                                                                                                                               |
| Geração e build                         | `make build`: exit 0, wheel e sdist. `make gen`, após corrigir o contrato sem seletores no template: exit 0, com verificações de ponto fixo, lazy-init e docs                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Primeira barreira obrigatória           | `make test`: exit 2; recibo `20260914T233654.583765Z-456708` informa `raw_return_code=-15`, `timed_out=true`. Houve falhas de contrato Make e timeouts de 60 s antes do limite de 600 s da suíte; nenhum aceite completo                                                                                                                                                                                                                                                                                                                                                                |
| Revalidação do merge local              | `make test` exit 2; recibo `20260915T002455.009064Z-1005606/suite-outcome.json`: retorno bruto -15, timeout verdadeiro, nenhum sinal encaminhado. 276 testes selecionados; preparação de fixtures de deps excedeu 60 s ao baixar/reconstruir dependências; a suíte parou em aproximadamente 21%                                                                                                                                                                                                                                                                                         |
| Último setup completo e falha posterior | Setup anterior exit 0, Mise 2026.9.8, uv 0.12.13, 160 pacotes; instalou flext-cli `641700e5f1d82c841aaaea496e22733d56ca3133`, flext-core `5a1317238e7e00a5d4250732bd4247c6dbce8d8c` e flext-tests `1e0bb2b334943c8299ffb6ad1258522ce2fd6ce9` por Git. Nova execução com Make gerado retornou exit 2: `Nested workspaces are not supported`, membro flext-api; seu recibo uv voltou a 0.12.10. Não há aceite atual de setup                                                                                                                                                              |
| Divergência de ferramenta observada     | `make status` exit 0, standalone/local, 160 pacotes compatíveis, mas exibiu uv 0.12.10 após setup usar 0.12.13. O template escolhe uv pelo PATH do chamador fora do bootstrap; ainda falta unificar essa escolha no responsável provisionado                                                                                                                                                                                                                                                                                                                                            |
| Geração e concorrência                  | Após liberação observada do lock, `make gen` exit 0 publicou Makefile/pyproject e verificou ponto fixo, lazy-init e docs. A nova geração para corrigir Beads retornou exit 2 por `filelock._error.Timeout`; `lslocks` confirmou outro processo com o journal de flext. Nenhum lock foi removido, processo interrompido ou timeout aumentado                                                                                                                                                                                                                                             |
| Cache e contrato de ambiente            | O bootstrap passou a declarar `UV_CACHE_DIR` no armazenamento persistente, porque o XDG cache do scratch forçava downloads/rebuilds por fixture. Removidos `UvEnvironmentPlan.lock_path` e sua asserção obsoleta; alterações ainda aguardam prova completa pelo caminho Make                                                                                                                                                                                                                                                                                                            |
| Tracker atual                           | `direnv exec <flext-rig> gc status`, cwd do city, exit 0: supervisor ativo, banco central com 26.296 registros. `direnv exec <flext-rig> bd show flext-c4k44 --json` e leitura de `flext-5fxu6.4` retornaram exit 0 após ajuste concorrente em `.envrc.local`. Comentário de fechamento em `flext-5fxu6.4` gravado com exit 0. Causa no gerador: metadata omitia `dolt_mode` apesar de SSOT=server; correção do produtor aguarda geração. Não houve banco substituto ou reinicialização                                                                                                 |
| Consumidores externos                   | `make help` exit 0 em ambos: ai-hub standalone, integração `dev`, PRs #777/#778; Cosmos workspace, integração `develop`, checkout agora em `fix/revalidation-apply-contract`. Nenhuma prova de geração ou runtime integrado desses consumidores foi obtida por esta execução                                                                                                                                                                                                                                                                                                            |
| Próxima ação concreta                   | Concluir a remoção do contrato nos responsáveis e consumidores; reparar/revalidar a suíte; absorver contribuições relacionadas, publicar e integrar administrativamente com prova dos SHAs integrados nos três projetos                                                                                                                                                                                                                                                                                                                                                                 |

Para recuperar contexto sem repetir a investigação: consulte o
[guia de execução](../guides/execution-context.md), o
[mapa dos ADRs](../architecture/adr/README.md) e a seção de retomada da skill canônica
`flext-law`. O Bead `flext-5fxu6.4` recebeu o checkpoint e o novo critério de aceite;
continua `in_progress`.

Registro crítico da execução de 14/09/2026, preparado por solicitação do operador. O
destinatário é quem retomará a correção. Este documento preserva evidências e a
sequência de retomada; o estado de execução continua no Beads. O registro original
abaixo é histórico. O PR #732 já foi integrado; a continuação permanece em **WIP**, sem
aceite de runtime completo. A tabela inicial prevalece sobre descrições antigas de
branch e estado do PR.

O checkpoint de implementação é
[`3bd09bddc`](https://github.com/flext-sh/flext-infra/commit/3bd09bddc2e835a6aa1412945d3859d9b74459e4),
na branch `fix/docs-renderer-contract`, pelo
[PR #732](https://github.com/flext-sh/flext-infra/pull/732), com destino `0.12.0-dev`.
Ele preserva o conjunto compartilhado de 172 arquivos alterados, com 1.562 inserções e
1.264 remoções. A branch contém também os checkpoints anteriores de documentação,
geração, circuito mod e execução de testes.

## 1. Pedido, prioridade e limite desta entrega

As chamadas do operador estabeleceram esta sequência:

1. Corrigir os problemas de `flext-infra` pela causa raiz, comprovar runtime completo e
   propagar para a branch de desenvolvimento por PR.
2. Usar o `make check` já iniciado e seu `check.lst` como ponto de partida. O operador
   esclareceu que não existia outro log de nohup.
3. Priorizar explicitamente **a automação que corrige namespaces**.
4. Investigar o plano que o agente vinha executando, confrontá-lo com as chamadas,
   criticar os desvios e preparar um handoff com documentos e Beads.
5. Gravar e publicar o estado atual como WIP, preservando o trabalho existente.
6. Estabilizar as contribuições de desenvolvimento com merges no-ff, concluir o trabalho
   operacional, integrar os PRs e testar a revisão integrada.
7. Entregar imediatamente o handoff atualizado e melhorar a recuperação de contexto em
   orientações, skills, planos, docs e ADRs nos seus responsáveis.
8. Usar merge administrativo e comprovar os consumidores externos `ai-hub` e
   `cosmos-main` nas respectivas branches de integração.
9. Exterminar `APPLY` em todos os projetos, superando as orientações antigas que ainda
   declaravam uma exceção de simulação.

As chamadas seis e sete superam o encerramento somente documental da quinta. A
publicação WIP preserva o trabalho intermediário; o resultado solicitado continua sendo
a integração validada. `main` não faz parte do destino solicitado.

Não havia um plano de execução persistido pelo agente neste checkout. A seção seguinte
reconstrói a sequência efetivamente adotada a partir da conversa, comandos, diffs e
logs; não apresenta um documento retrospectivo como se tivesse sido aprovado antes da
implementação.

## 2. Plano de execução reconstruído e confronto com o resultado

| Etapa adotada                                   | Resultado esperado                                        | Evidência e desvio                                                                                                                                                                                                                                                                |
| ----------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ler `check.lst` e localizar responsáveis        | Priorizar causas sistêmicas                               | A leitura encontrou 1.145 ocorrências de namespace e 298 violações no censo de runtime. Faltou transformar esse inventário em cobertura explícita do `make mod` antes de editar consumidores.                                                                                     |
| Reparar erros de tipos, documentos e descoberta | Desbloquear os caminhos reais                             | Houve correções úteis, mas foram tratadas como trilhas concorrentes ao problema principal, sem uma prova intermediária de automação estrutural funcionando.                                                                                                                       |
| Aplicar `make fix-enforcement`                  | Corrigir ocorrências pelo mecanismo do projeto            | A execução registrou 156 correções, 9.931 skips e 81 falhas. Também produziu tipos somente de leitura em contratos mutáveis e uma movimentação de constantes que quebrou o carregamento da CLI.                                                                                   |
| Corrigir o estrago e reduzir limites de arquivo | Recuperar funcionamento e gates                           | Parte da reparação usou edições manuais repetitivas e extrações de classes/testes fora de `make mod`. A causa do transformador foi corrigida apenas parcialmente.                                                                                                                 |
| Isolar o runtime standalone e regenerar         | Garantir que as verificações exercessem o projeto correto | O Make e o conformador de pyproject foram corrigidos nos responsáveis. `make status` agora confirma o checkout local. Os testes anteriores no runtime do pai não são prova da instalação standalone.                                                                              |
| Retomar `make mod` após a correção do operador  | Comprovar correção automática reproduzível                | A primeira tentativa parou por permissão no cache. Na retomada autorizada, fixtures passaram e 16 correções AST foram aplicadas, mas a fase semântica revelou ampliação indevida de escopo e ordem incorreta entre aninhamento e referências. Ainda não há ponto fixo comprovado. |
| Rodar os gates e integrar                       | Zero erro, runtime comprovado e PR aprovado               | O último check completo permaneceu vermelho; Ruff, Mypy e Pyright passaram, Pyrefly teve três erros corrigidos posteriormente. A preservação WIP foi publicada, mas o pedido vigente continua sendo integração com prova do runtime.                                              |

## 3. Documentos e decisões aplicáveis

O código e os comandos de `flext-infra` continuam pertencendo a este repositório. A
consulta aos documentos e ao tracker de `flext` foi autorizada explicitamente pelo
operador durante a preparação deste handoff.

- [AGENTS.md local](https://github.com/flext-sh/flext-infra/blob/0.12.0-dev/AGENTS.md) e
  a skill local `flext-law` em `.agents/skills/flext-law/SKILL.md`: responsáveis
  canônicos, preservação de alterações, fluxo estrutural por `make mod` e prova real.
- [ADR-005: SSOT e direção das facades](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/005-config-settings-constants-templates-schemas-ssot.md):
  configuração tipada, `c -> t -> p -> m -> u`, publicação transacional e migração com
  remoção dos responsáveis substituídos.
- [ADR-010: padronização e descoberta semântica, §3b](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/010-unified-project-standardization-via-codegen.md):
  descoberta em fontes reais, rewiring automático, ausência de progresso como falha,
  zero findings e diagnósticos no aceite.
- [ADR-014: forma das famílias e regras Rope](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/014-family-part-shape-rope-codemod-rules.md):
  classes órfãs, wrappers, replicação para consumidores e alinhamento entre os gates de
  namespace e codemod.
- [Plano de reconciliação e contratos Make](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/plans/2026-09-14-plan-reconciliation.md):
  contexto correlato de `flext-ro6mj.1`, não o plano original desta sessão. O PR #733
  deve ser reconciliado pelo efeito sobre os mesmos responsáveis de codemod/docs e pelo
  pedido posterior de concluir WIP; sua presença não prova que a coleta de todos os
  provedores esteja implementada ou validada.
- [Guia de desenvolvimento](../guides/development.md) e
  [padrão de automação](../guides/skill-automation-pattern.md): sequência nativa e
  responsabilidade de reproduzir mudanças nos consumidores.

Os quatro documentos de `flext` acima foram lidos no checkout em
`206c02ee1dd3f714a8164ade4b5605a6f71b8856`; esses caminhos estavam sem alterações locais
na consulta. Isso identifica a revisão documental, não prova sua integração remota.

ADR-012 não foi encontrado no diretório de ADRs dessa linha. O bead fechado
`flext-z0zkq` documenta a colisão histórica e determina ADR-005 §§1–2 e os docstrings de
`_settings.py`/`_config.py` como referências do padrão. A referência local em
`AGENTS.md` foi corrigida neste handoff; o restante da frota pertence a `flext-la3z5`.

Há divergências documentais que não podem ser ocultadas: ADR-005 §6 contém a proibição
antiga de AST; ADR-010 §3b e a skill local descrevem o circuito AST/Rope/LSP. ADR-010 §2
ainda menciona, enquanto o plano de 14/09 determina retirar `APPLY`. O checkpoint
compartilhado continha. Na retomada, essa divergência foi corrigida no template: os
verbos executam sua operação fixa e `make gen` regenerou o Makefile com exit 0. A
aceitação completa dos testes permanece pendente; o reparo não deve ser confundido com
um aceite anterior que nunca existiu. Essas diferenças não autorizam reverter
contribuições nem escolher uma regra silenciosamente. A retomada deve reconciliar a
intenção vigente no responsável e seu bead, sem introduzir outra gramática de comandos.

## 4. Crítica da execução

### 4.1 A principal prioridade não dirigiu as mudanças

O problema já era majoritariamente estrutural no primeiro log. Entretanto, o trabalho
concentrou-se em erros pontuais, tipos e extrações manuais. A mudança de prioridade só
ocorreu depois da chamada explícita do operador. O critério de progresso deveria ter
sido uma classe de violação corrigida de ponta a ponta pelo `make mod`, com consumidores
válidos e segunda execução sem efeitos.

| Medida nos logs               | Inicial | Último check completo |
| ----------------------------- | ------: | --------------------: |
| Namespace total               |   1.145 |                 1.099 |
| `NS-STRUCT`                   |     960 |                   953 |
| `NS-CONTRACT`                 |     137 |                    97 |
| `NS-IMPORT`                   |      48 |                    49 |
| Namespace em `src`            |     256 |                   247 |
| Namespace em `tests`          |     889 |                   852 |
| Violações do censo de runtime |     298 |                   298 |

A redução líquida de 46 ocorrências não demonstra convergência. A dimensão estrutural
quase não mudou, e a contagem de importações aumentou. Como houve edições compartilhadas
durante os comandos, essa comparação é descritiva; não permite atribuir cada diferença a
uma alteração específica.

### 4.2 O automatizador foi aplicado antes de provar seus contratos

A movimentação de constantes preservou trechos da expressão sem transportar corretamente
suas dependências, colocou declarações no nível do módulo e deixou
consumidores/importações inconsistentes. O resultado observado foi `NameError` durante o
carregamento da CLI. Corrigir manualmente os oito nomes recuperou esse caso, mas não
ensinou o automatizador a executar a operação corretamente.

O responsável ainda contém `_append_constant` com anexação no nível do módulo,
importações reconhecidas por padrões textuais e `Path.write_text` em múltiplos arquivos.
A correção do cálculo de pontos no import relativo é real e insuficiente. O lote
completo precisa ser planejado, validado e publicado pelo responsável transacional
existente antes que se aceite outra movimentação.

### 4.3 Houve reparações estruturais manuais não reproduzíveis

A extração de modelos de toolchain e a divisão dos testes de conformance foram feitas
fora do fluxo canônico. Os helpers extraídos conservaram nomes privados usados entre
módulos; o PR registra 22 diagnósticos de acesso privado em uma verificação posterior. A
contagem de nomes de testes preservados é útil para inventário, mas não prova
collection, fixtures ou execução equivalentes. Durante a publicação deste handoff, uma
alteração compartilhada tornou esses helpers públicos e atualizou seus consumidores nos
três módulos. Essa correção também foi adotada para o WIP; a prova funcional completa
continua pendente.

Essas alterações devem ser preservadas e corrigidas para frente. O próximo agente
precisa implementar a transformação reutilizável que reproduz a forma correta e
demonstrar que ela preserva comportamento. Outra divisão manual para reduzir LOC
repetiria o desvio.

### 4.4 A mutabilidade foi tratada como grafia de tipo

Converter `dict` em `Mapping` altera capacidades do contrato. O guard de
`typing_unifier.py` agora reconhece `dict[`, e consumidores afetados receberam tipos
mutáveis ou inferência concreta. Ainda falta provar pelo fluxo completo a distinção
entre parâmetro somente de leitura, parâmetro que é mutado, atributo mutável, retorno
concreto e container serializado.

`flext-6x6jr` especifica o caso de parâmetro. Ele não autoriza alargar todos os
atributos e retornos. Uma substituição indiscriminada, mesmo que reduza um gate, pode
invalidar operações em runtime ou no type checker.

### 4.5 A evidência foi fragmentada e ficou atrás do código

A primeira execução de testes usou o runtime do checkout pai. Depois houve correção de
isolamento, alterações adicionais e regeneração. Logs de check terminaram enquanto o
código continuava mudando. Parte da saída extensa do fixer não foi preservada
integralmente, e um caminho de log foi reutilizado. Faltou vincular cada rodada a uma
revisão e a uma identidade do conjunto de fontes observado.

No checkout atual, `make status` saiu 0 e confirmou runtime local, 160 pacotes
compatíveis e uv 0.12.10. Uma observação anterior registrou uv 0.12.13. Isso exige
preflight de identidade do toolchain; não permite afirmar que a versão instalada
corresponde ao contrato de newest release apenas porque o status passou.

### 4.6 Gates diferentes estão respondendo perguntas diferentes

O último check registrou `codemod=0` e `namespace=1099` no mesmo comando. Portanto, zero
no primeiro não prova conformidade de namespace. Em `class_nesting.py`, a fase retorna
plano vazio fora das famílias reconhecidas e quando encontra no máximo uma classe. Essa
fase, isoladamente, não cobre módulos sem classe, funções soltas ou todos os testes com
prefixo incorreto.

Também há um risco a testar em `batch_apply.py`: o loop anuncia cascata, mas
`_validate_fix_match` rejeita novos findings acionáveis após a primeira transformação.
Uma regra pode legitimamente revelar o padrão seguinte. Ainda não há reprodução deste
risco nesta sessão; não deve ser descrito como causa já comprovada do erro de cache.

### 4.7 A retomada inicialmente perguntou pelo plano errado

Durante este handoff, o agente perguntou pelo caminho de um plano externo. O operador
esclareceu que queria a revisão do plano que o próprio agente vinha executando. A
pergunta transferiu ao operador uma reconstrução que podia ser feita com a conversa e o
histórico. Este documento corrige esse enquadramento.

### 4.8 A compatibilidade foi investigada tarde demais

O agente removeu o seletor no template guiando-se pelo plano de verbos fixos, antes de
ler os contratos atuais dos consumidores externos. Ao encontrá-los, anunciou que
preservaria a exceção de simulação. O operador então esclareceu que o contrato inteiro
deve ser exterminado em todos os projetos. O desvio foi decidir a propagação sem
confrontar conjuntamente intenção atual, responsável, consumidores e orientação
publicada. A correção vigente é uma migração completa para verbos de operação fixa,
incluindo a remoção das instruções contraditórias; não criar uma exceção por projeto nem
enfraquecer os testes para manter o seletor.

## 5. O que foi preservado no código

| Responsável ou conjunto                                                                                      | Alteração preservada                                                                       | Limite da prova                                                                                     |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- |
| `templates/project/base/Makefile.j2` e `_utilities/pyproject_conform.py`                                     | Raiz standalone local e declaração uv que encerra descoberta de workspace ancestral        | `make status` local passou; teste de isolamento foi acrescentado, sem rodada final verde comprovada |
| `_utilities/project_discovery.py`                                                                            | Manifesto presente e inválido falha; ausência opcional continua representada pelo contrato | Regressão acrescentada, sem aceite final da suíte                                                   |
| `_utilities/docs_contract.py` e modelos de docs                                                              | Uso dos tokens tipados do Markdown e tratamento de navegação/âncoras                       | A branch já contém trabalho concorrente e resultados de docs registrados no PR                      |
| `workspace/_orchestrator_execution.py` e consumidores de Result                                              | Construção com o contrato genérico esperado                                                | Correções posteriores ao check exigem nova medição                                                  |
| `transformers/typing_unifier.py` e consumidores                                                              | Guard de mutabilidade e reparação das anotações alargadas indevidamente                    | Não prova convergência de todos os contratos                                                        |
| `_constants/codegen.py` e `codegen/_mise_artifacts_*`                                                        | Constantes inseridas na classe responsável e acessos corrigidos                            | A movimentação automática geral continua incompleta                                                 |
| `_models/codegen_toolchain.py` e `_models/codegen.py`                                                        | Separação dos modelos de toolchain, mantendo composição por herança                        | Extração manual; revalidar exports, importação e LOC                                                |
| `tests/unit/codegen/conform_support.py`, `test_codegen_make_contracts.py`, `test_codegen_script_dispatch.py` | Preservação dos testes extraídos; correção posterior dos acessos aos helpers públicos      | Comprovar collection, execução e ausência dos diagnósticos anteriores                               |
| `codemod/batch_apply.py`, `semantic_apply.py` e utilitários semânticos                                       | Aplicação de rewrites acionáveis antes da fase semântica; verificação das fontes propostas | Contribuições compartilhadas; `make mod` completo ainda não foi comprovado                          |
| Gates de censo/tier, geração e runner de pytest                                                              | Evidência causal e preservação do status de falha                                          | Não presumir aprovação a partir da existência da implementação                                      |

O commit é a autoridade para a lista completa de arquivos. Nenhuma parte do estado
compartilhado deve ser descartada para reconstruir artificialmente uma autoria isolada.

## 6. Evidências executáveis e suas limitações

Todos os comandos de implementação abaixo tiveram cwd na raiz do checkout `flext-infra`.
As consultas ao tracker usam o cwd na raiz de `flext`, conforme demonstrado pelo
operador. Os caminhos absolutos observados estão registrados nos comentários de
evidência do Beads, sem tornar a documentação dependente da máquina.

| Comando ou evidência                                                                   | Saída/resultado                                                                                                         | O que demonstra                                                                                                                  |
| -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `make check`, log inicial fornecido pelo operador                                      | Make terminou com erro 2; namespace 1.145; censo 298                                                                    | Ponto de partida, não revisão final                                                                                              |
| `make fix-enforcement`                                                                 | Exit 2; 156 fixed, 0 previewed, 9.931 skipped, 81 failed                                                                | Aplicação parcial com falhas; contagens recuperadas da sessão, sem log bruto completo retido                                     |
| `make check`, `check-repair-unrestricted.log`                                          | Exit 2; 1.119 erros agregados: pyrefly 9, mypy 6, LOC 4, censo 1, namespace 1.099; 481,45 s                             | Rodada anterior ao merge; terminou em 2026-09-14T21:39:53Z                                                                       |
| `make check`, `stabilize-merged-check.log`                                             | Exit 2; 569 erros; Ruff/lint 0, Mypy 0, Pyright 0, Pyrefly 3; namespace 382, codemod 180, LOC 3, censo 1; 608,43 s      | Terminou em 2026-09-14T23:12:38Z; alterações posteriores e concorrentes impedem certificar o checkpoint final com esta medição   |
| `make check`, `stabilize-runtime-check.log`                                            | Exit 2 em 2026-09-15T00:08:11Z; Ruff/lint, Mypy, Pyright e Pyrefly com zero erros; total 386, exclusivamente custom     | Satisfaz o recorte de check autorizado sobre as fontes daquela rodada, sem transformar o agregado vermelho em sucesso            |
| `make gen`, `stabilize-fixed-verbs-gen.log`                                            | Exit 0; `project conformance complete`, incluindo verificação de ponto fixo e recibos lazy-init/docs                    | Makefile regenerado pelo responsável após retirar o seletor; não constitui prova dos consumidores externos                       |
| `make build`, `stabilize-runtime-build.log`                                            | Exit 0; wheel e sdist produzidos                                                                                        | Artefatos do checkpoint foram construídos                                                                                        |
| `make test`, `stabilize-runtime-test.log`                                              | Exit 2; recibo `20260914T233654.583765Z-456708`: retorno bruto -15, timeout verdadeiro, nenhum sinal encaminhado        | Suíte interrompida pelo limite de 600 s, após erros de contrato e timeouts por caso; não houve aceite completo                   |
| `make mod`, `stabilize-mod.log`                                                        | Exit 2; fixtures exit 0; 16 correções AST aplicadas; erro `deferred-models phase left residue after application`        | A automação avançou, mas a transação semântica não foi publicada; o problema de permissão inicial deixou de ser a primeira falha |
| `make mod`, `stabilize-mod-local.log`                                                  | Exit 2 às 2026-09-14T23:30:07Z; publicação semântica de um arquivo; reaplicação sem alterações; 16 findings de detecção | Escopo e ordem corrigidos no caminho real; o comando acusa ausência de progresso e mantém a dívida visível                       |
| `make fmt`, `stabilize-runtime-fmt.log`                                                | Exit 0                                                                                                                  | Formatação após os reparos de escopo e ordem; não comprova o runtime semântico                                                   |
| `make mod`, `namespace-mod.log`                                                        | Exit 2; `OSError: [Errno 30] Read-only file system` em `mod-rule-fixtures-*`                                            | A execução não passou do preflight de fixtures                                                                                   |
| `make gen` e `make setup`, rodadas anteriores                                          | Exit 0                                                                                                                  | Gerador/setup exercitados antes do checkpoint; não certificam o conjunto final                                                   |
| Recibos de suíte `20260914T210624.850231Z-2834013` e `20260914T212545.368582Z-3122161` | `raw_return_code=-15`, `timed_out=true`, `forwarded_signal=null`                                                        | Execuções interrompidas por timeout; nenhum aceite da suíte completa                                                             |
| `make status`, durante o handoff                                                       | Exit 0; profile standalone; project e runtime locais; 160 pacotes compatíveis                                           | Preflight local, sem comprovação de todas as funções                                                                             |
| `make docs`, durante a publicação do handoff                                           | Última execução exit 2 em 2026-09-14T22:18:10Z: `atomic source changed` em `tests/unit/release/protocol_tests.py`       | Alteração compartilhada durante a geração invalidou a fotografia de fontes; não há aceite final de docs                          |
| `git diff --cached --check`, antes do checkpoint                                       | Exit 0                                                                                                                  | Integridade textual, não teste funcional                                                                                         |
| Fetch e comparação de referências                                                      | Exit 0; HEAD e branch remota iguais a `3bd09bddc`; base `a254c1f3f3e3491a5eea34c6a088c7285e454ca6`                      | Implementação preservada remotamente; a base é ancestral do checkpoint                                                           |

No check completo, as quatro falhas de LOC apontavam `_models/config.py`,
`_utilities/rope_analysis.py`, `codegen/conform.py` e o antigo módulo único de testes de
conformance. A extração posterior invalida essa última medição para o checkpoint. O
agregado `runtime-census=1` representa **298 violações**, não uma única correção
pendente.

Na validação documental, quatro caminhos de máquina foram substituídos por referências
portáveis, e as referências fora do site foram corrigidas. A auditoria seguinte reportou
zero problemas; o build ainda identificou os links externos ao conjunto MkDocs,
corrigidos antes da última tentativa. Essa última tentativa parou na mudança concorrente
de fonte descrita acima. O log `handoff-docs-publish.log` preserva a falha causal. Não
repetir uma execução sem renovar a identidade das fontes e adotar as mudanças
observadas.

Os logs locais estão no scratch externo de `flext-infra`, resolvido pelo responsável de
armazenamento em `config/codegen.yaml`; o comentário de `flext-5fxu6.4` preserva seu
caminho físico observado. `check-initial.lst` é o `check.lst` concluído, movido para
preservar evidência sem manter um arquivo estranho no layout do projeto. Não há log de
nohup.

| Arquivo                         | SHA-256 observado                                                  |
| ------------------------------- | ------------------------------------------------------------------ |
| `check-initial.lst`             | `89fc6973cf4b67bac6c144c128222e1797146fb4b86ec89b250d5aa92b4674e1` |
| `check-repair-unrestricted.log` | `67e02bad362ceb2a5fcacab555a343a7dfb70eab8e483b90046ce2d06da8c9d6` |
| `namespace-mod.log`             | `32e4f10dc734c5e9a5ca5657bd4a60cbfb64b8108519ee1bec1da5cfe5f27424` |

Esses arquivos e `.reports/tests/<execução>/suite-outcome.json` são evidências locais;
não são conteúdo publicado no Git. O PR e este handoff preservam os resultados
relevantes, sem publicar transcrições privadas.

Na conferência final, uma alteração compartilhada de `pyproject.toml` retirou a tabela
vazia `tool.uv.workspace`; também foram observados ajustes nos testes de raiz Make e nos
nomes dos campos de configuração Ruff. O estado foi preservado como WIP. A origem dessa
diferença da projeção não foi estabelecida, e o `make status` anterior não a certifica.
Antes de executar novamente a automação, verificar a correspondência entre perfil
standalone, conformador, projeção uv e runtime efetivo, regenerando pelo responsável
quando necessário.

## 7. Beads relacionados e uso correto

Os registros abaixo foram consultados ao vivo com `bd show`, usando `direnv` para
carregar o contexto do checkout `flext`, com cwd em `flext` e exit 0. A tentativa
inicial no cwd `flext-infra` retornou `no beads database found`; isso era uma diferença
de contexto, não prova de indisponibilidade do servidor do operador.

| Bead                          | Relação com a retomada                                                                                               |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `flext-5fxu6.4`               | Responsável principal: gerador/enforcement de infra; exige ciclo completo, ponto fixo e prova após merge             |
| `flext-5fxu6`                 | Programa pai: correções sistêmicas e propagação; não expandir esta entrega automaticamente para a frota              |
| `flext-pwmej`                 | Correlação dos gates: tipos, duplicação, codemod e limites de arquivo                                                |
| `flext-ocxtt`                 | Critérios de gates de infra e geração sem efeitos; as notas atuais citam também grpc e não provam aceite de infra    |
| `flext-6x6jr`                 | Conversão de container em parâmetro; preservar distinção entre leitura e mutabilidade                                |
| `flext-k7vvp`                 | Fixtures/snapshots de `make mod`; existe agora implementação de atualização no responsável, mas falta prova completa |
| `flext-c1vvr`                 | Cobertura de imports privados em `scripts`; revisar escopo declarado além de `src/tests`                             |
| `flext-z4ydq` e `flext-t9q8h` | Custo do namespace move e da descoberta de providers; não aumentar limites para esconder repetição de trabalho       |
| `flext-mu6mp`                 | Toda mudança de contrato precisa transportar a migração dos consumidores                                             |
| `flext-la3z5`                 | Autocorreção de infra antes da frota e reparação das referências obsoletas de ADR                                    |
| `flext-z0zkq`                 | Evidência histórica da referência ADR-012; fechado para seu escopo original, sem autorização para fechar a frota     |

Não foi criado um novo épico nem alterada a hierarquia para representar este handoff.
Comentários de evidência foram gravados e relidos em `flext-5fxu6.4`, `flext-pwmej`,
`flext-6x6jr` e `flext-la3z5`, apontando para este documento, o checkpoint e o PR.
Nenhum item foi fechado. As referências Cosmos já existentes no PR pertencem às
contribuições correlatas e não substituem o tracker FLEXT desta execução.

## 8. Sequência concreta de retomada

### 8.1 Confirmar o estado e reproduzir a primeira falha

Consultar a branch/PR atuais, absorver as alterações compatíveis, verificar o runtime
por `make status` e identificar a versão efetiva das ferramentas. Não criar uma
instalação paralela nem reutilizar resultados de outro runtime. Preservar novos logs com
nomes próprios e identidade da revisão observada.

O último **`make mod`**, no checkout de `flext-infra`, terminou com exit 2; consulte
`stabilize-mod-local.log`. A permissão do cache foi resolvida pela execução autorizada.
A falha seguinte era resíduo de deferred-models depois do aninhamento de
`_models/mise_toolchain.py`. O responsável `codemod/semantic_apply.py` agora aninha
antes de normalizar referências, mantendo as verificações de resíduo e a publicação
transacional. Essa execução publicou a transformação e comprovou zero alterações
semânticas na passagem seguinte. A primeira pendência do comando passou a ser os 16
findings de detecção (14 de ambiente e 2 de caminhada de ancestrais), relatados
causalmente como ausência de progresso. Não retirar essa verificação para obter exit 0.

Na mesma execução, `_utilities/discovery.py` promovia o membro para o workspace
ancestral. Essa promoção foi removida; o teste público
`test_open_workspace_keeps_the_requested_repository_boundary` agora distingue chamada
explícita ao workspace de chamada ao membro/pacote. A nova execução confirmou Rope na
raiz de infra, com 921 módulos em 1,35 s, em vez dos 4.737 módulos em 115,81 s. Ainda é
necessário executar o teste público, importar os modelos gerados no runtime e renovar o
aceite dos quatro analisadores, testes e build. Uma melhora de tempo e escopo não
substitui o aceite funcional.

### 8.2 Corrigir a automação na ordem das dependências

| Ordem | Responsáveis                                                                          | Resultado exigido                                                                                                                      |
| ----- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | `codemod/batch_gates.py`, `snapshot_reconciler.py`, regras e fixtures declaradas      | Fixtures completas validadas, falhas causais e fontes fora do escopo preservadas                                                       |
| 2     | `refactor/classvar_constant_autofix.py`, `fixers/rope_fixer.py`, publicação existente | Movimento para a classe correta, dependências de expressão e todos os consumidores preservados, sem escrita parcial                    |
| 3     | `transformers/typing_unifier.py` e regras de tipos                                    | Contratos de mutabilidade preservados; aliases canônicos compatíveis com uso real                                                      |
| 4     | `codemod/semantic_apply.py`, `_utilities/class_nesting.py` e responsáveis CST/Rope    | Cobrir órfãos, wrappers, funções/dados soltos, forma das facades e consumidores; bases e subclasses avaliadas com sua dependência real |
| 5     | `codemod/batch_apply.py` e inventário do namespace                                    | Cascata convergente; cada finding acionável resolvido, cada ambiguidade causalmente relatada, nenhum falso ponto fixo                  |
| 6     | `validate/_namespace_rules`, `validate/runtime_census.py`, gates correspondentes      | Mesmo escopo e contratos; relatórios íntegros, sem converter falhas em warning ou sucesso                                              |

As linhas acima são dependências de implementação, não autorização para criar um segundo
motor. Reutilizar as facades e primitivas atuais. Novas regras de política pertencem aos
dados tipados do catálogo. Cada transformação deve ter casos de comportamento pela
interface pública: importação e avaliação das constantes; alias de consumidor; colisões;
herança; collection de testes; mutação versus leitura; erro antes da publicação; segunda
aplicação sem diff.

Antes de ampliar o lote, demonstrar que a transformação reproduz corretamente um caso
real da classe de erro. Em seguida, executar o verbo nativo no escopo declarado
completo. Não substituir isso por uma lista de centenas de arquivos ou por scripts
temporários que reescrevem consumidores.

### 8.3 Recuperar a validação funcional

Depois da automação estrutural, regenerar exports e projeções, corrigir os contratos de
helpers de testes e tratar os módulos acima do limite pelo responsável de refatoração.
Executar a sequência nativa estabelecida:

```bash
make gen
make mod
make gen
make gen
make fix
make fmt
make check
make test
make build
make docs
make gen
```

Uma falha interrompe a invocação e mantém o trabalho na correção do responsável. Depois
de qualquer alteração pertinente, renovar a evidência afetada. Não ampliar timeout nem
remover Testmon para obter um resultado verde. Para testes interrompidos, usar os
recibos e o reportlog do runner atual para localizar a primeira falha/custo real;
contagens parciais não certificam a suíte.

### 8.4 Critérios de aceite antes da integração

- O runtime da automação trabalhada é exercitado pela interface nativa e sua reaplicação
  é verificada. Falhas restantes são ligadas ao seu Bead e não convertidas em prova de
  sucesso.
- Ruff, Mypy, Pyright e Pyrefly terminam sem erros. Pelo esclarecimento mais recente do
  operador, findings dos gates customizados podem permanecer. `make check` exits 0 by
  contract (operator ruling 2026-09-16); record the findings from
  `.reports/check/check-report.{md,sarif}`. Green means zero findings in that report.
- `make test`, build e documentação terminam com exit 0 no runtime declarado; a
  evidência identifica revisão, ambiente, seleção e resultado completo.
- Geração consecutiva atinge ponto fixo; não há responsáveis antigos, consumidores sem
  migração, arquivos temporários ou aliases de compatibilidade.
- O PR contém o escopo real, perde WIP somente após a validação, recebe a aprovação
  exigida e integra por merge commit em `0.12.0-dev`.
- O SHA integrado é revalidado, os Beads recebem as quatro fontes de evidência e só
  então se trata o encerramento. Propagação para consumidores adicionais segue seus
  próprios responsáveis e autorizações.

## 9. Limite de encerramento deste handoff

Este handoff deve permanecer disponível enquanto a estabilização prossegue. A crítica da
retomada é objetiva: o agente voltou a concentrar tempo no merge antes de atualizar a
entrega documental pedida, deixando o operador sem uma visão imediata do estado. A
correção é manter neste início o objetivo vigente, SHA/PR, primeira falha, última
evidência válida e próxima ação; detalhamento histórico fica nas seções seguintes e
execução permanece no Beads.

O checkpoint WIP não satisfaz os critérios de conclusão funcional. O handoff final
solicitado somente poderá informar PRs integrados quando houver URLs, SHAs de merge,
gates aplicáveis e runtime medido na integração. Até isso ocorrer, este documento é um
handoff utilizável de trabalho em andamento, sem declaração de encerramento funcional.
