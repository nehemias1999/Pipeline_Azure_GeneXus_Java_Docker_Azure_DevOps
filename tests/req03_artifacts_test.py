#!/usr/bin/env python3
"""Tests TDD del REQ-03 artifact-versioning (change hardening-cicd-pipeline).

Description: verifica que el build publique el WAR como Universal Package
    versionado con SHA256 + SBOM CycloneDX + tag Git v<version>, que el deploy
    descargue la version exacta y falle ante SHA mismatch, y que ningun .war
    quede trackeado en Git ni exista `latest` implicito.
Usage: python3 -m pytest tests/req03_artifacts_test.py -q || python3 tests/req03_artifacts_test.py
Env Vars: ninguna.
Dependencies: stdlib (unittest, yaml si esta instalado; si no, solo chequeos de texto).
"""

import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_YML = os.path.join(ROOT, "templates", "build.yml")
DEPLOY_YML = os.path.join(ROOT, "templates", "deploy.yml")
PIPELINE_YML = os.path.join(ROOT, "azure-pipelines.yml")
GITIGNORE = os.path.join(ROOT, ".gitignore")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestBuildPublishesVersionedArtifact(unittest.TestCase):
    """El build publica Universal Package versionado con integridad."""

    def test_publish_universal_package_exact_version(self) -> None:
        """build.yml publica Universal Package con version exacta."""
        text = read(BUILD_YML)
        self.assertIn("UniversalPackages@0", text)
        self.assertIn("command: publish", text)
        self.assertIn("java-application-dev", text)
        self.assertIn("versionOption: custom", text)
        self.assertRegex(text, r"versionPublish:.*parameters\.version")

    def test_publish_uses_configured_feed(self) -> None:
        """build.yml publica en el feed configurado, sin feed hardcodeado."""
        text = read(BUILD_YML)
        self.assertRegex(text, r"vstsFeedPublish:.*artifactFeed")
        self.assertNotIn("mygatsbysite", text)

    def test_sha256_generated(self) -> None:
        """build.yml genera el .sha256 del WAR."""
        text = read(BUILD_YML)
        self.assertIn("sha256sum", text)
        self.assertIn(".sha256", text)

    def test_sbom_cyclonedx(self) -> None:
        """build.yml genera SBOM CycloneDX (syft o manifest documentado)."""
        text = read(BUILD_YML)
        self.assertIn("sbom.cyclonedx.json", text)
        self.assertIn("cyclonedx", text.lower())

    def test_git_tag_with_access_token(self) -> None:
        """build.yml crea el tag v<version> con System.AccessToken, sin PAT."""
        text = read(BUILD_YML)
        self.assertRegex(text, r"git tag.*v\$\(appVersion\)|git tag.*parameters\.version")
        self.assertIn("System.AccessToken", text)
        self.assertNotIn("PATToken", text)

    def test_war_gate_fails_on_tracked_war(self) -> None:
        """build.yml falla si hay WAR trackeados en Git."""
        text = read(BUILD_YML)
        self.assertIn('git ls-files "*.war"', text)


class TestDeployVerifiesIntegrity(unittest.TestCase):
    """El deploy descarga la version exacta y verifica SHA antes de copiar."""

    def test_download_exact_version(self) -> None:
        """deploy.yml descarga por version exacta, nunca latest."""
        text = read(DEPLOY_YML)
        self.assertIn("UniversalPackages@0", text)
        self.assertIn("command: download", text)
        self.assertIn("java-application-dev", text)
        self.assertRegex(text, r"vstsPackageVersion:.*parameters\.version")

    def test_sha_verification_fails_on_mismatch(self) -> None:
        """deploy.yml verifica con sha256sum -c y falla ante mismatch."""
        text = read(DEPLOY_YML)
        self.assertIn("sha256sum -c", text)

    def test_no_implicit_latest(self) -> None:
        """deploy.yml no resuelve latest como version."""
        text = read(DEPLOY_YML)
        self.assertIsNone(
            re.search(r"version.*latest|latest.*version", text, re.IGNORECASE),
            "version latest implicita prohibida",
        )
        self.assertNotIn("vstsPackageVersion: '*'", text)
        self.assertNotIn('vstsPackageVersion: "*"', text)


class TestBinariesOutOfGit(unittest.TestCase):
    """Ningun .war queda en Git; el pipeline lo prohibe."""

    def test_gitignore_excludes_war(self) -> None:
        """.gitignore excluye *.war."""
        text = read(GITIGNORE)
        self.assertIn("*.war", text)

    def test_no_war_tracked(self) -> None:
        """git ls-files no reporta WAR trackeados."""
        proc = subprocess.run(
            ["git", "ls-files", "*.war"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.stdout.strip(), "")


class TestPipelineWiring(unittest.TestCase):
    """azure-pipelines.yml cablea feed/version y conserva trazabilidad."""

    def test_feed_and_version_wired(self) -> None:
        """El pipeline define artifactFeed/appVersion y los pasa a templates."""
        text = read(PIPELINE_YML)
        self.assertIn("artifactFeed", text)
        self.assertIn("java-app-artifacts", text)
        self.assertIn("appVersion", text)
        self.assertRegex(text, r"version: \$\(appVersion\)")
        self.assertRegex(text, r"artifactFeed: \$\(artifactFeed\)")

    def test_checkout_keeps_persisted_credentials(self) -> None:
        """El checkout conserva persistCredentials para el push del tag."""
        text = read(PIPELINE_YML)
        self.assertIn("persistCredentials: true", text)

    def test_yaml_parses(self) -> None:
        """Los tres YAML parsean sin error."""
        try:
            import yaml
        except ImportError:
            self.skipTest("pyyaml no instalado")
        for path in (BUILD_YML, DEPLOY_YML, PIPELINE_YML):
            with open(path, encoding="utf-8") as handle:
                self.assertIsNotNone(yaml.safe_load(handle), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
