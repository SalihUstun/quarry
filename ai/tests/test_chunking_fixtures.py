from scripts.generate_chunking_fixtures import main


def test_shared_chunking_fixtures_match_python_reference() -> None:
    assert main(["--check"]) == 0
