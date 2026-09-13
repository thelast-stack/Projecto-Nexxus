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
    create_operation,
    create_plan,
    create_replanned_plan,
    measure_operation,
    validate_demand,
)


def make_demand(quantity=20_000):
    return Demand(
        id="D-001",
        unit=LogisticsUnit("U-001", quantity),
        origin=Point("A", "Origem A"),
        destination=Point("B", "Destino B"),
        client="Cliente ABC",
        description="Farinha de trigo",
    )


def test_end_to_end_flow_with_stages_exception_and_replanning():
    demand = make_demand()
    resource = Resource("R-001", "Veículo 01", 25_000)

    validate_demand(demand)
    plan = create_plan(demand, resource, "P-001")
    operation = create_operation(demand, plan, "O-001")

    assert operation.state == OperationState.PLANNED
    operation.prepare()
    assert operation.state == OperationState.PREPARED
    assert all(stage.state == StageState.PREPARED for stage in operation.stages)

    operation.start()
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
    replanned = create_replanned_plan(demand, resource, "P-002", plan)
    assert replanned.version == 2

    operation.replan(replanned)
    exception.close()

    for stage in operation.stages[1:]:
        stage.start()
        stage.complete()

    operation.complete("20 t entregues", "POD-001")
    demand.state = DemandState.COMPLETED

    assert operation.state == OperationState.COMPLETED
    assert all(stage.state == StageState.COMPLETED for stage in operation.stages)
    assert operation.result == "20 t entregues"
    assert operation.evidence == "POD-001"


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

    replanned = create_replanned_plan(demand, resource, "P-002", plan)
    assert replanned.version == 2
    assert replanned.demand_id == demand.id


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
    operation = create_operation(demand, plan, "O-001")

    try:
        operation.start()
        assert False, "Expected operation to require PREPARED state"
    except ValueError:
        pass


def test_measurement_calculates_deviation():
    measurement = measure_operation(20_000, 19_500, 8, 9.5)

    assert measurement["quantity_deviation"] == -500
    assert measurement["duration_deviation_hours"] == 1.5
