from dataclasses import dataclass, field

from .vector_data import Vector3


@dataclass
class ROVData:
    attitude: Vector3 = field(default_factory=Vector3)
    angular_acceleration: Vector3 = field(default_factory=Vector3)
    angular_velocity: Vector3 = field(default_factory=Vector3)
    acceleration: Vector3 = field(default_factory=Vector3)
    velocity: Vector3 = field(default_factory=Vector3)
    depth: float = 0.0
    ambient_temperature: float = 25.0
    ambient_pressure: float = 101.3
    internal_temperature: float = 30.0
    cardinal_direction: float = 0.0
    grove_water_sensor: int = 0
    actuator_1: float = 0.0
    actuator_2: float = 0.0
    actuator_3: float = 0.0
    actuator_4: float = 0.0
    actuator_5: float = 0.0
    actuator_6: float = 0.0
