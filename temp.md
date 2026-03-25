
Dựa trên `pyproject.toml` và README, bạn có thể làm như sau:

---

## Chạy nhanh (không cài vào hệ thống)

Đã có `uv` và đang ở thư mục project:

```bash
cd /home/billarch/Github/personal/billpanel
uv sync                    # cài dependency
uv run python run.py       # chạy app
```

Hoặc dùng entry point:

```bash
uv run billpanel
```

---

## Chạy test

```bash
uv sync --group dev        # cài thêm dev deps (pytest, ruff, ...)
uv run pytest              # chạy toàn bộ test
```

Chạy một file test:

```bash
uv run pytest tests/test_config.py -v
```

---

## Cài trực tiếp (editable / development)

Cài project ở chế độ “editable” để sửa code và chạy không cần cài lại:

```bash
cd /home/billarch/Github/personal/billpanel
uv sync
uv pip install -e .        # hoặc: pip install -e .
```

Sau đó có thể chạy từ bất kỳ đâu:

```bash
billpanel
# hoặc
python -m billpanel
```

(Lệnh `billpanel` chỉ có khi shell đang dùng đúng môi trường có cài package.)

---

## Linter / format (development)

```bash
uv run ruff check src/
uv run ruff format src/
```

---

## Tóm tắt lệnh

| Mục đích | Lệnh |
|----------|------|
| Cài dependency | `uv sync` |
| Chạy app | `uv run python run.py` hoặc `uv run billpanel` |
| Chạy test | `uv run pytest` |
| Cài editable | `uv sync` rồi `uv pip install -e .` |
| Config mặc định | `uv run generate_default_config` |
| Tạo keybindings Hyprland | `uv run create_keybindings` |
| Debug | `uv run billpanel --debug` |

**Lưu ý:** Cần có sẵn GTK, Playerctl, và môi trường Hyprland/Wayland (nếu chạy full panel). Nếu chỉ chạy test hoặc import code thì `uv run pytest` hoặc `uv run python -c "from billpanel.services import audio_visualizer_service; print('ok')"` là đủ.