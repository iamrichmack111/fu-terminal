#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import socket
import os

def cmd(command, timeout=8):
    try:
        p = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout
        )
        out = (p.stdout + p.stderr).strip()
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, str(e)

def section(title):
    print()
    print(title)
    print("─" * 76)

def show(command, timeout=8):
    print(f"$ {command}")
    rc, out = cmd(command, timeout)
    print(out if out else "(no output)")
    if rc:
        print(f"[exit {rc}]")
    print()

def kubernetes():
    section("◆ FU KUBERNETES DOCTOR")
    print("READ ONLY — no Kubernetes resources will be modified.")

    if not shutil.which("kubectl"):
        print("\n✗ kubectl not found")
        return

    section("NODES")
    show("kubectl get nodes -o wide")

    section("PODS")
    show("kubectl get pods -A -o wide")

    section("UNHEALTHY PODS")
    show(
        """kubectl get pods -A --no-headers | """
        """awk '$4 != "Running" && $4 != "Completed" {print}'"""
    )

    section("DEPLOYMENTS")
    show("kubectl get deployments -A")

    section("SERVICES")
    show("kubectl get svc -A")

    section("INGRESS")
    show("kubectl get ingress -A")

    section("RECENT WARNING EVENTS")
    show(
        "kubectl get events -A "
        "--field-selector type=Warning "
        "--sort-by=.lastTimestamp | tail -n 25"
    )

    section("RESOURCE USAGE")
    show("kubectl top nodes 2>/dev/null || true")
    show("kubectl top pods -A 2>/dev/null | head -n 25 || true")

    print("FU Kubernetes Doctor completed without modifying the cluster.")

    section("FINDINGS")
    show(
        'python3 "/home/richmack/Applications/granite-fu/kubernetes_findings.py"',
        timeout=10
    )


def docker():
    section("◆ FU DOCKER DOCTOR")
    print("READ ONLY — no containers, images, volumes, or caches will be removed.")

    if not shutil.which("docker"):
        print("\n✗ docker not found")
        return

    section("CONTAINERS")
    show("docker ps -a")

    section("RESOURCE USAGE")
    show("docker stats --no-stream")

    section("DISK USAGE")
    show("docker system df")

    section("UNHEALTHY / EXITED")
    show(
        """docker ps -a --format '{{.Names}}\\t{{.Status}}' | """
        """grep -Ei 'unhealthy|exited|dead|restarting' || true"""
    )

    section("NETWORKS")
    show("docker network ls")

    section("VOLUMES")
    show("docker volume ls")

    print("FU Docker Doctor completed without modifying Docker.")


def network():
    section("◆ FU NETWORK DOCTOR")
    print("READ ONLY — no network configuration will be changed.")

    section("HOST")
    print("Hostname:", socket.gethostname())

    section("ADDRESSES")
    show("ip -brief addr")

    section("ROUTES")
    show("ip route")

    section("DNS")
    show("resolvectl status 2>/dev/null | head -n 60 || cat /etc/resolv.conf")

    section("LISTENING PORTS")
    show("ss -lntup")

    section("DEFAULT GATEWAY")
    rc, gateway = cmd("ip route | awk '/default/ {print $3; exit}'")

    if gateway:
        print("Gateway:", gateway)
        show(f"ping -c 2 -W 2 {gateway}", timeout=6)
    else:
        print("No default gateway detected.")

    section("INTERNET CONNECTIVITY")
    show("ping -c 2 -W 2 1.1.1.1", timeout=6)

    section("DNS RESOLUTION")
    show("getent hosts example.com")

    print("FU Network Doctor completed without modifying networking.")


def system():
    section("◆ FU SYSTEM DOCTOR")
    print("READ ONLY — no services, processes, packages, or files will be modified.")

    section("UPTIME / LOAD")
    show("uptime")

    section("MEMORY")
    show("free -h")

    section("FILESYSTEM")
    show("df -h")

    section("FAILED SERVICES")
    show("systemctl --failed --no-pager")

    section("TOP CPU")
    show("ps aux --sort=-%cpu | head -n 11")

    section("TOP MEMORY")
    show("ps aux --sort=-%mem | head -n 11")

    section("KERNEL ERRORS")
    show(
        "journalctl -k -p err --since '-1 hour' "
        "--no-pager 2>/dev/null | tail -n 30 || true"
    )

    section("SYSTEM ERRORS")
    show(
        "journalctl -p err --since '-1 hour' "
        "--no-pager 2>/dev/null | tail -n 30 || true"
    )

    print("FU System Doctor completed without modifying the system.")


parser = argparse.ArgumentParser()
parser.add_argument("doctor", choices=["kubernetes", "docker", "network", "system"])
args = parser.parse_args()

{
    "kubernetes": kubernetes,
    "docker": docker,
    "network": network,
    "system": system,
}[args.doctor]()
