"""Persistência em SQLite para o NEXXUS Logística.

Cada agregado (Demanda, Recurso, Plano, Operação, Medição) é guardado como
JSON numa tabela própria, indexado pela chave usada em app.py (o id da
demanda). Isto evita perder todo o estado ao reiniciar o processo, sem
introduzir infraestrutura nova: sqlite3 é biblioteca padrão do Python, e a
base de dados é um único ficheiro local.
"""

import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

from nexxus_logistica import (
    Allocation,
    Capacity,
    CapacityState,
    Demand,
    DemandState,
    Event,
    ExceptionState,
    LogisticsException,
    LogisticsUnit,
    Operation,
    OperationState,
    Plan,
    Point,
    Resource,
    Stage,
    StageState,
)

DB_PATH = os.environ.get("NEXXUS_DB_PATH", str(Path(__file__).parent / "nexxus.db"))

_TABLES = ("demands", "resources", "plans", "operations", "measurements")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        for table in _TABLES:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (key TEXT PRIMARY KEY, data TEXT NOT NULL)")


def _json_default(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)} is not JSON serializable")


def _save(table: str, key: str, data: dict) -> None:
    payload = json.dumps(data, default=_json_default)
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO {table} (key, data) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
            (key, payload),
        )


def _load_all(table: str) -> dict:
    with _connect() as conn:
        rows = conn.execute(f"SELECT key, data FROM {table}").fetchall()
    return {key: json.loads(data) for key, data in rows}


def _load_typed(table: str, decoder) -> dict:
    """Carrega uma tabela aplicando `decoder` a cada linha, ignorando registos
    que já não correspondem ao formato atual (ex.: gravados por uma versão
    anterior do modelo, antes de um campo novo ter sido acrescentado) em vez
    de rebentar o arranque de toda a aplicação por causa de uma linha antiga."""
    result = {}
    for key, raw in _load_all(table).items():
        try:
            result[key] = decoder(raw)
        except (KeyError, ValueError, TypeError) as exc:
            print(f"[storage] a ignorar registo incompatível em '{table}' (key={key}): {exc}")
    return result


def _parse_dt(value):
    return datetime.fromisoformat(value) if value else None


# --------------------------------------------------------------- save

def save_demand(demand: Demand) -> None:
    _save("demands", demand.id, asdict(demand))


def save_resource(key: str, resource: Resource) -> None:
    _save("resources", key, asdict(resource))


def save_plan(key: str, plan: Plan) -> None:
    _save("plans", key, asdict(plan))


def save_operation(key: str, operation: Operation) -> None:
    _save("operations", key, asdict(operation))


def save_measurement(key: str, measurement: dict) -> None:
    _save("measurements", key, measurement)


# --------------------------------------------------------------- load

def _demand_from_dict(d: dict) -> Demand:
    return Demand(
        id=d["id"],
        unit=LogisticsUnit(**d["unit"]),
        origin=Point(**d["origin"]),
        destination=Point(**d["destination"]),
        client=d.get("client", ""),
        description=d.get("description", ""),
        deadline=_parse_dt(d.get("deadline")),
        state=DemandState(d["state"]),
        conditions=d.get("conditions", []),
        notes=d.get("notes", ""),
    )


def _plan_from_dict(d: dict) -> Plan:
    a = d["allocation"]
    c = d["capacity"]
    capacity = Capacity(
        id=c["id"],
        resource_id=c["resource_id"],
        quantity=c["quantity"],
        unit=c.get("unit", "kg"),
        state=CapacityState(c["state"]),
    )
    allocation = Allocation(
        resource_id=a["resource_id"],
        capacity_id=a["capacity_id"],
        quantity=a["quantity"],
        state=a.get("state", "allocated"),
        start=_parse_dt(a.get("start")),
        end=_parse_dt(a.get("end")),
    )
    return Plan(
        id=d["id"],
        demand_id=d["demand_id"],
        allocation=allocation,
        capacity=capacity,
        version=d.get("version", 1),
        state=d.get("state", "active"),
        planned_start=_parse_dt(d.get("planned_start")),
        planned_end=_parse_dt(d.get("planned_end")),
    )


def _stage_from_dict(d: dict) -> Stage:
    return Stage(
        id=d["id"],
        name=d["name"],
        sequence=d["sequence"],
        state=StageState(d["state"]),
        resource_id=d.get("resource_id"),
        planned_start=_parse_dt(d.get("planned_start")),
        planned_end=_parse_dt(d.get("planned_end")),
        actual_start=_parse_dt(d.get("actual_start")),
        actual_end=_parse_dt(d.get("actual_end")),
    )


def _event_from_dict(d: dict) -> Event:
    return Event(
        id=d["id"],
        type=d["type"],
        timestamp=_parse_dt(d["timestamp"]),
        description=d.get("description", ""),
        stage_id=d.get("stage_id"),
    )


def _exception_from_dict(d: dict) -> LogisticsException:
    return LogisticsException(
        id=d["id"],
        type=d["type"],
        severity=d["severity"],
        description=d["description"],
        source_event_id=d.get("source_event_id"),
        stage_id=d.get("stage_id"),
        impact=d.get("impact"),
        decision=d.get("decision"),
        treatment=d.get("treatment"),
        state=ExceptionState(d["state"]),
    )


def _operation_from_dict(d: dict) -> Operation:
    return Operation(
        id=d["id"],
        demand_id=d["demand_id"],
        plan_id=d["plan_id"],
        stages=[_stage_from_dict(s) for s in d["stages"]],
        state=OperationState(d["state"]),
        events=[_event_from_dict(e) for e in d.get("events", [])],
        exceptions=[_exception_from_dict(e) for e in d.get("exceptions", [])],
        result=d.get("result"),
        evidence=d.get("evidence"),
    )


def load_demands() -> dict:
    return _load_typed("demands", _demand_from_dict)


def load_resources() -> dict:
    return _load_typed("resources", lambda value: Resource(**value))


def load_plans() -> dict:
    return _load_typed("plans", _plan_from_dict)


def load_operations() -> dict:
    return _load_typed("operations", _operation_from_dict)


def load_measurements() -> dict:
    return _load_all("measurements")
