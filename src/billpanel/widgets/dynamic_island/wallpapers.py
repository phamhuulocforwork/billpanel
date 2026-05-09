import contextlib
import fcntl
import hashlib
import json
import os
import random
import subprocess
import threading
import cairo
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import PangoCairo
from loguru import logger
from PIL import Image
from PIL import ImageDraw

from billpanel import constants as cnst
from billpanel.config import cfg
from billpanel.utils.window_manager import WindowManagerContext
from billpanel.widgets.dynamic_island.base import BaseDiWidget


class WallpaperApply:
    @staticmethod
    def apply_with_feh(wallpaper: str):
        try:
            subprocess.run(
                ["feh", "--no-fehbg", "--bg-fill", str(wallpaper)],
                check=True,
            )
        except FileNotFoundError:
            logger.error("feh is not installed")
        except subprocess.CalledProcessError:
            logger.error("Unknown error when installing wallpaper (feh)")

    @staticmethod
    def apply_with_awww(wallpaper: str):
        transition_fps = 60
        cursor_pos = "0,0"

        try:
            output = subprocess.check_output(
                ["wlr-randr", "--json"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for output_info in json.loads(output):
                for mode in output_info["modes"]:
                    if mode.get("current"):
                        transition_fps = int(round(mode["refresh"]))
                        break
                else:
                    continue
                break
        except Exception:
            logger.warning("Couldn't get the screen frequency using wlr-randr")

        try:
            output = subprocess.check_output(
                ["hyprctl", "cursorpos"],
                text=True,
            ).strip()
            cursor_pos = output if output else cursor_pos
        except Exception:
            logger.warning("Couldn't get the cursor position")

        try:
            subprocess.run(
                [
                    "awww",
                    "img",
                    str(wallpaper),
                    "--transition-bezier",
                    ".43,1.19,1,.4",
                    "--transition-type",
                    "grow",
                    "--transition-duration",
                    "0.4",
                    "--transition-fps",
                    str(transition_fps),
                    "--invert-y",
                    "--transition-pos",
                    cursor_pos,
                ],
                check=True,
            )
        except Exception:
            logger.error("Unknown error when installing wallpaper (awww)")


class WallpaperSelector(BaseDiWidget, Box):
    focuse_kb: bool = True
    _mapping_lock = threading.Lock()

    def __init__(self):
        Box.__init__(
            self,
            name="wallpapers",
            spacing=10,
            orientation="v",
            h_expand=False,
            v_expand=False,
        )
        self.config = cfg.modules.dynamic_island.wallpapers
        self.CACHE_DIR = cnst.WALLPAPERS_THUMBS_DIR
        self.WALLPAPERS_DIRS = [
            i
            for i in (Path(x).expanduser() for x in self.config.wallpapers_dirs)
            if i.exists()
        ]

        self.CACHE_MAPPING_FILEPATH = cnst.CACHE_MAPPING_FILEPATH
        os.makedirs(self.CACHE_DIR, exist_ok=True)

        # Собираем файлы из всех директорий и сохраняем их полные пути
        self.files_with_paths = []
        for wallpapers_dir in self.WALLPAPERS_DIRS:
            for file_name in os.listdir(str(wallpapers_dir)):
                if self._is_image(file_name):
                    full_path = os.path.join(wallpapers_dir, file_name)
                    self.files_with_paths.append((file_name, full_path))

        # Сортируем по имени файла (без учета пути)
        self.files_with_paths.sort(key=lambda x: x[0].lower())

        # очистка невалидного кэша
        self._validate_cache_mapping()

        self.thumbnails = []
        self.thumbnail_queue = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.selected_index = -1
        self.random_item_name = "__random_wallpaper__"

        # UI Setup остается без изменений
        self.viewport = Gtk.IconView(name="wallpaper-icons")
        self.viewport.set_model(Gtk.ListStore(GdkPixbuf.Pixbuf, str))
        self.viewport.set_pixbuf_column(0)
        self.viewport.set_text_column(-1)
        self.viewport.set_item_width(0)
        self.viewport.connect("item-activated", self.on_wallpaper_selected)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(
            b"#wallpaper-icons { background-color: transparent; }"
        )
        self.viewport.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.scrolled_window = ScrolledWindow(
            name="scrolled-window",
            spacing=10,
            h_expand=True,
            v_expand=True,
            child=self.viewport,
        )

        self.search_entry = Entry(
            name="search-entry-walls",
            placeholder="Search Wallpapers...",
            h_expand=True,
            notify_text=lambda entry, *_: self.arrange_viewport(entry.get_text()),
            on_key_press_event=self.on_search_entry_key_press,
        )
        self.search_entry.props.xalign = 0.5
        self.search_entry.connect("focus-out-event", self.on_search_entry_focus_out)

        self.header_box = CenterBox(
            name="header-box",
            spacing=8,
            orientation="h",
            center_children=[self.search_entry],
        )

        self.add(self.header_box)
        self.add(self.scrolled_window)
        self._start_thumbnail_thread()
        self.setup_file_monitor()
        self.show_all()
        self.search_entry.grab_focus()

    def _validate_cache_mapping(self):
        """Удаляет невалидные записи из кэша при запуске."""
        if not os.path.exists(self.CACHE_MAPPING_FILEPATH):
            return

        with self._mapping_lock:
            try:
                with open(self.CACHE_MAPPING_FILEPATH) as f:
                    mapping = json.load(f)

                valid_mapping = {}
                for cache_file, real_path in mapping.items():
                    if os.path.exists(real_path):
                        valid_mapping[cache_file] = real_path
                    else:
                        cache_path = os.path.join(self.CACHE_DIR, cache_file)
                        if os.path.exists(cache_path):
                            os.remove(cache_path)

                # Атомарное обновление файла маппинга
                if len(valid_mapping) != len(mapping):
                    temp_path = f"{self.CACHE_MAPPING_FILEPATH}.tmp"
                    with open(temp_path, "w") as f:
                        json.dump(valid_mapping, f, indent=2)
                    os.replace(temp_path, self.CACHE_MAPPING_FILEPATH)

            except Exception as e:
                logger.error(f"Cache validation error: {e}")

    def _get_cache_lock_path(self):
        """Возвращает полный путь к lock-файлу."""
        return f"{self.CACHE_MAPPING_FILEPATH}.lock"

    def setup_file_monitor(self):
        self.file_monitors = []
        self.symlink_monitors = []

        for wallpapers_dir in self.WALLPAPERS_DIRS:
            gfile = Gio.File.new_for_path(str(wallpapers_dir))

            # Монитор изменений в директории
            file_monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            file_monitor.connect("changed", self.on_directory_changed)
            self.file_monitors.append(file_monitor)

            # Монитор изменений символических ссылок
            symlink_monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
            symlink_monitor.connect("changed", self.on_symlink_changed)
            self.symlink_monitors.append(symlink_monitor)

    def on_symlink_changed(self, _monitor, _file, _other_file, event_type):
        if event_type in (
            Gio.FileMonitorEvent.CHANGES_DONE_HINT,
            Gio.FileMonitorEvent.CHANGED,
        ):
            needs_reload = False
            for wallpapers_dir in self.WALLPAPERS_DIRS:
                if os.path.realpath(wallpapers_dir) != getattr(
                    self, f"_last_symlink_target_{hash(wallpapers_dir)}", None
                ):
                    setattr(
                        self,
                        f"_last_symlink_target_{hash(wallpapers_dir)}",
                        os.path.realpath(wallpapers_dir),
                    )
                    needs_reload = True
            if needs_reload:
                self._reload_wallpapers()

    def _reload_wallpapers(self):
        """Очистка кэша при изменении директорий."""
        if os.path.exists(self.CACHE_MAPPING_FILEPATH):
            with contextlib.suppress(Exception):
                os.remove(self.CACHE_MAPPING_FILEPATH)

        lock_path = self._get_cache_lock_path()
        if os.path.exists(lock_path):
            with contextlib.suppress(Exception):
                os.remove(lock_path)

        for file in os.listdir(self.CACHE_DIR):
            if file.endswith(".png"):
                with contextlib.suppress(Exception):
                    os.remove(os.path.join(self.CACHE_DIR, file))

        self.thumbnails = []
        self.thumbnail_queue = []
        self.viewport.get_model().clear()

        # Перезагружаем файлы из всех директорий
        self.files_with_paths = []
        for wallpapers_dir in self.WALLPAPERS_DIRS:
            for file_name in os.listdir(str(wallpapers_dir)):
                if self._is_image(file_name):
                    full_path = os.path.join(wallpapers_dir, file_name)
                    self.files_with_paths.append((file_name, full_path))

        self.files_with_paths.sort(key=lambda x: x[0].lower())
        self._start_thumbnail_thread()

    def on_directory_changed(self, _monitor, file, _other_file, event_type):
        file_name = file.get_basename()
        file_parent = os.path.dirname(file.get_path())

        if event_type == Gio.FileMonitorEvent.DELETED:
            # Удаляем файл из списка, если он там есть
            self.files_with_paths = [
                (fn, fp)
                for fn, fp in self.files_with_paths
                if not (fn == file_name and os.path.dirname(fp) == file_parent)
            ]

            # Удаляем миниатюру из кэша
            full_path = os.path.join(file_parent, file_name)
            try:
                real_path = os.path.realpath(full_path)
                file_hash = hashlib.md5(
                    real_path.encode(), usedforsecurity=False
                ).hexdigest()
                cache_file = f"{file_hash}.png"
                with contextlib.suppress(Exception):
                    os.remove(os.path.join(self.CACHE_DIR, cache_file))
            except Exception:
                ...

            GLib.idle_add(self.arrange_viewport, self.search_entry.get_text())

        elif event_type == Gio.FileMonitorEvent.CREATED and self._is_image(file_name):
            new_name = file_name.lower().replace(" ", "-")
            if new_name != file_name:
                try:
                    os.rename(
                        os.path.join(file_parent, file_name),
                        os.path.join(file_parent, new_name),
                    )
                    file_name = new_name
                except Exception:
                    ...

            full_path = os.path.join(file_parent, file_name)
            if not any(
                fn == file_name and fp == full_path for fn, fp in self.files_with_paths
            ):
                self.files_with_paths.append((file_name, full_path))
                self.files_with_paths.sort(key=lambda x: x[0].lower())
                self.executor.submit(self._process_file, file_name, full_path)

        elif event_type == Gio.FileMonitorEvent.CHANGED and self._is_image(file_name):
            full_path = os.path.join(file_parent, file_name)
            if any(
                fn == file_name and fp == full_path for fn, fp in self.files_with_paths
            ):
                with contextlib.suppress(Exception):
                    real_path = os.path.realpath(full_path)
                    file_hash = hashlib.md5(
                        real_path.encode(), usedforsecurity=False
                    ).hexdigest()
                    cache_file = f"{file_hash}.png"
                    os.remove(os.path.join(self.CACHE_DIR, cache_file))
                self.executor.submit(self._process_file, file_name, full_path)

    def arrange_viewport(self, query: str = ""):
        model = self.viewport.get_model()
        model.clear()

        if not query.strip():
            random_thumb = self._create_random_thumbnail()
            model.append([random_thumb, self.random_item_name])

        filtered = [
            (thumb, name)
            for thumb, name in self.thumbnails
            if query.casefold() in name.casefold()
        ]
        filtered.sort(key=lambda x: x[1].lower())
        for pixbuf, name in filtered:
            model.append([pixbuf, name])
        if query.strip() and model:
            self.update_selection(0)

    def on_wallpaper_selected(self, iconview, path):
        file_name = iconview.get_model()[path][1]

        if file_name == self.random_item_name:
            if not self.files_with_paths:
                return
            _file_name, full_path = random.choice(self.files_with_paths)
        else:
            full_path = next(
                (fp for fn, fp in self.files_with_paths if fn == file_name), None
            )
            if full_path is None:
                return

        method_not_supported_msg = (
            "The {method} method is not supported. Wallpaper application canceled."
        )

        if WindowManagerContext.is_x11():
            if self.config.x11_method == "feh":
                WallpaperApply.apply_with_feh(full_path)
            else:
                logger.warning(method_not_supported_msg.format(method=self.config.x11_method))
                return
        elif WindowManagerContext.is_wayland():
            if self.config.wayland_method == "awww":
                WallpaperApply.apply_with_awww(full_path)
            else:
                logger.warning(method_not_supported_msg.format(method=self.config.wayland_method))
                return
        else:
            logger.warning("Unsupported window manager")
            return

        if self.config.save_current_wall:
            try:
                current_wall = Path(self.config.current_wall_path)
                current_wall.parent.mkdir(parents=True, exist_ok=True)
                current_wall.unlink(missing_ok=True)
                current_wall.symlink_to(target=full_path)
            except Exception:
                logger.warning(
                    f'Failed to set a link to the current wallpaper at path "{self.config.current_wall_path}"'
                )

    def on_search_entry_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right):
            self.move_selection_2d(event.keyval)
            return True
        elif (
            event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
            and self.selected_index != -1
        ):
            path = Gtk.TreePath.new_from_indices([self.selected_index])
            self.on_wallpaper_selected(self.viewport, path)
            return True
        return False

    def move_selection_2d(self, keyval):
        model = self.viewport.get_model()
        if not model:
            return

        if self.selected_index == -1:
            new_index = 0 if keyval in (Gdk.KEY_Down, Gdk.KEY_Right) else len(model) - 1
        else:
            cols = max(1, self.viewport.get_allocation().width // 108)
            delta = {
                Gdk.KEY_Right: 1,
                Gdk.KEY_Left: -1,
                Gdk.KEY_Down: cols,
                Gdk.KEY_Up: -cols,
            }[keyval]
            new_index = max(0, min(len(model) - 1, self.selected_index + delta))

        self.update_selection(new_index)

    def update_selection(self, index: int):
        self.viewport.unselect_all()
        path = Gtk.TreePath.new_from_indices([index])
        self.viewport.select_path(path)
        self.viewport.scroll_to_path(path, False, 0.5, 0.5)
        self.selected_index = index

    def _start_thumbnail_thread(self):
        GLib.Thread.new("thumbnail-loader", self._preload_thumbnails, None)

    def _preload_thumbnails(self, _):
        for file_name, full_path in self.files_with_paths:
            self.executor.submit(self._process_file, file_name, full_path)

    def _process_file(self, file_name, full_path):
        cache_path = self._get_cache_path(full_path)
        if not cache_path:
            return

        if os.path.exists(cache_path) and os.path.getmtime(
            cache_path
        ) > os.path.getmtime(full_path):
            self.thumbnail_queue.append((cache_path, file_name))
        else:
            try:
                with Image.open(full_path) as img:
                    size = min(img.size)
                    left = (img.width - size) // 2
                    top = (img.height - size) // 2
                    img_cropped = img.crop((left, top, left + size, top + size))
                    img_cropped = img_cropped.convert("RGBA").resize(
                        (500, 500), Image.LANCZOS
                    )
                    img_cropped = self._add_rounded_corners(img_cropped, 15)

                    temp_path = f"{cache_path}.tmp"
                    img_cropped.save(temp_path, "PNG")
                    os.replace(temp_path, cache_path)

                self.thumbnail_queue.append((cache_path, file_name))
            except Exception:
                return

        GLib.idle_add(self._process_batch)

    def _process_batch(self):
        with self._mapping_lock:
            processed = []
            for cache_path, file_name in self.thumbnail_queue:
                if os.path.exists(cache_path):
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file(cache_path)
                        scaled_pixbuf = pixbuf.scale_simple(
                            96, 96, GdkPixbuf.InterpType.BILINEAR
                        )
                        self.thumbnails.append((scaled_pixbuf, file_name))
                        processed.append((scaled_pixbuf, file_name))
                    except Exception:
                        continue
            if processed:
                self.arrange_viewport(self.search_entry.get_text())
            self.thumbnail_queue = []

    def _get_cache_path(self, full_path: str) -> str:
        try:
            real_path = os.path.realpath(full_path)
            file_hash = hashlib.md5(
                real_path.encode(), usedforsecurity=False
            ).hexdigest()
            cache_file = f"{file_hash}.png"
            cache_path = os.path.join(self.CACHE_DIR, cache_file)

            with self._mapping_lock:
                lock_path = self._get_cache_lock_path()
                try:
                    with open(lock_path, "w") as lock_file:
                        fcntl.flock(lock_file, fcntl.LOCK_EX)

                        mapping = {}
                        if os.path.exists(self.CACHE_MAPPING_FILEPATH):
                            try:
                                with open(self.CACHE_MAPPING_FILEPATH) as f:
                                    mapping = json.load(f)
                            except json.JSONDecodeError:
                                os.remove(self.CACHE_MAPPING_FILEPATH)

                        mapping[cache_file] = real_path

                        temp_path = f"{self.CACHE_MAPPING_FILEPATH}.tmp"
                        with open(temp_path, "w") as f:
                            json.dump(mapping, f, indent=2)

                        os.replace(temp_path, self.CACHE_MAPPING_FILEPATH)
                        return cache_path
                finally:
                    if os.path.exists(lock_path):
                        os.remove(lock_path)
        except Exception as e:
            logger.error(f"Cache error: {e}")
            return None

    @staticmethod
    def _add_rounded_corners(im: Image.Image, radius: int) -> Image.Image:
        mask = Image.new("L", im.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), im.size], radius=radius, fill=255)
        im.putalpha(mask)
        return im

    @staticmethod
    def _is_image(file_name: str) -> bool:
        return file_name.lower().endswith(
            (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")
        )

    def _create_random_thumbnail(self) -> GdkPixbuf.Pixbuf:
        temp_path = os.path.join(self.CACHE_DIR, "__random__.png")
        if os.path.exists(temp_path):
            return GdkPixbuf.Pixbuf.new_from_file(temp_path)

        size = 96
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surface)

        # Transparent background
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()

        # Rounded rectangle background
        radius = 12
        x, y, w, h = 0, 0, size, size
        cr.new_sub_path()
        cr.arc(x + w - radius, y + radius, radius, -1.57079632679, 0)
        cr.arc(x + w - radius, y + h - radius, radius, 0, 1.57079632679)
        cr.arc(x + radius, y + h - radius, radius, 1.57079632679, 3.14159265359)
        cr.arc(x + radius, y + radius, radius, 3.14159265359, 4.71238898038)
        cr.close_path()
        cr.set_source_rgba(1, 1, 1, 0.12)
        cr.fill()

        # Center icon using Nerd Font
        layout = PangoCairo.create_layout(cr)
        layout.set_text("", -1)
        desc = Pango.FontDescription("JetBrainsMono Nerd Font 32")
        layout.set_font_description(desc)

        ink_rect, _ = layout.get_pixel_extents()
        cr.set_source_rgba(1, 1, 1, 0.95)
        x_pos = (size / 2) - (ink_rect.x + ink_rect.width / 2)
        y_pos = (size / 2) - (ink_rect.y + ink_rect.height / 2)
        cr.move_to(x_pos, y_pos)
        PangoCairo.show_layout(cr, layout)

        surface.write_to_png(temp_path)
        return GdkPixbuf.Pixbuf.new_from_file(temp_path)

    def on_search_entry_focus_out(self, widget, _):
        if self.get_mapped():
            widget.grab_focus()
        return False
