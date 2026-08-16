import os
import subprocess
from datetime import datetime

class ProjectAuditor:
    def __init__(self):
        self.report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "checks": {},
            "score": 0,
            "total_checks": 0,
            "remaining_todos": 0
        }

    def check_file_exists(self, filepath, label):
        exists = os.path.exists(filepath)
        self.report["checks"][label] = "PASSED ✅" if exists else "FAILED ❌"
        self.report["total_checks"] += 1
        if exists:
            self.report["score"] += 1

    def run_tests(self):
        try:
            res = subprocess.run(["python3", "main.py", "--test"], capture_output=True, text=True)
            passed = "16/16 Tests PASSED" in res.stdout or res.returncode == 0
            self.report["checks"]["Automated Test Suite (16/16)"] = "PASSED ✅" if passed else "FAILED ❌"
        except Exception:
            self.report["checks"]["Automated Test Suite (16/16)"] = "FAILED ❌"
        
        self.report["total_checks"] += 1
        if self.report["checks"]["Automated Test Suite (16/16)"] == "PASSED ✅":
            self.report["score"] += 1

    def count_todos(self):
        todo_count = 0
        for root, _, files in os.walk("."):
            if "venv" in root or ".git" in root:
                continue
            for file in files:
                if file.endswith(".py") and file != "audit.py":
                    with open(os.path.join(root, file), "r", errors="ignore") as f:
                        todo_count += f.read().count("TODO")
        self.report["remaining_todos"] = todo_count

    def send_notification(self, score_pct):
        title = "🛡️ PMMP Pro-G4 Perpetual Audit Complete"
        message = f"Score: {score_pct}% ({self.report['score']}/{self.report['total_checks']} passed)\nActive TODOs: {self.report['remaining_todos']}"
        
        try:
            subprocess.run([
                "notify-send",
                title,
                message,
                "-i", "dialog-information",
                "-t", "5000"
            ])
        except Exception as e:
            print(f"Failed to trigger desktop notification: {e}")

    def generate_report(self):
        completion_pct = int((self.report["score"] / self.report["total_checks"]) * 100)
        
        markdown_content = f"""# 🛡️ PMMP Pro-G4 Perpetual Audit Report

**Last Audited:** `{self.report['timestamp']}`  
**Project Completion Score:** `{completion_pct}%` (`{self.report['score']}/{self.report['total_checks']}` checks passed)  
**Open TODO Items:** `{self.report['remaining_todos']}`

---

## 📋 System Audit Breakdown

| Component / Check | Audit Status |
| :--- | :--- |
"""
        for check, status in self.report["checks"].items():
            markdown_content += f"| {check} | {status} |\n"

        with open("AUDIT_REPORT.md", "w") as f:
            f.write(markdown_content)

        print(f"✅ Audit complete! Score: {completion_pct}%. Written to AUDIT_REPORT.md")
        self.send_notification(completion_pct)

if __name__ == "__main__":
    auditor = ProjectAuditor()
    
    # 1. Core Runtime Files
    auditor.check_file_exists("config/default.json", "Default Configuration")
    auditor.check_file_exists("requirements.txt", "Requirements Tracked")
    auditor.check_file_exists("charm_faiss.index", "FAISS Vector Index")
    auditor.check_file_exists("vehicle_baselines.json", "Vehicle Baselines")
    
    # 2. DevOps & Production Artifacts (From Readiness Report)
    auditor.check_file_exists(".env.example", "Environment Template (.env.example)")
    auditor.check_file_exists("Dockerfile", "Docker Container Spec")
    auditor.check_file_exists("CHANGELOG.md", "Release Changelog")
    auditor.check_file_exists(".github/workflows/ci-cd.yml", "CI/CD Pipeline Workflow")
    
    # 3. Automated Test Suite Execution
    auditor.run_tests()
    
    # 4. Code Debt Scan
    auditor.count_todos()
    
    # 5. Generate Output Report & OS Banner
    auditor.generate_report()
