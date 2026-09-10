from dataclasses import dataclass
from record.record_types import RecordType

@dataclass(frozen=True)
class ClientRecord:
    id: int
    record_type: str
    name: str
    address_line_1: str
    address_line_2: str
    address_line_3: str
    city: str
    state: str
    zip_code: str
    country: str
    phone_number: str

    def __post_init__(self):
        if self.record_type != RecordType.CLIENT.value:
            raise ValueError("Client record_type must be 'client'")
