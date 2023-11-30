from typing import List

import py
import pytest
from great_expectations_contrib.package import (
    Dependency,
    DomainExpert,
    GitHubUser,
    GreatExpectationsContribPackageManifest,
    Maturity,
)

from great_expectations.core.expectation_diagnostics.expectation_diagnostics import (
    ExpectationDiagnostics,
)
from great_expectations.expectations.core.expect_column_min_to_be_between import (
    ExpectColumnMinToBeBetween,
)
from great_expectations.expectations.core.expect_column_most_common_value_to_be_in_set import (
    ExpectColumnMostCommonValueToBeInSet,
)
from great_expectations.expectations.core.expect_column_stdev_to_be_between import (
    ExpectColumnStdevToBeBetween,
)


@pytest.fixture
def package() -> GreatExpectationsContribPackageManifest:
    return GreatExpectationsContribPackageManifest()


@pytest.fixture
def diagnostics() -> List[ExpectationDiagnostics]:
    expectations = [
        ExpectColumnMinToBeBetween,
        ExpectColumnMostCommonValueToBeInSet,
        ExpectColumnStdevToBeBetween,
    ]
    return list(map(lambda e: e().run_diagnostics(), expectations))


def test_update_expectations(
    package: GreatExpectationsContribPackageManifest,
    diagnostics: List[ExpectationDiagnostics],
):
    package._update_expectations(diagnostics)

    assert package.expectation_count == 3
    assert package.expectations and all(
        isinstance(expectation, ExpectationDiagnostics)
        for expectation in package.expectations
    )
    assert (
        package.status and package.status.production == 3 and package.status.total == 3
    )
    assert package.maturity == Maturity.PRODUCTION


def test_update_dependencies_with_valid_path(
    tmpdir: py.path.local, package: GreatExpectationsContribPackageManifest
):
    requirements_file = tmpdir.mkdir("tmp").join("requirements.txt")
    contents = """
altair>=4.0.0,<5  # package
Click>=7.1.2  # package
mistune>=0.8.4,<2.0.0  # package
numpy>=1.14.1  # package
ruamel.yaml>=0.16,<0.17.18  # package
    """
    requirements_file.write(contents)

    package._update_dependencies(str(requirements_file))
    assert package.dependencies == [
        Dependency(
            text="altair", link="https://pypi.org/project/altair", version="<5, >=4.0.0"
        ),
        Dependency(
            text="Click", link="https://pypi.org/project/Click", version=">=7.1.2"
        ),
        Dependency(
            text="mistune",
            link="https://pypi.org/project/mistune",
            version="<2.0.0, >=0.8.4",
        ),
        Dependency(
            text="numpy", link="https://pypi.org/project/numpy", version=">=1.14.1"
        ),
        Dependency(
            text="ruamel.yaml",
            link="https://pypi.org/project/ruamel.yaml",
            version="<0.17.18, >=0.16",
        ),
    ]


def test_update_dependencies_with_invalid_path_exits_early(
    package: GreatExpectationsContribPackageManifest,
):
    dependencies = [Dependency(text="my_dep", link="my_link")]
    package.dependencies = dependencies

    package._update_dependencies("my_fake_path.txt")

    # Unchanged attrs since file state is invalid
    assert package.dependencies == dependencies


def test_update_from_package_info_with_valid_path(
    tmpdir: py.path.local, package: GreatExpectationsContribPackageManifest
):
    package_info_file = tmpdir.mkdir("tmp").join("package_info.yml")
    contents = """
    """
    package_info_file.write(contents)

    package._update_from_package_info(str(package_info_file))


def test_update_from_package_info_with_valid_path_with_missing_keys(
    tmpdir: py.path.local, package: GreatExpectationsContribPackageManifest
):
    code_owners = [GitHubUser("John Doe")]
    domain_experts = [DomainExpert("Charles Dickens")]
    package.code_owners = code_owners
    package.domain_experts = domain_experts

    package_info_file = tmpdir.mkdir("tmp").join("package_info.yml")
    contents = """
    """
    package_info_file.write(contents)

    package._update_from_package_info(str(package_info_file))

    # Unchanged attrs since file state is invalid
    assert package.code_owners == code_owners
    assert package.domain_experts == domain_experts


def test_update_from_package_info_with_invalid_path_exits_early(
    package: GreatExpectationsContribPackageManifest,
):
    code_owners = [GitHubUser("John Doe")]
    domain_experts = [DomainExpert("Charles Dickens")]
    package.code_owners = code_owners
    package.domain_experts = domain_experts

    package._update_from_package_info("my_fake_path.yml")

    # Unchanged attrs since file state is invalid
    assert package.code_owners == code_owners
    assert package.domain_experts == domain_experts
