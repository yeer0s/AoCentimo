#!/usr/bin/env python3
"""Prove the offline guarantee, statically, from the AST.

The README claims this project makes zero network calls, spawns no processes and
executes no dynamic code. That is the main reason to trust it with a tax return,
so it is checked rather than asserted — and checked here, in the repo, so a
reader can run it themselves instead of taking a CI badge on faith.

WHAT THIS DOES NOT PROVE. It is a static audit, not a sandbox. It catches the
accidental and the obvious: a networking import, a shell-out, a dynamic import,
a builtin eval. It is NOT a defence against a determined malicious contributor,
who has many ways to reach a network that no import-level check can see. The
real control there is that this is a small project where every PR is read. Say
that plainly rather than implying the audit is a security boundary.

Deliberately AST-based, not grep-based. A regex for `eval\\(` matches
`re.compile(`-style attribute calls and misses aliased imports; the parser knows
the difference between the builtin `eval(...)` and a method named `.eval(...)`.

    python scripts/offline_audit.py            # audit scripts/
    python scripts/offline_audit.py --selftest # prove the audit can FAIL

Exit 0 = clean.
"""

import argparse
import ast
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# Modules that could move data off the machine, spawn a process, or reach into
# native memory. Any import of these — direct, aliased, or `from x import y` —
# breaks the offline guarantee.
FORBIDDEN_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib2", "urllib3", "requests", "httpx",
    "aiohttp", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "xmlrpc",
    "subprocess", "multiprocessing", "ctypes", "webbrowser", "asyncio",
    "socketserver", "wsgiref", "paramiko", "boto3",
}

# Builtins that execute text as code. `compile` is intentionally NOT here:
# re.compile is ubiquitous and harmless, and the builtin compile() alone is not
# a data-exfiltration risk without eval/exec beside it.
FORBIDDEN_CALLS = {"eval", "exec", "__import__"}

# Attribute calls that shell out or import by name. `os` cannot go in
# FORBIDDEN_MODULES (the project legitimately needs os.path), so the dangerous
# MEMBERS are named instead. Added 2026-07-24 after an adversarial review showed
# os.system("curl ... http://host") passed the audit with zero findings — and
# would ALSO evade the CI socket-blocking job, because it spawns a separate
# process rather than opening a socket in this interpreter.
FORBIDDEN_ATTRS = {
    ("os", "system"), ("os", "popen"), ("os", "spawnl"), ("os", "spawnv"),
    ("os", "spawnve"), ("os", "execl"), ("os", "execv"), ("os", "execve"),
    ("os", "fork"), ("os", "posix_spawn"), ("os", "startfile"),
    ("importlib", "import_module"), ("subprocess", "run"), ("subprocess", "Popen"),
    ("shutil", "which"), ("platform", "popen"),
}
FORBIDDEN_MODULES_ATTR_ONLY = {"importlib"}


class Auditor(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.findings = []

    def _flag(self, node, what):
        self.findings.append((self.path, node.lineno, what))

    def visit_Import(self, node):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in FORBIDDEN_MODULES_ATTR_ONLY:
                self._flag(node, "imports '%s' (dynamic import surface)" % alias.name)
            if root in FORBIDDEN_MODULES:
                self._flag(node, "imports '%s'" % alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        root = (node.module or "").split(".")[0]
        if root in FORBIDDEN_MODULES:
            self._flag(node, "imports from '%s'" % node.module)
        self.generic_visit(node)

    def visit_Call(self, node):
        # A BARE name: eval(...). obj.eval() is somebody else's method.
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            self._flag(node, "calls builtin %s()" % node.func.id)
        # A dotted call: os.system(...), importlib.import_module(...).
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            pair = (node.func.value.id, node.func.attr)
            if pair in FORBIDDEN_ATTRS:
                self._flag(node, "calls %s.%s() — shells out or imports by name"
                           % pair)
        self.generic_visit(node)


def audit(directory):
    findings = []
    for root, _dirs, files in os.walk(directory):
        if "__pycache__" in root:
            continue
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            a = Auditor(os.path.relpath(path, os.path.dirname(directory)))
            a.visit(tree)
            findings.extend(a.findings)
    return findings


def selftest():
    """A clean report is only meaningful if a dirty one would have been caught."""
    print("offline-audit self-test — injecting violations the audit claims to catch")
    cases = [
        ("import socket", "direct import"),
        ("import urllib.request", "submodule import"),
        ("from subprocess import run", "from-import"),
        ("import socket as s", "aliased import"),
        ("x = eval('1+1')", "builtin eval"),
        ("y = exec('pass')", "builtin exec"),
        ("import os\nos.system('curl http://x')", "os.system shell-out"),
        ("import os\nos.popen('nc h 443')", "os.popen shell-out"),
        ("import importlib\nimportlib.import_module('socket')", "importlib by name"),
        ("import os\nos.execv('/bin/sh', [])", "os.execv"),
    ]
    benign = [
        ("import re\nR = re.compile('x')", "re.compile must NOT trip it"),
        ("class Q:\n    def eval(self): pass\nQ().eval()", "obj.eval() must NOT trip it"),
        ("import json, hashlib, decimal", "stdlib offline modules are fine"),
        ("import os\np = os.path.join('a','b')", "os.path must NOT trip it"),
        ("import os\nos.walk('.')", "os.walk must NOT trip it"),
    ]
    failures = 0
    tmp = tempfile.mkdtemp()
    pkg = os.path.join(tmp, "scripts")
    os.makedirs(pkg, exist_ok=True)
    for src, label in cases:
        p = os.path.join(pkg, "probe.py")
        open(p, "w", encoding="utf-8").write(src + "\n")
        caught = bool(audit(pkg))
        print("  %-22s %s" % (label, "caught" if caught else "SURVIVED"))
        failures += 0 if caught else 1
    for src, label in benign:
        p = os.path.join(pkg, "probe.py")
        open(p, "w", encoding="utf-8").write(src + "\n")
        tripped = bool(audit(pkg))
        print("  %-22s %s" % (label, "FALSE POSITIVE" if tripped else "ok"))
        failures += 1 if tripped else 0
    print("=" * 60)
    print("SELF-TEST: %s" % ("PASS" if not failures else "FAIL (%d)" % failures))
    return 0 if not failures else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Prove the offline guarantee from the AST.")
    ap.add_argument("--selftest", action="store_true",
                    help="prove the audit can fail before trusting a clean result")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    findings = audit(HERE)
    print("offline audit — scanning %s" % os.path.relpath(HERE, os.path.dirname(HERE)))
    if findings:
        for path, line, what in findings:
            print("  VIOLATION %s:%d — %s" % (path, line, what))
        print("=" * 60)
        print("OFFLINE AUDIT: FAIL (%d violation(s)) — the privacy claim is broken."
              % len(findings))
        return 1
    n = sum(1 for r, _d, fs in os.walk(HERE) if "__pycache__" not in r
            for f in fs if f.endswith(".py"))
    print("  %d Python files, 0 networking/subprocess/ctypes imports, "
          "0 builtin eval/exec/__import__ calls" % n)
    print("=" * 60)
    print("OFFLINE AUDIT: PASS — no import- or call-level path to the network.")
    print("            (a static audit, not a sandbox — see the module docstring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
