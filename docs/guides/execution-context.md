# Recuperar e manter o contexto de execução

<!-- TOC START -->

- [Começar pela decisão pendente](#comecar-pela-decisao-pendente)
- [Registrar antes de ampliar o trabalho](#registrar-antes-de-ampliar-o-trabalho)
- [Reconciliar decisões com seus responsáveis](#reconciliar-decisoes-com-seus-responsaveis)
- [Diferenciar checkpoint de conclusão](#diferenciar-checkpoint-de-conclusao)

<!-- TOC END -->

O ponto de entrada da estabilização é o
[handoff de namespace e runtime](../roadmap/namespace-automation-handoff-2026-09-14.md).
Ele reconcilia pedidos, plano reconstruído, mudanças, críticas, ADRs e Beads. O Beads
continua sendo o responsável pelo estado de execução; o handoff contém evidência e
instruções de retomada, sem criar uma fila paralela de tarefas.

**Estado corrente (2026-09-17):** a tip ativa é `flext-infra@0.12.0-dev@a2bd0a726`
(superprojeto `676ae7aa3c`). Nenhum SHA citado no handoff de 14/09 é ancestral dela. O
CRG citado não existe no checkout atual — o único válido é da worktree `rope-modernize`,
construído em `469b26b4e`, ancestral da tip. O defeito `_lazy_analysis` em
`src/flext_infra/codegen/_conform/execute.py:376/598` permanece e os god modules estão
inalterados. Gas City task `flext-itpd1.2` mantém o cursor da convergência documental e
`flext-5fxu6.4` continua sendo o proprietário técnico da modernização. O handoff
versionado deste repositório é a rota standalone; planos locais do superprojeto
preservam contexto de sessão, mas não são links portáveis nem substituem o tracker. As
fases 3 e 8 ainda não têm prova verde. Esta correção substitui somente os SHA, fases e
proprietários caducos do handoff.

## Começar pela decisão pendente

O runtime correto define o comportamento; os testes verificam esse contrato. Extermine
mocks, ferramentas falsas, acesso a funções privadas e asserções que só verificam como o
código foi escrito. Substitua-os por entradas e efeitos observáveis através das
interfaces públicas, preservando a cobertura funcional. Primeiro reproduza o caminho
público real e identifique o artefato executado. Corrija testes ou fixtures obsoletos
depois dessa prova, sem mudar o ambiente para preservar suas expectativas. O resultado
de um teste não certifica, por si só, setup, geração ou consumo na revisão integrada.

Leia a tabela inicial do handoff e o Bead indicado antes de repetir uma busca ampla.
Confirme branch, HEAD, alterações locais, PR e base declarada. Verifique o runtime por
`make status`; o caminho de execução e a versão instalada precisam corresponder ao
código que será validado. Um log anterior ou uma instalação do workspace pai não
certifica o checkout standalone.

Trabalhe sobre a tip de integração recém-buscada em cada repositório envolvido,
preservando as contribuições existentes e integrando divergências para frente. O
contrato de `make setup` inclui aprovar o `.envrc` com `direnv allow`; os verbos
operacionais do Make ativam esse ambiente antes dos handlers e hooks. A provisão inicial
antecede essa ativação para permitir criar o ambiente. Confirme o funcionamento pelos
comandos reais, sem exigir que o operador envolva cada chamada em `direnv exec`. Os
testes verificam esse runtime; não definem nem substituem seu comportamento correto.

Na execução de 14/09/2026, o operador selecionou o tracker do checkout `flext`
explicitamente. O comando Beads precisa do diretório de trabalho dessa raiz, além do
ambiente carregado por `direnv`. Isso é contexto autorizado dessa execução, não uma
regra para procurar runtimes no pai de todo repositório. O banco é o central do Gas
City. Use `direnv exec <rig> bd ...` no checkout do rig e confira uma leitura real. Se a
geração apagar a escolha de servidor, corrija seu modelo/template e regenere; não
inicialize um banco embedded ou grave host/porta manualmente. O Gas City mantém a
resolução do endpoint.

O contrato recuperado do histórico de `.envrc` é gerado em `.envrc.local`:
`AGENTS_GAS_CITY_ROOT` seleciona a cidade, a publicação de runtime do Gas City fornece a
porta e a metadata do rig fornece seu banco em modo `server`. O `.envrc` carrega esse
arquivo ao final. A fonte de ambiente declarada em
`BeadsWorkspaceEnvironmentSpec.environment_sources` fornece a identidade da cidade; o
template não fixa sua localização nem uma porta. As leituras JSON precisam terminar com
sucesso antes de exportar as variáveis.

Servidor central não significa substituir a identidade de um rig pela do HQ. Um
redirecionamento para o HQ combinado com o banco do rig causou
`PROJECT IDENTITY MISMATCH`. A operação nativa `gc rig set-endpoint <rig> --inherit`,
executada na cidade, recuperou a vinculação; a prova foi uma leitura real com
`direnv exec <rig> bd show <id> --json`. Não recrie metadata ou bancos manualmente para
contornar essa validação.

As correções mais recentes do operador exigem provisionamento e atualização
exclusivamente por `make setup`, dependências Git nos tips das branches de integração
declaradas e remoção de `APPLY`, `uv.lock` e `mise.lock` em todos os produtores e
consumidores. Corrija o responsável do setup e regenere pelo `make gen`; instalações
manuais não substituem o ciclo. Ignorar um lock no Git não remove o contrato se setup,
deps, build ou release ainda o recriam ou leem.

## Registrar antes de ampliar o trabalho

Mantenha no início do handoff o pedido vigente, suas exceções, SHA/PR, primeira falha,
última evidência completa e próxima ação concreta. Atualize esse bloco ao mudar escopo,
integrar contribuições, encontrar uma falha diferente ou publicar um checkpoint. Quando
o operador pedir o handoff, entregue o link disponível imediatamente e indique o estado
real da integração.

Cada evidência deve identificar comando, diretório, revisão observada, exit code e
resultado decisivo. Uma execução em andamento, interrompida ou sem seu exit code não é
verde. Alterações concorrentes exigem nova leitura antes de gravar e tornam necessária a
revalidação dos caminhos afetados.

## Reconciliar decisões com seus responsáveis

Use o [mapa de ADRs](../architecture/adr/README.md) para localizar os documentos reais.
Uma referência ausente é um problema documental a corrigir; não invente um ADR nem
reviva uma decisão superada. Registre divergências e a instrução mais recente que as
resolve. Planos de capacidades relacionadas não substituem o plano de execução da tarefa
atual.

Na automação de namespace, investigue catálogo, classificador, transformação, publicação
e consumidores nessa ordem. Um finding zero de codemod não prova que o gate de namespace
está verde. Preserve mutabilidade, herança, imports e collection; valide a transformação
na interface pública antes de ampliar o lote. Refatorações estruturais continuam
passando pelo `make mod`.

## Diferenciar checkpoint de conclusão

Um WIP publicado preserva o trabalho e permite revisão. Conclusão exige os critérios do
Bead ativo, integração e runtime medido no SHA integrado. Exceções registradas em
handoffs históricos, incluindo aceite temporário com gates customizados vermelhos, não
transferem para uma revisão ou Bead posterior. O contrato atual exige os verbos
canônicos sem warnings ou findings residuais.

O handoff final relaciona PRs, commits de merge e prova após integração aos Beads. Se
algo permanece pendente, o texto deve nomeá-lo e oferecer a próxima ação executável, sem
declarar fechamento funcional.

## Producer acceptance correction

The global conformity activation policy lives in `config/tooling.yaml` under
`Infra.check_policy`. Disabled enforcement retains raw conformity findings and never
converts their severity or a broken invocation into success. Ruff, Pyrefly, Mypy and
Pyright always block acceptance; consumers cannot override this policy. Canonical
suppression entries require explicit operator authorization before any change. The
authorized Rope override enables analysis without `py.typed`; it does not suppress
diagnostics. Validate the producer before consuming its package.

The operator reaffirmed observational execution on 2026-09-24: conformity checks still
run. Do not replace their results with suspended or unexecuted entries. External
analyzer failures remain blocking, including Markdown and security.
