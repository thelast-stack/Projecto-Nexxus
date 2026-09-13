"""Núcleo de domínio do NEXXUS Logística.

Implementa o ciclo mínimo definido no Core Logística:
Demanda -> Plano -> Operação (com Etapas) -> Execução -> Exceção/Replaneamento
-> Resultado -> Medição.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DemandState(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    PLANNED = "planned"
    IN_EXECUTION = "in_execution"
    COMPLETED = "completed"


class OperationState(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    PREPARED = "prepared"
    IN_EXECUTION = "in_execution"
    COMPLETED = "completed"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"


class StageState(str, Enum):
    PENDING = "pending"
    PREPARED = "prepared"
    IN_EXECUTION = "in_execution"
    COMPLETED = "completed"
    EXCEPTION = "exception"


class ExceptionState(str, Enum):
    OPEN = "open"
    EVALUATED = "evaluated"
    TREATED = "treated"
    CLOSED = "closed"


class CapacityState(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    IN_USE = "in_use"
    RELEASED = "released"


@dataclass
class LogisticsUnit:
    id: str
    quantity: float
    unit: str = "kg"


@dataclass
class Point:
    id: str
    name: str


@dataclass
class Resource:
    id: str
    name: str
    capacity: float
    unit: str = "kg"
    available: bool = True


@dataclass
class Demand:
    id: str
    unit: LogisticsUnit
    origin: Point
    destination: Point
    client: str = ""
    description: str = ""
    deadline: datetime | None = None
    state: DemandState = DemandState.RECEIVED
    conditions: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Capacity:
    id: str
    resource_id: str
    quantity: float
    unit: str = "kg"
    state: CapacityState = CapacityState.AVAILABLE

    def reserve(self) -> None:
        if self.state != CapacityState.AVAILABLE:
            raise ValueError("Capacity must be available to be reserved")
        self.state = CapacityState.RESERVED

    def use(self) -> None:
        if self.state != CapacityState.RESERVED:
            raise ValueError("Capacity must be reserved before use")
        self.state = CapacityState.IN_USE

    def release(self) -> None:
        if self.state != CapacityState.IN_USE:
            raise ValueError("Capacity must be in use before releasing")
        self.state = CapacityState.RELEASED


@dataclass
class Allocation:
    resource_id: str
    capacity_id: str
    quantity: float
    state: str = "allocated"
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class Plan:
    id: str
    demand_id: str
    allocation: Allocation
    capacity: Capacity
    version: int = 1
    state: str = "active"
    planned_start: datetime | None = None
    planned_end: datetime | None = None


@dataclass
class Stage:
    id: str
    name: str
    sequence: int
    state: StageState = StageState.PENDING
    resource_id: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None

    def prepare(self) -> None:
        if self.state != StageState.PENDING:
            raise ValueError("Stage must be pending to be prepared")
        self.state = StageState.PREPARED

    def start(self) -> None:
        if self.state != StageState.PREPARED:
            raise ValueError("Stage must be prepared before starting")
        self.state = StageState.IN_EXECUTION
        self.actual_start = datetime.now()

    def complete(self) -> None:
        if self.state != StageState.IN_EXECUTION:
            raise ValueError("Stage must be in execution to complete")
        self.state = StageState.COMPLETED
        self.actual_end = datetime.now()


@dataclass
class Event:
    id: str
    type: str
    timestamp: datetime
    description: str = ""
    stage_id: str | None = None


@dataclass
class LogisticsException:
    id: str
    type: str
    severity: str
    description: str
    source_event_id: str | None = None
    stage_id: str | None = None
    impact: str | None = None
    decision: str | None = None
    treatment: str | None = None
    state: ExceptionState = ExceptionState.OPEN

    def evaluate(self, impact: str, decision: str) -> None:
        if self.state != ExceptionState.OPEN:
            raise ValueError("Exception must be open to be evaluated")
        self.impact = impact
        self.decision = decision
        self.state = ExceptionState.EVALUATED

    def treat(self, treatment: str) -> None:
        if self.state != ExceptionState.EVALUATED:
            raise ValueError("Exception must be evaluated before treatment")
        self.treatment = treatment
        self.state = ExceptionState.TREATED

    def close(self) -> None:
        if self.state != ExceptionState.TREATED:
            raise ValueError("Exception must be treated before closing")
        self.state = ExceptionState.CLOSED


@dataclass
class Operation:
    id: str
    demand_id: str
    plan_id: str
    stages: list[Stage]
    state: OperationState = OperationState.PLANNED
    events: list[Event] = field(default_factory=list)
    exceptions: list[LogisticsException] = field(default_factory=list)
    result: str | None = None
    evidence: str | None = None

    def prepare(self) -> None:
        if self.state != OperationState.PLANNED:
            raise ValueError("Operation must be planned before preparing")
        for stage in self.stages:
            stage.prepare()
        self.state = OperationState.PREPARED
        self.register_event("operation_prepared")

    def start(self) -> None:
        if self.state != OperationState.PREPARED:
            raise ValueError("Operation must be prepared before starting")
        self.state = OperationState.IN_EXECUTION
        self.register_event("operation_started")

    def register_event(self, event_type: str, description: str = "", stage_id: str | None = None) -> Event:
        event = Event(f"E-{len(self.events) + 1:03d}", event_type, datetime.now(), description, stage_id)
        self.events.append(event)
        return event

    def register_exception(self, exception: LogisticsException) -> None:
        if self.state != OperationState.IN_EXECUTION:
            raise ValueError("Exception can only be registered during execution")
        self.exceptions.append(exception)
        self.state = OperationState.EXCEPTION
        self.register_event("exception", exception.description, exception.stage_id)

    def replan(self, plan: Plan) -> None:
        if self.state != OperationState.EXCEPTION:
            raise ValueError("Replanning requires an exception state")
        if plan.demand_id != self.demand_id:
            raise ValueError("Plan does not belong to demand")
        self.plan_id = plan.id
        self.state = OperationState.IN_EXECUTION
        self.register_event("replanned", f"plan={plan.id}, version={plan.version}")

    def complete(self, result: str, evidence: str) -> None:
        if self.state != OperationState.IN_EXECUTION:
            raise ValueError("Operation must be in execution to complete")
        self.result = result
        self.evidence = evidence
        self.state = OperationState.COMPLETED
        self.register_event("operation_completed", result)


def validate_demand(demand: Demand) -> None:
    if demand.unit.quantity <= 0:
        raise ValueError("Logistics unit quantity must be greater than zero")
    if demand.origin.id == demand.destination.id:
        raise ValueError("Origin and destination must be different")
    demand.state = DemandState.VALIDATED


def _check_resource_for_demand(resource: Resource, demand: Demand) -> None:
    """Validações de recurso partilhadas entre o primeiro plano e o replaneamento."""
    if not resource.available:
        raise ValueError("Resource is not available")
    if resource.unit != demand.unit.unit:
        raise ValueError("Resource capacity unit does not match logistics unit")
    if resource.capacity < demand.unit.quantity:
        raise ValueError("Resource capacity is insufficient")


def create_plan(
    demand: Demand,
    resource: Resource,
    plan_id: str,
    version: int = 1,
    planned_start: datetime | None = None,
    planned_end: datetime | None = None,
) -> Plan:
    """Cria o primeiro plano de uma demanda. Exige que a demanda esteja validada."""
    if demand.state != DemandState.VALIDATED:
        raise ValueError("Demand must be validated before planning")
    _check_resource_for_demand(resource, demand)
    capacity = Capacity(f"CAP-{plan_id}", resource.id, demand.unit.quantity, resource.unit)
    capacity.reserve()
    demand.state = DemandState.PLANNED
    return Plan(
        id=plan_id,
        demand_id=demand.id,
        allocation=Allocation(resource.id, capacity.id, demand.unit.quantity),
        capacity=capacity,
        version=version,
        planned_start=planned_start,
        planned_end=planned_end,
    )


def create_replanned_plan(
    demand: Demand,
    resource: Resource,
    plan_id: str,
    previous_plan: Plan,
    planned_start: datetime | None = None,
    planned_end: datetime | None = None,
) -> Plan:
    """Cria uma nova versão do plano durante o tratamento de uma exceção.

    Ao contrário de create_plan, NÃO exige que a demanda esteja em
    DemandState.VALIDATED, porque nesta altura a demanda já avançou para
    PLANNED ou IN_EXECUTION. Esta era a causa do bug em que qualquer
    tentativa de replaneamento a partir do app.py rebentava com
    "Demand must be validated before planning".

    A capacidade do plano anterior é liberada e uma nova capacidade é
    reservada e colocada imediatamente em uso, porque o replaneamento
    retoma a execução de imediato (não volta a ficar apenas "planeada").
    """
    if previous_plan.demand_id != demand.id:
        raise ValueError("Previous plan does not belong to demand")
    _check_resource_for_demand(resource, demand)
    if previous_plan.capacity.state == CapacityState.IN_USE:
        previous_plan.capacity.release()

    new_capacity = Capacity(f"CAP-{plan_id}", resource.id, demand.unit.quantity, resource.unit)
    new_capacity.reserve()
    new_capacity.use()

    return Plan(
        id=plan_id,
        demand_id=demand.id,
        allocation=Allocation(resource.id, new_capacity.id, demand.unit.quantity),
        capacity=new_capacity,
        version=previous_plan.version + 1,
        planned_start=planned_start,
        planned_end=planned_end,
    )


def start_operation(operation: Operation, plan: Plan) -> None:
    """Inicia a operação e coloca a capacidade reservada em uso."""
    operation.start()
    plan.capacity.use()


def complete_operation(operation: Operation, plan: Plan, result: str, evidence: str) -> None:
    """Conclui a operação e liberta a capacidade que estava em uso."""
    operation.complete(result, evidence)
    plan.capacity.release()


def create_operation(demand: Demand, plan: Plan, operation_id: str) -> Operation:
    if plan.demand_id != demand.id:
        raise ValueError("Plan does not belong to demand")
    resource_id = plan.allocation.resource_id
    stages = [
        Stage(f"{operation_id}-S1", "pickup", 1, resource_id=resource_id),
        Stage(f"{operation_id}-S2", "transport", 2, resource_id=resource_id),
        Stage(f"{operation_id}-S3", "delivery", 3, resource_id=resource_id),
    ]
    return Operation(id=operation_id, demand_id=demand.id, plan_id=plan.id, stages=stages)


def measure_operation(
    planned_quantity: float,
    actual_quantity: float,
    planned_duration_hours: float,
    actual_duration_hours: float,
) -> dict:
    return {
        "planned_quantity": planned_quantity,
        "actual_quantity": actual_quantity,
        "quantity_deviation": actual_quantity - planned_quantity,
        "planned_duration_hours": planned_duration_hours,
        "actual_duration_hours": actual_duration_hours,
        "duration_deviation_hours": actual_duration_hours - planned_duration_hours,
    }


def run_demo() -> dict:
    """Executa o cenário mínimo de ponta a ponta, incluindo replaneamento real."""
    demand = Demand(
        id="D-001",
        unit=LogisticsUnit("U-001", 20_000),
        origin=Point("A", "Origem A"),
        destination=Point("B", "Destino B"),
        client="Cliente ABC",
        description="Farinha de trigo",
    )
    resource = Resource("R-001", "Veículo 01", 25_000)

    validate_demand(demand)
    plan = create_plan(demand, resource, "P-001", planned_start=datetime.now())
    operation = create_operation(demand, plan, "O-001")
    operation.prepare()
    start_operation(operation, plan)
    demand.state = DemandState.IN_EXECUTION

    operation.stages[0].start()
    operation.stages[0].complete()
    departure_event = operation.register_event("departure", "Saída da origem A", operation.stages[1].id)

    exception = LogisticsException(
        id="X-001",
        type="atraso",
        severity="media",
        description="Avaria do veículo durante o transporte",
        source_event_id=departure_event.id,
        stage_id=operation.stages[1].id,
    )
    operation.register_exception(exception)
    exception.evaluate(impact="atraso na entrega de aproximadamente 2 horas", decision="substituir veículo e retomar")
    exception.treat("veículo substituído; retomada a etapa de transporte")

    # create_replanned_plan já não exige que a demanda esteja VALIDATED --
    # é chamada com a demanda em PLANNED/IN_EXECUTION, como acontece de facto.
    replanned = create_replanned_plan(demand, resource, "P-002", plan, planned_start=datetime.now())
    operation.replan(replanned)
    exception.close()

    for stage in operation.stages[1:]:
        stage.start()
        stage.complete()

    operation.register_event("arrival", "Chegada ao destino B", operation.stages[2].id)
    complete_operation(operation, replanned, "20 000 kg entregues", "POD-001")
    demand.state = DemandState.COMPLETED

    measurement = measure_operation(20_000, 20_000, 8, 9.5)
    return {
        "demand": demand,
        "plan": plan,
        "replanned_plan": replanned,
        "operation": operation,
        "exception": exception,
        "measurement": measurement,
    }


if __name__ == "__main__":
    result = run_demo()
    print(result["operation"].state.value)
    print(result["measurement"])
