from dataclasses import dataclass
from src.record.record_types import RecordType

@dataclass(frozen=True)
class AirlineRecord:
    id: int
    record_type: str
    company_name: str

    def __post_init__(self):
        if self.record_type != RecordType.AIRLINE.value:
            raise ValueError("Airline record_type must be 'airline'")
