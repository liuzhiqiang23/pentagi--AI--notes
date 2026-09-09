# 部署篇：PentAGI 上线（WSL2 + Docker Desktop + GLM）

## 一、部署路径

PentAGI 官方只提供 Docker Compose 部署。本机（Windows 11）当时**既没有 Docker 也没有 WSL2**，于是分四步走：

1. **装 WSL2**（v2.7.13）——坑：`wsl.exe` 在非提权 shell 里自装无效，只会打印“请运行 wsl --install”。需用 `Start-Process wsl.exe -ArgumentList '--install','--no-distribution' -Verb RunAs -Wait` 触发 UAC 提权才能真正装。
2. **启用“虚拟机平台”可选组件**（WSL2 的底层）——提权跑 `dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart`。**必须重启电脑生效**；重启后验证：`HypervisorPresent=True`。
3. **装 Docker Desktop**（29.7.2）——`winget install Docker.DockerDesktop --silent`。
4. **克隆 + 配置 + compose up**：
   ```bash
   git clone https://github.com/vxcontrol/pentagi.git D:\pentagi
   cd D:\pentagi && cp .env.example .env   # 按需修改
   docker compose up -d
   ```

## 二、镜像拉取踩坑

- Docker Hub 在国内**直连不稳定**：`docker compose up` 中途报 `failed to copy ... EOF`。
- 解法：**直接重试即可续传**（已下载层会复用），无需配镜像加速。重试脚本：
  ```bash
  for i in 1 2 3 4 5; do docker compose up -d && break; sleep 20; done
  ```
- 首个任务会现场拉 `vxcontrol/kali-linux`（**20.5GB**），UI 上任务一直显示 Waiting，约 10 分钟——**别误判为卡死**。

## 三、LLM Provider 配置（以 GLM 为例）

PentAGI 原生支持 GLM / DeepSeek / Kimi / Qwen / MiniMax / Ollama / OpenAI 兼容端点等 10+ 供应商。API Key 走 **.env 环境变量**（服务端），UI 里只是“角色→模型”的映射。

```bash
# 智谱国内平台的关键三行
GLM_API_KEY=your_key
GLM_SERVER_URL=https://open.bigmodel.cn/api/paas/v4   # 默认是 z.ai 国际版，国内 key 必须改
GLM_PROVIDER=                                        # LiteLLM 前缀，直连留空
```

- Embedding：`EMBEDDING_PROVIDER=openai` + `EMBEDDING_URL=https://open.bigmodel.cn/api/paas/v4` + `EMBEDDING_MODEL=embedding-3`（OpenAI 兼容姿势通吃国产端点）。
- 改 .env 后要 `docker compose up -d` 让容器重建生效。
- 验证 key 与模型可用性，先直连 API 测过再进 UI：
  ```bash
  curl https://open.bigmodel.cn/api/paas/v4/chat/completions -H "Authorization: Bearer $KEY" \
    -d '{"model":"glm-5.2","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
  ```
- **坑**：某模型可能在 chat 接口可用但**不在 `/v4/models` 列表里**（智谱平台不一致）——PentAGI 的“Test”按钮校验模型列表就会报 400。选模型前先查 `GET /v4/models` 确认在列（实测 `glm-4.5-flash` 不在列、`glm-5.3-flash` 在列且免费）。

## 四、沙箱机制

- 每个 Flow 启动时创建一个 **Kali 沙箱容器**（`pentagi-terminal-<id>`），nmap/sqlmap/metasploit 等 20+ 工具都在里面，与宿主机隔离。
- 保持默认 `DOCKER_INSIDE=false`——不要给沙箱挂载宿主机 Docker 套接字（沙箱逃逸风险，官方文档明确警告）。

## 五、访问与账号

- Web UI：`https://localhost:8443`（自签证书，浏览器提示“高级→继续前往”即可）。
- 默认账号 `admin@pentagi.com / admin`，**首登立即改密**。
- 一键启动脚本（检测/拉起 Docker → compose up → 开浏览器）可参考本仓库使用的 `PentAGI-Launcher.cmd` 思路（注意批处理变量延迟展开坑，见下）。

## 六、当日其它小坑

| 现象 | 根因 |
|---|---|
| `cmd` 启动器报“此时不应有 24” | 括号块内 `%var%` 提前展开 → 改用 label+goto 结构 |
| Git Bash 里跑批处理 timeout 报错 | PATH 里 GNU timeout 抢先 → 脚本内写死 `%SystemRoot%\System32\timeout.exe` |
| 提权命令输出丢失 | `Start-Process -Verb RunAs` 的窗口不回流 → 用 `*> 文件` 落盘再读 |

_完_
