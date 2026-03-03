from typing import Type

from ..tester import Tester, Test
from ..specs import TestSpecs


class JsTest(Test):
    def __init__(self, tester, result):
        """
        Initialize a JavaScript test created by tester.

        The result was created after running Jest.
        """
        self._test_name = result["name"]
        self.status = result["status"]
        self.message = result["message"]
        super().__init__(tester)

    @property
    def test_name(self) -> str:
        """The name of this test"""
        return self._test_name

    @Test.run_decorator
    def run(self) -> str:
        """
        Return a json string containing all test result information.
        """
        if self.status == "passed":
            return self.passed(message=self.message)
        elif self.status == "failed":
            return self.failed(message=self.message)
        else:
            return self.error(message=self.message)


class JsTester(Tester):
    def __init__(
        self,
        specs: TestSpecs,
        test_class: Type[JsTest] = JsTest,
        resource_settings: list[tuple[int, tuple[int, int]]] | None = None,
    ) -> None:
        """
        Initialize a JavaScript tester using the specifications in specs.

        This tester will create tests of type test_class.
        """
        super().__init__(specs, test_class, resource_settings=resource_settings)

    
    @Tester.run_decorator
    def run(self) -> None:
       raise NotImplementedError(
           "todo"
       )