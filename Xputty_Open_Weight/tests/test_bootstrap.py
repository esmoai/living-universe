import importlib.util
from tools.bootstrap import supported
from tools.check_setup import check


def test_python314_is_rejected_and_supported_interpreters_are_accepted():
    assert not supported((3, 14, 0))
    assert not supported((3, 13, 0))
    assert supported((3, 11, 9))
    assert supported((3, 10, 0))


def test_missing_numpy_is_reported_before_build(monkeypatch):
    original = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name == "numpy" else original(name),
    )
    report = check()
    assert not report["ready"] and "numpy" in report["missing"]
