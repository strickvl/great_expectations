from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import List, Tuple

from great_expectations.core.expectation_configuration import ExpectationConfiguration
from great_expectations.core.expectation_diagnostics.expectation_test_data_cases import (
    ExpectationTestDataCases,
)
from great_expectations.core.expectation_diagnostics.supporting_types import (
    AugmentedLibraryMetadata,
    ExpectationDescriptionDiagnostics,
    ExpectationDiagnosticCheckMessage,
    ExpectationDiagnosticMaturityMessages,
    ExpectationErrorDiagnostics,
    ExpectationExecutionEngineDiagnostics,
    ExpectationMetricDiagnostics,
    ExpectationRendererDiagnostics,
    ExpectationTestDiagnostics,
)
from great_expectations.core.util import convert_to_json_serializable
from great_expectations.types import SerializableDictDot

# from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class ExpectationDiagnostics(SerializableDictDot):
    """An immutable object created by Expectation.run_diagnostics.
    It contains information introspected from the Expectation class, in formats that can be renderered at the command line, and by the Gallery.

    It has three external-facing use cases:

    1. `ExpectationDiagnostics.to_dict()` creates the JSON object that populates the Gallery.
    2. `ExpectationDiagnostics.generate_checklist()` creates CLI-type string output to assist with development.
    """

    # This object is taken directly from the Expectation class, without modification
    examples: List[ExpectationTestDataCases]
    gallery_examples: List[ExpectationTestDataCases]

    # These objects are derived from the Expectation class
    # They're a combination of direct introspection of existing properties,
    # and instantiating the Expectation with test data and actually executing
    # methods.
    # For example, we can verify the existence of certain Renderers through
    # introspection alone, but in order to see what they return, we need to
    # instantiate the Expectation and actually run the method.

    library_metadata: AugmentedLibraryMetadata
    description: ExpectationDescriptionDiagnostics
    execution_engines: ExpectationExecutionEngineDiagnostics

    renderers: List[ExpectationRendererDiagnostics]
    metrics: List[ExpectationMetricDiagnostics]
    tests: List[ExpectationTestDiagnostics]
    errors: List[ExpectationErrorDiagnostics]
    maturity_checklist: ExpectationDiagnosticMaturityMessages

    def to_json_dict(self) -> dict:
        result = convert_to_json_serializable(data=asdict(self))
        result["execution_engines_list"] = sorted(
            [
                engine
                for engine, _bool in result["execution_engines"].items()
                if _bool is True
            ]
        )
        return result

    def generate_checklist(self) -> str:
        """Generates the checklist in CLI-appropriate string format."""
        return self._convert_checks_into_output_message(
            self.description["camel_name"],
            self.maturity_checklist,
        )

    @staticmethod
    def _check_library_metadata(
        library_metadata: AugmentedLibraryMetadata,
    ) -> ExpectationDiagnosticCheckMessage:
        """Check whether the Expectation has a library_metadata object"""

        return ExpectationDiagnosticCheckMessage(
            message="Has a library_metadata object",
            passed=library_metadata.library_metadata_passed_checks,
        )

    @staticmethod
    def _check_docstring(
        description: ExpectationDescriptionDiagnostics,
    ) -> ExpectationDiagnosticCheckMessage:
        """Check whether the Expectation has an informative docstring"""

        message = "Has a docstring, including a one-line short description"
        if "short_description" in description:
            short_description = description["short_description"]
        else:
            short_description = None
        if short_description not in {"", "\n", "TODO: Add a docstring here", None}:
            return ExpectationDiagnosticCheckMessage(
                message=message,
                sub_messages=[
                    {
                        "message": f'"{short_description}"',
                        "passed": True,
                    }
                ],
                passed=True,
            )

        else:
            return ExpectationDiagnosticCheckMessage(
                message=message,
                passed=False,
            )

    @classmethod
    def _check_example_cases(
        cls,
        examples: List[ExpectationTestDataCases],
        tests: List[ExpectationTestDiagnostics],
    ) -> ExpectationDiagnosticCheckMessage:
        """Check whether this Expectation has at least one positive and negative example case (and all test cases return the expected output)"""

        message = "Has at least one positive and negative example case, and all test cases pass"
        (
            positive_case_count,
            negative_case_count,
        ) = cls._count_positive_and_negative_example_cases(examples)
        unexpected_case_count = cls._count_unexpected_test_cases(tests)
        passed = (
            (positive_case_count > 0)
            and (negative_case_count > 0)
            and (unexpected_case_count == 0)
        )
        print(positive_case_count, negative_case_count, unexpected_case_count, passed)
        return ExpectationDiagnosticCheckMessage(
            message=message,
            passed=passed,
        )

    @staticmethod
    def _check_core_logic_for_at_least_one_execution_engine(
        test_results: List[ExpectationTestDiagnostics],
    ) -> ExpectationDiagnosticCheckMessage:
        """Check whether core logic for this Expectation exists and passes tests on at least one Execution Engine"""

        sub_messages = []
        backend_results = defaultdict(list)
        passed = False
        message = "Has core logic and passes tests on at least one Execution Engine"

        for test_result in test_results:
            backend_results[test_result.backend].append(test_result.test_passed)

        if backends_passing_all_tests := [
            backend for backend, value in backend_results.items() if all(value)
        ]:
            passed = True
            backend = backends_passing_all_tests[0]
            sub_messages.append(
                {
                    "message": f"All {len(backend_results[backend])} tests for {backend} are passing",
                    "passed": True,
                }
            )

        if not test_results:
            sub_messages.append(
                {
                    "message": "There are no test results",
                    "passed": False,
                }
            )

        return ExpectationDiagnosticCheckMessage(
            message=message,
            passed=passed,
            sub_messages=sub_messages,
        )

    @staticmethod
    def _check_core_logic_for_all_applicable_execution_engines(
        test_results: List[ExpectationTestDiagnostics],
    ) -> ExpectationDiagnosticCheckMessage:
        """Check whether core logic for this Expectation exists and passes tests on all applicable Execution Engines"""

        backends_passing_all_tests = []
        backends_failing_any_tests = []
        failing_names = []
        backend_results = defaultdict(list)
        message = "Has core logic that passes tests for all applicable Execution Engines and SQL dialects"
        for test_result in test_results:
            backend_results[test_result.backend].append(test_result.test_passed)
            if test_result.test_passed is False:
                failing_names.append(test_result.test_title)

        for backend, value in backend_results.items():
            if all(value):
                backends_passing_all_tests.append(backend)
            else:
                backends_failing_any_tests.append(backend)

        passed = bool(backends_passing_all_tests and not backends_failing_any_tests)
        sub_messages = [
            {
                "message": f"All {len(backend_results[backend])} tests for {backend} are passing",
                "passed": True,
            }
            for backend in backends_passing_all_tests
        ]
        for backend in backends_failing_any_tests:
            num_tests = len(backend_results[backend])
            num_passing = backend_results[backend].count(True)
            sub_messages.append(
                {
                    "message": f"Only {num_passing} / {num_tests} tests for {backend} are passing",
                    "passed": False,
                }
            )

        if failing_names:
            sub_messages.append(
                {
                    "message": f"Failing: {', '.join(failing_names)}",
                    "passed": False,
                }
            )

        if not test_results:
            sub_messages.append(
                {
                    "message": "There are no test results",
                    "passed": False,
                }
            )

        return ExpectationDiagnosticCheckMessage(
            message=message,
            passed=passed,
            sub_messages=sub_messages,
        )

    @staticmethod
    def _count_positive_and_negative_example_cases(
        examples: List[ExpectationTestDataCases],
    ) -> Tuple[int, int]:
        """Scans examples and returns a 2-ple with the numbers of cases with success == True and success == False"""

        positive_cases: int = 0
        negative_cases: int = 0

        for test_data_cases in examples:
            for test in test_data_cases["tests"]:
                success = test["output"].get("success")
                if success is True:
                    positive_cases += 1
                elif success is False:
                    negative_cases += 1
        return positive_cases, negative_cases

    @staticmethod
    def _count_unexpected_test_cases(
        test_diagnostics: ExpectationTestDiagnostics,
    ) -> int:
        """Scans test_diagnostics and returns the number of cases that did not pass."""

        unexpected_cases: int = 0

        for test in test_diagnostics:
            passed = test["test_passed"] is True
            if not passed:
                unexpected_cases += 1

        return unexpected_cases

    @staticmethod
    def _convert_checks_into_output_message(
        class_name: str, maturity_messages: ExpectationDiagnosticMaturityMessages
    ) -> str:
        """Converts a list of checks into an output string (potentially nested), with ✔ to indicate checks that passed."""

        output_message = f"Completeness checklist for {class_name}:"

        checks = (
            maturity_messages.experimental
            + maturity_messages.beta
            + maturity_messages.production
        )

        for check in checks:
            if check["passed"]:
                output_message += f"\n ✔ {check['message']}"
            else:
                output_message += f"\n   {check['message']}"

            if "sub_messages" in check:
                for sub_message in check["sub_messages"]:
                    if sub_message["passed"]:
                        output_message += f"\n    ✔ {sub_message['message']}"
                    else:
                        output_message += f"\n      {sub_message['message']}"
        output_message += "\n"

        return output_message

    @staticmethod
    def _check_input_validation(
        expectation_instance,
        examples: List[ExpectationTestDataCases],
    ) -> ExpectationDiagnosticCheckMessage:
        """Check that the validate_configuration method returns True"""
        passed = False
        sub_messages = []
        try:
            first_test = examples[0]["tests"][0]
        except IndexError:
            sub_messages.append(
                {
                    "message": "No example found to get kwargs for ExpectationConfiguration",
                    "passed": passed,
                }
            )
        else:
            if "validate_configuration" not in expectation_instance.__class__.__dict__:
                sub_messages.append(
                    {
                        "message": "No validate_configuration method defined",
                        "passed": passed,
                    }
                )
            else:
                expectation_config = ExpectationConfiguration(
                    expectation_type=expectation_instance.expectation_type,
                    kwargs=first_test.input,
                )
                passed = expectation_instance.validate_configuration(expectation_config)

        return ExpectationDiagnosticCheckMessage(
            message="Has basic input validation and type checking",
            passed=passed,
            sub_messages=sub_messages,
        )

    @staticmethod
    def _check_renderer_methods(
        expectation_instance,
    ) -> ExpectationDiagnosticCheckMessage:
        """Check if all statment renderers are defined"""
        # For now, don't include the "question" and "descriptive" types since they are so
        # sparsely implemented
        # all_renderer_types = {"diagnostic", "prescriptive", "question", "descriptive"}
        all_renderer_types = {"diagnostic", "prescriptive"}
        renderer_names = [
            name
            for name in dir(expectation_instance)
            if name.endswith("renderer") and name.startswith("_")
        ]
        renderer_types = {name.split("_")[1] for name in renderer_names}
        passed = renderer_types - {"question", "descriptive"} == all_renderer_types
        return ExpectationDiagnosticCheckMessage(
            # message="Has all four statement Renderers: question, descriptive, prescriptive, diagnostic",
            message="Has both statement Renderers: prescriptive and diagnostic",
            passed=passed,
        )

    @staticmethod
    def _check_linting(expectation_instance) -> ExpectationDiagnosticCheckMessage:
        """Check if linting checks pass for Expectation"""
        # TODO: Perform linting checks instead of just giving thumbs down
        return ExpectationDiagnosticCheckMessage(
            message="Passes all linting checks",
            passed=False,
        )

    @staticmethod
    def _check_full_test_suite(
        library_metadata: AugmentedLibraryMetadata,
    ) -> ExpectationDiagnosticCheckMessage:
        """Check library_metadata to see if Expectation has a full test suite"""
        return ExpectationDiagnosticCheckMessage(
            message="Has a full suite of tests, as determined by a code owner",
            passed=library_metadata.has_full_test_suite,
        )

    @staticmethod
    def _check_manual_code_review(
        library_metadata: AugmentedLibraryMetadata,
    ) -> ExpectationDiagnosticCheckMessage:
        """Check library_metadata to see if a manual code review has been performed"""
        return ExpectationDiagnosticCheckMessage(
            message="Has passed a manual review by a code owner for code standards and style guides",
            passed=library_metadata.manually_reviewed_code,
        )
