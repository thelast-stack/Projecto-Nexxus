from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class DemandState(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    PLANNED = "planned"
    IN_EXECUTION = "in_execution"
    COMPLETED = "completed"


class OperationState(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    IN_EXECUTION = "in_execution"
    COMPLETED = "completed"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"


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
    deadline: Optional[datetime] = None
    state: DemandState = DemandState.RECEIVED
    conditions: List[str] = field(default_factory=list)


@dataclass
class Allocation:
    resource_id: str
    quantity: float


@dataclass
class Plan:
    id: str
    demand_id: str
    allocation: Allocation
    state: str = "planned"


@dataclass
class Event:
    type: str
    timestamp: datetime
    description: str = ""


@dataclass
class Operation:
    id: str
    demand_id: str
    plan_id: str
    stages: List[str]
    state: OperationState = OperationState.CREATED
    events: List[Event] = field(default_factory=list)
    exceptions: List[str] = field(default_factory=list)
    result: Optional[str] = None
    evidence: Optional[str] = None

    def register_event(self, event_type: str, description: str = "") -> None:
        self.events.append(Event(event_type, datetime.now(), description))

    def start(self) -> None:
        if self.state not in {OperationState.CREATED, OperationState.PLANNED}:
            raise ValueError("Operation cannot start from its current state")
        self.state = OperationState.IN_EXECUTION
        self.register_event("operation_started")

    def register_exception(self, description: str) -> None:
        if self.state != OperationState.IN_EXECUTION:
            raise ValueError("Exception can only be registered during execution")
        self.exceptions.append(description)
        self.state = OperationState.EXCEPTION
        self.register_event("exception", description)

    def replan(self, plan_id: str) -> None:
        if self.state != OperationState.EXCEPTION:
            raise ValueError("Replanning requires an exception state")
        self.plan_id = plan_id
        self.state = OperationState.IN_EXECUTION
        self.register_event("replanned", f"plan={plan_id}")

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


def create_plan(demand: Demand, resource: Resource, plan_id: str) -> Plan:
    if demand.state != DemandState.VALIDATED:
        raise ValueError("Demand must be validated before planning")
    if not resource.available:
        raise ValueError("Resource is not available")
    if resource.unit != demand.unit.unit:
        raise ValueError("Resource capacity unit does not match logistics unit")
    if resource.capacity < demand.unit.quantity:
        raise ValueError("Resource capacity is insufficient")

    demand.state = DemandState.PLANNED
    return Plan(
        id=plan_id,
        demand_id=demand.id,
        allocation=Allocation(resource.id, demand.unit.quantity),
    )


def create_operation(demand: Demand, plan: Plan, operation_id: str) -> Operation:
    if plan.demand_id != demand.id:
        raise ValueError("Plan does not belong to demand")
    return Operation(
        id=operation_id,
        demand_id=demand.id,
        plan_id=plan.id,
        stages=["pickup", "transport", "delivery"],
        state=OperationState.PLANNED,
    )


def measure_operation(
    planned_quantity: float,
    actual_quantity: float,
    planned_duration_hours: float,
    actual_duration_hours: float,
) -> dict:
    quantity_deviation = actual_quantity - planned_quantity
    duration_deviation = actual_duration_hours - planned_duration_hours
    return {
        "planned_quantity": planned_quantity,
        "actual_quantity": actual_quantity,
        "quantity_deviation": quantity_deviation,
        "planned_duration_hours": planned_duration_hours,
        "actual_duration_hours": actual_duration_hours,
        "duration_deviation_hours": duration_deviation,
    }


def run_demo() -> dict:
    """Execute the minimum end-to-end logistics scenario."""
    demand = Demand(
        id="D-001",
        unit=LogisticsUnit("U-001", 20_000),
        origin=Point("A", "Origem A"),
        destination=Point("B", "Destino B"),
    )
    resource = Resource("R-001", "Veículo 01", 25_000)

    validate_demand(demand)
    plan = create_plan(demand, resource, "P-001")
    operation = create_operation(demand, plan, "O-001")
    operation.start()
    operation.register_event("departure", "Saída da origem A")
    operation.register_exception("Atraso operacional")

    replanned = Plan(
        id="P-002",
        demand_id=demand.id,
        allocation=Allocation(resource.id, demand.unit.quantity),
    )
    operation.replan(replanned.id)
    operation.register_event("arrival", "Chegada ao destino B")
    operation.complete("20_000 kg entregues", "POD-001")
    demand.state = DemandState.COMPLETED

    measurement = measure_operation(20_000, 20_000, 8, 9.5)
    return {
        "demand": demand,
        "plan": plan,
        "operation": operation,
        "measurement": measurement,
    }


if __name__ == "__main__":
    result = run_demo()
    print(result["operation"].state.value)
    print(result["measurement"])
