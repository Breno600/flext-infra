"""Tests that the custom-handler policy is declared per Make profile.

``custom_handler_policy`` was a single flat rule applied to every profile, but
the profiles have genuinely different contracts:

* a standalone repository may only define private
  ``_custom_<verb>_<what>`` handlers and hooks;
* a workspace *root* orchestrates the members, so its ``custom.mk`` legitimately
  owns public orchestration targets and the variables they read.

Applying the member rule to the root made ``codegen conform`` reject the root's
own surface on every run and block the whole transaction -- which is why no
other generated artifact could be landed.

The policy is therefore keyed by profile, and the engine selects the entry for
the profile it is conforming instead of assuming one shape fits every project.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping

from flext_tests import tm

from flext_infra import c, config, m
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import t


class TestsFlextInfraCustomHandlerPolicyIsProfileAware:
    def test_every_declared_profile_has_a_custom_handler_policy(self) -> None:
        """Each Make profile declares the contract for its own custom surface."""
        codegen_profiles: t.VariadicTuple[m.Infra.ProfileSpec] = (
            config.Infra.codegen.profiles
        )
        declared = frozenset(
            c.Infra.MakeProfile(profile.name) for profile in codegen_profiles
        )
        handler_policies: Mapping[str, m.Infra.CustomHandlerPolicy] = (
            config.Infra.codegen.make.custom_handler_policies
        )
        covered = frozenset(
            c.Infra.MakeProfile(profile) for profile in handler_policies
        )

        tm.that(declared - covered, eq=frozenset())

    def test_repository_root_may_own_public_orchestration_targets(self) -> None:
        """The root profile permits the public targets it actually ships."""
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.WORKSPACE
            ]
        )

        tm.that(policy.allow_public_targets, eq=True)

    def test_standalone_stays_private_only(self) -> None:
        """A standalone custom surface may only define private handlers."""
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )

        tm.that(policy.allow_public_targets, eq=False)

    def test_validator_honours_the_permissions_it_is_given(self) -> None:
        """A permissive policy accepts what a strict one rejects.

        The ``allow_*`` flags were declarative only: the validator read just
        ``target_pattern``, so a repository root's own public targets and
        variables were rejected no matter what the config permitted.
        """
        content = "WORKSPACE_BASE ?= 0.12.0-dev\ndone-check:\n\t@echo hi\n"
        strict: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )
        permissive: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.WORKSPACE
            ]
        )
        validate = FlextInfraCodegenConform.validate_custom_make

        tm.that(validate(content, strict).failure, eq=True)
        tm.that(validate(content, permissive).success, eq=True)

    def test_policy_keys_are_normalised_to_profile_values(self) -> None:
        """Lookup succeeds for both a raw string and its StrEnum member.

        ``MakeProfile`` is a ``StrEnum``, so a key declared in YAML and the same
        profile passed as an enum member must resolve to ONE entry. If the two
        forms produced separate keys, a lookup would silently miss and fall back
        to the strict base policy -- exactly the failure that made conform
        reject the repository root's own custom surface.
        """
        policies: t.MutableMappingKV[str, m.Infra.CustomHandlerPolicy] = dict(
            config.Infra.codegen.make.custom_handler_policies
        )
        profile: c.Infra.MakeProfile = c.Infra.MakeProfile.WORKSPACE

        tm.that(set(policies), eq={member.value for member in c.Infra.MakeProfile})
        tm.that(policies[profile] is policies[profile.value], eq=True)
