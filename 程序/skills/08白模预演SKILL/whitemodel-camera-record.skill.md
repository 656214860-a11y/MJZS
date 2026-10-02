---
name: whitemodel-camera-record
displayName: 机位录制
description: 把机位与运动录成一条可复用的路径，并出可播放的白模小片
stage: 白模预演
capabilities: []
preferredModels: []
fallbackModels: []
tools: [whitemodel.recordCamera, whitemodel.setCamera]
dependsOn: [whitemodel-scene-build]
conflictsWith: []
parallelizable: true
paid: false
input: [sceneJson, cameraPlan]
output: [cameraPath, previewClip]
constraints: [路径平滑, 关键帧完整, 时长贴合镜头]
feedback:
  - onProgress: 更新三虎进度
  - onError: 可重试自动重试, 不可重试通知
  - onComplete: 通知并推进阶段
examples:
  - 用户："把这一镜的机位录下来" → whitemodel.recordCamera({ shotId })
  - 用户："这条运镜能复用吗" → whitemodel.exportCameraPath({ shotId })
---

## 说明
### 这个 SKILL 干什么
把镜头语言方案落成真正的机位数据：起点、终点、中间的插值，录成一条路径；顺带渲一段
低分辨率白模小片，让你先看运动对不对再看成片。

### 具体做四件事
1. 摆机位：按镜头方案设好起始与结束机位。
2. 录路径：把推拉摇移跟走一遍，中间关键帧补满。
3. 出小片：后台渲染低分辨率预览，画幅与时长贴合这一镜。
4. 交路径：把路径数据导出，后面的视频生成直接读。

### 什么时候用它
- 正式生成之前先看运动对不对。
- 同一个景要复用机位，先录成路径。

### 输入／输出
- 输入：场景工程、由已采用分镜提供的镜头机位方案。
- 输出：机位路径、白模预览小片。

### 用到的工具
- `whitemodel.recordCamera`：07 白模预演 → 录制运镜
- `whitemodel.setCamera`：07 白模预演 → 镜头机位

### 约束与验收
- 路径要平滑：出现一顿一顿的就重录。
- 时长贴合镜头：白模小片与分镜时长一致才看得准。
- 不要打开 Blender 桌面窗口：后台跑，用户要看时自己调工程文件。

### 进度与反馈
- `onProgress`：这一步的进度写到三虎的进度面板与「手动制作XX」的执行结果里。
- `onError`：可重试的走 agent 的退避重试，不可重试的把原因记进错误账本并说给你听。
- `onComplete`：收尾时推进阶段，并在三虎那儿报一句结果。
- 模型不写死在这个 SKILL 里：由 ModelRouter 按 capabilities、成本与可用性在 preferredModels／
  fallbackModels 里挑；阶段配置面板上手选的那一档优先。
