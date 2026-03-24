import json
import os
import subprocess
import time

from capacity_manager import CapacityManager


class SwarmOrchestrator:
    """Orchestrates multiple agents (Jules, Gemini CLI) based on capacity."""

    def __init__(self):
        self.cm = CapacityManager()
        self.repo_root = os.getcwd()
        self.swarm_root = "/tmp/hyperadmin-swarm"
        os.makedirs(self.swarm_root, exist_ok=True)

    def get_ready_issues(self):
        """Fetch issues labeled 'agent-task' and 'ready'."""
        cmd = [
            "gh",
            "issue",
            "list",
            "--label",
            "agent-task",
            "--label",
            "ready",
            "--json",
            "number,title,labels,body",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return []

    def dispatch_to_jules(self, issue):
        """Assign issue to Jules for autonomous fix."""
        if not self.cm.has_capacity("jules"):
            print("Jules at capacity. Skipping...")
            return False

        print(f"Dispatching Issue #{issue['number']} to Jules...")
        self.cm.consume("jules")

        # Trigger Jules via assignment or direct CLI call
        # For Jules Pro, we might just assign the issue.
        subprocess.run(
            ["gh", "issue", "edit", str(issue["number"]), "--add-assignee", "jules-cli[bot]"]
        )
        subprocess.run(
            [
                "gh",
                "issue",
                "edit",
                str(issue["number"]),
                "--remove-label",
                "ready",
                "--add-label",
                "in-progress",
            ]
        )
        return True

    def dispatch_to_gemini(self, issue):
        """Run gemini-cli in an isolated git worktree."""
        if not self.cm.has_capacity("gemini-flash"):
            print("Gemini API at capacity. Skipping...")
            return False

        issue_num = issue["number"]
        branch_name = f"swarm/issue-{issue_num}"
        worktree_path = f"{self.swarm_root}/issue-{issue_num}"

        print(f"Dispatching Issue #{issue_num} to Gemini Swarm in {worktree_path}...")
        self.cm.consume("gemini-flash")

        try:
            # 1. Create worktree
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, worktree_path, "develop"], check=True
            )

            # 2. Run Gemini CLI in worktree (mock command for now)
            # In real usage: npx @google/gemini-cli --prompt "Solve issue: ..."
            print(f"Running Gemini CLI in {worktree_path}...")

            # 3. After completion, commit and push (Agent should do this)
            # subprocess.run(["git", "add", ".", "&&", "git", "commit", "-m", f"fix(core): solve #{issue_num}", "&&", "git", "push", "origin", branch_name], cwd=worktree_path, shell=True)

            # 4. Clean up labels
            subprocess.run(
                [
                    "gh",
                    "issue",
                    "edit",
                    str(issue_num),
                    "--remove-label",
                    "ready",
                    "--add-label",
                    "in-progress",
                ]
            )
            return True
        except Exception as e:
            print(f"Failed to dispatch to Gemini: {e}")
            return False

    def run_loop(self):
        """Continuous orchestration loop."""
        print("Starting Swarm Orchestrator loop...")
        while True:
            issues = self.get_ready_issues()
            for issue in issues:
                labels = [l["name"] for l in issue["labels"]]
                if "size:small" in labels:
                    self.dispatch_to_jules(issue)
                else:
                    self.dispatch_to_gemini(issue)

            time.sleep(60)  # Wait a minute before next check


if __name__ == "__main__":
    orchestrator = SwarmOrchestrator()
    # To run once for demo:
    # orchestrator.run_loop()
    print("Orchestrator initialized. Ready to run.")
