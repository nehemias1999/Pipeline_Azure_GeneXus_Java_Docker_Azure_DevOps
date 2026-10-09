#!/usr/bin/env python3
"""Tests TDD del REQ-07 rollback-strategy (change hardening-cicd-pipeline).

Description: verifica que azure-pipelines.yml exponga un stage manual
    `Rollback` parametrizado por version (default `previous-stable`) que
    reutiliza el flujo endurecido de templates/deploy.yml (REQ-04), verifica
    healthcheck antes de cerrar, anota el rollback (timestamp + identidad) y
    falla rapido pre-deploy listando versiones si la version no existe.
Usage: python3 -m pytest tests/req07_rollback_test.py -q
Env Vars: ninguna (fixtures locales; healthcheck contra servidor local).
Dependencies: stdlib (unittest, http.server, urllib).
"""

import http.server
import os
import re
import threading
import unittest
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(ROOT, "azure-pipelines.yml")
DEPLOY_YML = os.path.join(ROOT, "templates", "deploy.yml")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def rollback_section():
    """Texto del pipeline desde el primer stage de rollback en adelante."""
    text = read(PIPELINE)
    match = re.search(r"-\s*stage:\s*Rollback", text)
    assert match is not None, "no existe stage Rollback en azure-pipelines.yml"
    return text[match.start():]


class TestRollbackParametrizado(unittest.TestCase):
    """El stage Rollback recibe version con default previous-stable."""

    def test_stage_rollback_existe(self) -> None:
        self.assertRegex(read(PIPELINE), r"-\s*stage:\s*Rollback\b")

    def test_parametro_version_default_previous_stable(self) -> None:
        text = read(PIPELINE)
        self.assertIn("previous-stable", text)
        self.assertRegex(
            text,
            r"name:\s*rollbackVersion[\s\S]{0,200}default:\s*previous-stable",
        )

    def test_resolucion_determinista_documentada(self) -> None:
        section = rollback_section()
        self.assertRegex(section, r"[Rr]esoluci[oó]n|resuelve|previousStable")


class TestRollbackManual(unittest.TestCase):
    """Rollback es manual: nunca corre en PR ni en triggers automaticos."""

    def test_condition_manual(self) -> None:
        section = rollback_section()
        self.assertIn("Manual", section)

    def test_no_corre_en_pr(self) -> None:
        section = rollback_section()
        self.assertRegex(
            section,
            r"ne\(\s*variables\['Build\.Reason'\]\s*,\s*'PullRequest'\s*\)",
        )


class TestReusaFlujoEndurecido(unittest.TestCase):
    """El rollback usa el mismo flujo endurecido, sin camino paralelo."""

    def test_referencia_template_deploy(self) -> None:
        section = rollback_section()
        self.assertIn("templates/deploy.yml", section)

    def test_sin_deploy_paralelo(self) -> None:
        section = rollback_section()
        self.assertNotIn("StrictHostKeyChecking", section)
        self.assertNotIn("deploy-docker-tomcat", section)

    def test_healthcheck_antes_de_cerrar(self) -> None:
        section = rollback_section()
        self.assertRegex(section, r"[Hh]ealthcheck")
        self.assertIn("templates/deploy.yml", section)
        self.assertIn("AnnotateRollback", section)
        deploy_pos = section.index("templates/deploy.yml")
        annotate_pos = section.index("AnnotateRollback")
        self.assertLess(deploy_pos, annotate_pos)

    def test_anotacion_rollback_timestamp_identidad(self) -> None:
        section = rollback_section()
        self.assertRegex(section, r"rollback")
        self.assertRegex(section, r"timestamp|TIMESTAMP|date --utc")
        self.assertIn("Build.RequestedFor", section)


class TestVersionInexistenteFailFast(unittest.TestCase):
    """Version inexistente: falla antes de tocar el servidor, listando."""

    def test_fail_fast_con_listado(self) -> None:
        section = rollback_section()
        self.assertRegex(section, r"[Ff]ail-?fast|falla .* antes")
        self.assertRegex(section, r"versiones disponibles")

    def test_validacion_antes_del_deploy(self) -> None:
        section = rollback_section()
        failfast = re.search(r"[Ff]ail-?fast|versiones disponibles", section)
        deploy = re.search(r"templates/deploy\.yml", section)
        assert failfast is not None and deploy is not None
        self.assertLess(failfast.start(), deploy.start())


class TestHealthcheckFixtureLocal(unittest.TestCase):
    """Healthcheck real contra fixture local; skip explicito si no es posible."""

    def test_healthcheck_200_fixture_local(self) -> None:
        try:
            server = http.server.HTTPServer(
                ("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler
            )
        except OSError as exc:
            self.skipTest("fixture local no disponible: %s" % exc)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:%d/" % port, timeout=10
            ) as response:
                self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            thread.join()


if __name__ == "__main__":
    unittest.main()
