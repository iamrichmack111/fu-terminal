#!/usr/bin/env python3
import subprocess
import shutil
import json


def run(cmd):
    try:
        p = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=10
        )
        return p.stdout.strip() or p.stderr.strip()
    except Exception as e:
        return f"ERROR: {e}"


def section(name):
    print()
    print(name)
    print("─" * 88)


print()
print("◆ FU KUBERNETES STORAGE DOCTOR")
print("─" * 88)
print("READ ONLY — no Kubernetes, containerd, or filesystem data will be modified.")

section("FILESYSTEM")
print(run(["df", "-h", "/"]))

section("INODES")
print(run(["df", "-ih", "/"]))

section("NODE STORAGE CONDITIONS")
print(run([
    "kubectl", "get", "nodes",
    "-o",
    "custom-columns="
    "NAME:.metadata.name,"
    "READY:.status.conditions[?(@.type=='Ready')].status,"
    "DISK:.status.conditions[?(@.type=='DiskPressure')].status,"
    "MEMORY:.status.conditions[?(@.type=='MemoryPressure')].status,"
    "PID:.status.conditions[?(@.type=='PIDPressure')].status"
]))

section("RICHMACK DISK CONDITION")
print(run([
    "kubectl", "get", "node", "richmack",
    "-o",
    "jsonpath={range .status.conditions[?(@.type=='DiskPressure')]}{.type}{'='}{.status}{' reason='}{.reason}{' message='}{.message}{' changed='}{.lastTransitionTime}{'\\n'}{end}"
]))

section("NODE CAPACITY")
print(run([
    "kubectl", "get", "node", "richmack",
    "-o",
    "custom-columns="
    "NAME:.metadata.name,"
    "EPHEMERAL:.status.capacity.ephemeral-storage,"
    "EPHEMERAL_ALLOCATABLE:.status.allocatable.ephemeral-storage"
]))

section("KUBELET FILESYSTEM VIEW")

raw = run([
    "kubectl", "get", "--raw",
    "/api/v1/nodes/richmack/proxy/stats/summary"
])

try:
    data = json.loads(raw)
    node = data.get("node", {})
    fs = node.get("fs", {})
    runtime = node.get("runtime", {})
    imagefs = runtime.get("imageFs", {})
    containerfs = runtime.get("containerFs", {})

    def gib(value):
        if value is None:
            return "unknown"
        return f"{value / (1024 ** 3):.1f} GiB"

    capacity = fs.get("capacityBytes")
    available = fs.get("availableBytes")
    used = fs.get("usedBytes")

    pct = None
    if capacity and used is not None:
        pct = used / capacity * 100

    print(f"Node capacity       {gib(capacity)}")
    print(f"Node used           {gib(used)}" + (
        f" ({pct:.1f}%)" if pct is not None else ""
    ))
    print(f"Node available      {gib(available)}")
    print(f"ImageFS used        {gib(imagefs.get('usedBytes'))}")
    print(f"ContainerFS used    {gib(containerfs.get('usedBytes'))}")
    print(f"Inodes used         {fs.get('inodesUsed', 'unknown')}")
    print(f"Inodes free         {fs.get('inodesFree', 'unknown')}")

except Exception:
    print("Kubelet filesystem statistics unavailable")

section("CONTAINERD / K3S STORAGE")
paths = [
    "/var/lib/rancher/k3s",
    "/var/lib/rancher/k3s/agent/containerd",
    "/var/lib/kubelet",
    "/var/log",
]

for path in paths:
    print(run(["sudo", "-n", "du", "-sh", path]))

section("CONTAINERD IMAGES")
if shutil.which("k3s"):
    images = run([
        "sudo", "-n", "k3s", "ctr",
        "images", "list"
    ])
    lines = images.splitlines()
    if len(lines) <= 8:
        print(images)
    else:
        print("\n".join(lines[:8]))
        print(f"... {len(lines) - 8} additional image row(s) omitted")
else:
    print("k3s command not found")

section("RECENT STORAGE EVENTS")
print(run([
    "bash", "-lc",
    "kubectl get events -A --sort-by=.lastTimestamp | "
    "grep -E 'DiskPressure|FreeDiskSpace|ImageGC|EvictionThreshold' | tail -n 10"
]))

print()
print("No resources were modified.")
