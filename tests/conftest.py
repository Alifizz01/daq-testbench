import threading

import pytest
import pyvisa

from daqsim.server import DaqModel, serve

# Illustrative limits, not taken from any vendor datasheet.
SPEC = {"dc_abs": 200e-6, "dc_rel": 100e-6, "noise_rms": 100e-6, "crosstalk_db": -90.0}


def pytest_addoption(parser):
    parser.addoption("--visa-resource", default=None,
                     help="VISA resource of a real instrument; default starts the simulator")
    parser.addoption("--inject-fault", default=None, metavar="KIND:CH",
                     help="simulator only, e.g. STUCK:3 or DROP:2")


def pytest_collection_modifyitems(config, items):
    real = config.getoption("--visa-resource") is not None
    for item in items:
        if real and "simulated" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="simulator-only test"))
        if not real and "hardware" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="needs --visa-resource"))


@pytest.fixture(scope="session")
def inst(request):
    resource = request.config.getoption("--visa-resource")
    srv = None
    if resource is None:
        srv = serve(DaqModel(), port=0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        resource = f"TCPIP::127.0.0.1::{srv.server_address[1]}::SOCKET"
    rm = pyvisa.ResourceManager("@py")
    i = rm.open_resource(resource, read_termination="\n", write_termination="\n", timeout=5000)
    i.write("*RST")
    fault = request.config.getoption("--inject-fault")
    if fault:
        kind, ch = fault.split(":")
        i.write(f"SIM:FAULT {kind},(@{ch})")
    yield i
    i.close()
    if srv:
        srv.shutdown()


@pytest.fixture
def channel_cfg(inst):
    """Apply range and sample settings for one test, restore defaults afterwards."""
    applied = []

    def apply(ch, rng=10.0, rate=1000, count=100):
        inst.write(f"CONF:VOLT:RANG {rng},(@{ch})")
        inst.write(f"SAMP:RATE {rate}")
        inst.write(f"SAMP:COUN {count}")
        applied.append(ch)
        err = inst.query("SYST:ERR?")
        assert err.startswith("0,"), f"instrument rejected configuration for CH{ch}: {err}"

    yield apply
    for ch in applied:
        inst.write(f"SOUR:VOLT 0,(@{ch})")
        inst.write(f"CONF:VOLT:RANG 10,(@{ch})")


def fetch(inst, ch):
    return [float(x) for x in inst.query(f"FETC? (@{ch})").split(",")]
