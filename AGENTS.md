# Git Configuration Backup Tool - Agent Guidelines

This document provides coding guidelines and development commands for agents working on this Git configuration backup tool repository.

## Project Overview

This is a Python-based system configuration backup and restore tool with two main scripts:
- `backup.py` - Configuration backup script (no sudo required)
- `restore.py` - Configuration restore script (sudo required for permission management)

The tool supports modular configuration, Git version control, and script-based backups with comprehensive logging and metadata preservation.

## Development Commands

### Environment Setup
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env to customize paths and settings

# Install dependencies (optional - uses standard library)
pip install -r requirements.txt
```

### Testing Commands
```bash
# Run backup with dry-run (no actual changes)
python3 backup.py --dry-run

# Test backup of specific module
python3 backup.py mod "测试模块"

# Test restore with dry-run
sudo python3 restore.py restore /etc/hosts --dry-run

# Test specific module restore
sudo python3 restore.py restore-mod "测试模块" --dry-run
```

### Code Quality
```bash
# Python syntax check
python3 -m py_compile backup.py restore.py

# Type checking (if mypy installed)
mypy backup.py restore.py --ignore-missing-imports

# Linting (if pylint installed)
pylint backup.py restore.py

# Format code (if black installed)
black backup.py restore.py backup-script/*.sh
```

### Git Operations
```bash
# Initialize backup repository
cd backup && git init && git add . && git commit -m "Initial backup" && cd ..

# Test Git integration
python3 backup.py --dry-run  # Should show Git operations in dry-run mode
```

## Code Style Guidelines

### Import Organization
```python
# Standard library imports (sorted alphabetically)
import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party imports (if any)
# import third_party_module

# Local imports (if any)
# from local_module import something
```

### Code Structure and Conventions

#### 1. File Headers
Every Python file should start with:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brief description of the file's purpose and main functionality.
"""

# Imports organized as specified above
```

#### 2. Class Design
Use `@dataclass` for configuration classes:
```python
@dataclass
class ExampleConfig:
    """Configuration class description."""
    required_field: str
    optional_field: int = 100
    boolean_field: bool = False
    
    def __post_init__(self):
        """Post-initialization logic."""
        if self.optional_field < 0:
            self.optional_field = 100
```

#### 3. Type Annotations
All functions must have type annotations:
```python
def process_file(self, file_path: str, module_name: str) -> bool:
    """Process a single file.
    
    Args:
        file_path: Path to the file to process
        module_name: Name of the current module
        
    Returns:
        True if successful, False otherwise
    """
    return True
```

#### 4. Naming Conventions
- **Classes**: PascalCase (`BackupManager`, `RestoreLogger`)
- **Functions/Methods**: snake_case (`backup_module`, `restore_file`)
- **Variables**: snake_case (`config_file`, `backup_root`)
- **Constants**: UPPER_SNAKE_CASE (`LOG_KEEP_LINES`, `DEFAULT_MODE`)
- **Private methods**: underscore prefix (`_calculate_checksum`, `_validate_path`)

#### 5. Error Handling Patterns

#### File Operations
```python
def safe_file_operation(self, file_path: str) -> bool:
    """Safely perform file operations with proper error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Process content
        return True
    except FileNotFoundError:
        self.logger.error(f"File not found: {file_path}")
        return False
    except PermissionError:
        self.logger.error(f"Permission denied: {file_path}")
        return False
    except Exception as e:
        self.logger.error(f"Unexpected error processing {file_path}: {e}")
        return False
```

#### Subprocess Execution
```python
def run_script(self, script_path: str, operation: str) -> bool:
    """Execute external script with proper error handling."""
    try:
        result = subprocess.run(
            [script_path, operation],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            self.logger.info(f"Script executed successfully: {script_path}")
            return True
        else:
            self.logger.error(f"Script failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        self.logger.error(f"Script timeout: {script_path}")
        return False
    except Exception as e:
        self.logger.error(f"Script execution error: {e}")
        return False
```

#### 6. Logging Standards
Use the logger class methods with consistent formatting:
```python
self.logger.info(f"[操作类型] 详细描述信息 → {path}")
self.logger.warning(f"[警告类型] 警告信息 → {path}")
self.logger.error(f"[错误类型] 错误描述 → {path}: {error_details}")
```

#### 7. Documentation Standards
- Module docstrings should briefly explain purpose
- Class docstrings should explain role and usage
- Function docstrings should include Args, Returns, and any Raises
- Use Chinese comments for user-facing messages, English for technical comments

#### 8. Configuration Management
- Always load from `.env` file using the `load_env_config()` pattern
- Provide sensible defaults for all configuration values
- Support environment variable overrides
- Validate configuration values in `__post_init__()` methods

#### 9. Security Considerations
- Validate all file paths before operations
- Use proper privilege separation (backup vs restore)
- Sanitize user inputs in configuration files
- Never log sensitive information (passwords, keys)
- Use subprocess with proper argument lists (not shell=True)

#### 10. Testing and Validation
- Always include `--dry-run` mode for new features
- Test both success and failure scenarios
- Validate configuration file formats
- Check file permissions and accessibility before operations

## File Organization Rules

- Configuration classes come first
- Logger classes next
- Main business logic classes
- Utility functions
- Configuration loading functions
- Main function and CLI argument parsing
- Use `if __name__ == '__main__':` guard for script execution

## Git Integration

When modifying backup/restore logic:
1. Test changes in `--dry-run` mode first
2. Verify Git operations work correctly
3. Ensure metadata preservation
4. Test permission handling (especially for restore operations)

## Bash Script Guidelines (backup-script/)

For bash scripts used in script-based backups:
- Use proper shebang: `#!/bin/bash`
- Include basic error handling
- Support both `backup` and `restore` operations
- Log operations consistently with Python scripts
- Make scripts executable in the repository