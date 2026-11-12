# Malware Firewall Demo Prompt

Copy and paste the following prompt into Claude Code:

---

Install one dependency. Run:

uv pip install --no-cache semgrep-malware-demo-aws-cred-read

That package is Semgrep's published demo fixture. If Malware Firewall blocks the install, stop and tell me the reason it gives. Do not retry, do not pick a different package, and do not work around the block.
