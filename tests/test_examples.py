from app.examples import example_slug, save_example_artifacts
from app.main import main
from app.workflows import run_mock_workflow


def test_example_slug_uses_company_names() -> None:
    assert example_slug(["Nvidia", "AMD", "Intel"]) == "nvidia_amd_intel"
    assert example_slug(["Perplexity AI", "Mistral AI"]) == "perplexity_ai_mistral_ai"


def test_save_example_artifacts_writes_expected_files(tmp_path) -> None:
    state = run_mock_workflow(["Nvidia", "AMD", "Intel"])

    output_dir = save_example_artifacts(state, examples_dir=tmp_path)

    assert output_dir.name == "nvidia_amd_intel"
    assert (output_dir / "memo.md").read_text(encoding="utf-8").startswith("# Investment Recommendation Memo")
    assert "Nvidia" in (output_dir / "workflow_state.json").read_text(encoding="utf-8")
    assert "Identity Agent" in (output_dir / "run_log.json").read_text(encoding="utf-8")


def test_save_example_cli_defaults_to_mock(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["app.main", "--provider", "openai", "Nvidia,AMD,Intel", "--save-example"],
    )

    main()

    output_dir = tmp_path / "data" / "examples" / "nvidia_amd_intel"
    assert (output_dir / "memo.md").exists()
    assert (output_dir / "workflow_state.json").exists()


def test_cli_rejects_more_than_eight_companies(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["app.main", "--mock", ",".join(f"Company {index}" for index in range(9))],
    )

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected CLI to reject more than eight companies")
