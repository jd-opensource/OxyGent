"""Skill testing utilities for OxyGent preset skills.

This module provides utilities for testing skills, including validation
of SKILL.md files and helper functions for skill development.
"""

import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class SkillValidator:
    """Validator for SKILL.md files.

    Validates that a SKILL.md file conforms to the expected format
    and contains all required fields.
    """

    REQUIRED_FIELDS = ["name", "description"]
    RECOMMENDED_FIELDS: List[str] = []

    def __init__(self, skill_path: Path):
        """Initialize validator for a skill.

        Args:
            skill_path: Path to the SKILL.md file.
        """
        self.skill_path = skill_path
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.frontmatter: Dict[str, Any] = {}
        self.body: str = ""

    def validate(self) -> bool:
        """Validate the SKILL.md file.

        Returns:
            True if validation passes (no errors), False otherwise.
        """
        self.errors = []
        self.warnings = []

        # Check file exists
        if not self.skill_path.exists():
            self.errors.append(f"File does not exist: {self.skill_path}")
            return False

        # Read and parse
        try:
            content = self.skill_path.read_text(encoding="utf-8")
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False

        # Validate frontmatter format
        if not content.startswith("---"):
            self.errors.append("SKILL.md must start with frontmatter (---)")
            return False

        parts = content.split("---", 2)
        if len(parts) < 3:
            self.errors.append("Invalid frontmatter format (missing closing ---)")
            return False

        # Parse YAML frontmatter
        try:
            self.frontmatter = yaml.safe_load(parts[1])
            self.body = parts[2].strip()
        except yaml.YAMLError as e:
            self.errors.append(f"Failed to parse YAML frontmatter: {e}")
            return False

        # Validate required fields
        for field in self.REQUIRED_FIELDS:
            if field not in self.frontmatter:
                self.errors.append(f"Missing required field: {field}")

        # Check for recommended fields
        for field in self.RECOMMENDED_FIELDS:
            if field not in self.frontmatter:
                self.warnings.append(f"Missing recommended field: {field}")

        # Validate field types and formats
        self._validate_name()
        self._validate_description()
        self._validate_allowed_tools()
        self._validate_resources()
        self._validate_body()

        # Validate resources exist
        if "resources" in self.frontmatter:
            self._validate_resource_files()

        return len(self.errors) == 0

    def _validate_name(self):
        """Validate the name field."""
        if "name" not in self.frontmatter:
            return

        name = self.frontmatter["name"]
        if not isinstance(name, str):
            self.errors.append("Field 'name' must be a string")
            return

        # Check format: lowercase, hyphens allowed
        if not re.match(r"^[a-z][a-z0-9-]*$", name):
            self.warnings.append(
                "Field 'name' should be lowercase with hyphens (e.g., 'my-skill')"
            )

        # Check it matches directory name
        expected_dir = self.skill_path.parent.name
        if name != expected_dir:
            self.warnings.append(
                f"Field 'name' ({name}) should match directory name ({expected_dir})"
            )

    def _validate_description(self):
        """Validate the description field."""
        if "description" not in self.frontmatter:
            return

        description = self.frontmatter["description"]
        if not isinstance(description, str):
            self.errors.append("Field 'description' must be a string")
            return

        if len(description) < 10:
            self.warnings.append(
                "Description is too short (min 10 characters recommended)"
            )
        if len(description) > 200:
            self.warnings.append(
                "Description is too long (max 200 characters recommended)"
            )

    def _validate_allowed_tools(self):
        """Validate the allowed-tools field."""
        allowed_tools = self.frontmatter.get("allowed-tools")
        if allowed_tools is None:
            return

        if isinstance(allowed_tools, str):
            self.frontmatter["allowed-tools"] = [allowed_tools]
        elif isinstance(allowed_tools, list):
            # Filter non-string values
            valid = [t for t in allowed_tools if isinstance(t, str)]
            if len(valid) != len(allowed_tools):
                self.warnings.append(
                    "Field 'allowed-tools' contains non-string values which were ignored"
                )
            self.frontmatter["allowed-tools"] = valid
        else:
            self.warnings.append(
                "Field 'allowed-tools' must be a string or list, ignoring"
            )
            self.frontmatter["allowed-tools"] = []

    def _validate_resources(self):
        """Validate the resources field."""
        resources = self.frontmatter.get("resources")
        if resources is None:
            return

        if isinstance(resources, str):
            self.frontmatter["resources"] = [resources]
        elif isinstance(resources, list):
            # Filter non-string values
            valid = [r for r in resources if isinstance(r, str)]
            if len(valid) != len(resources):
                self.warnings.append(
                    "Field 'resources' contains non-string values which were ignored"
                )
            self.frontmatter["resources"] = valid
        else:
            self.warnings.append("Field 'resources' must be a string or list, ignoring")
            self.frontmatter["resources"] = []

    def _validate_body(self):
        """Validate the markdown body."""
        if not self.body:
            self.errors.append("SKILL.md body is empty")
            return

        # Check for sections
        if "## Overview" not in self.body and "## Instructions" not in self.body:
            self.warnings.append(
                "Body should include an '## Overview' or '## Instructions' section"
            )

        # Check for examples section
        if "## Example" not in self.body:
            self.warnings.append(
                "Body should include an '## Examples' section for clarity"
            )

    def _validate_resource_files(self):
        """Validate that referenced resource files exist."""
        skill_dir = self.skill_path.parent
        resources = self.frontmatter.get("resources", [])

        for resource in resources:
            resource_path = skill_dir / resource
            if not resource_path.exists():
                self.errors.append(f"Referenced resource file not found: {resource}")

    def get_report(self) -> str:
        """Get a formatted validation report.

        Returns:
            A string containing errors and warnings.
        """
        lines = []
        lines.append(f"Validation Report: {self.skill_path.name}")
        lines.append("=" * 60)

        if self.errors:
            lines.append(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  - {error}")

        if self.warnings:
            lines.append(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if not self.errors and not self.warnings:
            lines.append("\n✅ No issues found!")

        return "\n".join(lines)


class SkillTester:
    """Tester for skill functionality.

    Provides utilities for testing skills in isolation.
    """

    @staticmethod
    def create_test_skill(
        name: str,
        description: str,
        instructions: str,
        allowed_tools: Optional[List[str]] = None,
        resources: Optional[Dict[str, str]] = None,
    ) -> Path:
        """Create a temporary test skill file.

        Args:
            name: Skill name.
            description: Skill description.
            instructions: Skill instructions (markdown body).
            allowed_tools: Optional list of allowed tools.
            resources: Optional dict of resource files.

        Returns:
            Path to the created SKILL.md file.
        """
        tmpdir = Path(tempfile.mkdtemp())
        skill_dir = tmpdir / name
        skill_dir.mkdir()

        # Build frontmatter
        frontmatter: Dict[str, Any] = {
            "name": name,
            "description": description,
        }
        if allowed_tools:
            frontmatter["allowed-tools"] = allowed_tools
        if resources:
            frontmatter["resources"] = list(resources.keys())

        # Write SKILL.md
        content = f"---\n"
        content += yaml.dump(frontmatter, default_flow_style=False)
        content += "---\n\n"
        content += instructions

        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(content, encoding="utf-8")

        # Write resource files
        if resources:
            for filename, file_content in resources.items():
                resource_path = skill_dir / filename
                resource_path.write_text(file_content, encoding="utf-8")

        return skill_path

    @staticmethod
    def validate_skill_directory(skill_dir: Path) -> List[str]:
        """Validate all skills in a directory.

        Args:
            skill_dir: Directory containing skill subdirectories.

        Returns:
            List of validation report strings.
        """
        reports = []
        for skill_file in skill_dir.rglob("SKILL.md"):
            validator = SkillValidator(skill_file)
            validator.validate()
            reports.append(validator.get_report())
        return reports


def validate_all_preset_skills() -> Dict[str, Dict[str, Any]]:
    """Validate all preset skills.

    Returns:
        Dictionary mapping skill names to their validation reports.
    """
    preset_dir = Path(__file__).parent
    reports: Dict[str, Dict[str, Any]] = {}

    for skill_path in preset_dir.glob("*/SKILL.md"):
        validator = SkillValidator(skill_path)
        is_valid = validator.validate()
        reports[skill_path.parent.name] = {
            "valid": is_valid,
            "report": validator.get_report(),
            "errors": validator.errors,
            "warnings": validator.warnings,
        }

    return reports


if __name__ == "__main__":
    # Run validation on all preset skills
    import sys

    reports = validate_all_preset_skills()

    all_valid = True
    for skill_name, result in reports.items():
        if not result["valid"]:
            all_valid = False
        print(result["report"])
        print()

    if all_valid:
        print("✅ All preset skills are valid!")
        sys.exit(0)
    else:
        print("❌ Some preset skills have validation errors.")
        sys.exit(1)
