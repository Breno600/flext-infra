"""Bisect the metaclass conflict in the FlextInfraUtilities.Infra composition.

Imports each stem, then composes incrementally in the exact order used by
src/flext_infra/utilities.py. The first stem whose addition breaks the
composition is the deviant; the accumulated metaclass at that point identifies
the conflicting counterpart.
"""

from __future__ import annotations

import importlib
import traceback

STEMS: list[str] = [
    "FlextInfraUtilitiesBase",
    "FlextInfraUtilitiesProcess",
    "FlextInfraUtilitiesPromoted",
    "FlextInfraUtilitiesNetwork",
    "FlextInfraUtilitiesResourceLimits",
    "FlextInfraUtilitiesCodegen",
    "FlextInfraUtilitiesCodegenFilePlan",
    "FlextInfraUtilitiesCodegenNamespace",
    "FlextInfraUtilitiesPyprojectConform",
    "FlextInfraUtilitiesPyrefly",
    "FlextInfraUtilitiesProjectManagedArtifacts",
    "FlextInfraUtilitiesQualifiedNames",
    "FlextInfraUtilitiesDiscovery",
    "FlextInfraUtilitiesRopeCore",
    "FlextInfraUtilitiesRopeAnalysis",
    "FlextInfraUtilitiesRopeAnalysisWorkspace",
    "FlextInfraUtilitiesRopeAnalysisIntrospection",
    "FlextInfraUtilitiesRopeClassMove",
    "FlextInfraUtilitiesRopeHelpers",
    "FlextInfraUtilitiesRopeInventory",
    "FlextInfraUtilitiesRopeImports",
    "FlextInfraUtilitiesRopeModulePatch",
    "FlextInfraUtilitiesRopeRuntime",
    "FlextInfraUtilitiesRopeSource",
    "FlextInfraUtilitiesRopeStructure",
    "FlextInfraUtilitiesTransformerHeader",
    "FlextInfraUtilitiesDocs",
    "FlextInfraUtilitiesDocsApi",
    "FlextInfraUtilitiesDocsAudit",
    "FlextInfraUtilitiesDocsBuild",
    "FlextInfraUtilitiesDocsContract",
    "FlextInfraUtilitiesDocsFix",
    "FlextInfraUtilitiesDocsGenerate",
    "FlextInfraUtilitiesDocsGithubLinks",
    "FlextInfraUtilitiesDocsRender",
    "FlextInfraUtilitiesDocsScope",
    "FlextInfraUtilitiesDocsValidate",
    "FlextInfraUtilitiesWorkspaceManifest",
    "FlextInfraUtilitiesDependencies",
    "FlextInfraUtilitiesDeferredSelfReferenceRewrite",
    "FlextInfraUtilitiesGit",
    "FlextInfraUtilitiesIteration",
    "FlextInfraUtilitiesLintRecipes",
    "FlextInfraUtilitiesLogParser",
    "FlextInfraUtilitiesManagedConflicts",
    "FlextInfraUtilitiesSemanticCutover",
    "FlextInfraUtilitiesProtectedEdit",
    "FlextInfraUtilitiesRefactor",
    "FlextInfraUtilitiesRefactorCensus",
    "FlextInfraUtilitiesRefactorNamespaceFlext",
    "FlextInfraUtilitiesRefactorNamespaceCommon",
    "FlextInfraUtilitiesRefactorNamespaceMoves",
    "FlextInfraUtilitiesRelease",
    "FlextInfraUtilitiesRepository",
    "FlextInfraUtilitiesVersioning",
    "FlextInfraWorktreeLifecycle",
    "FlextInfraWorktreeProvisioning",
    "FlextInfraUtilitiesWorkspaceFingerprint",
    "FlextInfraUtilitiesCodemodProject",
    "FlextInfraUtilitiesPrivateImportAncestry",
    "FlextInfraUtilitiesPrivateImportFacades",
]


def resolve(name: str) -> type:
    module = importlib.import_module("flext_infra._utilities")
    return getattr(module, name)


def report(name: str, cls: type) -> str:
    return f"  {name}: metaclass={type(cls).__module__}.{type(cls).__name__} bases={[b.__name__ for b in cls.__bases__]}"


def main() -> None:
    print("== Phase 1: import stems one by one ==")
    resolved: dict[str, type] = {}
    for name in STEMS:
        try:
            resolved[name] = resolve(name)
        except Exception:
            print(f"IMPORT FAILED: {name}")
            traceback.print_exc()
            return
        print(report(name, resolved[name]))

    print("\n== Phase 2: incremental composition (same order as utilities.py) ==")
    accumulated: list[str] = [STEMS[0]]
    for name in STEMS[1:]:
        bases = tuple(resolved[n] for n in accumulated)
        try:
            composed = type(f"Infra_{len(accumulated)}", bases, {})
            meta = type(composed)
            print(f"+ {name}: OK (metaclass={meta.__name__})")
            accumulated.append(name)
        except TypeError as exc:
            print(f"\nCONFLICT adding: {name}")
            print(f"  error: {exc}")
            print(f"  deviant stem: {report(name, resolved[name])}")
            print("  accumulated stems' metaclasses:")
            for acc in accumulated:
                print(report(acc, resolved[acc]))
            print("\n== Phase 3: pairwise pin-down for the deviant ==")
            base_cls = resolved[STEMS[0]]
            for acc in accumulated:
                try:
                    type("P", (resolved[acc], resolved[name]), {})
                    print(f"  {acc} + {name}: OK")
                except TypeError:
                    print(f"  {acc} + {name}: CONFLICT  <-- conflicting pair")
            return
    print("\nNo conflict detected in this order?!")


if __name__ == "__main__":
    main()
