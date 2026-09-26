"""
Sphinx Extension for StrictDoc Export
=====================================

Copyright (c) 2025 Zephyr Project Contributors
SPDX-License-Identifier: Apache-2.0

Introduction
------------

This Sphinx extension runs the :program:`strictdoc` export command to generate RST files
from StrictDoc source files and places them in a specified output directory.  

Configuration options
---------------------

- ``strictdoc_source_dir``: The directory containing the StrictDoc source files. If this
    is not set, the extension will not run.

- ``strictdoc_output_dir``: The directory where the generated RST files will be placed.
    Defaults to `strictdoc_export`.

- ``strictdoc_config``: Path to a StrictDoc project config file, passed as
    ``--config``. Optional; needed when the sources rely on project settings
    such as grammar aliases.

"""
import os
import shutil
import subprocess
import tempfile
from sphinx.util import logging

# Initialize a logger for the extension
logger = logging.getLogger(__name__)

def run_strictdoc_export(app):
    """
    This function is connected to the 'build-inited' event.
    It executes the strictdoc export command in a temporary directory
    and moves the generated RST files to the correct location.

    Note: When used in conjunction with the Zephyr external content extension,
    this function should run after if you want to place the generated rst files
    into the same build directory.
    """

    config = app.config
    # Get the configuration values from conf.py, with default values.
    source_dir = config.strictdoc_source_dir
    output_dir = config.strictdoc_output_dir

    if not source_dir:
        logger.warning(
            "strictdoc_source_dir is not set in conf.py. "
            "The strictdoc_runner extension will do nothing."
        )
        return

    # Resolve the source and output paths.
    if os.path.isabs(source_dir):
        abs_source_dir = source_dir
    else:
        abs_source_dir = os.path.join(app.srcdir, source_dir)

    if os.path.isabs(output_dir):
        abs_output_dir = output_dir
    else:
        abs_output_dir = os.path.join(app.srcdir, output_dir)

    # Create a temporary directory to run the export in.
    temp_export_dir = tempfile.mkdtemp(prefix="strictdoc_")
    logger.info(f"Using temporary directory for strictdoc export: {temp_export_dir}")

    try:
        # Construct the command to be executed.
        command = [
            "strictdoc",
            "export",
            "--formats", "rst",
            "--output-dir", temp_export_dir,
        ]
        # StrictDoc otherwise looks for its project config in the current
        # directory, which during a Sphinx build is the build tree.
        if config.strictdoc_config:
            command += ["--config", config.strictdoc_config]
        command.append(abs_source_dir)

        logger.info(f"Running command: {' '.join(command)}")

        try:
            # Execute the command.
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout:
                logger.info(f"strictdoc output:\n{result.stdout}")
            if result.stderr:
                logger.info(f"strictdoc stderr:\n{result.stderr}")

        except FileNotFoundError:
            logger.error(
                "The 'strictdoc' command was not found. "
                "Please ensure that StrictDoc is installed and in your system's PATH."
            )
            return # Stop execution if strictdoc isn't found
        except subprocess.CalledProcessError as e:
            logger.error(
                f"The strictdoc command failed with exit code {e.returncode}.\n"
                f"Command: {' '.join(e.cmd)}\n"
                f"Stderr:\n{e.stderr}\n"
                f"Stdout:\n{e.stdout}"
            )
            return # Stop execution if the command fails

        # Define the path where strictdoc places the .rst files.
        strictdoc_rst_output_path = os.path.join(temp_export_dir, 'rst')

        if not os.path.isdir(strictdoc_rst_output_path):
            logger.warning(
                "strictdoc did not create the expected 'rst' subdirectory. "
                "No files will be copied."
            )
            return

        # Ensure the final destination directory exists.
        os.makedirs(abs_output_dir, exist_ok=True)

        # For a clean build, remove the old output directory if it exists.
        if os.path.isdir(abs_output_dir):
           shutil.rmtree(abs_output_dir)

        # Recursively copy the entire contents of the  'rst' folder
        # to the final output directory.
        shutil.copytree(strictdoc_rst_output_path, abs_output_dir)

        # The RST export does not carry the documents' images. StrictDoc keeps
        # them in _assets/ folders beside the .sdoc files and the generated RST
        # references them relative to that location, so mirror each folder to
        # the same relative place in the output.
        for dirpath, dirnames, _ in os.walk(abs_source_dir):
            if "_assets" in dirnames:
                rel_dir = os.path.relpath(dirpath, abs_source_dir)
                shutil.copytree(
                    os.path.join(dirpath, "_assets"),
                    os.path.join(abs_output_dir, rel_dir, "_assets"),
                    dirs_exist_ok=True,
                )
                dirnames.remove("_assets")

        logger.info(f"Successfully moved generated files to {abs_output_dir}")

    except Exception as e:
        logger.error(f"An unexpected error occurred during file operations: {e}")
    finally:
        # Clean up the temporary directory in all cases.
        logger.info(f"Removing temporary directory: {temp_export_dir}")
        #shutil.rmtree(temp_export_dir)


def setup(app):
    """
    This function is the entry point for the Sphinx extension.
    """
    app.add_config_value('strictdoc_source_dir', None, 'env', [str])
    app.add_config_value('strictdoc_output_dir', 'strictdoc_export', 'env', [str])
    app.add_config_value('strictdoc_config', None, 'env', [str])

    # We need to run after zephyr's copy_content extension
    app.connect('builder-inited', run_strictdoc_export, priority=600)

    return {
        'version': '0.2.0', # Incremented version for new feature
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
