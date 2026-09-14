"""Testes de integração: correm pedidos HTTP reais contra app.py.

Estes testes existem porque bugs como o do replaneamento (create_replanned_plan
exigia demand.state == VALIDATED) e o das cardinalidades (demanda dividida por
várias operações, ou várias demandas consolidadas numa operação) só são
visíveis ao correr o fluxo HTTP real, não pelos testes de domínio isolados.
test_nexxus_logistica.py cobre os objetos; este ficheiro cobre a camada web
que os liga entre si.
"""

import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer

# Isolar os testes: usar um ficheiro SQLite temporário, nunca a base de
# dados real do protótipo. Tem de ser definido ANTES de importar app/storage,
# porque storage.DB_PATH resolve o valor por omissão no momento da importação.
_TEST_DB = tempfile.NamedTemporaryFile(prefix="nexxus_test_", suffix=".db", delete=False)
_TEST_DB.close()
os.environ["NEXXUS_DB_PATH"] = _TEST_DB.name

import app as app_module  # noqa: E402
from app import App  # noqa: E402
from nexxus_logistica import DemandState, OperationState  # noqa: E402


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
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(_TEST_DB.name + suffix)
            except FileNotFoundError:
                pass

    def setUp(self):
        # app.py guarda o estado em dicionários ao nível do módulo;
        # isolamos cada teste para não herdar dados do teste anterior.
        app_module.DEMANDS.clear()
        app_module.RESOURCE_CATALOG.clear()
        app_module.PLANS.clear()
        app_module.OPERATIONS.clear()
        app_module.MEASUREMENTS.clear()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def post(self, path: str, data: dict):
        encoded = urllib.parse.urlencode(data, doseq=True).encode()
        request = urllib.request.Request(self.url(path), data=encoded, method="POST")
        return urllib.request.urlopen(request)

    def create_demand(self, **overrides) -> str:
        sequence = len(app_module.DEMANDS) + 1
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
        return f"D-{sequence:03d}"

    def add_catalog_resource(self, **overrides) -> str:
        payload = {"name": "Camiao01", "capacity": "25", "unit": "t"}
        payload.update(overrides)
        self.post("/resources", payload)
        return f"R-{len(app_module.RESOURCE_CATALOG):03d}"

    def plan_prepare_start(self, demand_id: str, quantity=None) -> str:
        """Planeia (parcial ou total), prepara e inicia a operação para uma
        única demanda. Devolve o operation_id criado."""
        resource_id = self.add_catalog_resource()
        demand = app_module.DEMANDS[demand_id]
        qty = quantity if quantity is not None else demand.remaining_quantity
        self.post("/plan-demand", {"demand_id": demand_id, "resource_id": resource_id, "quantity": f"{qty:g}"})
        operation_id = f"O-{len(app_module.OPERATIONS):03d}"
        self.post("/action", {"id": operation_id, "action": "prepare"})
        self.post("/action", {"id": operation_id, "action": "start"})
        return operation_id

    # ------------------------------------------------------------ criação

    def test_create_demand_persists_client_and_conditions(self):
        demand_id = self.create_demand()
        response = urllib.request.urlopen(self.url(f"/demand?id={demand_id}"))
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
        operation_id = self.plan_prepare_start(demand_id)

        self.post("/action", {"id": operation_id, "action": "start_stage", "stage_id": f"{operation_id}-S1"})
        self.post("/action", {"id": operation_id, "action": "complete_stage", "stage_id": f"{operation_id}-S1"})

        exception_response = self.post(
            "/action",
            {"id": operation_id, "action": "exception", "type": "avaria", "severity": "alta", "description": "Avaria do motor"},
        )
        self.assertEqual(exception_response.status, 200)

        replan_response = self.post(
            "/action", {"id": operation_id, "action": "replan", "description": "Substituir veículo e retomar"}
        )
        self.assertEqual(replan_response.status, 200)

        operation = app_module.OPERATIONS[operation_id]
        self.assertEqual(operation.state, OperationState.IN_EXECUTION)
        self.assertEqual(app_module.PLANS[operation.plan_id].version, 2)

        for suffix in ("S2", "S3"):
            stage_id = f"{operation_id}-{suffix}"
            self.post("/action", {"id": operation_id, "action": "start_stage", "stage_id": stage_id})
            self.post("/action", {"id": operation_id, "action": "complete_stage", "stage_id": stage_id})

        complete_response = self.post(
            "/action", {"id": operation_id, "action": "complete", "result": "20t entregues", "evidence": "POD-001"}
        )
        html = complete_response.read().decode()

        self.assertIn("20t entregues", html)
        self.assertEqual(app_module.DEMANDS[demand_id].state.value, "completed")

    def test_exception_type_and_severity_are_not_hardcoded(self):
        demand_id = self.create_demand()
        operation_id = self.plan_prepare_start(demand_id)
        self.post(
            "/action",
            {"id": operation_id, "action": "exception", "type": "falta de capacidade", "severity": "baixa", "description": "Recurso indisponível"},
        )
        exception = app_module.OPERATIONS[operation_id].exceptions[-1]

        self.assertEqual(exception.type, "falta de capacidade")
        self.assertEqual(exception.severity, "baixa")
        self.assertEqual(exception.description, "Recurso indisponível")

    def test_replan_without_pending_exception_is_rejected(self):
        demand_id = self.create_demand()
        operation_id = self.plan_prepare_start(demand_id)

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/action", {"id": operation_id, "action": "replan", "description": "x"})
        self.assertEqual(ctx.exception.code, 400)

    # ------------------------------------------------------- persistência

    def test_data_survives_simulated_restart(self):
        """Confirma que a persistência funciona: reconstrói o estado a
        partir da base de dados (não da memória), tal como aconteceria
        depois de reiniciar o processo do servidor."""
        import storage

        demand_id = self.create_demand()
        operation_id = self.plan_prepare_start(demand_id)
        self.post("/action", {"id": operation_id, "action": "start_stage", "stage_id": f"{operation_id}-S1"})
        self.post("/action", {"id": operation_id, "action": "complete_stage", "stage_id": f"{operation_id}-S1"})

        reloaded_demands = storage.load_demands()
        reloaded_operations = storage.load_operations()

        self.assertIn(demand_id, reloaded_demands)
        self.assertEqual(reloaded_demands[demand_id].client, "Cliente ABC")
        self.assertEqual(reloaded_demands[demand_id].state.value, "in_execution")

        self.assertIn(operation_id, reloaded_operations)
        reloaded_operation = reloaded_operations[operation_id]
        self.assertEqual(reloaded_operation.stages[0].state.value, "completed")
        self.assertEqual(reloaded_operation.stages[1].state.value, "prepared")

    # --------------------------------------------------- catálogo/etapas/eventos

    def test_resource_catalog_add_and_list(self):
        resource_id = self.add_catalog_resource(name="Camiao 02", capacity="30", unit="t")
        self.assertIn(resource_id, app_module.RESOURCE_CATALOG)

        html = urllib.request.urlopen(self.url("/resources")).read().decode()
        self.assertIn("Camiao 02", html)

    def test_planning_rejects_unknown_resource_id(self):
        demand_id = self.create_demand()
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post("/plan-demand", {"demand_id": demand_id, "resource_id": "R-999", "quantity": "20"})
        self.assertEqual(ctx.exception.code, 400)

    def test_custom_stage_names_are_used(self):
        demand_id = self.create_demand()
        resource_id = self.add_catalog_resource()
        self.post(
            "/plan-demand",
            {
                "demand_id": demand_id,
                "resource_id": resource_id,
                "quantity": "20",
                "stages": "recolha, transporte, entrega, descarga",
            },
        )
        operation_id = f"O-{len(app_module.OPERATIONS):03d}"
        stage_names = [s.name for s in app_module.OPERATIONS[operation_id].stages]
        self.assertEqual(stage_names, ["recolha", "transporte", "entrega", "descarga"])

    def test_event_location_and_quantity_are_recorded(self):
        demand_id = self.create_demand()
        operation_id = self.plan_prepare_start(demand_id)
        self.post(
            "/action",
            {"id": operation_id, "action": "event", "description": "Saiu da origem", "location": "Viana", "quantity": "20"},
        )
        event = app_module.OPERATIONS[operation_id].events[-1]
        self.assertEqual(event.location, "Viana")
        self.assertEqual(event.quantity, 20.0)

        html = urllib.request.urlopen(self.url(f"/operation?id={operation_id}")).read().decode()
        self.assertIn("Viana", html)

    # -------------------------------------------------- divisão e consolidação

    def test_demand_can_be_split_across_two_operations_via_http(self):
        """Cobre o gap identificado na auditoria do Core Logística: uma
        demanda de 30t não cabe num único recurso de 25t e é planeada em
        duas operações a partir da página da demanda."""
        demand_id = self.create_demand(quantity="30")
        resource_1 = self.add_catalog_resource(name="Camiao A", capacity="25")
        resource_2 = self.add_catalog_resource(name="Camiao B", capacity="25")

        self.post("/plan-demand", {"demand_id": demand_id, "resource_id": resource_1, "quantity": "20"})
        op_1 = f"O-{len(app_module.OPERATIONS):03d}"
        demand = app_module.DEMANDS[demand_id]
        self.assertEqual(demand.state, DemandState.PLANNED)
        self.assertAlmostEqual(demand.remaining_quantity, 10)

        self.post("/plan-demand", {"demand_id": demand_id, "resource_id": resource_2, "quantity": "10"})
        op_2 = f"O-{len(app_module.OPERATIONS):03d}"
        self.assertTrue(app_module.DEMANDS[demand_id].fully_allocated)

        html = urllib.request.urlopen(self.url(f"/demand?id={demand_id}")).read().decode()
        self.assertIn(op_1, html)
        self.assertIn(op_2, html)

        for op_id in (op_1, op_2):
            self.post("/action", {"id": op_id, "action": "prepare"})
            self.post("/action", {"id": op_id, "action": "start"})
            for suffix in ("S1", "S2", "S3"):
                stage_id = f"{op_id}-{suffix}"
                self.post("/action", {"id": op_id, "action": "start_stage", "stage_id": stage_id})
                self.post("/action", {"id": op_id, "action": "complete_stage", "stage_id": stage_id})

        self.post("/action", {"id": op_1, "action": "complete", "result": "20t entregues", "evidence": "POD-A"})
        self.assertEqual(app_module.DEMANDS[demand_id].state, DemandState.IN_EXECUTION)

        self.post("/action", {"id": op_2, "action": "complete", "result": "10t entregues", "evidence": "POD-B"})
        self.assertEqual(app_module.DEMANDS[demand_id].state, DemandState.COMPLETED)
        self.assertEqual(app_module.DEMANDS[demand_id].delivered_quantity, 30)

    def test_multiple_demands_can_be_consolidated_via_http(self):
        """Cobre o outro gap identificado na auditoria: três demandas de
        clientes diferentes consolidadas numa única operação a partir de
        /consolidate."""
        demand_a = self.create_demand(client="Cliente A", quantity="5")
        demand_b = self.create_demand(client="Cliente B", quantity="8")
        demand_c = self.create_demand(client="Cliente C", quantity="7")
        resource_id = self.add_catalog_resource(name="Camiao consolidado", capacity="25")

        self.post(
            "/consolidate",
            {
                "demand_ids": [demand_a, demand_b, demand_c],
                f"qty_{demand_a}": "5",
                f"qty_{demand_b}": "8",
                f"qty_{demand_c}": "7",
                "resource_id": resource_id,
            },
        )
        operation_id = f"O-{len(app_module.OPERATIONS):03d}"
        operation = app_module.OPERATIONS[operation_id]
        self.assertEqual(set(operation.demand_ids), {demand_a, demand_b, demand_c})
        self.assertEqual(operation.total_quantity, 20)

        html = urllib.request.urlopen(self.url(f"/operation?id={operation_id}")).read().decode()
        self.assertIn(demand_a, html)
        self.assertIn(demand_b, html)
        self.assertIn(demand_c, html)

        self.post("/action", {"id": operation_id, "action": "prepare"})
        self.post("/action", {"id": operation_id, "action": "start"})
        for demand_id in (demand_a, demand_b, demand_c):
            self.assertEqual(app_module.DEMANDS[demand_id].state, DemandState.IN_EXECUTION)

        for suffix in ("S1", "S2", "S3"):
            stage_id = f"{operation_id}-{suffix}"
            self.post("/action", {"id": operation_id, "action": "start_stage", "stage_id": stage_id})
            self.post("/action", {"id": operation_id, "action": "complete_stage", "stage_id": stage_id})

        self.post("/action", {"id": operation_id, "action": "complete", "result": "3 entregas", "evidence": "POD-CONS"})

        for demand_id, expected_qty in ((demand_a, 5), (demand_b, 8), (demand_c, 7)):
            demand = app_module.DEMANDS[demand_id]
            self.assertEqual(demand.state, DemandState.COMPLETED)
            self.assertEqual(demand.delivered_quantity, expected_qty)

    def test_consolidation_rejects_insufficient_capacity(self):
        demand_a = self.create_demand(client="Cliente A", quantity="15")
        demand_b = self.create_demand(client="Cliente B", quantity="15")
        resource_id = self.add_catalog_resource(name="Camiao pequeno", capacity="25")

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post(
                "/consolidate",
                {
                    "demand_ids": [demand_a, demand_b],
                    f"qty_{demand_a}": "15",
                    f"qty_{demand_b}": "15",
                    "resource_id": resource_id,
                },
            )
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
