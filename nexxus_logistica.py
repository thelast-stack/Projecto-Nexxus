from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class DemandState(str, Enum):
    RECEIVED="received"; VALIDATED="validated"; PLANNED="planned"; IN_EXECUTION="in_execution"; COMPLETED="completed"
class OperationState(str, Enum):
    CREATED="created"; PLANNED="planned"; PREPARED="prepared"; IN_EXECUTION="in_execution"; COMPLETED="completed"; EXCEPTION="exception"; CANCELLED="cancelled"
class StageState(str, Enum):
    PENDING="pending"; PREPARED="prepared"; IN_EXECUTION="in_execution"; COMPLETED="completed"; EXCEPTION="exception"
class ExceptionState(str, Enum):
    OPEN="open"; EVALUATED="evaluated"; TREATED="treated"; CLOSED="closed"

@dataclass
class LogisticsUnit: id:str; quantity:float; unit:str="kg"
@dataclass
class Point: id:str; name:str
@dataclass
class Resource: id:str; name:str; capacity:float; unit:str="kg"; available:bool=True
@dataclass
class Demand:
    id:str; unit:LogisticsUnit; origin:Point; destination:Point; deadline:datetime|None=None; state:DemandState=DemandState.RECEIVED; conditions:list[str]=field(default_factory=list)
@dataclass
class Allocation:
    resource_id:str; quantity:float; state:str="allocated"; start:datetime|None=None; end:datetime|None=None
@dataclass
class Plan:
    id:str; demand_id:str; allocation:Allocation; version:int=1; state:str="active"; planned_start:datetime|None=None; planned_end:datetime|None=None
@dataclass
class Stage:
    id:str; name:str; sequence:int; state:StageState=StageState.PENDING; resource_id:str|None=None; planned_start:datetime|None=None; planned_end:datetime|None=None; actual_start:datetime|None=None; actual_end:datetime|None=None
    def prepare(self):
        if self.state!=StageState.PENDING: raise ValueError("Stage must be pending")
        self.state=StageState.PREPARED
    def start(self):
        if self.state!=StageState.PREPARED: raise ValueError("Stage must be prepared")
        self.state=StageState.IN_EXECUTION; self.actual_start=datetime.now()
    def complete(self):
        if self.state!=StageState.IN_EXECUTION: raise ValueError("Stage must be in execution")
        self.state=StageState.COMPLETED; self.actual_end=datetime.now()
@dataclass
class Event:
    id:str; type:str; timestamp:datetime; description:str=""; stage_id:str|None=None
@dataclass
class LogisticsException:
    id:str; type:str; severity:str; impact:str; source_event_id:str|None=None; stage_id:str|None=None; decision:str|None=None; treatment:str|None=None; state:ExceptionState=ExceptionState.OPEN
    def evaluate(self,impact,decision): self.impact=impact; self.decision=decision; self.state=ExceptionState.EVALUATED
    def treat(self,treatment):
        if self.state!=ExceptionState.EVALUATED: raise ValueError("Exception must be evaluated")
        self.treatment=treatment; self.state=ExceptionState.TREATED
    def close(self):
        if self.state!=ExceptionState.TREATED: raise ValueError("Exception must be treated")
        self.state=ExceptionState.CLOSED
@dataclass
class Operation:
    id:str; demand_id:str; plan_id:str; stages:list[Stage]; state:OperationState=OperationState.PLANNED; events:list[Event]=field(default_factory=list); exceptions:list[LogisticsException]=field(default_factory=list); result:str|None=None; evidence:str|None=None
    def prepare(self):
        if self.state!=OperationState.PLANNED: raise ValueError("Operation must be planned")
        for s in self.stages: s.prepare()
        self.state=OperationState.PREPARED; self.register_event("operation_prepared")
    def start(self):
        if self.state!=OperationState.PREPARED: raise ValueError("Operation must be prepared")
        self.state=OperationState.IN_EXECUTION; self.register_event("operation_started")
    def register_event(self,event_type,description="",stage_id=None):
        e=Event(f"E-{len(self.events)+1:03d}",event_type,datetime.now(),description,stage_id); self.events.append(e); return e
    def register_exception(self,exception):
        if self.state!=OperationState.IN_EXECUTION: raise ValueError("Exception requires execution")
        self.exceptions.append(exception); self.state=OperationState.EXCEPTION; self.register_event("exception",exception.type,exception.stage_id)
    def replan(self,plan):
        if self.state!=OperationState.EXCEPTION: raise ValueError("Replanning requires exception")
        if plan.demand_id!=self.demand_id: raise ValueError("Plan does not belong to demand")
        self.plan_id=plan.id; self.state=OperationState.IN_EXECUTION; self.register_event("replanned",f"plan={plan.id}, version={plan.version}")
    def complete(self,result,evidence):
        if self.state!=OperationState.IN_EXECUTION: raise ValueError("Operation must be in execution")
        self.result=result; self.evidence=evidence; self.state=OperationState.COMPLETED; self.register_event("operation_completed",result)

def validate_demand(demand):
    if demand.unit.quantity<=0: raise ValueError("Logistics unit quantity must be greater than zero")
    if demand.origin.id==demand.destination.id: raise ValueError("Origin and destination must be different")
    demand.state=DemandState.VALIDATED

def create_plan(demand,resource,plan_id,version=1,planned_start=None,planned_end=None):
    if demand.state!=DemandState.VALIDATED: raise ValueError("Demand must be validated before planning")
    if not resource.available: raise ValueError("Resource is not available")
    if resource.unit!=demand.unit.unit: raise ValueError("Resource capacity unit does not match logistics unit")
    if resource.capacity<demand.unit.quantity: raise ValueError("Resource capacity is insufficient")
    demand.state=DemandState.PLANNED
    return Plan(plan_id,demand.id,Allocation(resource.id,demand.unit.quantity),version,"active",planned_start,planned_end)

def create_replanned_plan(demand,resource,plan_id,previous_plan,planned_start=None,planned_end=None):
    return create_plan(demand,resource,plan_id,previous_plan.version+1,planned_start,planned_end)

def create_operation(demand,plan,operation_id):
    if plan.demand_id!=demand.id: raise ValueError("Plan does not belong to demand")
    rid=plan.allocation.resource_id
    stages=[Stage(f"{operation_id}-S1","pickup",1,resource_id=rid),Stage(f"{operation_id}-S2","transport",2,resource_id=rid),Stage(f"{operation_id}-S3","delivery",3,resource_id=rid)]
    return Operation(operation_id,demand.id,plan.id,stages)

def measure_operation(planned_quantity,actual_quantity,planned_duration_hours,actual_duration_hours):
    return {"planned_quantity":planned_quantity,"actual_quantity":actual_quantity,"quantity_deviation":actual_quantity-planned_quantity,"planned_duration_hours":planned_duration_hours,"actual_duration_hours":actual_duration_hours,"duration_deviation_hours":actual_duration_hours-planned_duration_hours}

def run_demo():
    demand=Demand("D-001",LogisticsUnit("U-001",20000),Point("A","Origem A"),Point("B","Destino B")); resource=Resource("R-001","Veículo 01",25000)
    validate_demand(demand); plan=create_plan(demand,resource,"P-001",planned_start=datetime.now()); op=create_operation(demand,plan,"O-001"); op.prepare(); op.start()
    op.stages[0].start(); op.stages[0].complete(); event=op.register_event("departure","Saída da origem A",op.stages[1].id)
    ex=LogisticsException("X-001","atraso","media","impacto no prazo",event.id,op.stages[1].id); op.register_exception(ex); ex.evaluate("atraso de entrega","replanear"); ex.treat("ajustar plano")
    replanned=Plan("P-002",demand.id,Allocation(resource.id,demand.unit.quantity),2,"active",datetime.now()); op.replan(replanned); ex.close()
    for s in op.stages[1:]: s.start(); s.complete()
    op.register_event("arrival","Chegada ao destino B",op.stages[2].id); op.complete("20_000 kg entregues","POD-001"); demand.state=DemandState.COMPLETED
    return {"demand":demand,"plan":plan,"replanned":replanned,"operation":op,"measurement":measure_operation(20000,20000,8,9.5)}
