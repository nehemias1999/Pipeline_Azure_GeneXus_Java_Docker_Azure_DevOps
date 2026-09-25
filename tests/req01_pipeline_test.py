#!/usr/bin/env python3
# ==============================================================================
# Description: Test de validacion TDD para REQ-01 pipeline-core-multistage.
#   Verifica que azure-pipelines.yml + templates/ cumplan el contrato de
#   interfaz (stages, environments, triggers, timeouts, sin secretos).
# Author: SDD implementer (REQ-01)
# Usage: python3 tests/req01_pipeline_test.py  (o: python3 -m unittest
#   tests.req01_pipeline_test -v). Exit 0 si todo pasa, !=0 si algo falla.
# Env Vars: ninguna.
# Dependencies: python3 + pyyaml (stdlib unittest, sin pytest).
# Output / Exit codes: resumen unittest en STDOUT; 0 OK, 1 fallos/errores.
# ==============================================================================
"""Validacion del pipeline multi-stage de REQ-01 (RED->GREEN->REFACTOR)."""

import glob
import os
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "azure-pipelines.yml")
TEMPLATES = sorted(glob.glob(os.path.join(ROOT, "templates", "*.yml")))
REQUIRED_TEMPLATES = {"build.yml", "deploy.yml", "security-scan.yml"}
REQUIRED_STAGES = {"Build", "Deploy_DEV", "Deploy_QA", "Deploy_PROD"}
FORBIDDEN = ["511E367C", "10.200.200.200", "SetAndCreateFinalWARFile"]


def load_all():
    """Carga el pipeline principal y todos los templates como YAML."""
    docs = {}
    for path in [MAIN] + TEMPLATES:
        with open(path, "r", encoding="utf-8") as handle:
            docs[path] = yaml.safe_load(handle)
    return docs


def walk(node):
    """Itera recursivamente sobre dicts/listas de un documento YAML."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def raw_text():
    """Texto crudo de todos los YAML para busqueda de secretos/IP."""
    texts = {}
    for path in [MAIN] + TEMPLATES:
        with open(path, "r", encoding="utf-8") as handle:
            texts[path] = handle.read()
    return texts


def code_text():
    """Texto YAML sin comentarios (el stage fantasma se menciona solo en
    comentarios explicativos, nunca como dependsOn real)."""
    code = {}
    for path, text in raw_text().items():
        lines = [
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        ]
        code[path] = "\n".join(lines)
    return code


class TestReq01Pipeline(unittest.TestCase):
    """Contrato REQ-01: azure-pipelines.yml + templates/build,deploy,..."""

    def test_files_exist_and_parse(self):
        """Existen los 4 YAML y parsean sin errores."""
        self.assertTrue(os.path.isfile(MAIN), "falta azure-pipelines.yml")
        names = {os.path.basename(p) for p in TEMPLATES}
        self.assertTrue(
            REQUIRED_TEMPLATES.issubset(names),
            f"faltan templates: {REQUIRED_TEMPLATES - names}",
        )
        docs = load_all()  # lanza si hay error de parseo
        for path, doc in docs.items():
            self.assertIsInstance(doc, dict, f"{path} no es un mapping YAML")

    def test_no_dangling_depends_on(self):
        """Ningun stage/job depende de un stage inexistente."""
        main = load_all()[MAIN]
        stages = main.get("stages", [])
        names = {
            s.get("stage") for s in stages if isinstance(s, dict) and "stage" in s
        }
        self.assertTrue(
            REQUIRED_STAGES.issubset(names),
            f"stages faltantes: {REQUIRED_STAGES - names}",
        )
        for stage in stages:
            depends = stage.get("dependsOn", [])
            if isinstance(depends, str):
                depends = [depends]
            for dep in depends or []:
                self.assertIn(
                    dep, names, f"dependsOn fantasma: {dep} en {stage.get('stage')}"
                )
        for path, text in code_text().items():
            for token in FORBIDDEN:
                self.assertNotIn(token, text, f"{token} en {path}")

    def test_no_hardcoded_secrets_or_ip(self):
        """Sin ApplicationKey ni IP del host legacy en el pipeline nuevo."""
        for path, text in raw_text().items():
            self.assertNotIn("511E367C", text, f"secreto hardcodeado en {path}")
            self.assertNotIn("10.200.200.200", text, f"IP hardcodeada en {path}")

    def test_stages_and_environments(self):
        """Build/DEV/QA/PROD existen; QA/PROD usan environment con approval."""
        main = load_all()[MAIN]
        by_stage = {s.get("stage"): s for s in main.get("stages", [])}
        for name in REQUIRED_STAGES:
            self.assertIn(name, by_stage, f"falta stage {name}")
        blob = yaml.safe_dump(main)
        self.assertIn("QA", blob)
        self.assertIn("PROD", blob)
        for name in ("Deploy_QA", "Deploy_PROD"):
            stage_blob = yaml.safe_dump(by_stage[name])
            self.assertIn(
                "environment", stage_blob, f"{name} sin environment (approval)"
            )
            self.assertIn(
                "succeeded()", stage_blob, f"{name} sin condition succeeded()"
            )

    def test_triggers_main_and_pr(self):
        """Trigger push a main + validacion PR contra main."""
        main = load_all()[MAIN]
        trigger = yaml.safe_dump(main.get("trigger", {}))
        pr = yaml.safe_dump(main.get("pr", {}))
        self.assertIn("main", trigger, "trigger sin rama main")
        self.assertIn("main", pr, "pr sin rama main")

    def test_timeouts_and_fail_on_stderr(self):
        """Todo job con timeout; tareas shell con failOnStderr: true."""
        docs = load_all()
        jobs = [
            n
            for doc in docs.values()
            for n in walk(doc)
            if isinstance(n, dict) and ("job" in n or "deployment" in n)
        ]
        self.assertGreater(len(jobs), 0, "no se encontraron jobs")
        for job in jobs:
            name = job.get("job") or job.get("deployment")
            self.assertIn(
                "timeoutInMinutes", job, f"job {name} sin timeoutInMinutes"
            )
        shells = [
            n
            for doc in docs.values()
            for n in walk(doc)
            if isinstance(n, dict)
            and isinstance(n.get("task"), str)
            and n["task"].split("@")[0] in ("Bash", "CmdLine", "PowerShell")
        ]
        self.assertGreater(len(shells), 0, "no hay tareas shell que validar")
        for task in shells:
            inputs = task.get("inputs", {})
            self.assertTrue(
                inputs.get("failOnStderr") in (True, "true"),
                f"tarea {task.get('displayName', task['task'])} sin failOnStderr",
            )

    def test_parameters(self):
        """Parametros environment (DEV/QA/PROD) y version 1.0.$(BuildId)."""
        main = load_all()[MAIN]
        params = {p["name"]: p for p in main.get("parameters", [])}
        self.assertIn("environment", params)
        values = str(params["environment"].get("values", []))
        for env in ("DEV", "QA", "PROD"):
            self.assertIn(env, values, f"environment sin valor {env}")
        self.assertIn("version", params)
        default = str(params["version"].get("default", ""))
        self.assertIn("1.0.", default, "version sin default 1.0.x")
        self.assertIn("BuildId", default, "version sin $(BuildId)")

    def test_deploy_template_params(self):
        """deploy.yml recibe environment/version/artifactFeed y valida vacios."""
        path = os.path.join(ROOT, "templates", "deploy.yml")
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        doc = yaml.safe_load(text)
        params = {p["name"] for p in doc.get("parameters", [])}
        self.assertTrue(
            {"environment", "version", "artifactFeed"}.issubset(params),
            f"deploy.yml sin parametros requeridos: {params}",
        )
        self.assertIn("-z", text, "deploy.yml no falla si hay parametros vacios")

    def test_pipeline_metadata_artifact(self):
        """Build publica el artefacto pipeline-metadata (version, commit)."""
        blob = yaml.safe_dump(load_all()[MAIN])
        self.assertIn("pipeline-metadata", blob, "falta artefacto pipeline-metadata")

    def test_pool_demands(self):
        """Pool documentado con demands para GeneXus/MSBuild."""
        main = load_all()[MAIN]
        pool = main.get("pool", {})
        blob = yaml.safe_dump(pool).lower()
        self.assertIn("demand", blob, "pool sin demands")
        self.assertIn(
            "msbuild", blob, "pool sin demand de MSBuild/GeneXus documentada"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
