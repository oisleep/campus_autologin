给**美丽的女朋友**准备的CUMT校园网强制下线后自动登录脚本

# Campus AutoLogin（macOS）——中文说明

自动为高校校园网（表单型 Captive Portal，如锐捷 / 深澜 / Drcom 类）完成后台登录的守护程序。  
适合在 **锁屏 / 无人值守** 的情况下，自动重建认证会话，让远程工具（AnyDesk / SSH 等）能够在登录后接入。

> 说明：本工具只适用于**表单式认证**（表单 POST 或简单重定向）。若门户使用复杂 JS 加密或 SPA，可能需要 Selenium 降级方案。

---

## 仓库结构（示例）

```
campus-autologin-mac/
├── bin/
│   └── campus_autologin.py        # 自动登录脚本（Python 健壮版）
├── launchd/
│   └── com.campus.autologin.plist # launchd 用户级配置
├── requirements.txt
└── README.md                      # 就是这个文件（中文）
```

---

## 快速概览（工作原理）

1. 周期或网络变化时向 `http://clients3.google.com/generate_204` 等 URL 发起请求判断是否被重定向到认证门户。  
2. 若检测到门户，脚本从 macOS **Keychain** 读取用户名和密码，GET 登录页解析表单（包含隐藏字段/CSRF），再 POST 提交凭据。  
3. 成功后脚本记录日志，LaunchAgent 保证常驻与网络事件触发。

---

## 安装与配置步骤（详细）

### 1. 克隆仓库

```bash
git clone https://github.com/oisleep/campus_autologin.git
cd campus_autologin
```

### 2. 创建 Python 虚拟环境并安装依赖

```bash
python3 -m venv ~/venvs/campus_login
source ~/venvs/campus_login/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` 应包含：

```
requests
beautifulsoup4
lxml
```

### 3. 把凭据写入 macOS Keychain（**非常重要：不要把密码写入仓库/脚本**）

请把你的校园网用户名/密码存进 Keychain，脚本会从 Keychain 读取。**替换下面的 `YOUR_USERNAME` / `YOUR_PASSWORD`**：

```bash
# 将用户名存为 campus_net_user（可选）
security add-generic-password -a "$(whoami)" -s "campus_net_user" -w "YOUR_USERNAME" -U
# 将密码存为 campus_net_pass
security add-generic-password -a "$(whoami)" -s "campus_net_pass" -w "YOUR_PASSWORD" -U
```

### 4. 编辑脚本（可选）

脚本已内置自动解析表单与常用判断逻辑，但特殊门户可能需手动微调：

- 路径：`bin/campus_autologin.py`
- 可调整项：`CHECK_URLS`, `SUCCESS_HINTS`, 超时时间、重试次数等。

### 5. 手动测试（强烈建议）

```bash
source ~/venvs/campus_login/bin/activate
python bin/campus_autologin.py --verbose
tail -n 200 /tmp/campus_autologin.log
```

### 6. 配置 LaunchAgent（常驻）

1. 复制 plist 到用户 LaunchAgents：

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.campus.autologin.plist ~/Library/LaunchAgents/
```

2. 编辑 `com.campus.autologin.plist`：修改脚本路径为你的实际路径。  
3. 加载 Agent：

```bash
launchctl load ~/Library/LaunchAgents/com.campus.autologin.plist
launchctl list | grep com.campus.autologin
```

---

## 7. AnyDesk 与电源设置

- 开启 AnyDesk **Unattended Access**，设置强密码并允许开机自启。  

- 在系统隐私设置中授予 AnyDesk **辅助功能 / 屏幕录制** 权限。  

- 不要合盖；关闭自动睡眠，或使用：

  ```bash
  caffeinate -dimsu &
  ```

---

## 模拟测试方法

1. 忘记 Wi-Fi → 重新连接。  

2. 切换 Wi-Fi 开关。  

3. 修改 MAC 地址：  

   ```bash
   sudo ifconfig en0 ether xx:xx:xx:xx:xx:xx
   ```

4. 直接请求检测 URL：

   ```bash
   curl -i http://clients3.google.com/generate_204
   ```

---

## 调试

- 日志路径：`/tmp/campus_autologin.log`  
- 浏览器抓包 → Network → Request URL / Form Data / Hidden Fields → 对照脚本调整。  
- 若门户依赖 JS → 考虑 Selenium 版本。

---

## 合规提示

- 部分学校强制夜间断网是政策规定，本工具无法绕过物理封网。  
- 建议申请科研/夜间账号，而非强行绕过。  
- 请确保密码只存在 Keychain，不要硬编码到脚本或仓库。

---

## License

禁止用于任何商业用途，使用者自行承担因违规使用导致的风险。
