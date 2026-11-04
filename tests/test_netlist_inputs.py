"""Reject unsupported sizing and preserve topology during input expansion."""
import pytest

from src.utility import config
from src.utility.entity import Circuit, Model
from src.utility.util import parse_netlist, read_cdl_file


@pytest.fixture(autouse=True)
def initialize_config():
    config.init()


def netlist(parameters="nfin=2", model="nmos"):
    return f".SUBCKT X A Y VDD VSS\nM0 Y A VSS VSS {model} w=46n l=16n {parameters}\n.ENDS X\n"


@pytest.mark.parametrize("value", ["1", "3", "13", "0", "-2", "2.5", "nan", "inf", "{fins}", None])
def test_invalid_fin_count_is_rejected_without_adding_devices(value):
    circuit = Circuit()
    with pytest.raises(ValueError, match=r"M0.nfin"):
        parse_netlist(netlist("" if value is None else f"nfin={value}"), circuit)
    assert not circuit.transistors
    assert all(not net.connected_transistors for net in circuit.nets.values())


@pytest.mark.parametrize("nfin,m,count", [(2, 1, 1), (4, 1, 2), (2, 4, 4), (6, 3, 9), (2, "2.0", 2)])
def test_parallel_multiplicity_and_fins_expand_exactly(nfin, m, count):
    circuit = Circuit()
    parse_netlist(netlist(f"nfin={nfin} m={m} nf=1 par=1"), circuit)
    assert len(circuit.transistors) == count
    assert sum(t.nfin for t in circuit.transistors.values()) == nfin * float(m)
    assert set(circuit.transistors) == {f"M0S{i}" for i in range(count)}
    for transistor in circuit.transistors.values():
        assert transistor.m == 1
        assert transistor.model == Model.NMOS
        assert transistor.gate == "A"
        assert {transistor.source, transistor.drain} == {"Y", "VSS"}
        assert transistor.bulk == "VSS"
        for pin, net in transistor.terminals.items():
            if pin != "bulk":  # Well connections are not routed as signal pins.
                assert (transistor.name, pin) in circuit.nets[net].connected_transistors


@pytest.mark.parametrize("parameters", ["m=0", "m=-1", "m=1.5", "m={copies}", "nf=3", "par=4", "nf=0"])
def test_unsupported_multiplicity_is_rejected(parameters):
    circuit = Circuit()
    with pytest.raises(ValueError, match=r"M0\.(m|nf|par)"):
        parse_netlist(netlist(f"nfin=2 {parameters}"), circuit)
    assert not circuit.transistors


@pytest.mark.parametrize("name,polarity", [
    ("nmos_rvt", Model.NMOS), ("pmos_lvt", Model.PMOS),
    ("asap7_nfet", Model.NMOS), ("ASAP7_NFET", Model.NMOS),
    ("asap7_pfet", Model.PMOS), ("NMOS", Model.NMOS),
    ("gf180mcu_fd_pr__nfet_03v3", Model.NMOS),
])
def test_polarity_uses_model_tokens(name, polarity):
    circuit = Circuit()
    parse_netlist(netlist(model=name), circuit)
    assert circuit.transistors["M0S0"].model == polarity


@pytest.mark.parametrize("name", ["unknown", "np_device", "pmos_nfet", "snapdragon"])
def test_unknown_or_ambiguous_models_are_rejected(name):
    circuit = Circuit()
    with pytest.raises(ValueError, match="Unknown or ambiguous"):
        parse_netlist(netlist(model=name), circuit)
    assert not circuit.transistors


def test_explicit_model_mapping_reaches_file_parser(tmp_path):
    path = tmp_path / "custom.cdl"
    path.write_text(netlist(model="CUSTOM_DEVICE"))
    circuit, = read_cdl_file(path, model_map={"custom_device": Model.NMOS})
    assert circuit.transistors["M0S0"].model == Model.NMOS


def test_direct_circuit_api_validates_before_mutating():
    circuit = Circuit(model_map={"custom": "nmos"})
    args = dict(name="M0", source="VSS", gate="A", drain="Y", bulk="VSS", model="custom", w="46n", l="16n")
    for invalid in (dict(nfin=1), dict(nfin=2, nf=2), dict(nfin=2, m=0)):
        with pytest.raises(ValueError):
            circuit.add_transistor(**args, **invalid)
        assert not circuit.transistors and not circuit.nets
    circuit.add_transistor(**args, nfin=2, m=2)
    assert len(circuit.transistors) == 2
