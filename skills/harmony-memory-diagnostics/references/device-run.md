# 真机运行与取证

## 设备与构建

1. 检查 `hdc`、项目构建器及 SDK 是否可用。工具通常由用户 shell 配置；仅读取所需配置，不输出 token 或完整环境。
2. `hdc list targets` 后逐台读取设备类型，区分 USB/无线真机与模拟器。目标不明确时询问，不因某个地址可连就选中。
3. 读取项目现有构建脚本和实际 build 配置。使用已验证的 DevEco/Hvigor 或项目封装入口；明确本地还是远程构建，不擅自切换源码联编与二进制依赖。
4. 保存构建结果、源代码差异和包路径/哈希。构建日志保存在本地，只展示脱敏的错误摘要；个别依赖会把整个环境写入日志。
5. 根据包签名、架构和设备兼容性安装，覆盖安装通常可用 `hdc -t <device> install -r <signed.hap>`。不要把“进程返回成功”当作安装成功，核对输出与应用版本。

运行命令示例，包和 Ability 从工程解析：

```bash
hdc -t <device> shell aa force-stop <bundle>
hdc -t <device> shell aa start -b <bundle> -a <ability>
hdc -t <device> shell ps -A -o PID,ARGS
hdc -t <device> shell bm dump -n <bundle>
```

只在本次协议需要重启、且业务已停止时 force-stop。已有运行版本足以完成只读诊断时，不必重新编译安装。

## UI 导航

```bash
hdc -t <device> shell uitest dumpLayout -p /data/local/tmp/<unique-name>.json
hdc -t <device> file recv /data/local/tmp/<unique-name>.json <local-layout.json>
hdc -t <device> shell uitest uiInput click <x> <y>
hdc -t <device> shell uitest uiInput keyEvent Back
hdc -t <device> shell snapshot_display -f /data/local/tmp/<unique-name>.jpeg
hdc -t <device> file recv /data/local/tmp/<unique-name>.jpeg <local-screen.jpeg>
```

- 优先查新鲜布局里的唯一 id，其次精确文本，再由 bounds 求中心；关键动作前重新读取。屏幕尺寸、权限弹窗与页面渲染会使旧坐标失效。
- 用功能状态计时：可见计时器、开始日志或引擎事件；点击时间只是请求发起时间。报告计时误差。
- 操作完成后确认控件或业务状态确实切换，保存前后布局与截图。上传/保存后台完成需独立日志或明确状态，尾页可见不能代替完成证明。
- 只处理当前场景需要的权限。不自动同意无关权限或触发页面上的消息发送。
- AOD 可能表现为只有时钟的布局。可以唤醒并正常上滑解锁；要求密码时交回用户，不反复点击。可先检查 `power-shell help`；若临时覆盖熄屏时间，记录并在结束时恢复。
- `snapshot_display` 在部分设备只接受 JPEG；先看命令帮助。远端临时文件使用本次唯一名称，不覆盖其他任务文件。

## 连续趋势与异常

主 PID 在正式采集开始前固定。快照期间可能出现同名临时进程，不能把所有相同 ARGS 的 PID 当作主进程相加。子进程独立记录，汇总时写清命名规则和作用域。

主进程重启、崩溃、UI 无法继续或场景被他人操作时，保存证据并停止该批连续测试；不要补一条新 PID 曲线当作同一批次。确认是否重开批次，遵循用户已有重试授权。操作超时由用户/场景协议定义；超时样本单列，不能当作清理完成后的残留。

怀疑诊断引入卡顿时先停诊断操作，读取本机命令帮助后导出应用故障事件、时间和栈。明确异常是在业务期间、快照期间还是测试完成后，不把“未再录音”写成“全程无异常”。
