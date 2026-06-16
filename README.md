# Mercury PoE Switch — Home Assistant 集成

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

一个用于水星 (Mercury) SE109P Pro PoE 交换机的 Home Assistant 自定义集成。支持 PoE 供电控制、功率监控、端口状态统计、环回检测等功能。

> 该型号常以中科网联、巨联等品牌出现，只要是同款固件界面，均可使用本集成。

> ⚠️ **声明**: 本项目代码主要由 AI 生成，仅供学习和研究用途。使用者请自行评估代码质量和安全性，在生产环境使用前请充分测试。

## 功能

| 功能 | 实体类型 | 说明 |
|------|----------|------|
| PoE 端口开关 | `switch` | 独立控制 8 个 PoE 端口的供电开关（1-8 口） |
| PoE 功率总览 | `sensor` | 总功率、已用功率、剩余功率、功率使用率 |
| PoE 端口监控 | `sensor` | 每个端口：功率(W)、电流(mA)、电压(V)、供电状态、PD Class |
| 端口速率 | `sensor` | 每个端口（1-9 口）的收发包速率 (pkts/s) |
| 端口统计 | `sensor` | 每个端口的正常/失败收发包计数 |
| 端口连接状态 | `sensor` | 每个端口的连接状态和实际协商速率 |
| 环回检测 | `binary_sensor` | 检测网络环回，`problem` 设备类别 |
| 设备信息 | `sensor` | 固件版本、MAC 地址、IP 地址、运行时间 |
| 重新上电 | `button` | 一键重新上电（PoE 端口断电再恢复） |

## 截图

> 配置完成后，在 Home Assistant 中会生成一个设备和数十个传感器实体，PoE 端口开关可直接在 Lovelace 仪表盘中使用。

## 安装

> 要求 Home Assistant 版本 ≥ `2024.1.0`。

### 方式一：HACS 安装（推荐）

> 如果你还未安装 HACS，请先访问 [hacs.xyz](https://hacs.xyz/) 按照指引完成安装。

1. 在 Home Assistant 侧边栏打开 **HACS**
2. 点击 **集成**
3. 点击右上角 `⋮` 菜单 → **自定义存储库**
4. 在弹出的对话框中填入：
   - **URL**: `https://github.com/weiecn/ha-mercury-switch`
   - **类别**: 选择 **集成**
5. 点击 **添加**
6. 在搜索框中输入 **Mercury PoE Switch**
7. 点击 **下载**
8. **重启 Home Assistant**

> 后续有新版本时，HACS 会提示更新，一键即可升级。

### 方式二：手动安装

<details>
<summary>通过 git clone 安装</summary>

```bash
# 进入 Home Assistant 配置目录下的 custom_components
cd /path/to/your/homeassistant/config/custom_components

# 克隆仓库
git clone https://github.com/weiecn/ha-mercury-switch.git mercury_switch

# 重启 Home Assistant
docker restart homeassistant
# 或者
ha core restart
```
</details>

<details>
<summary>通过下载 ZIP 包安装</summary>

```bash
# 1. 下载仓库 ZIP 包
wget https://github.com/weiecn/ha-mercury-switch/archive/main.zip

# 2. 解压
unzip main.zip

# 3. 只复制 integration 目录到 custom_components
cp -r ha-mercury-switch-main/custom_components/mercury_switch \
     /path/to/your/homeassistant/config/custom_components/

# 4. 清理
rm -rf ha-mercury-switch-main main.zip

# 5. 重启 Home Assistant
```
</details>

手动安装后的目录结构应为：

```
config/
└── custom_components/
    └── mercury_switch/
        ├── __init__.py
        ├── manifest.json
        ├── api.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── sensor.py
        ├── switch.py
        ├── button.py
        ├── binary_sensor.py
        ├── strings.json
        └── translations/
            └── zh-Hans.json
```

### 更新

**HACS 用户**: 在 HACS 面板中点击更新即可。

**手动安装用户**:

```bash
cd /path/to/your/homeassistant/config/custom_components/mercury_switch
git pull
# 或重新下载 ZIP 覆盖
# 然后重启 Home Assistant
```

### 卸载

1. 删除集成实体：**设置 → 设备与服务 → Mercury Switch → `⋮` → 删除**
2. 删除文件：`rm -rf /path/to/your/homeassistant/config/custom_components/mercury_switch`
3. 重启 Home Assistant

## 配置

> 本集成通过 Home Assistant 的 UI 配置，无需手动编辑 YAML。

1. 进入 **设置 → 设备与服务 → 添加集成**
2. 搜索 **"Mercury PoE Switch"**
3. 填写连接信息：
   - **IP 地址**: 交换机的 IP 地址（例如 `192.168.1.100`）
   - **用户名**: 交换机管理用户名（默认 `admin`）
   - **密码**: 交换机管理密码
4. 点击提交，集成会自动验证连接并完成配置

## 支持的设备

- **Mercury (水星) SE109P Pro** — 9 口千兆 PoE 交换机（8 PoE + 1 上行）

其他使用相同固件界面的 OEM 型号理论上也可使用。如果你的设备不在此列表中但能正常工作，欢迎提交 Issue 告知我们。

## 工作原理

本集成通过 HTTP 协议与交换机的 Web 管理界面通信：

1. **登录认证** — 使用交换机自定义的 XOR 编码算法加密密码，通过 `/logon.cgi` 登录并获取 SessionID
2. **数据采集** — 每 30 秒轮询交换机的 HTML 管理页面，从中提取 JavaScript 变量获取实时数据：
   - `PoeConfigRpm.htm` — PoE 配置和端口供电状态
   - `PortSettingRpm.htm` — 以太网端口速率/双工状态
   - `MainRpm.htm` — 运行时间、收发包速率、环回检测
   - `PortStatisticsRpm.htm` — 端口收发数据包统计
   - `LoopPreventionRpm.htm` — 环回防护配置
   - `SystemInfoRpm.htm` — 系统固件和硬件信息
3. **控制指令** — 通过 CGI 接口发送 POST 请求来控制 PoE 端口开关、重新上电等

## 实体列表

<details>
<summary>点击展开完整实体列表</summary>

| 实体 ID | 名称 | 类型 |
|---------|------|------|
| `switch.poe_port_1` ~ `switch.poe_port_8` | PoE Port 1~8 | switch |
| `button.poe_port_1_power_cycle` ~ `button.poe_port_8_power_cycle` | PoE Port 1~8 Power Cycle | button |
| `sensor.total_power` | PoE 总功率 | sensor |
| `sensor.used_power` | PoE 已用功率 | sensor |
| `sensor.remaining_power` | PoE 剩余功率 | sensor |
| `sensor.power_usage_pct` | PoE 功率使用率 | sensor |
| `sensor.poe_port_1_power` ~ `sensor.poe_port_8_power` | PoE 端口 1~8 功率 | sensor |
| `sensor.poe_port_1_current` ~ `sensor.poe_port_8_current` | PoE 端口 1~8 电流 | sensor |
| `sensor.poe_port_1_voltage` ~ `sensor.poe_port_8_voltage` | PoE 端口 1~8 电压 | sensor |
| `sensor.poe_port_1_status` ~ `sensor.poe_port_8_status` | PoE 端口 1~8 供电状态 | sensor |
| `sensor.poe_port_1_pd_class` ~ `sensor.poe_port_8_pd_class` | PoE 端口 1~8 PD Class | sensor |
| `sensor.port_1_rx_rate` ~ `sensor.port_9_rx_rate` | 端口 1~9 收包速率 | sensor |
| `sensor.port_1_tx_rate` ~ `sensor.port_9_tx_rate` | 端口 1~9 发包速率 | sensor |
| `sensor.port_1_tx_good` ~ `sensor.port_9_tx_good` | 端口 1~9 正常发包 | sensor |
| `sensor.port_1_tx_bad` ~ `sensor.port_9_tx_bad` | 端口 1~9 失败发包 | sensor |
| `sensor.port_1_rx_good` ~ `sensor.port_9_rx_good` | 端口 1~9 正常收包 | sensor |
| `sensor.port_1_rx_bad` ~ `sensor.port_9_rx_bad` | 端口 1~9 失败收包 | sensor |
| `sensor.port_1_link_status` ~ `sensor.port_9_link_status` | 端口 1~9 连接状态 | sensor |
| `sensor.port_1_link_speed` ~ `sensor.port_9_link_speed` | 端口 1~9 实际速率 | sensor |
| `sensor.uptime` | 运行时间 | sensor |
| `sensor.loop_prevention` | 环回保护 | sensor |
| `binary_sensor.loop_detected` | Loop Detected | binary_sensor |

</details>

## 自动化示例

```yaml
# 当端口 3 连接的设备离线时，重新上电
automation:
  - alias: "PoE 端口 3 设备离线重启"
    trigger:
      - platform: state
        entity_id: sensor.poe_port_3_status
        to: "未供电"
    action:
      - service: button.press
        target:
          entity_id: button.poe_port_3_power_cycle
      - delay:
          seconds: 30

# 当网络环回检测到时发送通知
automation:
  - alias: "网络环回告警"
    trigger:
      - platform: state
        entity_id: binary_sensor.loop_detected
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ 网络环回告警"
          message: "交换机检测到网络环回，请检查网络连接！"
```

## 调试

如果遇到问题，请在 Home Assistant 的 `configuration.yaml` 中启用调试日志：

```yaml
logger:
  logs:
    custom_components.mercury_switch: debug
```

然后重启 Home Assistant 并查看日志。

## 常见问题

**Q: 连接失败 / 登录失败？**  
A: 请确保交换机 IP 地址正确，且 Home Assistant 与交换机在同一网络中。尝试用浏览器访问 `http://<交换机IP>` 确认可以打开管理界面。

**Q: 数据更新不及时？**  
A: 默认轮询间隔为 30 秒，这是平衡数据时效性和交换机负载的合理设置。

**Q: 支持其他型号的水星交换机吗？**  
A: 只要是相同固件界面（SE109P Pro 及其 OEM 版本），理论上都兼容。其他型号需要验证。

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

- 🐛 报告 Bug：[提交 Issue](https://github.com/weiecn/ha-mercury-switch/issues)
- 💡 功能建议：[提交 Issue](https://github.com/weiecn/ha-mercury-switch/issues)
- 🔧 代码贡献：[Fork + Pull Request](https://github.com/weiecn/ha-mercury-switch/pulls)

## 鸣谢

- 水星 (Mercury) SE109P Pro 交换机的逆向分析
- [Home Assistant](https://www.home-assistant.io/) 开源社区
