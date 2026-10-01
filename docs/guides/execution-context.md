# Recuperar e manter o contexto de execução

<!-- TOC START -->

- [Começar pela decisão pendente](#comecar-pela-decisao-pendente)
- [Registrar antes de ampliar o trabalho](#registrar-antes-de-ampliar-o-trabalho)
- [Reconciliar decisões com seus responsáveis](#reconciliar-decisoes-com-seus-responsaveis)
- [Diferenciar checkpoint de conclusão](#diferenciar-checkpoint-de-conclusao)
- [Bounded Mypy failure status](#bounded-mypy-failure-status)
- [Abstraction-boundary project identity](#abstraction-boundary-project-identity)
- [Codemod scanner contract](#codemod-scanner-contract)

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
operacionais do Make ativam esse ambiente antes dos handlers e hooks, exceto o produtor
de ativação declarado em `make.verbs`. Para `gen`, o pin e o ambiente físico já
provisionado são exigidos antes de `pre-gen` e do handler selecionado. O handler padrão
executa uma única transação conform, que inclui a geração do `.envrc`; um `_custom-gen`
declarado continua substituindo esse handler. Só então o Make ativa o ambiente gerado e
executa `post-gen`. Uma falha do produtor ou da ativação impede o hook posterior e
mantém o comando vermelho. Assim, `make gen` pode reparar uma ativação gerada quebrada
sem outro escritor fora do journal. A provisão inicial continua sendo responsabilidade
de `make setup`. Confirme o funcionamento pelos comandos reais, sem exigir que o
operador envolva cada chamada em `direnv exec`. Os testes verificam esse runtime; não
definem nem substituem seu comportamento correto.

A ativação consulta `bin-paths` no Mise pinado já instalado e antepõe os diretórios
reais das ferramentas aos shims compartilhados do host. Essa consulta é isolada, offline
e congelada: não instala ferramentas nem altera os locks. O `.envrc` acompanha também
`mise.version` e `mise.lock`, para recarregar os caminhos após `make upg`. Pin ausente
exige `make upg`; runtime ainda não instalado exige `make setup`, cuja provisão ocorre
antes de ativar o ambiente.

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

As correções mais recentes do operador (2026-09-24) declaram `latest` na configuração e
fazem de `make upg` o único verbo que resolve versões novas e grava os `uv.lock` e
`mise.lock` versionados. `make setup`, `make gen` e `make fmt` nunca atualizam: instalam
congelados a partir desses locks, que é o caminho do CI. Dependências Git seguem os tips
das branches de integração declaradas e `APPLY` continua removido. Cada requisito
interno `flext-*` declara no `pyproject.toml` a sua linha de integração, nunca um
commit: o commit resolvido existe só no `uv.lock`, e só o `make upg` o move para o tip
da linha. O manifesto não fixa revisões (`project.dependency_revisions` foi removido).
Um commit deixado na projeção do `pyproject.toml` é resíduo: o `make gen` o re-renderiza
na linha detectada e nunca o regrava; quando a projeção não traz linha alguma, o
`project.flext_source` escrito à mão no manifesto a declara, e um commit numa fonte
escrita à mão falha (operador 2026-09-28, `flext-oe420`). Corrija o responsável do setup
ou do `upg` e regenere pelo `make gen`; instalações manuais não substituem o ciclo.

O código de um checkout executa no ambiente do seu `RUNTIME_ROOT`. O Makefile gerado
exporta esse `RUNTIME_ROOT` e o `flext-infra` o lê como declaração tipada: a validação
`fresh-import` roda as sondas com o Python do ambiente físico externo declarado pelo
Makefile, nunca com o interpretador que hospeda a ferramenta. Sem declaração, o dono
deriva a raiz Git do checkout; uma declaração sem interpretador falha.

O ambiente pertence ao `RUNTIME_ROOT` (D-VENV, `flext-x8gn6`). Um membro anexado como
submódulo usa o ambiente do superprojeto Git que o contém; um checkout standalone ou uma
worktree vinculada tem o seu próprio. A pasta física fica no diretório irmão configurado
por `make.runtime_environment_directory`, com o caminho absoluto do checkout como
identidade. O Makefile gerado, o `.envrc` gerado e `runtime_environment_dir` resolvem
essa localização pelo mesmo caminho físico: entrar no checkout por um symlink não muda o
ambiente selecionado. Nenhum ambiente é emprestado de outro checkout por symlink.

Uma raiz de workspace declara cada membro anexado, de qualquer família (`flext-*` ou
não), como fonte Git inline na linha de integração do próprio workspace, a mesma que o
`.gitmodules` governado exige do membro; só as dependências `flext-*` que não são
membros seguem a linha FLEXT. Assim o `uv.lock` da raiz resolve todos os membros sem
overlay `[tool.uv.workspace]` (`flext-kd07c`).

O mesmo `make upg` é o único escritor de `mise.version`, `bin/mise` e `bin/mise.cmd`.
Ele resolve o release do Mise uma vez, pelo próprio Mise (`mise latest github:jdx/mise`,
autenticado por `GITHUB_TOKEN` e sujeito ao `minimum_release_age` do Mise), e gera os
dois launchers com `mise generate install-script --version <release> --windows`,
executado por esse release. Cada launcher embute o release e os checksums dele, então
chamadas diretas, por PATH ou por shim nunca consultam a rede para escolher versão.
`mise.version` leva um cabeçalho gerado seguido da única linha de release. `make gen`,
`make check` e o CI apenas verificam, offline, que os launchers embutem o release do
pin; um membro de workspace recebe do `make gen` da raiz a cópia exata desse trio, e só
a raiz de runtime executa `make upg`. O pacote `flext_infra` distribui em
`templates/bootstrap/` a cópia do trio do próprio flext-infra, usada apenas por um
repositório que ainda não tem nenhum ou que ainda carrega a projeção anterior ao bake,
cujos launchers resolvem `releases/latest` em tempo de execução: o `make gen` desse
repositório publica a cópia empacotada, já assada, e o `make upg` seguinte a regrava
para o release resolvido. Nunca edite esses arquivos; a correção é `make upg`. Um `bin/`
de projeto nunca entra no PATH (shell, `BASH_ENV` ou `GITHUB_PATH` do CI): o Mise liga
os shims compartilhados ao primeiro `mise` do PATH. Versione o pin, `mise.lock` e os
grafos nativos referenciados em `.mise/locks/` juntos; para ferramentas npm, o grafo
contém `package.json` e `aube-lock.yaml`. Esses arquivos também entram no contexto
Docker e nas fixtures de checkout. O setup congelado exige o grafo e seu digest válido,
conforme o
[contrato oficial de sidecars do Mise](https://mise.jdx.dev/dev-tools/mise-lock.html#native-dependency-sidecars).
Caches, instalações e grafos de locks locais continuam fora do Git. Não formate nem
edite o payload nativo: uma alteração dos bytes exige nova resolução pelo `make upg`. As
plataformas declaradas por `toolchain.mise_lockfile_platforms` compõem o lock junto com
a plataforma da máquina que executa a atualização, sempre incluída pelo Mise. Como
`MISE_SAFE` ignora os settings locais, o bootstrap encaminha `MISE_LOCKFILE`,
`MISE_LOCKED` e `MISE_LOCKFILE_PLATFORMS`, derivados do mesmo responsável tipado.
`MISE_LOCKED` ativa também a proteção global contra regravação durante a instalação:
`tool_config.locked` sozinho não protege essa fronteira. A prova de setup usa storage
Mise vazio e verifica os bytes dos locks, do pin e de todo o grafo nativo depois da
instalação.

O contrato de locks versionados também remove a antiga exclusão de lock ausente do
SonarCloud. `codegen.sonarcloud.issue_exclusions` continua sendo a fonte única da
configuração do servidor. Com `SONAR_TOKEN` no ambiente, `make sonarcloud-sync` envia
uma lista não vazia pela API `settings/set`; uma lista vazia usa
[`settings/reset`](https://sonarcloud.io/web_api/api/settings/reset), com `component` e
`keys`. O comando relê `settings/values` e exige o valor efetivo exato, incluindo
exclusões herdadas. Se o reset revelar uma exclusão do nível superior, a divergência
permanece uma falha. Um falso positivo sobre o formato nativo `aube-lock.yaml` exige
adjudicação individual com prova de instalação congelada; não autoriza exclusões amplas
nem alteração do payload nativo.

Depois de resolver o release do Mise, o bootstrap mantém essa versão em todas as
chamadas da mesma operação e no lifecycle recursivo. O `upg` inicializa os gitlinks
declarados antes de resolver os locks Python. Os demais verbos que dependem do runtime
recusam um pin ausente ou não resolvido antes da ativação; `help` e `clean` continuam
sendo operações locais sem essa dependência.

O bootstrap de rede recebe credencial explícita no ambiente do processo: `GH_TOKEN` tem
precedência sobre `GITHUB_TOKEN`. O Make não consulta `gh` nem o keyring. Sem ambas,
`make setup` pode reutilizar ferramentas e dependências já provisionadas; a operação
que precisar da rede falha no backend responsável. Um token inválido preserva o erro
nativo do backend, sem nova
tentativa anônima ou troca de fonte. O Mise lê o mesmo `GITHUB_TOKEN`; o Make remove do
ambiente dos recipes qualquer `MISE_GITHUB_TOKEN` herdado, porque um alias da mesma
credencial teria precedência sobre ela. O launcher de credenciais ou job de CI deve
injetar `GITHUB_TOKEN` no processo; containers recebem a variável ou o secret do
BuildKit explicitamente.

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
transferem para uma revisão ou Bead posterior. A configuração atual mantém uma
suspensão explícita do gate `namespace`; o responsável tipado valida sua autoridade
e seu escopo. Os gates de lint, format e type-checkers
(`pyrefly`, `mypy`, `pyright`) nunca são suspensíveis: o modelo rejeita essa
suspensão ao carregar a configuração. `make check` falha quando a seleção não
contém projetos ou quando um projeto selecionado não tem `pyproject.toml`; nenhum
projeto é pulado em silêncio. Local, CI e hooks derivam seus gates do mesmo conjunto
ativo, preservando a partição de tipagem já declarada: `CI=N make check` executa a
interseção com `make.ci.local_check_gates`, `CI=Y make check` executa o complemento e
`make check` sem `CI` executa a união. O pre-push de `check` remove o `CI` herdado para
executar todos os gates ativos; os demais verbos do hook mantêm o token local. O
workflow de CI executa as duas partições, sem sobreposição. Os validadores conservam sua
severidade e os gates funcionais ativos continuam exigindo execução sem warnings ou
findings residuais.

`smells` não pertence às partições de `make check`. O comando selector-free
`make smells` executa o mesmo gate de análise em separado e falha quando encontra
defeitos. Seus achados são tratados em uma campanha posterior para todos os projetos.
The verb owns every smell family, from qlty and from the runtime census alike. The
families derive from the flext-core smell catalog: every smell tag plus the rule id of
each catalog row that carries one. Ownership is routing: the `runtime-census` gate of
`make check` never evaluates, reports, or counts those families, and the `smells` gate
grades all of them. No hand-written list declares them.

O handoff final relaciona PRs, commits de merge e prova após integração aos Beads. Se
algo permanece pendente, o texto deve nomeá-lo e oferecer a próxima ação executável, sem
declarar fechamento funcional.

## Bounded Mypy failure status

The Linux Mypy command applies `prlimit` before launching the checker. In the observed
Mypy 2.3.1 run, an exhausted plugin allocation produced `INTERNAL ERROR` and exit status
2;
[the tagged Mypy source](https://github.com/python/mypy/blob/v2.3.1/mypy/main.py#L167-L174)
assigns status 2 to blocking internal errors. This is version-specific behavior, not a
fixed expectation for later Mypy releases. The resource test requires the workload to
start, then a nonzero raw status and a diagnostic without a timeout; it never rewrites
the result into a synthetic `MemoryError` or success. The Darwin supervisor can instead
terminate a process whose resident memory exceeds its limit.

## Abstraction-boundary project identity

The boundary gate reads the declared project identity through
`u.Infra.read_project_metadata_result`. Owner exemptions and TOML allowances use that
typed identity, so renaming a checkout or creating a linked worktree does not change its
policy. A consumer placed in an owner's named directory remains a consumer. Missing or
malformed project metadata blocks the gate and preserves the metadata reader's
diagnostic; directory names are never identity fallbacks.

## Codemod scanner contract

The operator's 2026-09-24 decision, retained by `flext-1pquc`, makes codemod policy
findings observational. This exception applies to those findings only. It does not
accept failed rule discovery, failed scanner execution, incomplete output, or invalid
diagnostic payloads, and it does not close the associated migration work.

The gate consumes the complete native `ast-grep scan --json=compact` array. The
[documented scan contract](https://ast-grep.github.io/reference/cli/scan.html) and
[native diagnostic schema](https://ast-grep.github.io/guide/tools/json) distinguish a
completed scan with error-severity findings (exit 1) from a completed scan without
error-severity findings (exit 0). Exit 1 must carry only ast-grep's complete terminal
diagnostic, whose count equals the validated error-severity findings. Additional
traversal diagnostics remain blocking: ast-grep can continue after an unreadable path
and still return exit 1 because another file contains a finding. The scanner boundary
checks the
[native terminal diagnostic](https://github.com/ast-grep/ast-grep/blob/0.45.3/crates/cli/src/utils/error_context.rs#L200)
and rejects extra output from the
[native path worker](https://github.com/ast-grep/ast-grep/blob/0.45.3/crates/cli/src/utils/worker.rs#L92).
Timeouts, forwarded signals, other exit codes, malformed JSON, and disagreement between
exit code and diagnostic severities remain failures, even when stdout exists. Both
whole-project checks and `check_files` scan every elected provider rule.

`GateExecution.observational_issues` retains original file, position, rule, message, and
severity separately from blocking issues and error counts. Workspace reports display
observation counts separately. SARIF uses explicit observational notes and retains the
native severity in each note; raw scanner output remains available on the execution. A
passing gate therefore proves the scanner contract, not zero migration findings.

The same repair validates projected Ruff first-party namespaces strictly: a malformed
value cannot be replaced with discovered namespaces. A declared empty list remains
empty; namespace discovery applies only when the list is absent. A bare Python
annotation does not replace an existing facade binding. Mypy's module-specific
`follow_untyped_imports` policy analyzes Rope's installed source without suppressing
`import-untyped`; the typed tooling policy owns both template and dependency-modernizer
projections. See the
[Mypy option contract](https://mypy.readthedocs.io/en/stable/config_file.html#follow-untyped-imports).
