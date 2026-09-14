"""Núcleo de domínio do NEXXUS Logística.

Implementa o ciclo mínimo definido no Core Logística:
Demanda -> Plano -> Operação (com Etapas) -> Execução -> Exceção/Replaneamento
-> Resultado -> Medição.

Cardinalidade Demanda <-> Operação
-----------------------------------
A versão anterior assumia implicitamente 1 Demanda : 1 Plano : 1 Operação, o
que não cobre dois casos comuns em logística real (auditoria do Core
Logística como Nível 2):

  1) DIVISÃO — uma demanda grande (ex.: 30t) excede a capacidade de um único
     recurso e precisa de ser servida por duas ou mais operações (dois
     veículos, duas viagens).
  2) CONSOLIDAÇÃO — várias demandas de clientes diferentes são transportadas
     juntas numa única operação (um camião, uma rota, várias entregas).

Para cobrir os dois casos sem inventar nada fora do Core Logística já
definido, o Plano e a Operação passam a referenciar uma LISTA de
`DemandAllocation` (demanda + quantidade coberta por esta operação), em vez
de um único `demand_id`. Cada Demanda guarda quanto da sua quantidade total
já foi alocada a algum plano (`allocated_quantity`) e quanto já foi
efectivamente entregue (`delivered_quantity`). Isto permite:

  - dividir uma demanda por várias operações (cada uma com uma
    `DemandAllocation` parcial para a mesma demand_id);
  - agrupar várias demandas na mesma operação (cada uma com a sua própria
    `DemandAllocation` dentro da mesma lista);

sem precisar de um conceito novo de "Manifesto" ou "Consolidação" — a lista
de alocações já é suficiente para os dois casos.
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
    # Quanto da quantidade total já foi coberto por algum plano. Fica menor
    # que unit.quantity enquanto a demanda ainda está a ser dividida por
    # várias operações (uma parte planeada, outra ainda por planear).
    allocated_quantity: float = 0.0
    # Quanto já foi efectivamente entregue (operações concluídas).
    delivered_quantity: float = 0.0

    @property
    def remaining_quantity(self) -> float:
        """Quantidade que ainda não foi coberta por nenhum plano."""
        return round(self.unit.quantity - self.allocated_quantity, 6)

    @property
    def fully_allocated(self) -> bool:
        return self.remaining_quantity <= 1e-9

    @property
    def fully_delivered(self) -> bool:
        return round(self.unit.quantity - self.delivered_quantity, 6) <= 1e-9


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
    """Alocação do lado do RECURSO: quanto da capacidade do recurso está
    comprometida com este plano (independentemente de quantas demandas o
    plano cobre)."""

    resource_id: str
    capacity_id: str
    quantity: float
    state: str = "allocated"
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class DemandAllocation:
    """Alocação do lado da DEMANDA: quanto desta demanda específica está
    coberto por um dado Plano/Operação. Uma lista destas é o que permite
    dividir uma demanda por várias operações, ou juntar várias demandas
    numa só operação."""

    demand_id: str
    quantity: float


@dataclass
class Plan:
    id: str
    allocations: list[DemandAllocation]
    allocation: Allocation
    capacity: Capacity
    version: int = 1
    state: str = "active"
    planned_start: datetime | None = None
    planned_end: datetime | None = None

    @property
    def demand_ids(self) -> list[str]:
        return [a.demand_id for a in self.allocations]

    @property
    def total_quantity(self) -> float:
        return round(sum(a.quantity for a in self.allocations), 6)


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
    location: str | None = None
    quantity: float | None = None


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
    plan_id: str
    allocations: list[DemandAllocation]
    stages: list[Stage]
    state: OperationState = OperationState.PLANNED
    events: list[Event] = field(default_factory=list)
    exceptions: list[LogisticsException] = field(default_factory=list)
    result: str | None = None
    evidence: str | None = None

    @property
    def demand_ids(self) -> list[str]:
        return [a.demand_id for a in self.allocations]

    @property
    def total_quantity(self) -> float:
        return round(sum(a.quantity for a in self.allocations), 6)

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

    def register_event(
        self,
        event_type: str,
        description: str = "",
        stage_id: str | None = None,
        location: str | None = None,
        quantity: float | None = None,
    ) -> Event:
        event = Event(f"E-{len(self.events) + 1:03d}", event_type, datetime.now(), description, stage_id, location, quantity)
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
        if set(plan.demand_ids) != set(self.demand_ids):
            raise ValueError("Plan does not cover the same demands as the operation")
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


def _as_demand_list(demands) -> list:
    """Aceita tanto uma única Demand como uma lista de Demand, para que
    chamadas de uma única demanda (o caso mais comum) não precisem de
    embrulhar tudo em listas."""
    if isinstance(demands, Demand):
        return [demands]
    demands = list(demands)
    if not demands:
        raise ValueError("At least one demand is required")
    return demands


def _check_resource_for_quantity(resource: Resource, unit: str, total_quantity: float) -> None:
    """Validações de recurso partilhadas entre o primeiro plano e o replaneamento."""
    if not resource.available:
        raise ValueError("Resource is not available")
    if resource.unit != unit:
        raise ValueError("Resource capacity unit does not match logistics unit")
    if resource.capacity < total_quantity:
        raise ValueError("Resource capacity is insufficient")


def create_plan(
    demands,
    resource: Resource,
    plan_id: str,
    quantities: dict[str, float] | None = None,
    version: int = 1,
    planned_start: datetime | None = None,
    planned_end: datetime | None = None,
) -> Plan:
    """Cria um plano cobrindo uma ou mais demandas (consolidação) e/ou uma
    parte da quantidade de cada uma (divisão).

    `demands` pode ser uma única Demand (caso comum: uma demanda, quantidade
    total) ou uma lista de Demand (consolidação). `quantities`, se indicado,
    é um mapa demand_id -> quantidade a cobrir por este plano; quando
    omitido, assume-se a quantidade restante (`remaining_quantity`) de cada
    demanda, ou seja, o comportamento anterior (uma demanda, tudo de uma
    vez) continua a funcionar sem alterações nas chamadas existentes.
    """
    demand_list = _as_demand_list(demands)
    unit = demand_list[0].unit.unit

    allocations: list[DemandAllocation] = []
    for demand in demand_list:
        if demand.state not in (DemandState.VALIDATED, DemandState.PLANNED):
            raise ValueError(f"Demand {demand.id} must be validated before planning")
        if demand.unit.unit != unit:
            raise ValueError("All demands in a plan must share the same logistics unit")

        quantity = demand.remaining_quantity if quantities is None else quantities.get(demand.id)
        if quantity is None or quantity <= 0:
            raise ValueError(f"Invalid planning quantity for demand {demand.id}")
        if quantity > demand.remaining_quantity + 1e-9:
            raise ValueError(f"Planning quantity exceeds remaining quantity for demand {demand.id}")

        allocations.append(DemandAllocation(demand.id, quantity))

    total_quantity = round(sum(a.quantity for a in allocations), 6)
    _check_resource_for_quantity(resource, unit, total_quantity)

    capacity = Capacity(f"CAP-{plan_id}", resource.id, total_quantity, resource.unit)
    capacity.reserve()

    for demand, allocation in zip(demand_list, allocations):
        demand.allocated_quantity = round(demand.allocated_quantity + allocation.quantity, 6)
        demand.state = DemandState.PLANNED

    return Plan(
        id=plan_id,
        allocations=allocations,
        allocation=Allocation(resource.id, capacity.id, total_quantity),
        capacity=capacity,
        version=version,
        planned_start=planned_start,
        planned_end=planned_end,
    )


def create_replanned_plan(
    resource: Resource,
    plan_id: str,
    previous_plan: Plan,
    planned_start: datetime | None = None,
    planned_end: datetime | None = None,
) -> Plan:
    """Cria uma nova versão do plano durante o tratamento de uma exceção.

    Cobre exactamente as mesmas demandas e quantidades do plano anterior
    (`previous_plan.allocations`) — replanear troca o recurso e/ou o
    tempo, não o que está a ser transportado. Ao contrário de create_plan,
    NÃO exige que as demandas estejam em DemandState.VALIDATED, porque a
    esta altura já avançaram para PLANNED ou IN_EXECUTION. Esta era a causa
    do bug em que qualquer tentativa de replaneamento a partir do app.py
    rebentava com "Demand must be validated before planning".

    A capacidade do plano anterior é liberada e uma nova capacidade é
    reservada e colocada imediatamente em uso, porque o replaneamento
    retoma a execução de imediato (não volta a ficar apenas "planeada").
    """
    unit = previous_plan.capacity.unit
    total_quantity = previous_plan.total_quantity
    _check_resource_for_quantity(resource, unit, total_quantity)

    if previous_plan.capacity.state == CapacityState.IN_USE:
        previous_plan.capacity.release()

    new_capacity = Capacity(f"CAP-{plan_id}", resource.id, total_quantity, unit)
    new_capacity.reserve()
    new_capacity.use()

    return Plan(
        id=plan_id,
        allocations=list(previous_plan.allocations),
        allocation=Allocation(resource.id, new_capacity.id, total_quantity),
        capacity=new_capacity,
        version=previous_plan.version + 1,
        planned_start=planned_start,
        planned_end=planned_end,
    )


def start_operation(operation: Operation, plan: Plan, demands: dict[str, Demand]) -> None:
    """Inicia a operação, coloca a capacidade reservada em uso, e avança
    para IN_EXECUTION cada demanda coberta por esta operação (uma demanda
    dividida por várias operações só muda de estado quando a primeira
    delas arranca; as restantes continuam PLANNED até arrancarem também)."""
    operation.start()
    plan.capacity.use()
    for allocation in operation.allocations:
        demand = demands.get(allocation.demand_id)
        if demand and demand.state == DemandState.PLANNED:
            demand.state = DemandState.IN_EXECUTION


def complete_operation(
    operation: Operation, plan: Plan, result: str, evidence: str, demands: dict[str, Demand]
) -> None:
    """Conclui a operação, liberta a capacidade que estava em uso, e
    contabiliza a quantidade entregue em cada demanda coberta por esta
    operação. Uma demanda só passa a COMPLETED quando TODA a sua
    quantidade tiver sido entregue — o que pode exigir mais do que uma
    operação, no caso de uma demanda dividida."""
    operation.complete(result, evidence)
    plan.capacity.release()
    for allocation in operation.allocations:
        demand = demands.get(allocation.demand_id)
        if demand is None:
            continue
        demand.delivered_quantity = round(demand.delivered_quantity + allocation.quantity, 6)
        if demand.fully_delivered:
            demand.state = DemandState.COMPLETED


def create_operation(
    plan: Plan,
    operation_id: str,
    stage_names: list[str] | None = None,
) -> Operation:
    resource_id = plan.allocation.resource_id
    names = stage_names or ["pickup", "transport", "delivery"]
    stages = [
        Stage(f"{operation_id}-S{sequence}", name, sequence, resource_id=resource_id)
        for sequence, name in enumerate(names, start=1)
    ]
    return Operation(id=operation_id, plan_id=plan.id, allocations=list(plan.allocations), stages=stages)


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
    """Executa o cenário mínimo de ponta a ponta (uma demanda, uma
    operação), incluindo replaneamento real."""
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
    operation = create_operation(plan, "O-001")
    operation.prepare()
    start_operation(operation, plan, {demand.id: demand})

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
    replanned = create_replanned_plan(resource, "P-002", plan, planned_start=datetime.now())
    operation.replan(replanned)
    exception.close()

    for stage in operation.stages[1:]:
        stage.start()
        stage.complete()

    operation.register_event("arrival", "Chegada ao destino B", operation.stages[2].id)
    complete_operation(operation, replanned, "20 000 kg entregues", "POD-001", {demand.id: demand})

    measurement = measure_operation(20_000, 20_000, 8, 9.5)
    return {
        "demand": demand,
        "plan": plan,
        "replanned_plan": replanned,
        "operation": operation,
        "exception": exception,
        "measurement": measurement,
    }


def run_demo_split() -> dict:
    """Cenário de DIVISÃO: uma demanda de 30t excede a capacidade de um
    único recurso (25t) e é servida por duas operações (dois veículos)."""
    demand = Demand(
        id="D-100",
        unit=LogisticsUnit("U-100", 30_000),
        origin=Point("A", "Fábrica Viana"),
        destination=Point("B", "Armazém Luanda"),
        client="Cliente XYZ",
        description="Cimento",
    )
    validate_demand(demand)

    truck_1 = Resource("R-101", "Camião 01", 25_000)
    truck_2 = Resource("R-102", "Camião 02", 25_000)

    plan_1 = create_plan(demand, truck_1, "P-100A", quantities={demand.id: 20_000})
    assert demand.state == DemandState.PLANNED
    assert demand.remaining_quantity == 10_000
    op_1 = create_operation(plan_1, "O-100A")

    plan_2 = create_plan(demand, truck_2, "P-100B", quantities={demand.id: 10_000})
    assert demand.fully_allocated
    op_2 = create_operation(plan_2, "O-100B")

    demands = {demand.id: demand}
    for operation, plan in ((op_1, plan_1), (op_2, plan_2)):
        operation.prepare()
        start_operation(operation, plan, demands)
        for stage in operation.stages:
            stage.start()
            stage.complete()

    # A demanda continua IN_EXECUTION até a SEGUNDA operação também concluir.
    complete_operation(op_1, plan_1, "20t entregues (viagem 1/2)", "POD-100A", demands)
    assert demand.state == DemandState.IN_EXECUTION
    complete_operation(op_2, plan_2, "10t entregues (viagem 2/2)", "POD-100B", demands)
    assert demand.state == DemandState.COMPLETED
    assert demand.fully_delivered

    return {"demand": demand, "operations": [op_1, op_2], "plans": [plan_1, plan_2]}


def run_demo_consolidation() -> dict:
    """Cenário de CONSOLIDAÇÃO: três demandas de clientes diferentes,
    todas pequenas, são transportadas juntas numa única operação (um
    camião, uma rota)."""
    origin = Point("A", "Centro de distribuição")
    destination = Point("B", "Zona industrial")

    demand_a = Demand(id="D-200", unit=LogisticsUnit("U-200", 5_000), origin=origin, destination=destination, client="Cliente A")
    demand_b = Demand(id="D-201", unit=LogisticsUnit("U-201", 8_000), origin=origin, destination=destination, client="Cliente B")
    demand_c = Demand(id="D-202", unit=LogisticsUnit("U-202", 7_000), origin=origin, destination=destination, client="Cliente C")
    for demand in (demand_a, demand_b, demand_c):
        validate_demand(demand)

    truck = Resource("R-200", "Camião consolidado", 25_000)

    plan = create_plan([demand_a, demand_b, demand_c], truck, "P-200")
    assert plan.total_quantity == 20_000
    operation = create_operation(plan, "O-200")

    demands = {d.id: d for d in (demand_a, demand_b, demand_c)}
    operation.prepare()
    start_operation(operation, plan, demands)
    for stage in operation.stages:
        stage.start()
        stage.complete()

    complete_operation(operation, plan, "3 entregas concluídas na mesma rota", "POD-200", demands)

    assert all(d.state == DemandState.COMPLETED for d in demands.values())
    return {"demands": demands, "operation": operation, "plan": plan}


if __name__ == "__main__":
    result = run_demo()
    print("run_demo:", result["operation"].state.value, result["measurement"])

    split_result = run_demo_split()
    print(
        "run_demo_split:",
        split_result["demand"].state.value,
        [op.state.value for op in split_result["operations"]],
    )

    consolidation_result = run_demo_consolidation()
    print(
        "run_demo_consolidation:",
        [d.state.value for d in consolidation_result["demands"].values()],
        consolidation_result["operation"].state.value,
    )
