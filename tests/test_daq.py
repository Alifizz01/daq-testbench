import math
import statistics

import pytest

from conftest import SPEC, fetch

CHANNELS = range(1, 9)
RANGES = [(1.0, 0.9), (10.0, 9.0), (10.0, -5.0), (100.0, 50.0)]


def test_identity(inst):
    idn = inst.query("*IDN?").split(",")
    assert len(idn) == 4, f"*IDN? should have 4 fields, got {idn}"


@pytest.mark.parametrize("ch", CHANNELS)
@pytest.mark.parametrize("rng,v_true", RANGES)
def test_dc_accuracy(inst, channel_cfg, ch, rng, v_true):
    channel_cfg(ch, rng=rng)
    inst.write(f"SOUR:VOLT {v_true},(@{ch})")
    mean = statistics.fmean(fetch(inst, ch))
    limit = SPEC["dc_abs"] + SPEC["dc_rel"] * abs(v_true)
    err = mean - v_true
    assert abs(err) <= limit, (
        f"CH{ch} range {rng} V: read {mean:.6f} V for {v_true} V applied, "
        f"error {err * 1e6:.1f} uV exceeds +/-{limit * 1e6:.1f} uV")


@pytest.mark.parametrize("ch", CHANNELS)
def test_noise_rms(inst, channel_cfg, ch):
    channel_cfg(ch, rng=1.0, count=500)
    inst.write(f"SOUR:VOLT 0,(@{ch})")
    rms = statistics.pstdev(fetch(inst, ch))
    assert rms <= SPEC["noise_rms"], (
        f"CH{ch}: noise {rms * 1e6:.1f} uVrms > {SPEC['noise_rms'] * 1e6:.0f} uVrms")
    assert rms > 0, f"CH{ch}: zero noise, channel is likely stuck"


@pytest.mark.parametrize("victim", CHANNELS)
def test_crosstalk(inst, channel_cfg, victim):
    aggressor = victim % 8 + 1
    channel_cfg(victim, rng=1.0, count=500)
    channel_cfg(aggressor, rng=10.0)
    inst.write(f"SOUR:VOLT 0,(@{victim})")
    base = statistics.fmean(fetch(inst, victim))
    inst.write(f"SOUR:VOLT 9,(@{aggressor})")
    hot = statistics.fmean(fetch(inst, victim))
    db = 20 * math.log10(max(abs(hot - base), 1e-12) / 9.0)
    assert db <= SPEC["crosstalk_db"], (
        f"CH{aggressor}->CH{victim}: crosstalk {db:.1f} dB above limit {SPEC['crosstalk_db']} dB")


@pytest.mark.parametrize("ch", CHANNELS)
@pytest.mark.parametrize("count", [10, 1000])
def test_sample_count_complete(inst, channel_cfg, ch, count):
    channel_cfg(ch, count=count)
    got = len(fetch(inst, ch))
    assert got == count, f"CH{ch}: expected {count} samples, got {got} ({count - got} dropped)"


def test_out_of_range_reports_overload(inst, channel_cfg):
    channel_cfg(1, rng=1.0)
    inst.write("SOUR:VOLT 5,(@1)")
    assert float(inst.query("MEAS:VOLT? (@1)")) >= 9.9e37, "5 V on 1 V range should read overload"


def test_illegal_range_rejected(inst):
    inst.write("CONF:VOLT:RANG 3,(@1)")
    assert inst.query("SYST:ERR?").startswith("-224"), "3 V range should raise -224"


@pytest.mark.simulated
@pytest.mark.parametrize("kind", ["STUCK", "DROP"])
def test_fault_injection_is_detected(inst, channel_cfg, kind):
    """Self-test: inject a fault on CH8 and confirm the checks used above would flag it."""
    channel_cfg(8, rng=1.0, count=200)
    inst.write(f"SIM:FAULT {kind},(@8)")
    try:
        s = fetch(inst, 8)
        if kind == "STUCK":
            assert statistics.pstdev(s) == 0, "stuck channel should show zero spread"
        else:
            assert len(s) < 200, "drop fault should lose samples"
    finally:
        inst.write("SIM:FAULT NONE,(@8)")


@pytest.mark.hardware
def test_real_instrument_identity(inst):
    assert "SIMDAQ" not in inst.query("*IDN?"), "pointed at the simulator, not hardware"
