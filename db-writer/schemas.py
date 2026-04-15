from pydantic import BaseModel
from typing import Literal, Optional

class MetaData(BaseModel):
    rov_id: str
    event_id: str
    mission_id: str

class AttitudeReading(BaseModel):
    value: float
    unit: Literal["deg"]
    timestamp: float

class AngularVelocityReading(BaseModel):
    value: float
    unit: Literal["rad/s"]
    timestamp: float

class AngularAccelReading(BaseModel):
    value: float
    unit: Literal["rad/s²"]
    timestamp: float

class AccelReading(BaseModel):
    value: float
    unit: Literal["m/s²"]
    timestamp: float

class VelocityReading(BaseModel):
    value: float
    unit: Literal["m/s"]
    timestamp: float

class DepthReading(BaseModel):
    value: float
    unit: Literal["m"]
    timestamp: float

class TempReading(BaseModel):
    value: float
    unit: Literal["C"]
    timestamp: float

class PressureReading(BaseModel):
    value: float
    unit: Literal["Pa"]
    timestamp: float

class GroveWaterReading(BaseModel):
    value: float
    unit: Literal["?"]
    timestamp: float

class ActuatorReading(BaseModel):
    value: float
    unit: Literal["%"]
    timestamp: float

class TelemetryData(BaseModel):
    timestamp: float
    id: str
    
    attitude_x: Optional[AttitudeReading] = None
    attitude_y: Optional[AttitudeReading] = None
    attitude_z: Optional[AttitudeReading] = None
    
    angular_velocity_x: Optional[AngularVelocityReading] = None
    angular_velocity_y: Optional[AngularVelocityReading] = None
    angular_velocity_z: Optional[AngularVelocityReading] = None
    
    angular_acceleration_x: Optional[AngularAccelReading] = None
    angular_acceleration_y: Optional[AngularAccelReading] = None
    angular_acceleration_z: Optional[AngularAccelReading] = None
    
    acceleration_x: Optional[AccelReading] = None
    acceleration_y: Optional[AccelReading] = None
    acceleration_z: Optional[AccelReading] = None
    
    velocity_x: Optional[VelocityReading] = None
    velocity_y: Optional[VelocityReading] = None
    velocity_z: Optional[VelocityReading] = None
    
    depth: Optional[DepthReading] = None
    ambient_temperature: Optional[TempReading] = None
    internal_temperature: Optional[TempReading] = None
    ambient_pressure: Optional[PressureReading] = None
    
    cardinal_direction: Optional[str] = None
    grove_water_sensor: Optional[GroveWaterReading] = None
    
    actuator_1: Optional[ActuatorReading] = None
    actuator_2: Optional[ActuatorReading] = None
    actuator_3: Optional[ActuatorReading] = None
    actuator_4: Optional[ActuatorReading] = None
    actuator_5: Optional[ActuatorReading] = None
    actuator_6: Optional[ActuatorReading] = None

class ValidatedPayload(BaseModel):
    meta: MetaData
    telemetry: TelemetryData