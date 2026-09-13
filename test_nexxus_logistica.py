from nexxus_logistica import *


def make_demand(quantity=20000):
    return Demand("D-001", LogisticsUnit("U-001", quantity), Point("A", "Origem A"), Point("B", "Destino B"))


def test_end_to_end_flow_with_exception_replanning_and_stages():
    demand=make_demand(); resource=Resource("R-001","Veículo 01",25000)
    validate_demand(demand); plan=create_plan(demand,resource,"P-001"); op=create_operation(demand,plan,"O-001")
    assert op.state==OperationState.PLANNED
    op.prepare(); assert op.state==OperationState.PREPARED
    assert all(s.state==StageState.PREPARED for s in op.stages)
    op.start(); op.stages[0].start(); op.stages[0].complete()
    event=op.register_event("departure","Saída",op.stages[1].id)
    ex=LogisticsException("X-001","atraso","media","prazo",event.id,op.stages[1].id)
    op.register_exception(ex); assert ex.state==ExceptionState.OPEN; assert op.state==OperationState.EXCEPTION
    ex.evaluate("atraso","replanear"); ex.treat("novo plano")
    replanned=Plan("P-002",demand.id,Allocation(resource.id,20000),2,"active",datetime.now())
    op.replan(replanned); ex.close(); assert replanned.version==2
    for s in op.stages[1:]: s.start(); s.complete()
    op.complete("20 t entregues","POD-001"); demand.state=DemandState.COMPLETED
    assert op.state==OperationState.COMPLETED
    assert all(s.state==StageState.COMPLETED for s in op.stages)
    assert op.result=="20 t entregues" and op.evidence=="POD-001"


def test_capacity_must_be_sufficient():
    demand=make_demand(); resource=Resource("R-001","Veículo 01",15000); validate_demand(demand)
    try: create_plan(demand,resource,"P-001"); assert False
    except ValueError as exc: assert "capacity" in str(exc).lower()


def test_measurement_calculates_deviation():
    m=measure_operation(20000,19500,8,9.5)
    assert m["quantity_deviation"]==-500; assert m["duration_deviation_hours"]==1.5


def test_operation_cannot_start_before_prepared():
    demand=make_demand(); validate_demand(demand); plan=create_plan(demand,Resource("R","Veículo",25000),"P-001"); op=create_operation(demand,plan,"O-001")
    try: op.start(); assert False
    except ValueError: pass
