"""Testes de integração: correm pedidos HTTP reais contra app.py.

Estes testes existem porque o bug do replaneamento (create_replanned_plan
exigia demand.state == VALIDATED, mas a demanda já tinha avançado para
PLANNED) só era visível ao correr o fluxo HTTP real, não pelos testes de
domínio isolados. test_nexxus_logistica.py cobre os objetos; este ficheiro
cobre a camada web que os liga entre si.
"""

import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer

import app as app_module
from app import App
from nexxus_logistica import OperationState


class NexxusAppIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), App)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        # app.py guarda o estado em dicionários ao nível do módulo;
        # isolamos cada teste para não herdar dados do teste anterior.
        app_module.DEMANDS.clear()
        app_module.RESOURCES.clear()
        app_module.PLANS.clear()
        app_module.OPERATIONS.clear()
        app_module.MEASUREMENTS.clear()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def post(self, path: str, data: dict):
        encoded = urllib.parse.urlencode(data).encode()
        request = urllib.request.Request(self.url(path), data=encoded, method="POST")
        return urllib.request.urlopen(request)

    def create_demand(self, **overrides) -> str:
        payload = {
            "client": "Cliente ABC",
            "description": "Farinha",
            "quantity": "20",
            "unit": "t",
            "origin": "Fabrica",
            "destination": "Armazem",
            "conditions": "carga seca",
            "notes": "entregar de manha",
        }
        payload.update(overrides)
        self.post("/create", payload)
        return "D-001"

    def plan_prepare_start(self, demand_id: str) -> None:
        self.post("/action", {"id": demand_id, "action": "plan", "resource": "Camiao01", "capacity": "25"})
        self.post("/action", {"id": demand_id, "action": "prepare"})
        self.post("/action", {"id": demand_id, "action": "start"})

    # ------------------------------------------------------------ criação

    def test_create_demand_persists_client_and_conditions(self):
        demand_id = self.create_demand()
        response = urllib.request.urlopen(self.url(f"/operation?id={demand_id}"))
        html = response.read().decode()

        self.assertIn("Cliente ABC", html)
        self.assertIn("carga seca", html)
        self.assertIn("entregar de manha", html)

    def test_create_demand_rejects_invalid_input(self):
        payload = {
            "client": "",
            "description": "",
            "quantity": "0",
            "unit": "t",
            "origin": "A",
            "destination": "A",
        }
        encoded = urllib.parse.urlencode(payload).encode()
        request = urllib.request.Request(self.url("/create"), data=encoded, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 400)

    # -------------------------------------------------- fluxo com exceção

    def test_full_flow_including_replanning_reaches_completion(self):
        """Regressão: este é exatamente o caminho que ficava partido antes
        da correção de create_replanned_plan (rebentava com 500 no passo
        de 'replan'). Cobre também o guard-rail de exceção/gravidade reais."""
        demand_id = self.create_demand()
        self.plan_prepare_start(demand_id)

        self.post("/action", {"id": demand_id, "action": "start_stage", "stage_id": f"O-{demand_id}-S1"})
        self.post("/action", {"id": demand_id, "action": "complete_stage", "stage_id": f"O-{demand_id}-S1"})

        exception_response = self.post(
            "/action",
            {"id": demand_id, "action": "exception", "type": "avaria", "severity": "alta", "description": "Avaria do motor"},
        )
        self.assertEqual(exception_response.status, 200)

        replan_response = self.post(
            "/action", {"id": demand_id, "action": "replan", "description": "Substituir veículo e retomar"}
        )
        self.assertEqual(replan_response.status, 200)

        operation = app_module.OPERATIONS[demand_id]
        self.assertEqual(operation.state, OperationState.IN_EXECUTION)
        self.assertEqual(app_module.PLANS[demand_id].version, 2)

        for suffix in ("S2", "S3"):
            stage_id = f"O-{demand_id}-{suffix}"
            self.post("/action", {"id": demand_id, "action": "start_stage", "stage_id": stage_id})
            self.post("/action", {"id": demand_id, "action": "complete_stage", "stage_id": stage_id})

        complete_response = self.post(
            "/action", {"id": demand_id, "action": "complete", "result": "20t entregues", "evidence": "POD-001"}
        )
        html = complete_response.read().decode()

        self.assertIn("20t entregues", html)
        self.assertEqual(app_module.DEMANDS[demand_id].state.value, "completed")

    def test_exception_type_and_severity_are_not_hardcoded(self):
        demand_id = self.create_demand()
        self.plan_prepare_start(demand_id)
        self.post(
            "/action",
            {"id": demand_id, "action": "exception", "type": "falta de capacidade", "severity": "baixa", "description": "Recurso indisponível"},
        )
        exception = app_module.OPERATIONS[demand_id].exceptions[-1]

        self.assertEqual(exception.type, "falta de capacidade")
        self.assertEqual(exception.severity, "baixa")
        self.assertEqual(exception.description, "Recurso indisponível")

    def test_replan_without_pending_exception_is_rejected(self):
        demand_id = self.create_demand()
        self.plan_prepare_start(demand_id)

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/action", {"id": demand_id, "action": "replan", "description": "x"})
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
