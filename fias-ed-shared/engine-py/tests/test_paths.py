from fias_ed_engine import paths


def test_shared_root_contains_expected_dirs():
    for d in (paths.RULES_DIR, paths.SCHEMAS_DIR, paths.CONFORMANCE_DIR,
              paths.SCIENTIFIC_CONFIG_DIR, paths.DESIGN_TOKENS_DIR):
        assert d.parent == paths.SHARED_ROOT
    assert paths.SHARED_ROOT.name == "fias-ed-shared"


def test_external_dirs_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("FIAS_ED_EXPERIMENTS_DIR", str(tmp_path))
    monkeypatch.setenv("FIAS_ED_QTI_SYSTEM_DIR", str(tmp_path))
    assert paths.experiments_dir() == tmp_path
    assert paths.qti_system_dir() == tmp_path
