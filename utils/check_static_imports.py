# coding=utf-8
# Copyright 2022-present, the HuggingFace Inc. team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Contains a tool to reformat static imports in `huggingface_hub.__init__.py`."""
import argparse
import re
from pathlib import Path
from typing import NoReturn

import isort
from huggingface_hub import _SUBMOD_ATTRS


INIT_FILE_PATH = Path(__file__).parents[1] / "src" / "huggingface_hub" / "__init__.py"
SETUP_CFG_PATH = Path(__file__).parents[1] / "setup.cfg"

IF_TYPE_CHECKING_LINE = "\nif TYPE_CHECKING:  # pragma: no cover\n"
SUBMOD_ATTRS_PATTERN = re.compile("_SUBMOD_ATTRS = {[^}]+}")  # match the all dict


def check_static_imports(update_file: bool) -> NoReturn:
    """Check all imports are made twice (1 in lazy-loading and 1 in static checks).

    For more explanations, see `./src/huggingface_hub/__init__.py`.
    This script is used in the `make style` and `make quality` checks.
    """
    with INIT_FILE_PATH.open() as f:
        init_content = f.read()

    # Get first half of the `__init__.py` file.
    # WARNING: Content after this part will be entirely re-generated which means
    # human-edited changes will be lost !
    init_content_before_static_checks = init_content.split(IF_TYPE_CHECKING_LINE)[0]

    # Search and replace `_SUBMOD_ATTRS` dictionary definition. This ensures modules
    # and functions that can be lazy-loaded are alphabetically ordered for readability.
    if SUBMOD_ATTRS_PATTERN.search(init_content_before_static_checks) is None:
        print(
            "Error: _SUBMOD_ATTRS dictionary definition not found in"
            " `./src/huggingface_hub/__init__.py`."
        )
        exit(1)

    _submod_attrs_definition = (
        "_SUBMOD_ATTRS = {\n"
        + "\n".join(
            f'    "{module}": [\n'
            + "\n".join(f'        "{attr}",' for attr in sorted(_SUBMOD_ATTRS[module]))
            + "\n    ],"
            for module in sorted(_SUBMOD_ATTRS.keys())
        )
        + "\n}"
    )
    reordered_content_before_static_checks = SUBMOD_ATTRS_PATTERN.sub(
        _submod_attrs_definition, init_content_before_static_checks
    )

    # Generate the static imports given the `_SUBMOD_ATTRS` dictionary.
    static_imports = [
        f"    from .{module} import {attr} # noqa: F401"
        for module, attributes in _SUBMOD_ATTRS.items()
        for attr in attributes
    ]

    # Generate the expected `__init__.py` file content and apply formatter on it.
    expected_init_content = isort.code(
        reordered_content_before_static_checks
        + IF_TYPE_CHECKING_LINE
        + "\n".join(static_imports)
        + "\n",
        config=isort.Config(settings_path=SETUP_CFG_PATH),
    )

    # If expected `__init__.py` content is different, test fails. If '--update-init-file'
    # is used, `__init__.py` file is updated before the test fails.
    if init_content != expected_init_content:
        if update_file:
            with INIT_FILE_PATH.open("w") as f:
                f.write(expected_init_content)

            print(
                "✅ Imports have been updated in `./src/huggingface_hub/__init__.py`."
                "\n   Please make sure the changes are accurate and commit them."
            )
            exit(0)
        else:
            print(
                "❌ Expected content mismatch in"
                " `./src/huggingface_hub/__init__.py`.\n   It is most likely that you"
                " added a module/function to `_SUBMOD_ATTRS` and did not update the"
                " 'static import'-part.\n   Please run `make style` or `python"
                " utils/check_static_imports.py --update-file`."
            )
            exit(1)

    print("✅ All good!")
    exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update-file",
        action="store_true",
        help=(
            "Whether to fix `./src/huggingface_hub/__init__.py` if a change is"
            " detected."
        ),
    )
    args = parser.parse_args()

    check_static_imports(update_file=args.update_file)
