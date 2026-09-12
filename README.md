<div align="center">

# PentAGI 部署实战笔记

**用一台 Windows 11 电脑,一天跑通 AI 自主渗透测试平台**

[![platform](https://img.shields.io/badge/platform-Windows%2011%20·%20WSL2%20·%20Docker-blue)](##-运行环境参考)
[![lang](https://img.shields.io/badge/文档-中文-red)](#)
[![stars](https://img.shields.io/github/stars/liuzhiqiang23/pentagi--AI--notes?style=social)](https://github.com/liuzhiqiang23/pentagi--AI--notes/stargazers)

**[中文](#这个仓库是什么) | [English](#english)**

</div>

> 2026-09-09 单日实录：从零部署 AI 渗透测试平台 → 排障 → 自建漏洞靶场 → AI 红蓝对抗 → 主机安全加固。

## 这个仓库是什么

一台 Windows 11 电脑上用一天时间，把 **PentAGI**（AI 自主渗透测试编排平台，Go 栈，Docker Compose 部署）从零跑通，并完成一轮完整的"授权渗透测试 + AI 自动修复 + 回归验证"闭环的**全过程笔记**。所有内容均已脱敏：不含任何 API Key、真实密码、内网细节。

**适合人群**：信息安全学习者 / 想了解 AI Agent 做安全测试长什么样的人 / 想在自己机器上复现 PentAGI 部署的人。

## 目录

```
pentagi-lab-notes/
├── README.md
├── docs/
│   ├── 01-部署篇-PentAGI上线.md        # WSL2+Docker+Compose 部署、20GB Kali 沙箱、GLM 对接
│   ├── 02-排障篇-代理污染之谜.md       # "假扫描结果"根因排查方法论（含对照实验设计）
│   ├── 03-运维篇-C盘空间救援.md        # Docker 40GB 数据盘迁移 + 目录联接(junction)
│   ├── 04-实战篇-红蓝对抗闭环.md       # 渗透→修复→30项回归测试，AI 全程自主完成
│   └── 05-加固篇-主机安全体检.md       # 检查清单 + MySQL/RDP 真实漏洞修复
├── lab/            # 故意含漏洞的靶场应用（SQLi/命令注入/XSS/弱口令）——仅供授权环境
└── lab-fixed/      # AI 渗透测试后输出的"加固版" + 它自己写的回归测试套件
```

## 内容速览

| 文档 | 一句话 |
|---|---|
| [部署篇](docs/01-部署篇-PentAGI上线.md) | PentAGI + Kali 沙箱(Docker) 在本机的完整落地过程与踩坑 |
| [排障篇](docs/02-排障篇-代理污染之谜.md) | 为什么 AI 扫出"全端口开放 + 全是 502"——系统代理劫持 Docker 流量的完整排查链 |
| [运维篇](docs/03-运维篇-C盘空间救援.md) | C 盘被 40GB Docker 数据盘塞满 → junction 迁移到 D 盘，释放 40G+ |
| [实战篇](docs/04-实战篇-红蓝对抗闭环.md) | 靶场设计 → AI 自主完成评估 → 揪出我埋的 3 洞 + 额外 5 个真实问题 → 写修复代码 → 30 项测试驱动到 30/30 |
| [加固篇](docs/05-加固篇-主机安全体检.md) | 真实主机的体检与修复（MySQL 全网卡监听、RDP、33060 X 协议端口） |

## 🗺 阅读路线

- **只想把 PentAGI 跑起来** → 01 部署篇
- **扫描结果不对劲 / 全是假数据** → 02 排障篇(方法论可迁移到任何 Docker 网络问题)
- **C 盘被 Docker 吃满了** → 03 运维篇
- **想看 AI 自主渗透到底能干什么** → 04 实战篇(本文最大亮点)
- **检查一下自己电脑的安全配置** → 05 加固篇

## 运行环境（参考）

- Windows 11（10.0.26200）+ WSL 2.7 + Docker Desktop（WSL2 后端）
- PentAGI：`vxcontrol/pentagi`（docker compose，含 pentagi / pgvector / scraper / postgres-exporter）
- 沙箱镜像：`vxcontrol/kali-linux`（约 20.5GB，内含 nmap/sqlmap/metasploit 等）
- LLM：智谱 GLM（也可无缝切 DeepSeek / MiMo / OpenAI 兼容端点）

## ⚠️ 安全边界声明

- 本仓库内容仅用于**授权环境**的安全研究与教学。
- 自主渗透 agent **只能对你有明确授权的目标**使用；对任何第三方系统运行均属违法。
- `lab/` 下的应用**故意含漏洞**，仅限本机/容器隔离环境练习，切勿暴露到公网。
- 文中所有账号密码均为虚构演示值。

## English

One-day field notes (2026-09-09) on standing up **PentAGI** — an autonomous AI pentest orchestration platform (Go, Docker Compose) — from scratch on a single Windows 11 machine, then running a full closed loop: **authorized pentest → AI-driven fixes → regression-verified hardening**. All content is sanitized (no API keys, real credentials, or internal network details).

| Doc | What it covers |
|---|---|
| [Deployment](docs/01-部署篇-PentAGI上线.md) | Full local setup: WSL2 + Docker Compose + 20GB Kali sandbox + GLM integration |
| [Troubleshooting](docs/02-排障篇-代理污染之谜.md) | Why the AI scanned "all ports open, everything 502" — system proxy hijacking Docker traffic, root-caused step by step |
| [Ops](docs/03-运维篇-C盘空间救援.md) | Moving a 40GB Docker data disk off C: with NTFS junctions |
| [Red vs Blue](docs/04-实战篇-红蓝对抗闭环.md) | Seeded-vuln lab → AI finds 3 planted + 5 real issues → writes its own fixes → 30/30 regression tests green |
| [Hardening](docs/05-加固篇-主机安全体检.md) | Real-host security checklist & fixes (MySQL binding, RDP, X-protocol port) |

⚠️ For **authorized environments only**. The apps in `lab/` are intentionally vulnerable — never expose them to the public internet.

---

如果这批笔记对你有帮助,欢迎点个 ⭐ Star —— 这是独立笔记作者唯一的更新动力。

**Star this repo if it helped you — it's the only fuel for an independent note-taker.** ⭐
