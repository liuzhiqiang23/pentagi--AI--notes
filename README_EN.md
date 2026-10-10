# PentAGI Deployment and Security Lab Notes

**A hands-on record of deploying PentAGI on Windows 11, troubleshooting it, and completing an authorized security-testing and remediation cycle.**

[中文](./README.md) | **English**

These notes document a one-day lab using Windows 11, WSL2, Docker Compose, and PentAGI. They cover deployment, troubleshooting misleading scan results, Docker storage migration, an authorized red-team/blue-team exercise, and host hardening. The notes are sanitized and contain no API keys, real passwords, or private network details.

## Contents

- `docs/01-部署篇-PentAGI上线.md` — WSL2 and Docker deployment, Kali sandbox, and model integration
- `docs/02-排障篇-代理污染之谜.md` — diagnosing proxy-related false or misleading scan results
- `docs/03-运维篇-C盘空间救援.md` — moving Docker data and using a Windows directory junction
- `docs/04-实战篇-红蓝对抗闭环.md` — authorized testing, remediation, and regression checks
- `docs/05-加固篇-主机安全体检.md` — a host-hardening checklist and example fixes
- `lab/` — intentionally vulnerable practice application
- `lab-fixed/` — hardened counterpart and regression checks

## Suggested reading order

Start with the deployment guide, then read the troubleshooting and operations notes. The red-team/blue-team exercise and hardening checklist are for understanding the complete authorized lab workflow.

## Safety

The vulnerable application is for an isolated environment that you own or are explicitly authorized to test. Do not scan, exploit, or access systems without permission. Treat example credentials and vulnerable configurations as lab material only; never reuse them in real services.

The detailed source documents remain in Chinese. This English README is an orientation and links to those original materials.
