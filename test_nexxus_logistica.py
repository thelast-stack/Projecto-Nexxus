from nexxus_logistica import (
    CapacityState,
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


def make_demand(quantity=20_000, demand_id="D-001"):
    return Demand(
        id=demand_id,
        unit=LogisticsUnit(f"U-{demand_id}", quantity),
        origin=Point("A", "Origem A"),
        destination=Point("B", "Destino B"),
        client="Cliente ABC",
        description="Farinha de trigo",
    )


# --------------------------------------------------------- fluxo original (1:1:1)

def test_end_to_end_flow_with_stages_exception_and_replanning():
    demand = make_demand()
    resource = Resource("R-001", "Veículo 01", 25_000)

    validate_demand(demand)
    plan = create_plan(demand, resource, "P-001")
    operation = create_operation(plan, "O-001")

    assert operation.state == OperationState.PLANNED
    assert plan.capacity.state == CapacityState.RESERVED
    operation.prepare()
    assert operation.state == OperationState.PREPARED
    assert all(stage.state == StageState.PREPARED for stage in operation.stages)

    demands = {demand.id: demand}
    start_operation(operation, plan, demands)
    assert plan.capacity.state == CapacityState.IN_USE
    assert demand.state == DemandState.IN_EXECUTION
    operation.stages[0].start()
    operation.stages[0].complete()
    event = operation.register_event("departure", "Saída", operation.stages[1].id)

    exception = LogisticsException(
        id="X-001",
        type="atraso",
        severity="media",
        description="Avaria do veículo",
        source_event_id=event.id,
        stage_id=operation.stages[1].id,
    )
    operation.register_exception(exception)
    assert exception.state == ExceptionState.OPEN
    assert operation.state == OperationState.EXCEPTION

    exception.evaluate(impact="atraso de entrega", decision="replanear")
    exception.treat("novo plano")

    # Este é o caminho que estava partido: replanear com a mesma função que o
    # app.py usa (create_replanned_plan), não construindo o Plan manualmente.
    replanned = create_replanned_plan(resource, "P-002", plan)
    assert replanned.version == 2
    assert plan.capacity.state == CapacityState.RELEASED
    assert replanned.capacity.state == CapacityState.IN_USE

    operation.replan(replanned)
    exception.close()

    for stage in operation.stages[1:]:
        stage.start()
        stage.complete()

    complete_operation(operation, replanned, "20 t entregues", "POD-001", demands)

    assert operation.state == OperationState.COMPLETED
    assert all(stage.state == StageState.COMPLETED for stage in operation.stages)
    assert operation.result == "20 t entregues"
    assert operation.evidence == "POD-001"
    assert replanned.capacity.state == CapacityState.RELEASED
    assert demand.state == DemandState.COMPLETED
    assert demand.fully_delivered


def test_replanning_does_not_require_demand_to_be_revalidated():
    """Regressão: create_replanned_plan rebentava porque exigia
    demand.state == VALIDATED, mas create_plan já tinha avançado a demanda
    para PLANNED. Este teste garante que o replaneamento funciona depois de
    a demanda já ter sido planeada, tal como acontece no app.py real."""
    demand = make_demand()
    resource = Resource("R-001", "Veículo 01", 25_000)

    validate_demand(demand)
    plan = create_plan(demand, resource, "P-001")
    assert demand.state == DemandState.PLANNED

    replanned = create_replanned_plan(resource, "P-002", plan)
    assert replanned.version == 2
    assert replanned.demand_ids == [demand.id]


def test_capacity_must_be_sufficient():
    demand = make_demand(20_000)
    resource = Resource("R-001", "Veículo 01", 15_000)
    validate_demand(demand)

    try:
        create_plan(demand, resource, "P-001")
        assert False, "Expected insufficient capacity error"
    except ValueError as exc:
        assert "capacity" in str(exc).lower()


def test_operation_cannot_start_before_prepared():
    demand = make_demand()
    validate_demand(demand)
    plan = create_plan(demand, Resource("R-001", "Veículo 01", 25_000), "P-001")
    operation = create_operation(plan, "O-001")

    try:
        operation.start()
        assert False, "Expected operation to require PREPARED state"
    except ValueError:
        pass


def test_capacity_lifecycle_reserved_in_use_released():
    demand = make_demand()
    resource = Resource("R-001", "Veículo 01", 25_000)
    validate_demand(demand)

    plan = create_plan(demand, resource, "P-001")
    assert plan.capacity.state == CapacityState.RESERVED
    assert plan.allocation.capacity_id == plan.capacity.id

    operation = create_operation(plan, "O-001")
    operation.prepare()
    demands = {demand.id: demand}
    start_operation(operation, plan, demands)
    assert plan.capacity.state == CapacityState.IN_USE

    for stage in operation.stages:
        stage.start()
        stage.complete()

    complete_operation(operation, plan, "entregue", "POD-001", demands)
    assert plan.capacity.state == CapacityState.RELEASED


def test_measurement_calculates_deviation():
    measurement = measure_operation(20_000, 19_500, 8, 9.5)

    assert measurement["quantity_deviation"] == -500
    assert measurement["duration_deviation_hours"] == 1.5


# --------------------------------------------------------- divisão (1 demanda : N operações)

def test_demand_can_be_split_across_two_operations():
    """Cenário identificado na auditoria do Core Logística: uma demanda de
    30t excede a capacidade de um único recurso (25t) e precisa de ser
    servida por duas operações."""
    demand = make_demand(30_000, demand_id="D-100")
    validate_demand(demand)

    truck_1 = Resource("R-101", "Camião 01", 25_000)
    truck_2 = Resource("R-102", "Camião 02", 25_000)

    plan_1 = create_plan(demand, truck_1, "P-100A", quantities={demand.id: 20_000})
    assert demand.state == DemandState.PLANNED
    assert demand.allocated_quantity == 20_000
    assert demand.remaining_quantity == 10_000
    assert not demand.fully_allocated

    plan_2 = create_plan(demand, truck_2, "P-100B", quantities={demand.id: 10_000})
    assert demand.allocated_quantity == 30_000
    assert demand.fully_allocated

    op_1 = create_operation(plan_1, "O-100A")
    op_2 = create_operation(plan_2, "O-100B")
    assert op_1.demand_ids == [demand.id]
    assert op_2.demand_ids == [demand.id]

    demands = {demand.id: demand}
    for operation, plan in ((op_1, plan_1), (op_2, plan_2)):
        operation.prepare()
        start_operation(operation, plan, demands)
        for stage in operation.stages:
            stage.start()
            stage.complete()

    complete_operation(op_1, plan_1, "20t entregues", "POD-100A", demands)
    # A demanda ainda não está totalmente entregue: falta a segunda viagem.
    assert demand.state == DemandState.IN_EXECUTION
    assert not demand.fully_delivered

    complete_operation(op_2, plan_2, "10t entregues", "POD-100B", demands)
    assert demand.state == DemandState.COMPLETED
    assert demand.fully_delivered
    assert demand.delivered_quantity == 30_000


def test_cannot_plan_more_than_remaining_quantity():
    demand = make_demand(30_000, demand_id="D-101")
    validate_demand(demand)
    resource = Resource("R-101", "Camião 01", 25_000)

    create_plan(demand, resource, "P-101A", quantities={demand.id: 20_000})
    try:
        create_plan(demand, resource, "P-101B", quantities={demand.id: 20_000})
        assert False, "Expected planning quantity to exceed remaining quantity"
    except ValueError as exc:
        assert "remaining" in str(exc).lower()


# --------------------------------------------------------- consolidação (N demandas : 1 operação)

def test_multiple_demands_can_be_consolidated_into_one_operation():
    """Cenário identificado na auditoria do Core Logística: três demandas de
    clientes diferentes, transportadas juntas numa única operação."""
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
    assert set(plan.demand_ids) == {"D-200", "D-201", "D-202"}

    operation = create_operation(plan, "O-200")
    demands = {d.id: d for d in (demand_a, demand_b, demand_c)}

    operation.prepare()
    start_operation(operation, plan, demands)
    assert all(d.state == DemandState.IN_EXECUTION for d in demands.values())

    for stage in operation.stages:
        stage.start()
        stage.complete()

    complete_operation(operation, plan, "3 entregas concluídas", "POD-200", demands)

    assert all(d.state == DemandState.COMPLETED for d in demands.values())
    assert demand_a.delivered_quantity == 5_000
    assert demand_b.delivered_quantity == 8_000
    assert demand_c.delivered_quantity == 7_000


def test_consolidation_requires_matching_unit():
    demand_a = Demand(id="D-300", unit=LogisticsUnit("U-300", 5, "t"), origin=Point("A", "A"), destination=Point("B", "B"))
    demand_b = Demand(id="D-301", unit=LogisticsUnit("U-301", 5, "kg"), origin=Point("A", "A"), destination=Point("B", "B"))
    validate_demand(demand_a)
    validate_demand(demand_b)
    resource = Resource("R-300", "Camião", 100, "t")

    try:
        create_plan([demand_a, demand_b], resource, "P-300")
        assert False, "Expected unit mismatch error"
    except ValueError as exc:
        assert "unit" in str(exc).lower()


def test_consolidated_capacity_must_cover_the_sum_of_demands():
    demand_a = Demand(id="D-400", unit=LogisticsUnit("U-400", 15_000), origin=Point("A", "A"), destination=Point("B", "B"))
    demand_b = Demand(id="D-401", unit=LogisticsUnit("U-401", 15_000), origin=Point("A", "A"), destination=Point("B", "B"))
    validate_demand(demand_a)
    validate_demand(demand_b)
    resource = Resource("R-400", "Camião", 25_000)

    try:
        create_plan([demand_a, demand_b], resource, "P-400")
        assert False, "Expected insufficient capacity error"
    except ValueError as exc:
        assert "capacity" in str(exc).lower()
