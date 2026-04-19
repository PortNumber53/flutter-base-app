"""Tests for the module scaffolding tool."""

import json
import tempfile
from pathlib import Path
import unittest

from automation.create_module import (
    ModuleConfig,
    create_module_structure,
    generate_module_descriptor,
    generate_pubspec,
    generate_readme,
    to_camel_case,
    to_pascal_case,
)


class TestHelpers(unittest.TestCase):
    def test_to_pascal_case(self):
        self.assertEqual(to_pascal_case("blog"), "Blog")
        self.assertEqual(to_pascal_case("blog_post"), "BlogPost")
        self.assertEqual(to_pascal_case("user_profile_settings"), "UserProfileSettings")

    def test_to_camel_case(self):
        self.assertEqual(to_camel_case("blog"), "blog")
        self.assertEqual(to_camel_case("blog_post"), "blogPost")
        self.assertEqual(to_camel_case("user_profile"), "userProfile")


class TestModuleConfig(unittest.TestCase):
    def test_module_id_extraction(self):
        config = ModuleConfig("module_blog", "minimal", [], [])
        self.assertEqual(config.module_id, "blog")

        config2 = ModuleConfig("blog", "minimal", [], [])
        self.assertEqual(config2.module_id, "blog")

    def test_class_name_generation(self):
        config = ModuleConfig("module_blog_post", "minimal", [], [])
        self.assertEqual(config.class_name, "BlogPostModule")

    def test_package_name(self):
        config = ModuleConfig("module_blog", "minimal", [], [])
        self.assertEqual(config.package_name, "module_blog")


class TestGenerateModuleDescriptor(unittest.TestCase):
    def test_basic_descriptor(self):
        config = ModuleConfig(
            name="module_blog",
            template="minimal",
            routes=["/blog"],
            gates=["blog.view"],
        )

        code = generate_module_descriptor(config)

        self.assertIn("class BlogModule extends ModuleDescriptor", code)
        self.assertIn("id => 'blog'", code)
        self.assertIn("version => '1.0.0'", code)
        self.assertIn("route: '/blog'", code)
        self.assertIn("gates: ['blog.view']", code)

    def test_empty_routes(self):
        config = ModuleConfig(
            name="module_test",
            template="minimal",
            routes=[],
            gates=[],
        )

        code = generate_module_descriptor(config)

        self.assertIn("// Add routes here", code)
        self.assertIn("// Add navigation entries here", code)


class TestGeneratePubspec(unittest.TestCase):
    def test_pubspec_generation(self):
        config = ModuleConfig(
            name="module_blog",
            template="minimal",
            routes=[],
            gates=[],
            version="1.2.3",
        )

        pubspec = generate_pubspec(config)

        self.assertIn("name: module_blog", pubspec)
        self.assertIn("version: 1.2.3", pubspec)
        self.assertIn("module_sdk", pubspec)


class TestGenerateReadme(unittest.TestCase):
    def test_readme_generation(self):
        config = ModuleConfig(
            name="module_blog",
            template="list-detail",
            routes=["/blog", "/blog/:id"],
            gates=["blog.view", "blog.create"],
        )

        readme = generate_readme(config)

        self.assertIn("# Blog Module", readme)
        self.assertIn("/blog", readme)
        self.assertIn("blog.view", readme)
        self.assertIn("list-detail", readme)


class TestCreateModuleStructure(unittest.TestCase):
    def test_dry_run(self):
        config = ModuleConfig(
            name="module_test",
            template="minimal",
            routes=["/test"],
            gates=["test.view"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            files = create_module_structure(config, output, dry_run=True)

            # Should return paths but not create files
            self.assertTrue(len(files) > 0)
            self.assertTrue(not any(f.exists() for f in files))

    def test_actual_creation(self):
        config = ModuleConfig(
            name="module_test",
            template="list-detail",
            routes=["/test"],
            gates=["test.view"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            files = create_module_structure(config, output)

            # Should create files
            self.assertTrue(len(files) > 0)
            self.assertTrue(all(f.exists() for f in files))

            # Check directory structure
            module_dir = output / "module_test"
            self.assertTrue(module_dir.exists())
            self.assertTrue((module_dir / "pubspec.yaml").exists())
            self.assertTrue((module_dir / "README.md").exists())
            self.assertTrue((module_dir / "module_config.json").exists())

            # Check module_config.json
            with open(module_dir / "module_config.json") as f:
                metadata = json.load(f)
            self.assertEqual(metadata["name"], "test")
            self.assertEqual(metadata["class_name"], "TestModule")


class TestIntegration(unittest.TestCase):
    def test_full_module_generation(self):
        """Test complete module generation flow."""
        config = ModuleConfig(
            name="module_inventory",
            template="list-detail",
            routes=["/inventory", "/inventory/:id", "/inventory/new"],
            gates=["inventory.view", "inventory.create", "inventory.edit"],
            version="1.0.0",
        )

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            files = create_module_structure(config, output)

            # Verify all expected files exist
            module_dir = output / "module_inventory"
            self.assertTrue((module_dir / "lib" / "src" / "inventory_module.dart").exists())

            # Verify the module descriptor
            descriptor_path = module_dir / "lib" / "src" / "inventory_module.dart"
            with open(descriptor_path) as f:
                content = f.read()
            self.assertIn("InventoryModule", content)
            self.assertIn("/inventory", content)
            self.assertIn("inventory.view", content)


if __name__ == "__main__":
    unittest.main()
