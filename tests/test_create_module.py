"""Tests for the module scaffolding tool."""

import json
import tempfile
from pathlib import Path

import pytest

from automation.create_module import (
    ModuleConfig,
    create_module_structure,
    generate_module_descriptor,
    generate_pubspec,
    generate_readme,
    to_camel_case,
    to_pascal_case,
)


class TestHelpers:
    def test_to_pascal_case(self):
        assert to_pascal_case("blog") == "Blog"
        assert to_pascal_case("blog_post") == "BlogPost"
        assert to_pascal_case("user_profile_settings") == "UserProfileSettings"

    def test_to_camel_case(self):
        assert to_camel_case("blog") == "blog"
        assert to_camel_case("blog_post") == "blogPost"
        assert to_camel_case("user_profile") == "userProfile"


class TestModuleConfig:
    def test_module_id_extraction(self):
        config = ModuleConfig("module_blog", "minimal", [], [])
        assert config.module_id == "blog"

        config2 = ModuleConfig("blog", "minimal", [], [])
        assert config2.module_id == "blog"

    def test_class_name_generation(self):
        config = ModuleConfig("module_blog_post", "minimal", [], [])
        assert config.class_name == "BlogPostModule"

    def test_package_name(self):
        config = ModuleConfig("module_blog", "minimal", [], [])
        assert config.package_name == "module_blog"


class TestGenerateModuleDescriptor:
    def test_basic_descriptor(self):
        config = ModuleConfig(
            name="module_blog",
            template="minimal",
            routes=["/blog"],
            gates=["blog.view"],
        )

        code = generate_module_descriptor(config)

        assert "class BlogModule extends ModuleDescriptor" in code
        assert "id => 'blog'" in code
        assert "version => '1.0.0'" in code
        assert "route: '/blog'" in code
        assert "gates: ['blog.view']" in code

    def test_empty_routes(self):
        config = ModuleConfig(
            name="module_test",
            template="minimal",
            routes=[],
            gates=[],
        )

        code = generate_module_descriptor(config)

        assert "// Add routes here" in code
        assert "// Add navigation entries here" in code


class TestGeneratePubspec:
    def test_pubspec_generation(self):
        config = ModuleConfig(
            name="module_blog",
            template="minimal",
            routes=[],
            gates=[],
            version="1.2.3",
        )

        pubspec = generate_pubspec(config)

        assert "name: module_blog" in pubspec
        assert "version: 1.2.3" in pubspec
        assert "module_sdk" in pubspec


class TestGenerateReadme:
    def test_readme_generation(self):
        config = ModuleConfig(
            name="module_blog",
            template="list-detail",
            routes=["/blog", "/blog/:id"],
            gates=["blog.view", "blog.create"],
        )

        readme = generate_readme(config)

        assert "# Blog Module" in readme
        assert "/blog" in readme
        assert "blog.view" in readme
        assert "list-detail" in readme


class TestCreateModuleStructure:
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
            assert len(files) > 0
            assert not any(f.exists() for f in files)

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
            assert len(files) > 0
            assert all(f.exists() for f in files)

            # Check directory structure
            module_dir = output / "module_test"
            assert module_dir.exists()
            assert (module_dir / "pubspec.yaml").exists()
            assert (module_dir / "README.md").exists()
            assert (module_dir / "module_config.json").exists()

            # Check module_config.json
            with open(module_dir / "module_config.json") as f:
                metadata = json.load(f)
                assert metadata["name"] == "test"
                assert metadata["class_name"] == "TestModule"


class TestIntegration:
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
            assert (module_dir / "lib" / "src" / "inventory_module.dart").exists()

            # Verify the module descriptor
            descriptor_path = module_dir / "lib" / "src" / "inventory_module.dart"
            with open(descriptor_path) as f:
                content = f.read()
                assert "InventoryModule" in content
                assert "/inventory" in content
                assert "inventory.view" in content
