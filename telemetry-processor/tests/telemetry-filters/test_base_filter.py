"""Unit tests for filters.base_filter."""

import pytest
from filters.base_filter import BaseFilter
from common.data_interface import TelemetryData


class PassthroughFilter(BaseFilter):

    def __init__(self):
        self.calls = 0

    def apply(self, data: TelemetryData) -> TelemetryData:
        self.calls += 1
        return data

    def reset(self):
        self.calls = 0


class TestBaseFilterContract:
    def test_cannot_instantiate_abstract_base(self):
        with pytest.raises(TypeError):
            BaseFilter()
            #Ensures it raises a type error

    def test_declares_apply_and_reset_as_abstract(self):
        assert BaseFilter.__abstractmethods__ == {"apply", "reset"}
        #Checks required methods are exactly "apply" and "reset"

    def test_subclass_missing_reset_cannot_be_instantiated(self):
        class NoReset(BaseFilter):
            def apply(self, data):
                return data

        with pytest.raises(TypeError):
            NoReset()
        #Subclass that forgets one method must be rejected

    def test_subclass_missing_apply_cannot_be_instantiated(self):
        class NoApply(BaseFilter):
            def reset(self):
                pass

        with pytest.raises(TypeError):
            NoApply()
        #Same as above but reveresed 

    def test_complete_subclass_can_be_instantiated(self):
        assert isinstance(PassthroughFilter(), BaseFilter)
    #Subclass that submits both works correctly and counts as a basefilter


class TestConcreteSubclassBehaviour:
    def test_apply_returns_telemetry_data(self, sample_telemetry_data):
        f = PassthroughFilter()
        assert f.apply(sample_telemetry_data) is sample_telemetry_data
        assert f.calls == 1
    #A subclass's apply successfully takes and returns a TelemtryData 

    def test_reset_clears_state(self, sample_telemetry_data):
        f = PassthroughFilter()
        f.apply(sample_telemetry_data)
        f.reset()
        assert f.calls == 0
    #Reset puts filters back to original state

    def test_base_methods_are_callable_via_super(self, sample_telemetry_data):
        """The abstract bodies are `pass`; subclasses may delegate safely."""

        class Delegating(BaseFilter):
            def apply(self, data):
                return super().apply(data)

            def reset(self):
                return super().reset()

        f = Delegating()
        assert f.apply(sample_telemetry_data) is None
        assert f.reset() is None
    #The base class methodbodies are just pass so a subclass can safely call them and get back "None"