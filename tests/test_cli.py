import io
import unittest
from contextlib import redirect_stdout

from automation import cli


class CliRenderTests(unittest.TestCase):
    def test_rendered_plan_lists_stages_and_steps(self) -> None:
        plan = cli.plan_for_flavors(("dev",), sha="123abc")[0]
        output = cli.render_plan(plan)
        self.assertIn("Flavor: dev (sha: 123abc)", output)
        self.assertIn("Stage: verification", output)
        self.assertIn("Stage: android", output)
        self.assertIn("Stage: ios", output)
        self.assertIn("flutter analyze", output)
        self.assertIn("bundle exec fastlane android build", output)

    def test_main_prints_plan_when_not_executing(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = cli.main(["--flavors", "prod", "--sha", "f00"])
        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Flavor: prod (sha: f00)", output)
        self.assertIn("bundle exec fastlane ios build", output)


if __name__ == "__main__":
    unittest.main()
