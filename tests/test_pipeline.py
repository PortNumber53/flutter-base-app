import unittest

from automation import pipeline


class ArtifactNameTests(unittest.TestCase):
    def test_android_artifact_name(self) -> None:
        self.assertEqual(
            pipeline.artifact_name("android", "dev", "abc123"), "wrapper-dev-abc123.aab"
        )

    def test_ios_artifact_name(self) -> None:
        self.assertEqual(
            pipeline.artifact_name("ios", "prod", "ff00aa"), "wrapper-prod-ff00aa.ipa"
        )

    def test_unknown_platform_raises(self) -> None:
        with self.assertRaises(ValueError):
            pipeline.artifact_name("web", "dev", "sha")


class PipelinePlanTests(unittest.TestCase):
    def test_plan_structure(self) -> None:
        plan = pipeline.build_pipeline_plan("stg", sha="deadbeef")
        self.assertEqual(plan.flavor, "stg")
        self.assertEqual(plan.sha, "deadbeef")
        stage_names = [stage.name for stage in plan.stages]
        self.assertEqual(stage_names, ["verification", "android", "ios"])

    def test_commands_include_expected_parameters(self) -> None:
        plan = pipeline.build_pipeline_plan("prod", sha="cafebabe")
        android_command = plan.stages[1].steps[0].command
        ios_command = plan.stages[2].steps[0].command

        self.assertIn("flavor:prod", android_command)
        self.assertIn("output:wrapper-prod-cafebabe.aab", android_command)
        self.assertIn("flavor:prod", ios_command)
        self.assertIn("output:wrapper-prod-cafebabe.ipa", ios_command)


class PlansForFlavorTests(unittest.TestCase):
    def test_multiple_flavors(self) -> None:
        plans = pipeline.plan_for_flavors(("dev", "prod"), sha="112233")
        self.assertEqual(len(plans), 2)
        flavors = [plan.flavor for plan in plans]
        self.assertEqual(flavors, ["dev", "prod"])
        for plan in plans:
            self.assertEqual(plan.sha, "112233")


if __name__ == "__main__":
    unittest.main()
