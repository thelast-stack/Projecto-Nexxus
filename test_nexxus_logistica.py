from nexxus_logistica import (
    Demand,
    DemandState,
    LogisticsUnit,
    Point,
    Resource,
    OperationState,
    create_operation,
    create_plan,
    measure_operation,
    validate_demand,
)


def make_demand(quantity=20_000):
    return Demand(
        id="D-001",
        unit=LogisticsUnit("U-001", quantity),
        origin=Point("A", "Origem A"),
        destination=Point("B", "Destino B"),
    )


def test_end_to_end_flow_with_exception_and_replanning():
    demand = make_demand()
    resource = Resource("R-001", "Veículo 01", 25_000)

    validate_demand(demand)
    plan = create_plan(demand, resource, "P-001")
    operation = create_operation(demand, plan, "O-001")

    operation.start()
    operation.register_event("departure")
    operation.register_exception("Atraso")
    operation.replan("P-002")
    operation.complete("20_000 kg entregues", "POD-001")
    demand.state = DemandState.COMPLETED

    assert demand.state == DemandState.COMPLETED
    assert operation.state == OperationState.COMPLETED
    assert operation.plan_id == "P-002"
    assert len(operation.exceptions) == 1
    assert operation.result == "20_000 kg entregues"
    assert operation.evidence == "POD-001"


def test_capacity_must_be_sufficient():
    demand = make_demand(20_000)
    resource = Resource("R-001", "Veículo 01", 15_000)
    validate_demand(demand)

    try:
        create_plan(demand, resource, "P-001")
        assert False, "Expected insufficient capacity error"
    except ValueError as exc:
        assert "capacity" in str(exc).lower()


def test_measurement_calculates_deviation():
    measurement = measure_operation(20_000, 19_500, 8, 9.5)

    assert measurement["quantity_deviation"] == -500
    assert measurement["duration_deviation_hours"] == 1.5
