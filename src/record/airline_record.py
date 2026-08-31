from dataclasses import dataclass

@dataclass(frozen=True)
class AirlineRecord:
    id: int
    record_type: str
    company_name: str