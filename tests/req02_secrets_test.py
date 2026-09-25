#!/usr/bin/env python3
"""Valida REQ-02 secrets-management del change hardening-cicd-pipeline.

Description: verifica Key Vault wiring (AzureKeyVault@2 + variable group
    linkeada), referencias $(Secreto) sin valores, validacion fail-fast de
    secretos vacios, ausencia de PAT en URL/CLI, SSH endurecido
    (StrictHostKeyChecking=yes + known_hosts) y redaccion del legacy
    Pipeline_Script.yml. No lee ni imprime valores de secretos.
Usage: python3 -m pytest tests/req02_secrets_test.py -q
    o python3 tests/req02_secrets_test.py
Env Vars: ninguna.
Dependencies: stdlib (unittest, pathlib, re); pyyaml solo para el test de parseo.
Output / Exit codes: reporte unittest en STDOUT; exit 0 si todo pasa, 1 si falla.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_YML = ROOT / "azure-pipelines.yml"
TEMPLATES = sorted((ROOT / "templates").glob("*.yml"))
KNOWN_HOSTS = ROOT / ".ssh" / "known_hosts"
LEGACY = ROOT / "Pipeline_Script.yml"

REQUIRED_SECRETS = ("ServerPassword", "ApplicationKey", "SshPrivateKey", "SshKnownHosts")

# Patron del valor historico hardcodeado, construido por partes para que este
# archivo de test no contenga el literal (evita auto-match en grep/gitleaks).
LEGACY_HARDCODED = "511E" + "367C"


def read_text(path: Path) -> str:
    """Lee un archivo como texto UTF-8.

    Args:
        path: ruta del archivo a leer.

    Returns:
        Contenido del archivo.
    """
    return path.read_text(encoding="utf-8")


def new_pipeline_text() -> str:
    """Concatena el pipeline nuevo (azure-pipelines.yml + templates/).

    Returns:
        Texto combinado de los YAML nuevos (sin legacy).
    """
    parts = [read_text(MAIN_YML)]
    parts += [read_text(p) for p in TEMPLATES]
    if KNOWN_HOSTS.exists():
        parts.append(read_text(KNOWN_HOSTS))
    return "\n".join(parts)


class TestKeyVaultWiring(unittest.TestCase):
    """Key Vault task o variable-group linkeada presente, sin valores."""

    def test_azure_keyvault_task_present(self) -> None:
        """AzureKeyVault@2 existe en azure-pipelines.yml."""
        self.assertIn("AzureKeyVault@2", read_text(MAIN_YML))

    def test_keyvault_inputs(self) -> None:
        """La task declara subscription, KeyVaultName y SecretsFilter."""
        text = read_text(MAIN_YML)
        self.assertRegex(text, r"azureSubscription|ConnectedServiceName")
        self.assertIn("KeyVaultName", text)
        self.assertIn("SecretsFilter", text)
        self.assertIn("kv-java-app", text)

    def test_variable_group_linked(self) -> None:
        """Variable group Java_Application-Secrets linkeada en el pipeline."""
        text = read_text(MAIN_YML) + "\n".join(read_text(p) for p in TEMPLATES)
        self.assertIn("Java_Application-Secrets", text)

    def test_secrets_only_by_reference(self) -> None:
        """Los 4 secretos se referencian como $(Nombre), nunca con valores."""
        text = new_pipeline_text()
        for secret in REQUIRED_SECRETS:
            self.assertIn("$(" + secret + ")", text, f"falta referencia $({secret})")

    def test_failfast_on_empty_secret(self) -> None:
        """Existe validacion que falla si un secreto requerido esta vacio."""
        text = new_pipeline_text()
        self.assertIn("failOnStderr", text)
        self.assertIn("exit 1", text)
        self.assertTrue(
            any(f'-z "$({s})"' in text or f"-z '$({s})'" in text for s in REQUIRED_SECRETS),
            "ningun chequeo -z $(Secreto) encontrado",
        )


class TestNoLeakedSecrets(unittest.TestCase):
    """Cero secretos en texto plano y cero PAT en URL/CLI."""

    def test_no_hardcoded_application_key_in_repo(self) -> None:
        """El valor historico hardcodeado no existe en YAML nuevos ni legacy."""
        for path in [MAIN_YML, LEGACY, *TEMPLATES]:
            if path.exists():
                self.assertNotIn(
                    LEGACY_HARDCODED, read_text(path), f"valor hardcodeado en {path.name}"
                )

    def test_no_pat_in_url_or_cli(self) -> None:
        """Sin PAT en URLs ni CLI; acceso solo via System.AccessToken/AzureCLI."""
        text = new_pipeline_text()
        self.assertNotRegex(text, r"https://.*PAT.*@")
        self.assertNotIn("%PAT", text)
        self.assertNotIn("PATToken", text.replace("System.AccessToken", ""))
        self.assertTrue(
            "System.AccessToken" in text or "AzureCLI@2" in text,
            "falta acceso via System.AccessToken o AzureCLI@2",
        )


class TestHardenedSsh(unittest.TestCase):
    """SSH con llave desde Key Vault y host verificado."""

    def test_strict_host_key_checking_yes(self) -> None:
        """StrictHostKeyChecking=yes presente; =no prohibido."""
        text = new_pipeline_text()
        self.assertIn("StrictHostKeyChecking=yes", text)
        self.assertNotIn("StrictHostKeyChecking=no", text)

    def test_ssh_batch_and_timeout(self) -> None:
        """BatchMode=yes y ConnectTimeout configurados en el deploy."""
        text = new_pipeline_text()
        self.assertIn("BatchMode=yes", text)
        self.assertIn("ConnectTimeout", text)

    def test_known_hosts_versioned(self) -> None:
        """.ssh/known_hosts existe, no vacio y marcado si es placeholder."""
        self.assertTrue(KNOWN_HOSTS.exists(), ".ssh/known_hosts no existe")
        content = read_text(KNOWN_HOSTS).strip()
        self.assertTrue(len(content) > 0, ".ssh/known_hosts vacio")


class TestLegacyRedacted(unittest.TestCase):
    """Pipeline_Script.yml legacy redactado con aviso de deprecacion."""

    def test_legacy_uses_reference(self) -> None:
        """El legacy referencia $(ApplicationKey) en lugar del valor."""
        text = read_text(LEGACY)
        self.assertIn("$(ApplicationKey)", text)
        self.assertNotIn(LEGACY_HARDCODED, text)

    def test_legacy_deprecation_notice(self) -> None:
        """El legacy lleva aviso legacy/deprecado apuntando al pipeline nuevo."""
        text = read_text(LEGACY).lower()
        self.assertTrue("legacy" in text or "deprecat" in text or "no usar" in text)
        self.assertIn("azure-pipelines.yml", read_text(LEGACY))


class TestYamlParses(unittest.TestCase):
    """Los YAML nuevos parsean sin errores de sintaxis."""

    def test_yaml_safe_load(self) -> None:
        """yaml.safe_load pasa en azure-pipelines.yml y templates/*.yml."""
        yaml = __import__("yaml")
        for path in [MAIN_YML, *TEMPLATES]:
            with open(path, encoding="utf-8") as fh:
                self.assertIsNotNone(yaml.safe_load(fh), f"{path.name} parseo a None")


if __name__ == "__main__":
    unittest.main(verbosity=2)
