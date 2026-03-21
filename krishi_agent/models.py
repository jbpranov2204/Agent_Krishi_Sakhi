from dataclasses import dataclass


@dataclass
class FarmerInput:
    location: str
    crop_type: str
    land_size: float
    irrigation: bool
    experience_level: str
