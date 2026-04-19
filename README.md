# 照片日期水印工具

一个带 GUI 的照片日期水印工具：读取 EXIF 拍摄日期（无 EXIF 时回退到文件修改时间），在照片右下角添加日期水印，不修改原图。

## 功能

- 选择照片文件夹 / 输出文件夹
- 实时预览第一张照片的水印效果
- 日期格式：`YYYY.MM.DD` / `YYYY年MM月DD日` / `MM/DD/YYYY`
- 字体样式（Arial / Times / Courier / 微软雅黑 / 宋体 / 黑体 / 楷体 等）
- 字体大小滑块
- 字体颜色拾色器（带自动对比阴影，保证在亮暗背景均可见）
- 支持 jpg、png、heic / heif
- 处理时显示进度条，后台线程不卡 UI

## 运行（开发模式）

```bash
pip install -r requirements.txt
python photo_date_watermark.py
```

## 打包为 Windows .exe

在 Windows 上，从 Python 3.10+ 环境运行：

```cmd
build.bat
```

产物位于 `dist\PhotoDateWatermark.exe`，单文件可直接分发。

手动命令等价于：

```
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name PhotoDateWatermark ^
  --collect-all pillow_heif ^
  photo_date_watermark.py
```

## 注意

- HEIC 输出会转存为 JPEG（HEIC 写入支持不稳定）。
- 字体查找依赖系统字体目录；在 Windows 上内置字体均可用。非 Windows 环境会回退到系统可用字体或 PIL 默认字体。
