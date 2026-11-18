# 快速上手：三种打开方式

三种，按需要选一种。

---

## A. 只想看，不跑代码（1 分钟）

发这几个文件就够了：

- `report/LexFlow_Report.pdf`（7 页报告）
- `report/LexFlow_Slides.pdf`（8 页幻灯片）
- `runs/ui_api.png`（界面截图）
- 再配一个 3–5 分钟录屏（`report/demo_script.md` 是脚本）

这条路最稳，不依赖环境、不烧 API。

---

## B. 本地跑（5 分钟，不需要 API key）

```bash
git clone <仓库地址>
cd lexflow

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 启动界面（没有 key 会自动用 mock 模式，界面和截图一样）
.venv/bin/python -m streamlit run app/streamlit_app.py
```

浏览器打开 `http://localhost:8501`。

想先看命令行版（零依赖，连 streamlit 都不用装）：

```bash
PYTHONPATH=src python3 -m lexflow.cli demo --with-tort
PYTHONPATH=src python3 eval/run_evals.py          # 12 案例 × 4 配置
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

### 接真实 DeepSeek（可选）

在项目根目录的 `.env` 写：

```
API-key=sk-...
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LEXFLOW_LLM=api
```

再启动界面即可。没有 key 时，`LLMConfig` 会自动回退到 mock，不会报错。

---

## C. 变成一个公网链接（可选）

### C1. Streamlit Community Cloud（推荐，免费）

1. 把本仓库推到 GitHub。
2. 打开 <https://share.streamlit.io> → New app → 选仓库。
3. Main file path 填 `app/streamlit_app.py`。
4. 不要加任何 secret，直接 Deploy：没 key 会自动 mock，适合公开演示。
5. 想用真实模型，再在 App settings → Secrets 加：

```toml
LLM_API_KEY = "sk-..."
LEXFLOW_LLM = "api"
LLM_MODEL = "deepseek-chat"
```

⚠️ 公网 + 真 key = 任何人点一下都可能花你的钱。公开演示版本建议保持 mock；真模型只在自己电脑上跑、或录屏。

### C2. 临时隧道（只在自己电脑上）

```bash
# 先切 mock，避免别人用你的 key
LEXFLOW_LLM=mock .venv/bin/python -m streamlit run app/streamlit_app.py

# 另开一个终端（需要安装 cloudflared）
cloudflared tunnel --url http://localhost:8501
```

会得到一个 `https://xxx.trycloudflare.com` 的临时地址；电脑关了就失效。

---

## 不要发的东西

| 不要发 | 原因 |
|---|---|
| `.env` | 里面有 API key |
| `.venv/` | 563MB，且只适用于你的机器 |
| `runs/*.sqlite` | 本地会话状态，可能含对话数据 |
| `__pycache__/`、`.DS_Store` | 垃圾文件 |

仓库根目录的 `.gitignore` 已经排除了这些；如果曾经 push 过 `.env`，去 DeepSeek 后台把 key 轮换一次。

---

## 常见问题

**Q：为什么别人打不开 `http://127.0.0.1:8503`？**
`127.0.0.1` 就是“这台电脑自己”，不是公网地址。要么让对方本地跑（B），要么部署（C1），要么发录屏（A）。

**Q：没有 API key 时能看到什么？**
能看到完整的追问、备忘录、事实表、引用和修订流程；只是“给当事人的说明”那段会缺（mock 不调用模型），其他一样。

**Q：需要装 Node / 前端吗？**
不需要。Streamlit 是 Python 的，`pip install -r requirements.txt` 就够。
