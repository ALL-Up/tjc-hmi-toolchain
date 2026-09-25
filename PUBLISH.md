# 上传到 GitHub —— 操作步骤

仓库已在本机整理好并完成首次提交：

```
<本仓库目录>\
```

体积 180 KB，25 个文件，1 个 commit（`fdc7391`）。下面是把它推上 GitHub 的步骤。

---

## 步骤 0（可选）：先本地确认一遍

想确认推送的就是想要的东西：

```bash
cd "<本仓库目录>"
git log --stat          # 看这次提交都包含什么
```

---

## 步骤 1：在 GitHub 上新建仓库

1. 打开 https://github.com/new
2. **Repository name** 填一个名字，建议：`tjc-hmi-toolchain`
3. **Description** 可以直接用：
   ```
   淘晶驰 (TJC) USART HMI 串口屏 .HMI 工程文件格式逆向与纯代码生成工具链
   ```
4. 可见性选 **Public**（想要私有也行，不影响后续步骤）
5. ⚠️ **关键：不要勾选** `Add a README file`、`.gitignore`、`license` ——
   本仓库这三样都已存在，勾了会产生冲突
6. 点 **Create repository**
7. 创建后页面会显示仓库地址，形如：
   ```
   https://github.com/<你的用户名>/tjc-hmi-toolchain.git
   ```
   记下来，下一步要用。

---

## 步骤 2：关联远程仓库并推送

> ## ⚠️ 先 cd，再敲 git
>
> **最容易犯的错：忘了第一行的 `cd`，于是在家目录（`$env:USERPROFILE`）里执行了 `git init`。**
> 那样会把**整个家目录**变成一个 git 仓库（`git status` 会列出你所有的配置目录），
> 一旦误跑 `git add -A`，你的配置文件甚至凭据就可能被提交进去。
>
> 敲任何 git 命令前，先确认提示符左边的路径是 `publish_stage`。
> 拿不准就先 `pwd`（或 `git rev-parse --show-toplevel`）看一眼。
> 已经踩了这个坑？见文末「常见问题 → 家目录被误 init 成 git 仓库」。

```bash
cd "<本仓库目录>"   # ← 别跳过这行！
pwd                                                  # 确认输出就是 publish_stage

git remote add origin https://github.com/<你的用户名>/tjc-hmi-toolchain.git
git branch -M main
git push -u origin main
```

> 💡 本仓库**已经添加好 `origin` 了**，所以 `git remote add` 会报
> `remote origin already exists` —— 那是正常的，跳过它直接 `git push` 即可。

推送时会要求登录：

- **推荐：Personal Access Token**
  GitHub 早已不支持账号密码。去
  https://github.com/settings/tokens → *Generate new token (classic)* →
  勾 **`repo`** 权限 → 生成 → 复制（只显示一次）。
  推送时：
  - Username：你的 GitHub 用户名
  - Password：**粘贴那个 token**（不是登录密码）
- 或者在弹出的浏览器窗口里点授权（装了 Git Credential Manager 时会有）

成功后刷新 GitHub 页面就能看到文件了。

---

## 步骤 3：补上仓库信息

推完之后建议做两件小事：

1. **改 LICENSE 里的版权人**（第 3 行 `Copyright (c) 2026 <YOUR NAME>`），
   把 `<YOUR NAME>` 换成你的名字或 GitHub ID，然后：
   ```bash
   git add LICENSE
   git commit -m "docs: 填写版权人"
   git push
   ```
2. **给仓库加 Topics**（GitHub 网页右上齿轮 → Topics），建议：
   ```
   tjc  usart-hmi  serial-display  reverse-engineering  embedded  stm32  python  hmi
   ```
   有助于被搜到。

---

## 备用路线：用 GitHub CLI（比手动建仓库省事）

如果本机装了 `gh`（GitHub 官方命令行）：

```bash
cd "<本仓库目录>"
gh auth login                                  # 浏览器授权一次
gh repo create tjc-hmi-toolchain --public --source=. --remote=origin --push
```

一条命令完成「建仓库 + 关联 + 推送」。

没装的话，Windows 下：
```bash
winget install --id GitHub.cli
```
> ⚠️ 本机实测 `winget` 下载 `gh` 会失败（`0x80190190 : Bad request (400)`，网络/代理原因）。
> 见「常见问题 → winget 下载失败」。**`gh` 不是必需的** ——
> 用 git + PAT 一样能推，别在这卡住。

装完**重开终端**再执行上面的命令。

---

## 常见问题

### 家目录被误 init 成 git 仓库

**症状**：在 `$env:USERPROFILE`（即 `C:\Users\<你的用户名>`）里敲过 `git init`，
之后在家目录下 `git status` 会列出
一大堆untracked目录（`.dsh/`、`.config/`、`.dotnet/` …）。

**危害**：家目录成了「工作区」。哪天误跑 `git add -A` + `commit`，配置文件和凭据就进版本库了。

**处理**（先确认没有真实数据在里面）：

```powershell
# 1) 看这个仓库到底追踪了什么 —— 正常应该只有你误建的 README.md 之类
git -C "$env:USERPROFILE" ls-files

# 2) 确认只有误建文件后，把 .git 移走（移动而非删除，可随时恢复）
Move-Item "$env:USERPROFILE\.git" "$env:USERPROFILE\Desktop\_home_git_backup" -Force

# 3) 顺手清掉误建的文件
Remove-Item "$env:USERPROFILE\README.md" -Force -ErrorAction SilentlyContinue

# 4) 核对：应输出 fatal: not a git repository
git -C "$env:USERPROFILE" rev-parse --is-inside-work-tree
```

> ⚠️ 步骤 1 若列出**任何你以为不在里面的文件**，先停下来别删，
> 把 `ls-files` 的结果发出来确认。

### `push` 报 `The requested URL returned error: 403`

先分清是**认证问题**还是**网络问题**。跑这条（空仓库 + 公开仓库，匿名就能访问）：

```powershell
git ls-remote https://github.com/<用户名>/<仓库名>.git
```

| 结果 | 结论 | 处理 |
|---|---|---|
| 正常退出、无输出 | 网络没问题 → **是认证** | 见下面「认证」 |
| **也是 403** | **网络被劫持**（最常见是加速器） | 见下面「加速器劫持」 |
| 超时 | 网络/代理不通 | 见下面「代理」 |

#### 加速器劫持（国内最常见的 403 元凶）

**症状**：`git ls-remote` 也 403，且 `winget`/`curl` 访问 github 同样失败。

**鉴别方法**：看 hosts 文件里 `github.com` 指向哪。

```powershell
Get-Content "$env:SystemRoot\System32\drivers\etc\hosts" | Select-String github
Test-NetConnection github.com -Port 443 | Select-Object RemoteAddress
```

如果输出里 `github.com` 指向 **`127.0.0.1`**，且 `RemoteAddress` 也是 `127.0.0.1`
→ 说明被 **Steam++（Watt Toolkit）** 之类的加速器劫持了：
它把 github 域名改写到本机，再由自己的本地代理（默认 `127.0.0.1:1182` / `:443`）转发。

**怎么确认是它**：直接问那个本地代理要一次响应，看 `Server` 头。

```powershell
curl.exe -sS -D - -o NUL --proxy http://127.0.0.1:1182 `
  "https://github.com/<用户名>/<仓库名>.git/info/refs?service=git-upload-pack"
```

若返回 `403` 且响应头里有 **`Server: WattToolkit`**（或类似加速器标识）
→ **403 是加速器给的，不是 GitHub 给的**。这时候你怎么调 git / token 都没用。

**处理**：关掉加速器的 GitHub 加速，然后**重开一个终端**。

1. 打开 Watt Toolkit / Steam++ → 「网络加速」→ 关闭 **GitHub** 相关条目；
   或者直接在托盘右键 **退出** 整个程序（正常退出会自动还原 hosts）
2. **关掉后必须重开终端** —— 加速器会把 `HTTP_PROXY=http://127.0.0.1:1182`
   注入到已启动的进程里，旧窗口的环境变量不会自动刷新
3. 验证劫持已解除（`RemoteAddress` 应是真实 GitHub IP，不是 `127.0.0.1`）：
   ```powershell
   Test-NetConnection github.com -Port 443 | Select-Object RemoteAddress
   ```
4. 重新 `git push`

> 💡 **加速器退出后 hosts 里可能残留**（比如程序异常终止）。
> 若 `github.com` 仍指向 `127.0.0.1`，需以**管理员**身份编辑
> `C:\Windows\System32\drivers\etc\hosts`，删掉 `# Steam++ Start … # Steam++ End`
> 之间的行，或在加速器界面里点一次「清理/还原 hosts」。
>
> 💡 **加速器关不掉怎么办（国内常态）：改用 SSH，加速器照常开着。**
> 这就是本机最终采用的方案 —— 见下面「方案 A」。

#### 方案 A（推荐）：改用 SSH，加速器不用关

**适用**：你不开加速器就上不了 GitHub，但加速器又把 git 的 HTTP(S) 打死。
**原理**：加速器只劫持 `github.com` / `api.github.com` / `*githubusercontent.com`
这几个**域名**；而 **`ssh.github.com` 不在劫持列表里**，且 SSH 根本不走 HTTP 代理。
所以 SSH-over-443 完全绕开这个坑，**加速器可以一直开着**（网页照常加速）。

**一次性配置（4 步）**：

```powershell
# ① 生成密钥（已有可跳过）
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -N '""' -C "你的标识"

# ② 复制公钥内容
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub"
```

③ 打开 https://github.com/settings/keys → **New SSH key** → 粘贴上一步的内容 → 保存
（这一步走浏览器，加速器正常加速，没问题）

```powershell
# ④ 让标准 github.com 的 SSH 自动转到 ssh.github.com:443
#    写进 $env:USERPROFILE\.ssh\config
```

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

**验证 + 切换远程地址**：

```powershell
ssh -T git@github.com
#  成功会显示: Hi <用户名>! You've successfully authenticated...
#  只显示 Permission denied (publickey) 且没有 Hi... → 公钥没加上，回第 ③ 步

git remote set-url origin ssh://git@ssh.github.com:443/<用户名>/<仓库名>.git
git push -u origin main
```

> 不想动 `~/.ssh/config` 也行，直接用显式地址即可（效果相同）：
> `ssh://git@ssh.github.com:443/<用户名>/<仓库名>.git`
>
> 本机实测：`ssh.github.com` 的 **22 和 443 都通**，
> banner 为 `SSH-2.0-<hash>`（GitHub 的 SSH 端点特征）。
> 优先用 443 —— 很多网络封 22 却放行 443。

#### 方案 B：不想配 SSH，就只让加速器「忽略 github.com」

在加速器的加速项里把 **`github.com` 设为忽略/不加速**，保留
`api.github.com`、`*githubusercontent.com` 等其它项。这样：
- `github.com` 恢复真实解析 → git 的 HTTP(S) 能直连
- 网页其它资源（头像、raw 文件）仍走加速

代价：`github.com` 网页本身不再被加速，可能变慢。
**若你连 github.com 网页都打不开，就别用这条，走方案 A。**

#### 方案 C：把加速器切成「系统代理模式」并让 git 走它

有些加速器提供「系统代理模式」（而非 hosts 改写）。切过去后：

```powershell
# 查系统代理端口：设置 → 网络和 Internet → 代理
git config --global http.proxy 127.0.0.1:<端口>
```

⚠️ 但加速器做 MITM，git 会报证书错误，需要**把加速器的根证书导入
「受信任的根证书颁发机构」**（`certmgr.msc`，当前用户 + 本地计算机都要加）。
**不建议**图省事直接 `git config --global http.sslVerify false` —— 那等于全局关掉
TLS 校验，会带来真实风险。

#### 方案 D：不走 git，直接网页上传

最省事、绝对能成。仓库已压成单个提交，网页上传得到的结果基本等价：

1. 打开 `https://github.com/<用户名>/<仓库名>/upload/main`
   （空仓库直接点 "uploading an existing file"）
2. 把 `publish_stage` 里的**文件夹整体拖进去**（GitHub 支持拖文件夹，会保留目录结构）
3. 写提交信息 → Commit

> ⚠️ 网页上传**不要**拖 `.git` 目录；`.gitignore` / `.gitattributes` 是普通文本文件，
> 可以一起上传。上传后仍需手改 `LICENSE` 里的 `<YOUR NAME>`。

**认证**：本机 `credential.helper = manager` 且 GCM 2.9.0 已就位，
正常情况下 `git push` 会**自动弹出浏览器**让你登录 GitHub。
如果没弹窗、直接 403，按顺序试：

```powershell
# ① 显式确认凭据助手配置
git config --global credential.helper manager

# ② 清掉可能过期的缓存凭据，再推（这次留意有没有弹浏览器）
cmdkey /list | Select-String github
git push -u origin main

# ③ 还不行就显式带 token 推一次（把 <TOKEN> 换成你的 PAT）
git push https://ALL-Up:<TOKEN>@github.com/ALL-Up/tjc-hmi-toolchain.git main
```

PAT 生成：https://github.com/settings/tokens → *Generate new token (classic)*
→ 勾 **`repo`** → 复制（只显示一次）。**注意 token 不是登录密码。**

**代理**：如果本机在跑代理软件（VPN / Clash / 等），先把它的**环境变量**临时清掉再试，
这是最常见的「403 但和账号无关」的原因：

```powershell
$env:HTTP_PROXY=""; $env:HTTPS_PROXY=""
git push -u origin main
```

反过来，如果你本来就需要代理才能连 GitHub，那就把代理配上（端口改成自己的）：

```powershell
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
# 用完了想取消：
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### `winget install --id GitHub.cli` 下载失败（400 Bad Request）

`winget` 的下载走系统 HTTP 栈，容易被代理/网络过滤拦掉，报
`Download request status is not success. 0x80190190 : Bad request (400)`。
和 git 的 403 常常是**同一个网络原因**。

**但 `gh` 不是必需的** —— 用 git + PAT 一样能推（见上）。真想要 `gh`，绕开 winget：

1. 浏览器打开 https://github.com/cli/cli/releases/latest
   下载 `gh_*_windows_amd64.msi`，双击安装（这条路径通常比 winget 通）
2. 或者先关掉代理软件再 `winget install --id GitHub.cli`
3. 装完**重开终端**（PATH 需要刷新），`gh --version` 验证

### 浏览器出现 GitHub 的 `Whoa there!`

这是 GitHub 的**风控 / 次级速率限制**页（不是 404，也不是被封号），**按 IP 判定**。
常见触发：

- 你在**共享出口 IP** 后面（加速器 / VPN / 公司网络，同一 IP 上很多人用）
- 短时间内请求过密（反复刷新、反复重试认证）
- 未登录状态下访问 `/settings/*` 这类敏感页 + IP 可疑

**症状会连带出现**：

```powershell
ssh -T git@github.com
# Connection reset by 20.205.243.160 port 443     ← 从这里判断被限流
```

> 注意区分三种结果：
> | 输出 | 含义 |
> |---|---|
> | `Permission denied (publickey)` | ✅ 通道正常，只差公钥没加 |
> | `Connection reset by ...` | ⚠️ **被限流了**（握手阶段被掐断） |
> | 超时 / refused | ❌ 端口不通 |

**判断是不是本地问题**（轻量探测，不做认证，不会加重风控）：

```powershell
# 只连一次读 banner。正常应回 SSH-2.0-<hash>
ssh -o BatchMode=yes -o ConnectTimeout=8 -p 443 git@ssh.github.com
```

若能拿到 banner 却仍在认证阶段 reset → **是 GitHub 限流，不是你的网络坏**。

**处理（按推荐顺序）**：

1. **立刻停手 15–30 分钟。** 每重试一次就延长封禁窗口 —— 刷新网页、重连 SSH 都算。
2. **换 IP（最快）**：切**手机热点**，新 IP 立刻干净。
   加公钥 + push 一次做完。
3. 或在同网络下等风控窗口自然过期。
4. 加公钥前**先确认已登录 GitHub** —— 未登录 + 可疑 IP 最容易吃这页。
5. 换 IP 后如果还有问题，再考虑让加速器**暂时**只忽略 `github.com`
   （见上文「方案 B」）。

> ⚠️ 风控期间**「加公钥」和「网页上传」两条路都会堵**（都要用网页）。
> 所以**换 IP 是唯一能立刻解开全部阻塞的动作** —— 别在原地反复试。

### `remote origin already exists`

```bash
git remote remove origin
git remote add origin https://github.com/<用户名>/<仓库名>.git
```


本仓库初始化时没加远程，正常不会遇到。真遇到就先删：
```bash
git remote remove origin
```

### 推送报 `failed to push some refs` / `rejected`

说明远程仓库不是空的（多半是建仓库时勾了 README）。
```bash
git pull --rebase origin main
git push -u origin main
```

### 推送卡住 / 报 SSL 或证书错误

本机实测 git 走 schannel 时若遇到证书吊销检查问题（`CRYPT_E_NO_REVOCATION_CHECK`），
可以：
```bash
git config http.schannelCheckRevoke false
```
或改用 SSH（`git@github.com:<用户名>/仓库名.git`）。

### 推送很慢

国内网络直连 GitHub 常常慢。可用代理（把端口换成你自己的）：
```bash
git config http.proxy http://127.0.0.1:7890
git config https.proxy http://127.0.0.1:7890
```
推完想取消：`git config --unset http.proxy`

### 想改仓库名/描述

都在 GitHub 网页的 **Settings** 里改，本地无需变动，
但若改了**仓库名**，记得同步远程地址：
```bash
git remote set-url origin https://github.com/<用户名>/<新仓库名>.git
```

---

## 上传前请自查（重要）

推送是公开发布，建议过一遍：

- [ ] **LICENSE 第 3 行的 `<YOUR NAME>` 已替换**
- [ ] `README.md` 里的项目描述符合你的意愿（特别是「免责与说明」一节）
- [ ] 确认 `reference/` 下的样本你真想公开 ——
      它们是**你自己机器的上位机生成**的工程文件，用于格式回归。
      如果你觉得连这些也不想公开，可以删掉 `truth_project.HMI.gz`：
      回归测试会**自动跳过**容器克隆那一项并明确提示，不会报错。
      （真值小样本 `reference/truth/*` 有同样性质，但只有 14 KB，
      建议保留 —— 没有它们回归测试就失去意义了。）
- [ ] 没有混进个人路径、口令、私钥
      ```bash
      git grep -n -i "password\|token\|secret\|api[_-]key"
      ```
- [ ] 没有混进大文件
      ```bash
      git ls-files | xargs -I{} du -h {}   # 逐个看体积，最大应为 truth_project.HMI.gz 约 8 KB
      ```

---

## 关于法律边界（建议读一下）

本项目的做法是**黑盒分析你自己机器上的上位机产出的工程文件**，
目的是让你能用程序生成自己的工程，不再手工拖控件。仓库里：

- ✅ 只包含**你自己产出的样本文件**、你自己写的 Python 代码、格式文档
- ❌ **不包含**淘晶驰上位机程序、其 DLL、任何解密工具或反编译产物

README 的「免责与说明」一节已写明这一点。发布时保持这些内容，
并把「上游反编译 DLL」相关的过程描述留在你自己的笔记里，不要写进公开仓库。
