import importlib.util, zipfile
from pathlib import Path


def test_distribution_excludes_private_data_and_preserves_launch_permissions(
    tmp_path, monkeypatch
):
    source = Path(__file__).resolve().parents[1] / "tools/build_packages.py"
    spec = importlib.util.spec_from_file_location("package_builder", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "VERSION").write_text("test")
    (tmp_path / "start.sh").write_text("#!/bin/sh\necho ready\n")
    (tmp_path / "server.py").write_text('print("ready")')
    (tmp_path / "storage").mkdir()
    (tmp_path / "storage/access-token").write_text("do-not-publish")
    (tmp_path / "web").mkdir()
    (tmp_path / "web/index.html").write_text("<h1>Xputty</h1>")
    artifact = module.build("linux")
    with zipfile.ZipFile(artifact["path"]) as z:
        assert not any("storage" in name for name in z.namelist())
        assert z.getinfo("Xputty_Open_Weight/start.sh").external_attr >> 16 & 0o111
        assert "Xputty_Open_Weight/server.py" in z.namelist()
        assert "FILE-MANIFEST.sha256.json" in z.namelist()
    artifact = module.build("shared-hosting")
    with zipfile.ZipFile(artifact["path"]) as z:
        assert "index.html" in z.namelist() and not any(
            "server.py" in name for name in z.namelist()
        )


def test_macos_affinity_api_is_optional(monkeypatch, tmp_path):
    # Darwin has no psutil cpu_affinity; the media processor must still run.
    import psutil
    from vox import media_processing

    class MacProcess:
        pass

    monkeypatch.setattr(psutil, "Process", MacProcess)
    monkeypatch.setattr(
        media_processing,
        "process_document",
        lambda *args: ([], {"status": "processed"}),
    )
    result = media_processing.execute(
        tmp_path / "sample.rtf", tmp_path / "out", "document", {"threads": 2}
    )
    assert result["report"]["status"] == "processed"
