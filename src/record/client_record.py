from dataclasses import dataclass

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