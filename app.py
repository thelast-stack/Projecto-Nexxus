from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import storage
from nexxus_logistica import (
    Demand,
    DemandState,
    ExceptionState,
    LogisticsException,
    LogisticsUnit,
    OperationState,
    Point,
    Resource,
    StageState,
    complete_operation,
    create_operation,
    create_plan,
    create_replanned_plan,
    measure_operation,
    start_operation,
    validate_demand,
)

DEMANDS = {}
RESOURCES = {}
RESOURCE_CATALOG = {}
PLANS = {}
OPERATIONS = {}
MEASUREMENTS = {}

storage.init_db()
DEMANDS.update(storage.load_demands())
RESOURCES.update(storage.load_resources())
RESOURCE_CATALOG.update(storage.load_catalog_resources())
PLANS.update(storage.load_plans())
OPERATIONS.update(storage.load_operations())
MEASUREMENTS.update(storage.load_measurements())

STYLE = """
body{font-family:Arial,sans-serif;max-width:980px;margin:0 auto;background:#f5f6f8;padding:28px;color:#20242a}
h1,h2,h3{margin-top:0}
.card{background:#fff;padding:24px;margin:16px 0;border-radius:12px;box-shadow:0 1px 4px #0001}
.card.warn{background:#fff8ec}
.card.ok{background:#eef8f0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.field{margin-bottom:16px}
.field label{display:block;font-weight:700;margin-bottom:6px}
input,textarea,select{box-sizing:border-box;width:100%;padding:11px;border:1px solid #cbd0d6;border-radius:7px;font-size:15px}
textarea{min-height:80px;resize:vertical}
button,a.button{display:inline-block;padding:11px 16px;background:#20242a;color:#fff;border:0;border-radius:7px;text-decoration:none;cursor:pointer;font-size:14px}
a.secondary{background:#e9ebee;color:#20242a}
.muted{color:#68707a}
.status{font-weight:700}
.flow{display:flex;gap:8px;flex-wrap:wrap}
.step{padding:8px 11px;background:#eef0f2;border-radius:7px}
.step.active{background:#20242a;color:#fff}
@media(max-width:700px){.grid{grid-template-columns:1fr}}
"""


def page(body: str) -> str:
    return f"""<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXXUS Logística</title>
<style>{STYLE}</style>
</head><body>{body}</body></html>"""


def field_value(form_data: dict, key: str) -> str:
    return form_data.get(key, [""])[0].strip()


def persist(demand_id: str) -> None:
    if demand_id in DEMANDS:
        storage.save_demand(DEMANDS[demand_id])
    if demand_id in RESOURCES:
        storage.save_resource(demand_id, RESOURCES[demand_id])
    if demand_id in PLANS:
        storage.save_plan(demand_id, PLANS[demand_id])
    if demand_id in OPERATIONS:
        storage.save_operation(demand_id, OPERATIONS[demand_id])
    if demand_id in MEASUREMENTS:
        storage.save_measurement(demand_id, MEASUREMENTS[demand_id])


class App(BaseHTTPRequestHandler):
    def send_page(self, body: str, code: int = 200) -> None:
        data = page(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, path: str) -> None:
        self.send_response(303)
        self.send_header("Location", path)
        self.end_headers()

    def read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return parse_qs(self.rfile.read(length).decode())

    # ------------------------------------------------------------------ GET

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.render_home()
            return

        if parsed.path == "/new":
            self.render_new_demand_form()
            return

        if parsed.path == "/resources":
            self.render_resources()
            return

        if parsed.path == "/operation":
            query = parse_qs(parsed.query)
            demand_id = field_value(query, "id")
            self.render_operation(demand_id)
            return

        self.send_page("<h1>404</h1>", 404)

    def render_home(self) -> None:
        cards = "".join(
            f'<div class="card"><h3>Demanda #{demand.id}</h3>'
            f'<p>{demand.client} · {demand.description} · {demand.unit.quantity:g} {demand.unit.unit} · '
            f'{demand.origin.name} → {demand.destination.name}</p>'
            f'<p class="status">Estado: {demand.state.value}</p>'
            f'<a class="button" href="/operation?id={demand.id}">Abrir</a></div>'
            for demand in DEMANDS.values()
        )
        self.send_page(
            "<h1>NEXXUS LOGÍSTICA</h1>"
            '<p class="muted">Demanda → Planeamento → Preparação → Execução → '
            "Exceção/Replaneamento → Resultado/Medição.</p>"
            '<p><a class="button" href="/new">+ Nova demanda</a> <a class="button secondary" href="/resources">Recursos</a></p>'
            + (cards or '<div class="card">Nenhuma demanda registada.</div>')
        )

    def render_new_demand_form(self) -> None:
        self.send_page("""
<h1>Nova demanda</h1>
<p class="muted">Nesta etapa descreva o que precisa ser realizado. O recurso e o planeamento serão definidos depois.</p>
<form method="post" action="/create">
<div class="card">
  <div class="field"><label>Cliente / solicitante *</label><input name="client" placeholder="Ex.: Cliente ABC" required></div>
</div>
<div class="card">
  <div class="grid">
    <div class="field"><label>O que será movimentado? *</label><input name="description" placeholder="Ex.: Farinha de trigo" required></div>
    <div class="field"><label>Quantidade *</label><input name="quantity" type="number" min="0.01" step="0.01" required></div>
    <div class="field"><label>Unidade *</label>
      <select name="unit"><option value="t">toneladas (t)</option><option value="kg">quilogramas (kg)</option><option value="un">unidades (un)</option></select>
    </div>
  </div>
</div>
<div class="card">
  <div class="grid">
    <div class="field"><label>Origem *</label><input name="origin" placeholder="Ex.: Fábrica Viana" required></div>
    <div class="field"><label>Destino *</label><input name="destination" placeholder="Ex.: Armazém Luanda" required></div>
  </div>
</div>
<div class="card">
  <div class="field"><label>Prazo</label><input name="deadline" type="datetime-local"></div>
  <div class="field"><label>Condições / restrições</label><textarea name="conditions" placeholder="Ex.: carga seca, horário de receção..."></textarea></div>
  <div class="field"><label>Observações</label><textarea name="notes" placeholder="Informação adicional relevante."></textarea></div>
</div>
<div class="card">
  <button type="submit">Criar e validar demanda</button>
  <a class="button secondary" href="/">Cancelar</a>
</div>
</form>""")

    def render_resources(self) -> None:
        rows = "".join(
            f"<li>{r.name} — {r.capacity:g} {r.unit} — "
            f"<b>{'disponível' if r.available else 'indisponível'}</b></li>"
            for r in RESOURCE_CATALOG.values()
        )
        self.send_page(f"""
<h1>Recursos</h1>
<p class="muted">Recursos disponíveis para alocar a planos. Consulte aqui antes de planear uma operação.</p>
<div class="card"><h2>Catálogo</h2>
<ol>{rows or "<li>Nenhum recurso registado ainda.</li>"}</ol></div>
<div class="card"><h2>Adicionar recurso</h2>
<form method="post" action="/resources">
<div class="grid">
<div class="field"><label>Nome *</label><input name="name" placeholder="Ex.: Camião 01" required></div>
<div class="field"><label>Capacidade *</label><input name="capacity" type="number" min="0.01" step="0.01" required></div>
<div class="field"><label>Unidade *</label>
<select name="unit"><option value="t">toneladas (t)</option><option value="kg">quilogramas (kg)</option><option value="un">unidades (un)</option></select>
</div>
</div>
<button>Adicionar ao catálogo</button></form></div>
<a class="button secondary" href="/">Voltar</a>""")

    def render_operation(self, demand_id: str) -> None:
        demand = DEMANDS.get(demand_id)
        if not demand:
            self.send_page("<h1>Demanda não encontrada</h1>", 404)
            return

        operation = OPERATIONS.get(demand_id)
        current_state = operation.state if operation else demand.state

        request_card = f"""
<div class="card"><h2>Pedido</h2>
<p><b>Solicitante:</b> {demand.client}</p>
<p><b>O que:</b> {demand.description} · <b>Quantidade:</b> {demand.unit.quantity:g} {demand.unit.unit}</p>
<p><b>Origem:</b> {demand.origin.name} → <b>Destino:</b> {demand.destination.name}</p>
<p><b>Prazo:</b> {demand.deadline or "Não definido"}</p>
<p><b>Condições:</b> {", ".join(demand.conditions) or "Nenhuma"}</p>
<p><b>Observações:</b> {demand.notes or "Nenhuma"}</p>
<p class="status">Estado da demanda: {demand.state.value}</p></div>"""

        action_card = self.render_action_card(demand, operation, current_state)
        stages_card = self.render_stages_card(operation)
        timeline_card = self.render_timeline_card(operation)

        self.send_page(
            f"<h1>Demanda #{demand.id}</h1>"
            f"{request_card}{action_card}{stages_card}{timeline_card}"
            '<a class="button secondary" href="/">Voltar</a>'
        )

    def render_action_card(self, demand: Demand, operation, current_state) -> str:
        oid = demand.id

        if operation is None:
            compatible = [r for r in RESOURCE_CATALOG.values() if r.unit == demand.unit.unit and r.available]
            if not compatible:
                return f"""
<div class="card warn"><h2>Planeamento</h2>
<p>Não há recursos no catálogo compatíveis com "{demand.unit.unit}".</p>
<a class="button" href="/resources">Adicionar recurso</a></div>"""

            options = "".join(
                f'<option value="{r.id}">{r.name} — {r.capacity:g} {r.unit}</option>' for r in compatible
            )
            return f"""
<div class="card"><h2>Planeamento</h2>
<p>A demanda está validada. Escolha o recurso do catálogo e, se necessário, personalize as etapas.</p>
<form method="post" action="/action">
<input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="plan">
<div class="field"><label>Recurso</label><select name="resource_id" required>{options}</select></div>
<div class="field"><label>Etapas (separadas por vírgula)</label>
<input name="stages" placeholder="Ex.: recolha, transporte, entrega — deixe em branco para o padrão">
</div>
<button>Confirmar planeamento</button></form></div>"""

        if current_state == OperationState.PLANNED:
            plan = PLANS[oid]
            resource = RESOURCES[oid]
            return f"""
<div class="card"><h2>Operação planeada</h2>
<p>Plano v{plan.version} · Recurso: <b>{resource.name}</b> · Capacidade: <b>{plan.capacity.quantity:g} {demand.unit.unit}</b> ({plan.capacity.state.value})</p>
<form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="prepare">
<button>Preparar operação</button></form></div>"""

        if current_state == OperationState.PREPARED:
            return f"""
<div class="card"><h2>Operação preparada</h2><p>Todas as etapas estão preparadas.</p>
<form method="post" action="/action"><input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="start">
<button>Iniciar execução</button></form></div>"""

        if current_state == OperationState.IN_EXECUTION:
            return self.render_execution_card(operation, oid)

        if current_state == OperationState.EXCEPTION:
            exception = operation.exceptions[-1]
            return f"""
<div class="card warn"><h2>⚠ Exceção — necessita intervenção</h2>
<p><b>Tipo:</b> {exception.type} · <b>Gravidade:</b> {exception.severity}</p>
<p><b>Descrição:</b> {exception.description}</p>
<form method="post" action="/action">
<input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="replan">
<div class="field"><label>Decisão / novo plano</label><input name="description" placeholder="Ex.: Substituir veículo e retomar às 14h" required></div>
<button>Replanear e retomar</button></form></div>"""

        # COMPLETED
        measurement = MEASUREMENTS.get(oid, {})
        plan = PLANS.get(oid)
        capacity_line = f'<p><b>Capacidade:</b> {plan.capacity.state.value}</p>' if plan else ""
        return f"""
<div class="card ok"><h2>Resultado</h2>
<p><b>Resultado:</b> {operation.result}</p>
<p><b>Evidência:</b> {operation.evidence}</p>
<p><b>Desvio de duração:</b> {measurement.get("duration_deviation_hours", "—")} h</p>
{capacity_line}</div>"""

    def render_execution_card(self, operation, oid: str) -> str:
        current_stage = next((s for s in operation.stages if s.state == StageState.IN_EXECUTION), None)
        pending_stage = next((s for s in operation.stages if s.state == StageState.PREPARED), None)

        stage_action = ""
        if current_stage:
            stage_action = f"""<p>Etapa em execução: <b>{current_stage.name}</b></p>
<form method="post" action="/action">
<input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="complete_stage">
<input type="hidden" name="stage_id" value="{current_stage.id}"><button>Concluir etapa</button></form>"""
        elif pending_stage:
            stage_action = f"""<p>Próxima etapa: <b>{pending_stage.name}</b></p>
<form method="post" action="/action">
<input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="start_stage">
<input type="hidden" name="stage_id" value="{pending_stage.id}"><button>Iniciar etapa</button></form>"""

        card = f"""
<div class="card"><h2>Execução</h2>
{stage_action}
<hr>
<form method="post" action="/action">
<input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="event">
<div class="field"><label>Evento ocorrido</label><input name="description" placeholder="Ex.: Saiu da origem às 10h" required></div>
<div class="grid">
<div class="field"><label>Localização (opcional)</label><input name="location" placeholder="Ex.: Viana, Luanda"></div>
<div class="field"><label>Quantidade (opcional)</label><input name="quantity" type="number" step="0.01"></div>
</div>
<button>Registar evento</button></form>
<hr>
<form method="post" action="/action">
<input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="exception">
<div class="grid">
<div class="field"><label>Tipo de exceção</label><input name="type" placeholder="Ex.: atraso, avaria" required></div>
<div class="field"><label>Gravidade</label>
<select name="severity"><option value="baixa">Baixa</option><option value="media" selected>Média</option><option value="alta">Alta</option></select></div>
</div>
<div class="field"><label>Descrição</label><input name="description" placeholder="Ex.: Avaria do veículo na etapa de transporte" required></div>
<button>Registar exceção</button></form>"""

        if all(s.state == StageState.COMPLETED for s in operation.stages):
            card += f"""
<hr>
<form method="post" action="/action">
<input type="hidden" name="id" value="{oid}"><input type="hidden" name="action" value="complete">
<div class="grid">
<div class="field"><label>Resultado</label><input name="result" placeholder="Ex.: Entrega realizada" required></div>
<div class="field"><label>Evidência</label><input name="evidence" placeholder="Ex.: POD-001 / assinatura" required></div>
</div>
<button>Concluir operação</button></form>"""

        return card + "</div>"

    def render_stages_card(self, operation) -> str:
        if not operation:
            return ""
        items = "".join(f"<li>{s.sequence}. {s.name} — <b>{s.state.value}</b></li>" for s in operation.stages)
        return f'<div class="card"><h2>Etapas</h2><ol>{items}</ol></div>'

    def render_timeline_card(self, operation) -> str:
        if not operation:
            items = "<li>Demanda criada e validada</li>"
        else:
            items = "".join(
                f"<li>{event.timestamp:%H:%M:%S} — <b>{event.type}</b> — {event.description}"
                + (f" · {event.location}" if event.location else "")
                + (f" · {event.quantity:g}" if event.quantity is not None else "")
                + "</li>"
                for event in operation.events
            )
        return f'<div class="card"><h2>Linha do tempo</h2><ol>{items}</ol></div>'

    # ----------------------------------------------------------------- POST

    def do_POST(self) -> None:
        form_data = self.read_form()
        value = lambda key: field_value(form_data, key)  # noqa: E731

        if self.path == "/create":
            self.handle_create(value)
            return

        if self.path == "/action":
            self.handle_action(value)
            return

        if self.path == "/resources":
            self.handle_create_resource(value)
            return

        self.redirect("/")

    def handle_create(self, value) -> None:
        try:
            quantity = float(value("quantity"))
        except ValueError:
            quantity = 0

        required = (value("client"), value("description"), value("origin"), value("destination"))
        if quantity <= 0 or not all(required) or value("origin") == value("destination"):
            self.send_page(
                "<h1>Validação falhou</h1><p>Verifique solicitante, item, quantidade e origem/destino.</p>", 400
            )
            return

        sequence = len(DEMANDS) + 1
        demand_id = f"D-{sequence:03d}"
        deadline_raw = value("deadline")
        deadline = datetime.fromisoformat(deadline_raw) if deadline_raw else None
        conditions_raw = value("conditions")

        demand = Demand(
            id=demand_id,
            unit=LogisticsUnit(f"U-{sequence:03d}", quantity, value("unit")),
            origin=Point(f"P-{sequence:03d}A", value("origin")),
            destination=Point(f"P-{sequence:03d}B", value("destination")),
            client=value("client"),
            description=value("description"),
            deadline=deadline,
            conditions=[conditions_raw] if conditions_raw else [],
            notes=value("notes"),
        )
        validate_demand(demand)
        DEMANDS[demand_id] = demand
        persist(demand_id)
        self.redirect(f"/operation?id={demand_id}")

    def handle_create_resource(self, value) -> None:
        try:
            capacity = float(value("capacity"))
        except ValueError:
            capacity = 0
        name = value("name")
        if not name or capacity <= 0:
            self.send_page("<h1>Validação falhou</h1><p>Indique nome e capacidade válidos.</p>", 400)
            return

        resource_id = f"R-{len(RESOURCE_CATALOG) + 1:03d}"
        resource = Resource(resource_id, name, capacity, value("unit"))
        RESOURCE_CATALOG[resource_id] = resource
        storage.save_catalog_resource(resource)
        self.redirect("/resources")

    def handle_action(self, value) -> None:
        demand_id = value("id")
        demand = DEMANDS.get(demand_id)
        if not demand:
            self.send_page("<h1>Demanda não encontrada</h1>", 404)
            return

        action = value("action")
        operation = OPERATIONS.get(demand_id)

        try:
            if action == "plan":
                self.action_plan(demand, demand_id, value)
            elif action == "prepare":
                operation.prepare()
            elif action == "start":
                start_operation(operation, PLANS[demand_id])
                demand.state = DemandState.IN_EXECUTION
            elif action == "start_stage":
                self.find_stage(operation, value("stage_id")).start()
            elif action == "complete_stage":
                self.find_stage(operation, value("stage_id")).complete()
            elif action == "event":
                quantity_raw = value("quantity")
                quantity = float(quantity_raw) if quantity_raw else None
                operation.register_event("event", value("description"), location=value("location") or None, quantity=quantity)
            elif action == "exception":
                self.action_register_exception(operation, value)
            elif action == "replan":
                self.action_replan(demand, demand_id, operation, value)
            elif action == "complete":
                complete_operation(operation, PLANS[demand_id], value("result"), value("evidence"))
                MEASUREMENTS[demand_id] = measure_operation(demand.unit.quantity, demand.unit.quantity, 8, 9.5)
                demand.state = DemandState.COMPLETED
        except ValueError as exc:
            self.send_page(f"<h1>Ação não pode ser concluída</h1><p>{exc}</p>", 400)
            return

        persist(demand_id)
        self.redirect(f"/operation?id={demand_id}")

    def action_plan(self, demand: Demand, demand_id: str, value) -> None:
        resource = RESOURCE_CATALOG.get(value("resource_id"))
        if resource is None:
            raise ValueError("Recurso não encontrado no catálogo")

        stage_names_raw = value("stages")
        stage_names = [s.strip() for s in stage_names_raw.split(",") if s.strip()] or None

        plan = create_plan(demand, resource, f"P-{demand_id}-v1")
        operation = create_operation(demand, plan, f"O-{demand_id}", stage_names)
        RESOURCES[demand_id] = resource
        PLANS[demand_id] = plan
        OPERATIONS[demand_id] = operation

    def action_register_exception(self, operation, value) -> None:
        current_stage_id = next(
            (stage.id for stage in operation.stages if stage.state == StageState.IN_EXECUTION), None
        )
        exception = LogisticsException(
            id=f"X-{operation.id}-{len(operation.exceptions) + 1}",
            type=value("type") or "não especificado",
            severity=value("severity") or "media",
            description=value("description"),
            stage_id=current_stage_id,
        )
        operation.register_exception(exception)

    def action_replan(self, demand: Demand, demand_id: str, operation, value) -> None:
        if not operation.exceptions or operation.state != OperationState.EXCEPTION:
            raise ValueError("Não há exceção pendente para replanear")

        old_plan = PLANS[demand_id]
        resource = RESOURCES[demand_id]
        new_plan = create_replanned_plan(demand, resource, f"P-{demand_id}-v{old_plan.version + 1}", old_plan)
        PLANS[demand_id] = new_plan

        exception = operation.exceptions[-1]
        decision_text = value("description")
        if exception.state == ExceptionState.OPEN:
            exception.evaluate(impact=decision_text, decision=decision_text)
        exception.treat(decision_text)
        operation.replan(new_plan)
        exception.close()

    @staticmethod
    def find_stage(operation, stage_id: str):
        return next(stage for stage in operation.stages if stage.id == stage_id)


if __name__ == "__main__":
    print("NEXXUS Logística: http://localhost:8000")
    HTTPServer(("0.0.0.0", 8000), App).serve_forever()
