# Local config overrides (per-clone, gitignored)

<!-- TOC START -->

- [Contract](#contract)
- [List-typed registries](#list-typed-registries)
- [Example](#example)

<!-- TOC END -->

The flext-infra codegen ships a **public** fleet configuration: everything in
`config/*.yaml` is tracked, published, and safe for an external adopter. Values that are
operator-private — consumer organizations, deploy-key contracts, private workspace
layouts — must never be committed here. They live in one optional, gitignored file:

```
config/codegen-overrides.local.yaml
```

## Contract

- **Merge order**: tracked `config/*.yaml` files first (sorted), then the platform user
  overlay (`$XDG_CONFIG_HOME/flext-infra/*.yaml`), then `codegen-overrides.local.yaml`
  **last** — the local file wins every scalar collision.
- **Merge semantics**: identical to the tracked pipeline — recursive dict merge, lists
  concatenate, scalars replace. Dict-typed registries (`ci_private_submodules`,
  `layout.project_overrides`, `dependabot_cooldown_days`) gain local entries beside the
  public ones.
- **Validation**: the merged document passes the same typed models (`extra="forbid"`),
  so a typo in the local file fails loudly at load time instead of silently diverging.
- **Read timing**: the file is read once, when the config singleton is first fetched
  (module import of `flext_infra.config`). Restart any long-running process after
  editing it.
- **Never track it**: `.gitignore` blocks `/config/codegen-overrides.local.yaml` by SSOT
  rule; the guard gate rejects any diff reintroducing private values.

## List-typed registries

`providers` and `make.docs.github_repos` concatenate. A provider name must resolve
**exactly once** across the merged list, so never re-declare a name the tracked files
already carry — declare it in one layer only.

## Example

```yaml
Infra:
  codegen:
    providers:
      - name: my-org
        organization: my-org
        base_url: https://github.com/my-org
        branch: main
    dependabot_cooldown_days:
      my-repo: 7
  release:
    publishable_prefixes:
      - my-repo-
```

Every governed standalone repository keeps referencing its provider by name from its own
`config/workspace.yaml`; the registry entry above is what lets the generator resolve it.
