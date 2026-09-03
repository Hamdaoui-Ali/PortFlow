from portflow import APP_NAME


def test_package_exposes_product_name() -> None:
    """Catch a missing or incorrectly wired public package identity."""
    assert APP_NAME == "PortFlow"
