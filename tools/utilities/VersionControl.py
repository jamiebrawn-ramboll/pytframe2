import os
import subprocess
from pathlib import Path
from typing import Literal

import arcpy

import utils.archelp as archelp
from utils.archelp import print
from utils.tool import Tool


class VersionControl(Tool):
    __slots__ = ["active_branch", "branches", "workdir"]

    def __init__(self) -> None:
        super().__init__()

        self.workdir: os.PathLike = Path(__file__).parents[2].absolute()

        # Initialize with safe defaults
        self.active_branch: str = "main"  # Default fallback
        self.branches: list[str] = ["main"]  # Default fallback

        try:
            self.active_branch = self.get_active_branch()
            self.branches = self.get_branches()
        except Exception as e:
            print(f"Git initialization failed: {e}", severity="WARNING")
            # Keep default values

        self.label = f"Version Control ({self.active_branch})"
        self.description = "Pulls the latest changes from the remote repository or switches to a different branch."
        self.category = "Version Control"
        return

    def getParameterInfo(self) -> list:
        branch = arcpy.Parameter(
            displayName="Branch",
            name="branch",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        branch.value = self.active_branch
        branch.filter.type = "ValueList"

        # Ensure branches list is valid before setting
        if self.branches and all(
            isinstance(b, str) and b.strip() for b in self.branches
        ):
            branch.filter.list = self.branches
        else:
            branch.filter.list = [self.active_branch]  # Fallback

        status = arcpy.Parameter(
            displayName="Status",
            name="status",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        status.controlCLSID = "{E5456E51-0C41-4797-9EE4-5269820C6F0E}"
        status.value = self.get_status()

        pull = arcpy.Parameter(
            displayName="Pull",
            name="pull",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        pull.value = True

        return [branch, pull, status]

    def updateParameters(self, parameters: list) -> None:
        params = archelp.Parameters(parameters)

        if params.branch.value != self.active_branch:
            params.pull.value = False
            params.pull.enabled = False
        else:
            params.pull.enabled = True

        params.status.value = self.get_status()
        return

    def execute(self, parameters: list, messages: list) -> None:
        params = archelp.Parameters(parameters)

        try:
            if params.pull.value:
                result = self.git_subprocess("pull", None, self.workdir)
                if result.returncode == 0:
                    print(result.stdout)
                else:
                    print(f"Pull failed: {result.stderr}", severity="ERROR")
            elif self.active_branch != params.branch.value:
                result = self.git_subprocess(
                    "checkout", params.branch.value, self.workdir
                )
                if result.returncode == 0:
                    print(result.stdout)
                else:
                    print(f"Checkout failed: {result.stderr}", severity="ERROR")
        except Exception as e:
            print(f"Git operation failed: {e}", severity="ERROR")

        print(self.get_status())

    def get_status(self) -> str:
        try:
            result = self.git_subprocess("status", None, self.workdir)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"Git status error: {result.stderr.strip()}"
        except Exception as e:
            return f"Unable to get git status: {e}"

    def get_branches(self) -> list[str]:
        try:
            result = self.git_subprocess("branch", "-a", self.workdir)
            if result.returncode == 0:
                return self.parse_git_branches(result.stdout)
            else:
                print(f"Failed to get branches: {result.stderr}", severity="WARNING")
                return [self.active_branch]  # Fallback to current branch
        except Exception as e:
            print(f"Error getting branches: {e}", severity="WARNING")
            return [self.active_branch]  # Fallback

    def get_active_branch(self) -> str:
        try:
            result = self.git_subprocess("branch", "--show-current", self.workdir)
            if result.returncode == 0:
                branch = result.stdout.strip()
                return branch if branch else "main"
            else:
                print(
                    f"Failed to get current branch: {result.stderr}", severity="WARNING"
                )
                return "main"
        except Exception as e:
            print(f"Error getting current branch: {e}", severity="WARNING")
            return "main"

    @staticmethod
    def git_subprocess(
        command: Literal["branch", "pull", "checkout", "status"],
        flag: Literal["-a", "--show-current"] | str | None,
        cwd: os.PathLike = None,
    ) -> subprocess.CompletedProcess:
        """Run a git command using subprocess"""
        try:
            result = subprocess.run(
                ["git", command] + ([flag] if flag else []),
                cwd=cwd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=30,  # Add timeout to prevent hanging
            )
            return result
        except subprocess.TimeoutExpired:
            # Create a mock failed result for timeout
            result = subprocess.CompletedProcess(
                args=["git", command] + ([flag] if flag else []),
                returncode=1,
                stdout="",
                stderr="Git command timed out",
            )
            return result
        except Exception as e:
            # Create a mock failed result for other exceptions
            result = subprocess.CompletedProcess(
                args=["git", command] + ([flag] if flag else []),
                returncode=1,
                stdout="",
                stderr=str(e),
            )
            return result

    @staticmethod
    def parse_git_branches(git_branches: str) -> list[str]:
        """Parse the output of 'git branch -a' and return clean branch names"""
        if not git_branches or not git_branches.strip():
            return ["main"]  # Default fallback

        branches = []
        for branch in git_branches.strip().split("\n"):
            # Clean the branch name
            clean_branch = branch.strip().replace("*", "").strip()

            # Skip empty lines
            if not clean_branch:
                continue

            # Handle remote branches - extract just the branch name
            if clean_branch.startswith("remotes/origin/"):
                clean_branch = clean_branch.replace("remotes/origin/", "")
            elif clean_branch.startswith("remotes/"):
                # Skip other remote references
                continue

            # Skip HEAD references
            if "HEAD" in clean_branch or "->" in clean_branch:
                continue

            # Only add if it's a valid branch name (no special chars that might cause issues)
            if clean_branch and not any(
                char in clean_branch for char in [" ", "\t", "\n", "\r"]
            ):
                branches.append(clean_branch)

        # Remove duplicates while preserving order
        seen = set()
        unique_branches = []
        for branch in branches:
            if branch not in seen:
                seen.add(branch)
                unique_branches.append(branch)

        # Ensure we always have at least one branch
        return unique_branches if unique_branches else ["main"]
