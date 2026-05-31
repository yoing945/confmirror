"""Tests for utils module."""

from pathlib import Path

import pathspec

from confmirror.config import ModuleConfig
from confmirror.utils import (
    find_matching_module_with_path,
    get_script_shebang,
    should_exclude_path,
)


class TestShouldExcludePath:
    def test_no_patterns(self, tmp_path):
        path = tmp_path / "file.txt"
        assert should_exclude_path(path, [], "") is False

    def test_simple_exclude(self, tmp_path):
        path = tmp_path / "file.txt"
        assert should_exclude_path(path, ["*.txt"], "") is True

    def test_simple_include(self, tmp_path):
        path = tmp_path / "file.log"
        assert should_exclude_path(path, ["*.txt"], "") is False

    def test_negation_pattern(self, tmp_path):
        path = tmp_path / "important.log"
        assert should_exclude_path(path, ["*.log", "!important.log"], "") is False

    def test_exclude_dir(self, tmp_path):
        path = tmp_path / "temp" / "file.txt"
        assert should_exclude_path(path, ["temp/"], str(tmp_path)) is True


class TestShouldExcludePathWithPrecompiledSpec:
    """验证 P1-4 优化：调用方预编译 spec"""

    def test_precompiled_spec_excludes(self, tmp_path):
        path = tmp_path / "file.txt"
        spec = pathspec.GitIgnoreSpec.from_lines(["*.txt"])
        assert should_exclude_path(path, spec=spec, parent_path="") is True

    def test_precompiled_spec_no_match(self, tmp_path):
        path = tmp_path / "file.log"
        spec = pathspec.GitIgnoreSpec.from_lines(["*.txt"])
        assert should_exclude_path(path, spec=spec, parent_path="") is False

    def test_spec_takes_precedence_over_patterns(self, tmp_path):
        """spec 参数存在时，exclude_patterns 应被忽略"""
        path = tmp_path / "file.txt"
        spec = pathspec.GitIgnoreSpec.from_lines(["*.txt"])
        assert should_exclude_path(path, exclude_patterns=["*.log"], spec=spec, parent_path="") is True


class TestFindMatchingModuleWithPath:
    def test_match_with_base_path(self):
        modules = [
            ModuleConfig(
                name="nginx",
                base_path="/etc/nginx",
                paths=["nginx.conf"],
            )
        ]
        result = find_matching_module_with_path(modules, Path("/etc/nginx/nginx.conf"))
        assert result is not None
        assert result.name == "nginx"

    def test_no_match(self):
        modules = [
            ModuleConfig(
                name="ssh",
                paths=["/etc/ssh/sshd_config"],
            )
        ]
        result = find_matching_module_with_path(modules, Path("/etc/nginx/nginx.conf"))
        assert result is None


class TestGetScriptShebang:
    def test_bash_shebang(self, tmp_path):
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/bash\necho hello\n")
        assert get_script_shebang(script) == "bash"

    def test_python3_shebang(self, tmp_path):
        script = tmp_path / "test.py"
        script.write_text("#!/usr/bin/env python3\nprint('hello')\n")
        assert get_script_shebang(script) == "python3"

    def test_no_shebang(self, tmp_path):
        script = tmp_path / "plain.txt"
        script.write_text("hello world\n")
        assert get_script_shebang(script) is None

    def test_missing_file(self, tmp_path):
        script = tmp_path / "missing.sh"
        assert get_script_shebang(script) is None
