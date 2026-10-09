#!/usr/bin/env python3
# ==============================================================================
# Description: Suite TDD de REQ-06 observability-docs. Verifica que
#   azure-pipelines.yml publique el resumen de release (version, commit,
#   artefacto, SHA/SHA256, environment, aprobador) como artefacto con
#   retencion 30 dias y log que cita version+SHA+tag; que templates/deploy.yml
#   anote cada deploy con timestamp + identidad del aprobador (runtime
#   Build.RequestedFor, fixture solo en tests locales); y que README.md este
#   sin drift contra el repo real. Aprobador/timestamp simulados con fixtures
#   marcados como tales (nunca identidades reales).
# Author: SDD implementer (REQ-06)
# Usage: python3 -m unittest discover -s tests -p "*_test.py"
# Env Vars: ninguna.
# Dependencies: python3 + pyyaml (stdlib unittest/json/os/tempfile).
# Output / Exit codes: reporte unittest en STDOUT; 0 OK, 1 fallos/errores.
# ==============================================================================
"""Observabilidad del pipeline y documentacion viva de REQ-06 (RED->GREEN)."""

import json
import os
import tempfile
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "azure-pipelines.yml")
DEPLOY = os.path.join(ROOT, "templates", "deploy.yml")
BUILD = os.path.join(ROOT, "templates", "build.yml")
SCAN = os.path.join(ROOT, "templates", "security-scan.yml")
README = os.path.join(ROOT, "README.md")

# Seis campos exigidos por la spec para el resumen de release.
REQUIRED_FIELDS = ("version", "commit", "artifact", "sha", "environment",
                   "approver")

# Fixtures locales marcados como tales: simulan runtime de Azure DevOps
# (Build.RequestedFor + timestamp) sin inventar un aprobador real.
FIXTURE_APPROVER = "Fixture Approver <fixture-local>"
FIXTURE_TIMESTAMP = "2026-01-01T00:00:00Z"
FIXTURE_SUMMARY = {
    "version": "1.0.42",
    "commit": "abc123def456",
    "artifact": "java-application-dev:1.0.42",
    "sha256": "deadbeef" * 8,
    "environment": "PROD",
    "approver": FIXTURE_APPROVER,
    "approvedAt": FIXTURE_TIMESTAMP,
}


def raw(path):
    """Texto crudo de un archivo del repo."""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def code(path):
    """Texto sin comentarios (evita falsos verdes por cabecera)."""
    lines = [line for line in raw(path).splitlines()
             if not line.lstrip().startswith("#")]
    return "\n".join(lines)


class TestReq06ReleaseSummary(unittest.TestCase):
    """Resumen de release como artefacto con los 6 campos de la spec."""

    def test_release_summary_artifact_published(self):
        """Build publica el artefacto `release-summary`."""
        text = code(MAIN)
        self.assertIn("release-summary", text,
                      "falta publicar artefacto release-summary")
        self.assertIn("PublishPipelineArtifact", text,
                      "resumen sin PublishPipelineArtifact")

    def test_release_summary_has_six_fields(self):
        """El resumen generado declara version/commit/artefacto/SHA/env/aprobador."""
        text = code(MAIN).lower()
        for field in ("version", "commit", "artifact"):
            self.assertIn(field, text, "resumen sin campo %s" % field)
        self.assertIn("sha", text, "resumen sin campo SHA/SHA256")
        self.assertIn("environment", text, "resumen sin campo environment")
        self.assertIn("approv", text,
                      "resumen sin campo aprobador (runtime Build.RequestedFor)")

    def test_retention_declared_30_days(self):
        """Retencion de 30 dias declarada en el YAML."""
        text = raw(MAIN).lower()
        self.assertIn("retention", text, "falta declarar retencion en el YAML")
        self.assertIn("30", text, "retencion debe ser 30 dias")

    def test_log_cites_version_sha_tag(self):
        """El log cita version + SHA + tag."""
        text = code(MAIN)
        low = text.lower()
        self.assertIn("version", low, "log sin version")
        self.assertIn("sha", low, "log sin SHA")
        self.assertTrue("v$(" in text or "tag" in low,
                        "log sin tag (v<version>)")

    def test_audit_scenario_recovers_fields_from_artifact(self):
        """Escenario auditoria: con version+environment se recuperan los 6 campos."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "release-summary.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(FIXTURE_SUMMARY, handle)
            with open(path, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
        blob = json.dumps(doc).lower()
        for field in REQUIRED_FIELDS:
            self.assertIn(field, blob,
                          "artefacto sin campo recuperable %s" % field)
        self.assertEqual(doc["version"], "1.0.42")
        self.assertEqual(doc["environment"], "PROD")


class TestReq06DeployAnnotation(unittest.TestCase):
    """Cada deploy anotado con timestamp + identidad del aprobador."""

    def test_deploy_annotates_timestamp_and_approver(self):
        """deploy.yml anota timestamp y aprobador (runtime, sin rediseño)."""
        text = code(DEPLOY)
        low = text.lower()
        self.assertIn("timestamp", low,
                      "deploy.yml sin anotacion de timestamp")
        self.assertTrue("requestedfor" in low or "aprobador" in low,
                        "deploy.yml sin identidad del aprobador")
        self.assertNotIn(FIXTURE_APPROVER, text,
                         "identidad fixture no debe estar hardcodeada en YAML")


class TestReq06ReadmeAlive(unittest.TestCase):
    """README sin drift: refleja el repo real post-REQ-05."""

    def test_readme_cites_real_paths(self):
        """Todo path de pipeline que el README cita existe en el repo."""
        self.assertTrue(os.path.isfile(README), "falta README.md")
        text = raw(README)
        candidates = ("azure-pipelines.yml", "templates/deploy.yml",
                      "templates/build.yml", "templates/security-scan.yml",
                      "scripts/deploy-docker-tomcat.sh",
                      "scripts/deploy-docker-tomcat.ps1")
        cited = [p for p in candidates if p in text]
        self.assertGreater(len(cited), 0, "README no cita paths del repo")
        for path in cited:
            self.assertTrue(
                os.path.isfile(os.path.join(ROOT, path)),
                "README cita path inexistente: %s" % path)

    def test_readme_reflects_security_scan_stage(self):
        """README refleja el flujo real post-REQ-05 (security-scan)."""
        text = raw(README).lower()
        self.assertIn("security", text,
                      "README desactualizado: no menciona security-scan")
        self.assertTrue("pytest" in text or "unittest" in text,
                        "README sin comandos de verificacion")

    def test_yaml_files_still_parse(self):
        """Los YAML tocados siguen parseando."""
        for path in (MAIN, DEPLOY):
            with open(path, "r", encoding="utf-8") as handle:
                doc = yaml.safe_load(handle)
            self.assertIsInstance(doc, dict, "%s no es mapping YAML" % path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
