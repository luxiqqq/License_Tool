"""
This module generates a human-readable text report summarizing the license analysis,
including compatibility status, AI suggestions, and paths to regenerated code.
"""

import os
from typing import List
from app.models.schemas import LicenseIssue

def generate_report(repo_path: str, main_license: str, issues: List[LicenseIssue]) -> str:
    """
    Generates a text report summarizing license compatibility issues.

    Args:
        repo_path (str): The path to the repository.
        main_license (str): The main license of the repository.
        issues (List[LicenseIssue]): A list of license issues detected.

    Returns:
        str: The path to the generated report file.
    """
    report_path = os.path.join(repo_path, "LICENSE_REPORT.txt")

    return report_path
