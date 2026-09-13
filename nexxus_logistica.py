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
@dataclass
class Event:
    id:str; type:str; timestamp:datetime; description:str=""; stage_id:str|None=None
@dataclass
class LogisticsException:
    id:str; type:str; severity:str; impact:str; source_event_id:str|None=None; stage_id:str|None=None; decision:str|None=None; treatment:str|None=None; state:ExceptionState=ExceptionState.OPEN
@dataclass
class Operation:
    id:str; demand_id:str; plan_id:str; stages:list[Stage]; state:OperationState=OperationState.PLANNED; events:list[Event]=field(default_factory=list); exceptions:list[LogisticsException]=field(default_factory=list); result:str|None=None; evidence:str|None=None

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

def create_operation(demand,plan,operation_id):
    if plan.demand_id!=demand.id: raise ValueError("Plan does not belong to demand")
    rid=plan.allocation.resource_id
    return Operation(operation_id,demand.id,plan.id,[Stage(f"{operation_id}-S1","pickup",1,resource_id=rid),Stage(f"{operation_id}-S2","transport",2,resource_id=rid),Stage(f"{operation_id}-S3","delivery",3,resource_id=rid)])

def measure_operation(planned_quantity,actual_quantity,planned_duration_hours,actual_duration_hours):
    return {"planned_quantity":planned_quantity,"actual_quantity":actual_quantity,"quantity_deviation":actual_quantity-planned_quantity,"planned_duration_hours":planned_duration_hours,"actual_duration_hours":actual_duration_hours,"duration_deviation_hours":actual_duration_hours-planned_duration_hours}
