from datetime import datetime
from dataclasses import dataclass

@dataclass(frozen=True)
class FlightRecord:
    client_id: int
    airline_id: int
    date: datetime
    start_city: str
    end_city: str