"""
Модуль автоматического парсинга метаданных видеофайлов.
Извлекает длительность, разрешение и формирует стандартные метки качества.

Поддерживает многоуровневую цепочку извлечения:
1. Встроенный парсер ISO/MP4 атомов (pure Python, 0 внешних зависимостей)
2. ffprobe (системная утилита)
3. OpenCV (cv2)
4. mutagen (MP4 метаданные)
5. Безопасный fallback на дефолтные значения при любых сбоях (скрипт никогда не падает).
"""

import json
import logging
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("bochflix.video_meta")


def format_duration(seconds: float) -> str:
    """
    Форматирует длительность в секундах в строку вида:
    - 'X ч Y мин' (если фильм длится 1 час и более, например '2 ч 29 мин')
    - 'X мин' (если фильм длится менее часа, например '45 мин')
    """
    if seconds <= 0:
        return "0 мин"

    total_minutes = round(seconds / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours > 0:
        if minutes > 0:
            return f"{hours} ч {minutes} мин"
        return f"{hours} ч"
    return f"{max(1, minutes)} мин"


def normalize_duration_str(raw: Any) -> str:
    """
    Нормализует любое представление длительности в стандартный вид:
    'X ч Y мин' или 'X мин'.

    Примеры:
    - 144 / '144' -> '2 ч 24 мин'
    - '131' -> '2 ч 11 мин'
    - '115 мин' -> '1 ч 55 мин'
    - '2 ч 29 мин' -> '2 ч 29 мин'
    - '45' / '45 мин' -> '45 мин'
    - 8966.5 (сек) -> '2 ч 29 мин'
    """
    if raw is None:
        return "0 мин"

    s = str(raw).strip()
    if not s:
        return "0 мин"

    # Если уже в формате 'X ч Y мин' или 'X ч'
    if re.match(r"^\d+\s*ч(\s*\d+\s*мин)?$", s):
        return s

    # Если в формате 'X мин' или 'Xm'
    m_min = re.match(r"^(\d+)\s*(?:мин|m|min)$", s, re.IGNORECASE)
    if m_min:
        val = int(m_min.group(1))
        h = val // 60
        rem_m = val % 60
        if h > 0:
            return f"{h} ч {rem_m} мин" if rem_m > 0 else f"{h} ч"
        return f"{max(1, rem_m)} мин"

    # Если передано чистое число
    if s.isdigit():
        val = int(s)
        # Если число больше 500 — это секунды, иначе минуты
        total_sec = val if val > 500 else val * 60
        m = round(total_sec / 60)
        h = m // 60
        rem_m = m % 60
        if h > 0:
            return f"{h} ч {rem_m} мин" if rem_m > 0 else f"{h} ч"
        return f"{max(1, rem_m)} мин"

    # Пробуем распарсить float секунды
    try:
        val_f = float(s)
        if val_f > 0:
            total_sec = val_f if val_f > 500 else val_f * 60
            return format_duration(total_sec)
    except ValueError:
        pass

    return s


def map_resolution_to_label(width: int, height: int) -> str:
    """
    Сопоставляет ширину и высоту кадра со стандартными метками качества:
    - До 720p: '144p', '240p', '360p', '480p', '720p HD'
    - 1080p: '1080p Full HD'
    - 1440p: '2K'
    - 2160p+: '4K'

    Корректно обрабатывает широкоформатные фильмы 2.35:1 / 2.39:1 (например, 1920x800 -> 1080p Full HD).
    """
    if width <= 0 or height <= 0:
        return "1080p Full HD"

    # Эффективная высота с учетом широкоформатного соотношения 16:9
    eff_height = max(height, int(width * 9 / 16)) if width > height else height

    if eff_height <= 144:
        return "144p"
    elif eff_height <= 240:
        return "240p"
    elif eff_height <= 360:
        return "360p"
    elif eff_height <= 480:
        return "480p"
    elif eff_height <= 720:
        return "720p HD"
    elif eff_height <= 1080:
        return "1080p Full HD"
    elif eff_height <= 1440:
        return "2K"
    else:
        return "4K"


def normalize_quality_str(raw: Any) -> str:
    """
    Нормализует строку разрешения к стандартным меткам:
    '144p', '240p', '360p', '480p', '720p HD', '1080p Full HD', '2K', '4K'.

    Примеры:
    - '720p' -> '720p HD'
    - '1080p' -> '1080p Full HD'
    - '4k' / '2160p' -> '4K'
    - '2k' / '1440p' -> '2K'
    """
    if raw is None:
        return "1080p Full HD"

    s = str(raw).strip()
    if not s:
        return "1080p Full HD"

    mapping = {
        "144p": "144p",
        "240p": "240p",
        "360p": "360p",
        "480p": "480p",
        "720p": "720p HD",
        "720p hd": "720p HD",
        "1080p": "1080p Full HD",
        "1080p full hd": "1080p Full HD",
        "1440p": "2K",
        "2k": "2K",
        "2160p": "4K",
        "4k": "4K",
    }
    low = s.lower()
    if low in mapping:
        return mapping[low]

    m = re.search(r"(\d{3,4})p?", low)
    if m:
        num = int(m.group(1))
        if num <= 144:
            return "144p"
        if num <= 240:
            return "240p"
        if num <= 360:
            return "360p"
        if num <= 480:
            return "480p"
        if num <= 720:
            return "720p HD"
        if num <= 1080:
            return "1080p Full HD"
        if num <= 1440:
            return "2K"
        return "4K"

    return s


def _extract_via_mp4_atoms(filepath: Path) -> Optional[Tuple[int, int, float]]:
    """
    Парсер контейнера ISO Base Media File Format (MP4 / M4V / MOV) на чистом Python.
    Парсит atom-структуру moov -> mvhd (длительность) и moov -> trak -> tkhd / stsd (разрешение).
    Работает мгновенно без внешних утилит и зависимостей.
    """
    try:
        file_size = filepath.stat().st_size
        if file_size < 16:
            return None

        duration = 0.0
        width = 0
        height = 0

        with open(filepath, "rb") as f:
            def scan_boxes(start: int, end: int, depth: int = 0) -> None:
                nonlocal duration, width, height
                pos = start
                while pos < end:
                    f.seek(pos)
                    hdr = f.read(8)
                    if len(hdr) < 8:
                        break
                    size, btype = struct.unpack(">I4s", hdr)
                    hdr_len = 8
                    if size == 1:
                        ext_hdr = f.read(8)
                        if len(ext_hdr) < 8:
                            break
                        size = struct.unpack(">Q", ext_hdr)[0]
                        hdr_len = 16
                    elif size == 0:
                        size = end - pos

                    if size < hdr_len:
                        break

                    box_end = pos + size
                    type_str = btype.decode("latin1", errors="ignore")

                    # Контейнерные атомы
                    if type_str in ("moov", "trak", "mdia", "minf", "stbl"):
                        scan_boxes(pos + hdr_len, box_end, depth + 1)
                    # Длительность из Movie Header Box (mvhd)
                    elif type_str == "mvhd" and duration <= 0:
                        payload = f.read(min(size - hdr_len, 32))
                        if len(payload) >= 20:
                            ver = payload[0]
                            if ver == 1 and len(payload) >= 28:
                                ts, dur = struct.unpack(">IQ", payload[20:32])
                            elif ver == 0:
                                ts, dur = struct.unpack(">II", payload[12:20])
                            else:
                                ts, dur = 0, 0
                            if ts > 0 and dur > 0:
                                duration = dur / ts
                    # Разрешение из Track Header Box (tkhd)
                    elif type_str == "tkhd" and (width <= 0 or height <= 0):
                        payload = f.read(min(size - hdr_len, 96))
                        if len(payload) >= 84:
                            ver = payload[0]
                            offset = 84 if ver == 1 else 76
                            if len(payload) >= offset + 8:
                                w_fixed, h_fixed = struct.unpack(">II", payload[offset : offset + 8])
                                w = w_fixed >> 16
                                h = h_fixed >> 16
                                if w > 0 and h > 0:
                                    width = w
                                    height = h
                    # Запасной вариант разрешения из Sample Table Sample Description (stsd)
                    elif type_str == "stsd" and (width <= 0 or height <= 0):
                        payload = f.read(min(size - hdr_len, 256))
                        if len(payload) >= 40:
                            for i in range(8, len(payload) - 30):
                                sample_type = payload[i + 4 : i + 8]
                                if sample_type in (
                                    b"avc1", b"avc2", b"hvc1", b"hev1",
                                    b"mp4v", b"s263", b"dvh1", b"vp09", b"av01",
                                ):
                                    se_start = i + 8
                                    if se_start + 28 <= len(payload):
                                        w, h = struct.unpack(">HH", payload[se_start + 24 : se_start + 28])
                                        if w > 0 and h > 0:
                                            width = w
                                            height = h
                                            break

                    pos = box_end

            scan_boxes(0, file_size)

        if width > 0 and height > 0 and duration > 0:
            return width, height, duration
        if width > 0 and height > 0:
            return width, height, duration
        if duration > 0:
            return 1920, 1080, duration
    except Exception as exc:
        logger.debug(f"MP4 atom parser failed for {filepath}: {exc}")

    return None


def _find_ffprobe_binary() -> Optional[str]:
    """Ищет бинарный файл ffprobe в PATH и стандартных директориях macOS/Linux."""
    for candidate in [
        shutil.which("ffprobe"),
        "/opt/homebrew/bin/ffprobe",
        "/usr/local/bin/ffprobe",
        "/usr/bin/ffprobe",
    ]:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _extract_via_ffprobe(filepath: Path) -> Optional[Tuple[int, int, float]]:
    """Парсинг через ffprobe."""
    ffprobe_bin = _find_ffprobe_binary()
    if not ffprobe_bin:
        return None

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration",
        "-show_entries", "format=duration",
        "-of", "json",
        str(filepath),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return None

        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        if not streams:
            return None

        v_stream = streams[0]
        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))

        duration = 0.0
        if "duration" in v_stream and v_stream["duration"]:
            duration = float(v_stream["duration"])
        elif "format" in data and "duration" in data["format"] and data["format"]["duration"]:
            duration = float(data["format"]["duration"])

        if width > 0 and height > 0:
            return width, height, duration
    except Exception:
        pass

    return None


def _extract_via_opencv(filepath: Path) -> Optional[Tuple[int, int, float]]:
    """Парсинг через OpenCV (cv2)."""
    try:
        import cv2

        cap = cv2.VideoCapture(str(filepath))
        if not cap.isOpened():
            return None

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        duration = 0.0
        if fps > 0 and frame_count > 0:
            duration = float(frame_count / fps)

        cap.release()

        if width > 0 and height > 0:
            return width, height, duration
    except Exception:
        pass

    return None


def _extract_via_mutagen(filepath: Path) -> Optional[float]:
    """Извлечение длительности через mutagen (для mp4/m4v)."""
    try:
        from mutagen.mp4 import MP4

        video = MP4(str(filepath))
        if video and video.info and hasattr(video.info, "length"):
            return float(video.info.length)
    except Exception:
        pass
    return None


def extract_video_metadata(video_path: str | Path) -> Dict[str, Any]:
    """
    Автоматически извлекает метаданные из видеофайла.
    Отказоустойчивая функция: если файл поврежден или метаданные не читаются,
    возвращает безопасные значения по умолчанию (не падает и не выбрасывает исключений).

    Возвращает словарь:
    {
        "width": int,
        "height": int,
        "duration_seconds": float,
        "duration_formatted": str,   # '2 ч 29 мин'
        "quality_label": str,        # '1080p Full HD', '720p HD', '4K' и т.д.
        "backend": str,              # 'mp4_atoms', 'ffprobe', 'opencv', 'mutagen' или 'fallback'
        "filename": str,
        "file_size_bytes": int,
    }
    """
    path = Path(video_path).expanduser().resolve()
    if not path.is_file():
        logger.warning(f"Видеофайл не найден: {path}")
        return {
            "width": 1920,
            "height": 1080,
            "duration_seconds": 0.0,
            "duration_formatted": "0 мин",
            "quality_label": "1080p Full HD",
            "backend": "fallback",
            "filename": path.name,
            "file_size_bytes": 0,
        }

    file_size = path.stat().st_size
    if file_size == 0:
        logger.warning(f"Видеофайл пустой (0 байт): {path}")
        return {
            "width": 1920,
            "height": 1080,
            "duration_seconds": 0.0,
            "duration_formatted": "0 мин",
            "quality_label": "1080p Full HD",
            "backend": "fallback",
            "filename": path.name,
            "file_size_bytes": 0,
        }

    width = 0
    height = 0
    duration = 0.0
    backend_used = "fallback"

    # 1. Пробуем чистый MP4 Atom Parser (самый быстрый, работает автономно)
    meta_mp4 = _extract_via_mp4_atoms(path)
    if meta_mp4:
        w, h, d = meta_mp4
        if w > 0 and h > 0:
            width, height = w, h
            backend_used = "mp4_atoms"
        if d > 0:
            duration = d

    # 2. Если MP4 парсер не дал полного результата, пробуем ffprobe
    if width <= 0 or height <= 0 or duration <= 0:
        meta_ffprobe = _extract_via_ffprobe(path)
        if meta_ffprobe:
            w, h, d = meta_ffprobe
            if width <= 0 and w > 0:
                width, height = w, h
                backend_used = "ffprobe"
            if duration <= 0 and d > 0:
                duration = d

    # 3. Если ffprobe недоступен или не помог, пробуем OpenCV
    if width <= 0 or height <= 0 or duration <= 0:
        meta_cv2 = _extract_via_opencv(path)
        if meta_cv2:
            w, h, d = meta_cv2
            if width <= 0 and w > 0:
                width, height = w, h
                backend_used = "opencv"
            if duration <= 0 and d > 0:
                duration = d

    # 4. Если длительность все еще не определена, пробуем mutagen
    if duration <= 0:
        dur_mut = _extract_via_mutagen(path)
        if dur_mut and dur_mut > 0:
            duration = dur_mut
            if backend_used == "fallback":
                backend_used = "mutagen"

    # 5. Безопасный fallback при нечитаемых метаданных
    if width <= 0 or height <= 0:
        width, height = 1920, 1080
        if backend_used == "fallback":
            logger.warning(
                f"Не удалось распознать габариты видео для '{path.name}'. Использованы значения по умолчанию 1920x1080."
            )

    duration_str = format_duration(duration)
    quality_label = map_resolution_to_label(width, height)

    return {
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 2),
        "duration_formatted": duration_str,
        "quality_label": quality_label,
        "backend": backend_used,
        "filename": path.name,
        "file_size_bytes": file_size,
    }
