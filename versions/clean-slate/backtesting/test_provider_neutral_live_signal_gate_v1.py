from backtesting.provider_neutral_live_signal_gate_v1 import LiveSignalGateV1

def test_signal_gate_requires_warmup():
    gate = LiveSignalGateV1()
    assert gate.evaluate(2)["status"] == "WARMUP_REQUIRED"
    assert gate.evaluate(30)["signal_generation_permitted"] is True
