#!/usr/bin/env python3
"""Tests TDD del REQ-04 hardened-deploy (change hardening-cicd-pipeline).

Description: verifica que el deploy remoto a Docker/Tomcat sea idempotente y
    seguro mediante scripts/deploy-docker-tomcat.ps1 y .sh (fail-fast, SHA
    re-check, scp con StrictHostKeyChecking=yes, backup *.bak-<version>,
    shutdown graceful con pkill solo como fallback tras timeout, startup.sh,
    healthcheck curl --fail con reintentos y restore ante fallo), que
    templates/deploy.yml invoque el script con la version exacta y HealthUrl
    por entorno, y que bat/ quede deprecado por escrito sin ser referenciado.
Usage: python3 -m pytest tests/req04_deploy_test.py -q || python3 tests/req04_deploy_test.py
Env Vars: ninguna.
Dependencies: stdlib (unittest, subprocess).
"""

import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SH = os.path.join(ROOT, "scripts", "deploy-docker-tomcat.sh")
PS1 = os.path.join(ROOT, "scripts", "deploy-docker-tomcat.ps1")
DEPLOY_YML = os.path.join(ROOT, "templates", "deploy.yml")
LEGACY_README = os.path.join(ROOT, "bat", "README.legacy.md")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestScriptsExist(unittest.TestCase):
    """Los scripts portables existen."""

    def test_sh_exists(self) -> None:
        self.assertTrue(os.path.isfile(SH), "falta scripts/deploy-docker-tomcat.sh")

    def test_ps1_exists(self) -> None:
        self.assertTrue(os.path.isfile(PS1), "falta scripts/deploy-docker-tomcat.ps1")


class TestShHardenedDeploy(unittest.TestCase):
    """El script .sh implementa el flujo endurecido."""

    def test_fail_fast_set_euo_pipefail(self) -> None:
        self.assertIn("set -euo pipefail", read(SH))

    def test_usage_sin_params_exit_1(self) -> None:
        proc = subprocess.run(
            ["bash", SH], capture_output=True, text=True, timeout=30
        )
        self.assertEqual(proc.returncode, 1)
        self.assertRegex(proc.stdout + proc.stderr, r"[Uu]sage|uso")

    def test_help_exit_0(self) -> None:
        proc = subprocess.run(
            ["bash", SH, "--help"], capture_output=True, text=True, timeout=30
        )
        self.assertEqual(proc.returncode, 0)
        self.assertRegex(proc.stdout, r"[Uu]sage|uso")

    def test_war_inexistente_falla_antes_de_ssh(self) -> None:
        proc = subprocess.run(
            [
                "bash", SH,
                "--war-path", "/tmp/no-existe-req04.war",
                "--version", "1.0.42",
                "--ssh-target", "nobody@invalid.invalid",
            ],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("scp", proc.stdout + proc.stderr)

    def test_scp_endurecido(self) -> None:
        text = read(SH)
        self.assertIn("scp", text)
        self.assertIn("StrictHostKeyChecking=yes", text)
        self.assertIn("BatchMode=yes", text)
        self.assertIn("ConnectTimeout=10", text)

    def test_sin_ssh_inseguro(self) -> None:
        self.assertNotIn("StrictHostKeyChecking=no", read(SH))

    def test_sha_recheck_local(self) -> None:
        text = read(SH)
        self.assertIn("sha256sum", text)
        self.assertIn(".sha256", text)

    def test_backup_versionado(self) -> None:
        self.assertRegex(read(SH), r"\.bak-")

    def test_docker_cp_y_ciclo_tomcat(self) -> None:
        text = read(SH)
        self.assertIn("docker cp", text)
        self.assertIn("shutdown.sh", text)
        self.assertIn("startup.sh", text)

    def test_pkill_solo_fallback(self) -> None:
        text = read(SH)
        self.assertNotIn("StrictHostKeyChecking=no", text)
        for line in text.splitlines():
            stripped = line.strip()
            if "pkill" in stripped and not stripped.startswith("#"):
                self.assertRegex(
                    stripped,
                    r"(?i)fallback|timeout|if|&&|\|\|",
                    "pkill fuera de fallback/timeout: %s" % stripped,
                )

    def test_healthcheck_con_reintentos_y_restore(self) -> None:
        text = read(SH)
        self.assertIn("curl", text)
        self.assertIn("--fail", text)
        self.assertRegex(text, r"[Rr]etry|[Rr]intento|for \(|for .* in|until|while")
        self.assertRegex(text, r"[Rr]estor|rollback")

    def test_usa_ssh_docker_curl_reales(self) -> None:
        text = read(SH)
        self.assertIn("ssh ", text)
        self.assertIn("docker", text)
        self.assertIn("curl", text)

    def test_cabecera_code_doc_standard(self) -> None:
        text = read(SH)
        self.assertRegex(text, r"Description:")
        self.assertRegex(text, r"Usage:")
        self.assertRegex(text, r"[Ee]xit")


class TestPs1HardenedDeploy(unittest.TestCase):
    """El script .ps1 implementa el mismo flujo endurecido."""

    def test_fail_fast_error_action(self) -> None:
        self.assertIn("ErrorActionPreference", read(PS1))

    def test_params_requeridos(self) -> None:
        text = read(PS1)
        self.assertIn("WarPath", text)
        self.assertIn("Version", text)
        self.assertIn("SshTarget", text)
        self.assertIn("HealthUrl", text)

    def test_defaults_documentados(self) -> None:
        text = read(PS1)
        self.assertIn("tomcat", text)
        self.assertIn("/usr/local/tomcat/webapps", text)
        self.assertIn("120", text)

    def test_scp_endurecido(self) -> None:
        text = read(PS1)
        self.assertIn("StrictHostKeyChecking=yes", text)
        self.assertIn("BatchMode=yes", text)

    def test_sin_ssh_inseguro_ni_pkill_incondicional(self) -> None:
        text = read(PS1)
        self.assertNotIn("StrictHostKeyChecking=no", text)
        bad = [
            line for line in text.splitlines()
            if "pkill -9" in line
            and not re.search(r"(?i)fallback|timeout|if", line)
        ]
        self.assertEqual(bad, [])

    def test_backup_healthcheck_restore(self) -> None:
        text = read(PS1)
        self.assertRegex(text, r"\.bak-")
        self.assertIn("--fail", text)
        self.assertRegex(text, r"[Rr]estor|rollback")
        self.assertIn("shutdown.sh", text)
        self.assertIn("startup.sh", text)

    def test_cabecera_code_doc_standard(self) -> None:
        text = read(PS1)
        self.assertRegex(text, r"Description:")
        self.assertRegex(text, r"Usage:")
        self.assertRegex(text, r"[Ee]xit")


class TestTemplateInvocaScript(unittest.TestCase):
    """templates/deploy.yml invoca el script con la version exacta."""

    def test_invoca_script(self) -> None:
        text = read(DEPLOY_YML)
        self.assertIn("deploy-docker-tomcat", text)

    def test_cubre_linux_y_windows(self) -> None:
        text = read(DEPLOY_YML)
        self.assertIn("deploy-docker-tomcat.sh", text)
        self.assertIn("deploy-docker-tomcat.ps1", text)
        self.assertIn("pwsh", text)

    def test_version_exacta(self) -> None:
        text = read(DEPLOY_YML)
        self.assertRegex(text, r"parameters\.version")

    def test_healthurl_por_entorno(self) -> None:
        text = read(DEPLOY_YML)
        self.assertRegex(text, r"[Hh]ealth[Uu]rl")
        self.assertRegex(text, r"healthUrl_")

    def test_interfaz_intacta(self) -> None:
        text = read(DEPLOY_YML)
        for param in ("environment", "version", "artifactFeed", "sshTarget"):
            self.assertIn(param, text)

    def test_no_referencia_bat_ni_ssh_inseguro(self) -> None:
        text = read(DEPLOY_YML)
        self.assertNotIn("bat/", text)
        self.assertNotIn("StrictHostKeyChecking=no", text)


class TestLegacyDeprecado(unittest.TestCase):
    """bat/ queda deprecado por escrito."""

    def test_readme_legacy(self) -> None:
        text = read(LEGACY_README)
        self.assertRegex(text, r"(?i)depreca")
        self.assertIn("scripts/", text)
        self.assertRegex(text, r"(?i)PAT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
