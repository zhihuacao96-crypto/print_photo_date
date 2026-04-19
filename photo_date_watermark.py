import io
import os
import sys
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image, ImageDraw, ImageFont
from PyQt5 import QtCore, QtGui, QtWidgets

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}

DATE_FORMATS = {
    "YYYY.MM.DD": "%Y.%m.%d",
    "YYYY年MM月DD日": "%Y年%m月%d日",
    "MM/DD/YYYY": "%m/%d/%Y",
}

FONT_MAP = {
    "Arial": "arial.ttf",
    "Arial Bold": "arialbd.ttf",
    "Times New Roman": "times.ttf",
    "Courier New": "cour.ttf",
    "Verdana": "verdana.ttf",
    "Georgia": "georgia.ttf",
    "Tahoma": "tahoma.ttf",
    "Impact": "impact.ttf",
    "微软雅黑": "msyh.ttc",
    "宋体": "simsun.ttc",
    "黑体": "simhei.ttf",
    "楷体": "simkai.ttf",
}


def read_exif_date(img):
    try:
        exif = img._getexif()
    except AttributeError:
        return None
    if not exif:
        return None
    for tag_id, value in exif.items():
        tag = ExifTags.TAGS.get(tag_id)
        if tag == "DateTimeOriginal" and isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                return None
    return None


def read_photo_date(path):
    try:
        with Image.open(path) as img:
            dt = read_exif_date(img)
            if dt:
                return dt
    except Exception:
        pass
    return datetime.fromtimestamp(os.path.getmtime(path))


def load_font(font_name, size):
    size = max(1, int(size))
    filename = FONT_MAP.get(font_name, font_name)
    for candidate in (filename, font_name):
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    for fallback in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(fallback, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_watermark(img, text, font, color):
    rgba = img.convert("RGBA")
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    margin = max(10, rgba.size[0] // 80)
    x = rgba.size[0] - text_w - margin - bbox[0]
    y = rgba.size[1] - text_h - margin - bbox[1]
    brightness = sum(color) / 3
    shadow = (0, 0, 0, 220) if brightness > 110 else (255, 255, 255, 220)
    try:
        offset = max(2, font.size // 24)
    except AttributeError:
        offset = 2
    for dx in (-offset, 0, offset):
        for dy in (-offset, 0, offset):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=color + (255,))
    return Image.alpha_composite(rgba, overlay)


def save_output(rgba, src_path, out_dir, src_info, src_format, src_qtables):
    src = Path(src_path)
    ext = src.suffix.lower()
    if ext in (".jpg", ".jpeg") and src_format == "JPEG":
        dst = Path(out_dir) / src.name
        out = rgba.convert("RGB")
        kwargs = {"format": "JPEG", "optimize": True}
        if src_qtables:
            kwargs["qtables"] = src_qtables
        else:
            kwargs["quality"] = 95
        sub = src_info.get("subsampling")
        kwargs["subsampling"] = sub if isinstance(sub, int) and sub >= 0 else 2
        if src_info.get("exif"):
            kwargs["exif"] = src_info["exif"]
        if src_info.get("icc_profile"):
            kwargs["icc_profile"] = src_info["icc_profile"]
        out.save(dst, **kwargs)
    elif ext == ".png":
        dst = Path(out_dir) / src.name
        kwargs = {"format": "PNG", "optimize": True}
        if src_info.get("icc_profile"):
            kwargs["icc_profile"] = src_info["icc_profile"]
        rgba.save(dst, **kwargs)
    else:
        dst = Path(out_dir) / (src.stem + ".jpg")
        out = rgba.convert("RGB")
        kwargs = {"format": "JPEG", "quality": 95, "subsampling": 2, "optimize": True}
        if src_info.get("exif"):
            kwargs["exif"] = src_info["exif"]
        if src_info.get("icc_profile"):
            kwargs["icc_profile"] = src_info["icc_profile"]
        out.save(dst, **kwargs)
    return dst


def process_one(src, out_dir, date_fmt, font_name, font_size, color):
    dt = read_photo_date(src)
    text = dt.strftime(date_fmt)
    with Image.open(src) as img:
        img.load()
        src_info = {
            "exif": img.info.get("exif"),
            "icc_profile": img.info.get("icc_profile"),
            "subsampling": img.info.get("subsampling"),
        }
        src_format = img.format
        src_qtables = getattr(img, "quantization", None)
        font = load_font(font_name, font_size)
        watermarked = draw_watermark(img, text, font, color)
    save_output(watermarked, src, out_dir, src_info, src_format, src_qtables)


class Worker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, int)
    error = QtCore.pyqtSignal(str)
    finished_all = QtCore.pyqtSignal(int, int)

    def __init__(self, files, out_dir, date_fmt, font_name, font_size, color):
        super().__init__()
        self.files = files
        self.out_dir = out_dir
        self.date_fmt = date_fmt
        self.font_name = font_name
        self.font_size = font_size
        self.color = color

    def run(self):
        ok, fail = 0, 0
        total = len(self.files)
        for i, src in enumerate(self.files):
            try:
                process_one(str(src), self.out_dir, self.date_fmt,
                            self.font_name, self.font_size, self.color)
                ok += 1
            except Exception as e:
                fail += 1
                self.error.emit(f"{Path(src).name}: {e}")
            self.progress.emit(i + 1, total)
        self.finished_all.emit(ok, fail)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("照片日期水印工具")
        self.resize(1000, 640)
        self.input_dir = ""
        self.output_dir = ""
        self.color = (255, 255, 255)
        self.worker = None
        self._preview_pix = None
        self._build_ui()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)

        left_container = QtWidgets.QWidget()
        left_container.setFixedWidth(320)
        left = QtWidgets.QVBoxLayout(left_container)
        root.addWidget(left_container, 0)

        self.btn_in = QtWidgets.QPushButton("选择照片文件夹")
        self.btn_in.clicked.connect(self.pick_input)
        left.addWidget(self.btn_in)
        self.lbl_in = QtWidgets.QLabel("未选择")
        self.lbl_in.setWordWrap(True)
        self.lbl_in.setStyleSheet("color: gray;")
        left.addWidget(self.lbl_in)

        self.btn_out = QtWidgets.QPushButton("选择输出文件夹")
        self.btn_out.clicked.connect(self.pick_output)
        left.addWidget(self.btn_out)
        self.lbl_out = QtWidgets.QLabel("未选择")
        self.lbl_out.setWordWrap(True)
        self.lbl_out.setStyleSheet("color: gray;")
        left.addWidget(self.lbl_out)

        left.addSpacing(8)
        left.addWidget(QtWidgets.QLabel("日期格式"))
        self.combo_fmt = QtWidgets.QComboBox()
        self.combo_fmt.addItems(DATE_FORMATS.keys())
        self.combo_fmt.currentTextChanged.connect(self.update_preview)
        left.addWidget(self.combo_fmt)

        left.addWidget(QtWidgets.QLabel("字体样式"))
        self.combo_font = QtWidgets.QComboBox()
        self.combo_font.addItems(FONT_MAP.keys())
        self.combo_font.currentTextChanged.connect(self.update_preview)
        left.addWidget(self.combo_font)

        self.lbl_size = QtWidgets.QLabel("字体大小: 48")
        left.addWidget(self.lbl_size)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(12, 500)
        self.slider.setValue(48)
        self.slider.valueChanged.connect(self._on_size_changed)
        left.addWidget(self.slider)

        self.btn_color = QtWidgets.QPushButton()
        self.btn_color.clicked.connect(self.pick_color)
        self._refresh_color_btn()
        left.addWidget(self.btn_color)

        left.addStretch(1)

        self.btn_start = QtWidgets.QPushButton("开始处理")
        self.btn_start.setStyleSheet("font-weight: bold; padding: 8px;")
        self.btn_start.clicked.connect(self.start_processing)
        left.addWidget(self.btn_start)

        self.progress = QtWidgets.QProgressBar()
        left.addWidget(self.progress)

        self.lbl_status = QtWidgets.QLabel("")
        self.lbl_status.setStyleSheet("color: #666;")
        left.addWidget(self.lbl_status)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(QtWidgets.QLabel("预览（第一张照片）"))
        self.preview = QtWidgets.QLabel("选择照片文件夹以预览")
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setStyleSheet("background: #1e1e1e; color: #888; border-radius: 4px;")
        self.preview.setMinimumSize(400, 400)
        right.addWidget(self.preview, 1)
        root.addLayout(right, 1)

    def _refresh_color_btn(self):
        r, g, b = self.color
        fg = "#000" if (r + g + b) / 3 > 128 else "#fff"
        self.btn_color.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: {fg}; padding: 6px;"
        )
        self.btn_color.setText(f"字体颜色  #{r:02X}{g:02X}{b:02X}")

    def _on_size_changed(self, v):
        self.lbl_size.setText(f"字体大小: {v}")
        self.update_preview()

    def pick_input(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择照片文件夹")
        if d:
            self.input_dir = d
            self.lbl_in.setText(d)
            self.lbl_in.setStyleSheet("color: #222;")
            self.update_preview()

    def pick_output(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择输出文件夹")
        if d:
            self.output_dir = d
            self.lbl_out.setText(d)
            self.lbl_out.setStyleSheet("color: #222;")

    def pick_color(self):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(*self.color), self, "选择字体颜色")
        if c.isValid():
            self.color = (c.red(), c.green(), c.blue())
            self._refresh_color_btn()
            self.update_preview()

    def list_images(self):
        if not self.input_dir:
            return []
        files = []
        for name in sorted(os.listdir(self.input_dir)):
            p = Path(self.input_dir) / name
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                files.append(p)
        return files

    def update_preview(self):
        files = self.list_images()
        if not files:
            self.preview.setText("未找到支持的图片")
            self._preview_pix = None
            return
        try:
            src = files[0]
            dt = read_photo_date(str(src))
            fmt = DATE_FORMATS[self.combo_fmt.currentText()]
            text = dt.strftime(fmt)
            with Image.open(src) as img:
                img.load()
                original_w = img.size[0]
                img.thumbnail((1600, 1600))
                scale = img.size[0] / original_w if original_w else 1.0
                preview_font_size = max(6, int(self.slider.value() * scale))
                font = load_font(self.combo_font.currentText(), preview_font_size)
                out = draw_watermark(img, text, font, self.color)
            buf = io.BytesIO()
            out.convert("RGB").save(buf, "JPEG", quality=85)
            pix = QtGui.QPixmap()
            pix.loadFromData(buf.getvalue())
            self._preview_pix = pix
            self._render_preview()
        except Exception as e:
            self.preview.setText(f"预览失败: {e}")
            self._preview_pix = None

    def _render_preview(self):
        if self._preview_pix is None:
            return
        scaled = self._preview_pix.scaled(
            self.preview.size(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._render_preview()

    def start_processing(self):
        if not self.input_dir:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择照片文件夹")
            return
        if not self.output_dir:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择输出文件夹")
            return
        if os.path.abspath(self.input_dir) == os.path.abspath(self.output_dir):
            QtWidgets.QMessageBox.warning(self, "提示", "输出文件夹不能与输入相同")
            return
        files = self.list_images()
        if not files:
            QtWidgets.QMessageBox.warning(self, "提示", "未找到支持的图片")
            return
        os.makedirs(self.output_dir, exist_ok=True)
        self.btn_start.setEnabled(False)
        self.progress.setMaximum(len(files))
        self.progress.setValue(0)
        self.lbl_status.setText(f"开始处理 {len(files)} 张…")
        self.worker = Worker(
            files,
            self.output_dir,
            DATE_FORMATS[self.combo_fmt.currentText()],
            self.combo_font.currentText(),
            self.slider.value(),
            self.color,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished_all.connect(self._on_done)
        self.worker.start()

    def _on_progress(self, cur, total):
        self.progress.setValue(cur)
        self.lbl_status.setText(f"处理中 {cur}/{total}")

    def _on_worker_error(self, msg):
        sys.stderr.write(msg + "\n")

    def _on_done(self, ok, fail):
        self.btn_start.setEnabled(True)
        self.lbl_status.setText(f"完成 — 成功 {ok}，失败 {fail}")
        QtWidgets.QMessageBox.information(
            self, "完成", f"处理完成。\n成功: {ok}\n失败: {fail}\n输出: {self.output_dir}"
        )


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
