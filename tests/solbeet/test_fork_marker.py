# Solbeet fork: the marker module and the package version agree.
from importlib.metadata import version

from parlant import solbeet


def test_that_the_package_version_is_the_fork_version() -> None:
    assert version("parlant") == solbeet.FORK_VERSION
    assert solbeet.FORK_VERSION.split("+")[0] == solbeet.UPSTREAM_BASE.lstrip("v")
