from ix_vahdat import __version__


def test_package_imports_with_version() -> None:
    assert __version__ == "0.1.0"
