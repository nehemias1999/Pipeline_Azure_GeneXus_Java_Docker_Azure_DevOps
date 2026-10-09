#!/usr/bin/env python3
# ==============================================================================
# Description: Suite TDD de REQ-05 security-gates. Verifica que
#   templates/security-scan.yml exponga steps bloqueantes (Gitleaks + Trivy
#   fs/WAR con SARIF + yamllint) y que Deploy_QA/PROD usen environment con
#   approval y condition succeeded(). El fixture de secreto es falso y seguro.
# Author: SDD implementer (REQ-05)
# Usage: python3 -m pytest tests/req05_security_test.py -q
# Env Vars: ninguna.
# Dependencies: python3 + pyyaml (stdlib unittest/shutil/subprocess/tempfile).
# Output / Exit codes: reporte pytest en STDOUT; 0 OK, 1 fallos/errores.
# ==============================================================================
"""Gates de seguridad bloqueantes de REQ-05 (RED->GREEN->REFACTOR)."""

import os
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, "templates", "security-scan.yml")
MAIN = os.path.join(ROOT, "azure-pipelines.yml")
DEPLOY = os.path.join(ROOT, "templates", "deploy.yml")

# Fixture falso y seguro: patron AKIA para que Gitleaks lo detecte por regla
# generica sin ser una credencial real (nunca commitear valores verdaderos).
FAKE_SECRET = "AKIAIOSFODNN7REQ05FAKE00"


def scan_text():
    """Texto crudo del template de escaneo."""
    with open(SCAN, "r", encoding="utf-8") as handle:
        return handle.read()


def scan_code():
    """Texto del template sin comentarios (evita falsos verdes por cabecera)."""
    lines = [line for line in scan_text().splitlines()
             if not line.lstrip().startswith("#")]
    return "\n".join(lines)


class TestReq05Security(unittest.TestCase):
    """Contrato REQ-05: gates bloqueantes + approvals QA/PROD."""

    def test_scan_template_parses_and_keeps_steps_interface(self):
        """El template parsea y sigue exponiendo `steps` sin cambiar nombre."""
        self.assertTrue(os.path.isfile(SCAN), "falta templates/security-scan.yml")
        with open(SCAN, "r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        self.assertIsInstance(doc, dict, "security-scan.yml no es mapping YAML")
        self.assertIn("steps", doc, "el template debe exponer `steps`")
        self.assertGreater(len(doc["steps"]), 0, "steps vacio")

    def test_gitleaks_gate_blocks_secret_without_exposing_value(self):
        """Gitleaks corre en el gate, falla ante secreto y no expone el valor."""
        text = scan_code().lower()
        self.assertIn("gitleaks", text, "falta gate Gitleaks")
        self.assertIn("detect", text, "Gitleaks debe usar `detect`")
        blob = scan_code()
        self.assertIn("--redact", blob, "Gitleaks debe listar sin exponer valor")
        self.assertIn("failOnStderr", blob, "falta failOnStderr: true")
        if shutil.which("gitleaks") is None:
            self.skipTest("gitleaks ausente en agente local: skip explicito")
        with tempfile.TemporaryDirectory() as tmp:
            victim = os.path.join(tmp, "leak.txt")
            with open(victim, "w", encoding="utf-8") as handle:
                handle.write("token = \"%s\"\n" % FAKE_SECRET)
            proc = subprocess.run(
                ["gitleaks", "detect", "--source", tmp, "--verbose",
                 "--redact", "--no-git"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(proc.returncode, 0, "Gitleaks no bloqueo secreto")
            combined = proc.stdout + proc.stderr
            self.assertIn("leak.txt", combined, "Gitleaks no lista el archivo")
            self.assertNotIn(FAKE_SECRET, combined, "valor secreto expuesto")

    def test_trivy_critical_blocks_and_publishes_sarif(self):
        """Trivy fs+WAR con HIGH/CRITICAL bloquea y publica SARIF."""
        text = scan_code()
        low = text.lower()
        self.assertIn("trivy", low, "falta gate Trivy")
        self.assertIn("HIGH,CRITICAL", text, "Trivy debe filtrar HIGH,CRITICAL")
        self.assertIn("sarif", low, "Trivy debe emitir reporte SARIF")
        self.assertIn(".war", low, "Trivy debe escanear el WAR")
        self.assertIn("PublishPipelineArtifact", text, "SARIF sin publicar")
        self.assertIn("failOnStderr", text, "falta failOnStderr: true")
        if shutil.which("trivy") is None:
            self.skipTest("trivy ausente en agente local: skip explicito")

    def test_yamllint_gate(self):
        """yamllint corre sobre pipeline/templates y es bloqueante."""
        import re
        code = scan_code()
        self.assertRegex(code, r"yamllint\s+\S+\.ya?ml",
                         "falta invocacion yamllint sobre YAML")

    def test_prod_waits_approval_after_green(self):
        """Deploy_QA/PROD con environment + condition succeeded()."""
        with open(MAIN, "r", encoding="utf-8") as handle:
            main = yaml.safe_load(handle)
        by_stage = {s.get("stage"): s for s in main.get("stages", [])}
        for name in ("Deploy_QA", "Deploy_PROD"):
            self.assertIn(name, by_stage, "falta stage %s" % name)
            blob = yaml.safe_dump(by_stage[name])
            self.assertIn("environment", blob, "%s sin environment" % name)
            self.assertIn("succeeded()", blob, "%s sin succeeded()" % name)
        with open(DEPLOY, "r", encoding="utf-8") as handle:
            deploy = handle.read()
        self.assertIn("environment:", deploy, "deploy.yml sin environment")

    def test_shell_tasks_fail_closed(self):
        """Tareas shell del gate con failOnStderr para fallo controlado."""
        with open(SCAN, "r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        shells = [s for s in doc.get("steps", [])
                  if isinstance(s, dict) and str(s.get("task", "")).startswith("Bash")]
        self.assertGreater(len(shells), 0, "sin tareas shell en el gate")
        for task in shells:
            inputs = task.get("inputs", {})
            self.assertTrue(
                inputs.get("failOnStderr") in (True, "true"),
                "tarea %s sin failOnStderr" % task.get("displayName"),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
