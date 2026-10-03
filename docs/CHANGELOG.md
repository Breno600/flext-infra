# Changelog

## 0.12.0 - 2026-09-04

- Release tag: `v0.12.0`

Full notes: `docs/releases/v0.12.0.md`

## 0.12.0-dev (unreleased)

- Distribution data is declared by `project.packaged_data_paths` in
  `config/workspace.yaml`. Entries are repository-relative files or directories;
  for example, `config/deployment.yaml` ships that catalog without its governance
  siblings. Both wheel and sdist consume the same validated declaration. Missing,
  escaping, overlapping or package-colliding inputs fail before publication.
  Directory selection respects the same Hatch/VCS filters in both archives;
  individually declared files remain explicit inputs. Symlink traversal rejects
  external targets, dangling links and cycles. Scaffolds validate future data
  against their planned destinations. Undeclared root directories are never
  included implicitly.

- `deps modernize` and every other consumer of the workspace project enumeration now
  skip `.gitmodules` members that set `flext-managed` to anything other than `true`, the
  same opt-out the workspace detector already honors; a governed member with a missing
  or unreadable `pyproject.toml` still fails loud.

# Documentation

<!-- TOC START -->

- [0.12.0 - 2026-09-04](#0120-2026-09-04)
- [0.12.0-dev (unreleased)](#0120-dev-unreleased)

<!-- TOC END -->
