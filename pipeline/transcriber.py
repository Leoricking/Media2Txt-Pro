import os
import time
import threading
import traceback
import ctypes
import site
import sys
import json
import tempfile
import subprocess
import queue
from typing import Optional, Dict, Any, Tuple, List, Callable

import av


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "")
    if not value:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def _norm(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _dbg(debug_callback, message: str):
    print(message)
    if debug_callback:
        try:
            debug_callback(message)
        except Exception:
            pass


class MonotonicProgressEmitter:
    """
    確保同一輪 transcribe 的進度只會遞增，不倒退。
    UI 若另外也有 monotonic 保護，兩邊會形成雙保險。
    """
    def __init__(self, progress_callback: Optional[Callable[[int], None]] = None):
        self.progress_callback = progress_callback
        self._last_value = -1
        self._lock = threading.Lock()

    @property
    def last_value(self) -> int:
        with self._lock:
            return self._last_value

    def emit(self, value: int):
        if not self.progress_callback:
            return

        try:
            value = int(value)
        except Exception:
            return

        value = max(0, min(100, value))

        with self._lock:
            if value <= self._last_value:
                return
            self._last_value = value

        try:
            self.progress_callback(value)
        except Exception:
            pass


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DEFAULT_LOCAL_MODEL_DIR = os.environ.get(
    "WHISPER_MODEL_DIR",
    os.path.join(BASE_DIR, "models", "faster-whisper-large-v3"),
).strip()

DEFAULT_REMOTE_MODEL_NAME = os.environ.get("WHISPER_MODEL_NAME", "large-v3").strip() or "large-v3"

OFFLINE_MODE = _env_bool("MEDIA2TXT_OFFLINE", default=False)
LOW_RESOURCE_MODE = _env_bool("MEDIA2TXT_LOW_RESOURCE", default=False)
FORCE_DEVICE = os.environ.get("WHISPER_DEVICE", "auto").strip().lower() or "auto"
FORCE_TRANSCRIBE_LANGUAGE = os.environ.get("MEDIA2TXT_TRANSCRIBE_LANGUAGE", "").strip().lower()

LONG_VIDEO_MINUTES = int(os.environ.get("MEDIA2TXT_LONG_VIDEO_MINUTES", "15"))
VERY_LONG_VIDEO_MINUTES = int(os.environ.get("MEDIA2TXT_VERY_LONG_VIDEO_MINUTES", "40"))
SUBPROCESS_ENABLED = _env_bool("MEDIA2TXT_TRANSCRIBE_SUBPROCESS", default=True)
IS_TRANSCRIBE_CHILD = _env_bool("MEDIA2TXT_TRANSCRIBE_CHILD", default=False)
GPU_COMPUTE_TYPE = os.environ.get("MEDIA2TXT_GPU_COMPUTE_TYPE", "int8_float16").strip() or "int8_float16"
CPU_COMPUTE_TYPE = os.environ.get("MEDIA2TXT_CPU_COMPUTE_TYPE", "int8").strip() or "int8"

_CUDA_INIT_CACHE: Optional[Dict[str, Any]] = None


def _is_valid_model_dir(path: str) -> bool:
    if not path:
        return False
    path = _norm(path)
    if not os.path.isdir(path):
        return False

    required_files = [
        "model.bin",
        "config.json",
        "tokenizer.json",
        "vocabulary.json",
        "preprocessor_config.json",
    ]
    return all(os.path.exists(os.path.join(path, name)) for name in required_files)


def find_local_model_dir() -> Optional[str]:
    candidates = [
        DEFAULT_LOCAL_MODEL_DIR,
        os.path.join(BASE_DIR, "models", "faster-whisper-large-v3"),
        os.path.join(BASE_DIR, "models", "faster-whisper-medium"),
        os.path.join(BASE_DIR, "models", "faster-whisper-small"),
    ]

    checked = set()
    for raw in candidates:
        if not raw:
            continue
        path = _norm(raw)
        if path in checked:
            continue
        checked.add(path)
        if _is_valid_model_dir(path):
            return path
    return None


def _get_media_duration_seconds(audio_path: str) -> Optional[float]:
    try:
        with av.open(audio_path, mode="r", metadata_errors="ignore") as container:
            if container.duration:
                return float(container.duration / av.time_base)
            if container.streams and container.streams.audio:
                stream = container.streams.audio[0]
                if stream.duration and stream.time_base:
                    return float(stream.duration * stream.time_base)
    except Exception:
        return None
    return None


def _find_sitepkg() -> str:
    try:
        pkgs = site.getsitepackages()
        if pkgs:
            return pkgs[-1]
    except Exception:
        pass
    return ""


def _candidate_nvidia_dirs() -> List[str]:
    sitepkg = _find_sitepkg()
    if not sitepkg:
        return []

    candidates = [
        os.path.join(sitepkg, "nvidia", "cublas", "bin"),
        os.path.join(sitepkg, "nvidia", "cudnn", "bin"),
        os.path.join(sitepkg, "nvidia", "cuda_nvrtc", "bin"),
        os.path.join(sitepkg, "nvidia", "cuda_runtime", "bin"),
    ]
    return [d for d in candidates if os.path.isdir(d)]


def _prepend_dirs_to_path(dirs: List[str]):
    current = os.environ.get("PATH", "")
    existing = current.split(os.pathsep) if current else []
    prepend = []
    for d in dirs:
        if d not in existing:
            prepend.append(d)
    if prepend:
        os.environ["PATH"] = os.pathsep.join(prepend + existing)


def _safe_add_dll_directory(dir_path: str) -> bool:
    try:
        os.add_dll_directory(dir_path)
        return True
    except Exception:
        return False


def _try_preload_dll(fullpath: str) -> Tuple[bool, str]:
    try:
        ctypes.WinDLL(fullpath)
        return True, ""
    except Exception as e:
        return False, str(e)


def initialize_cuda_runtime(debug_callback=None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    在 Python 進程內固定注入 CUDA DLL 搜尋路徑。
    不能只靠 run.bat。
    """
    global _CUDA_INIT_CACHE

    if _CUDA_INIT_CACHE is not None and not force_refresh:
        return _CUDA_INIT_CACHE

    info: Dict[str, Any] = {
        "sitepkg": _find_sitepkg(),
        "dll_dirs": [],
        "added_dirs": [],
        "preloaded": {},
        "ready": False,
        "reason": "",
    }

    dirs = _candidate_nvidia_dirs()
    info["dll_dirs"] = dirs

    if not dirs:
        info["reason"] = "No NVIDIA DLL directories found under site-packages."
        _CUDA_INIT_CACHE = info
        _dbg(debug_callback, f"[transcriber] CUDA INIT: {info}")
        return info

    _prepend_dirs_to_path(dirs)

    for d in dirs:
        ok = _safe_add_dll_directory(d)
        if ok:
            info["added_dirs"].append(d)

    sitepkg = info["sitepkg"]
    dll_candidates = [
        os.path.join(sitepkg, "nvidia", "cublas", "bin", "cublas64_12.dll"),
        os.path.join(sitepkg, "nvidia", "cudnn", "bin", "cudnn64_9.dll"),
    ]

    preload_ok = True
    for dll_path in dll_candidates:
        if os.path.exists(dll_path):
            ok, err = _try_preload_dll(dll_path)
            info["preloaded"][dll_path] = {"ok": ok, "error": err}
            if not ok:
                preload_ok = False
        else:
            info["preloaded"][dll_path] = {"ok": False, "error": "file not found"}
            preload_ok = False

    info["ready"] = preload_ok
    if not preload_ok and not info["reason"]:
        info["reason"] = "One or more CUDA DLLs could not be preloaded."

    _CUDA_INIT_CACHE = info
    _dbg(debug_callback, f"[transcriber] CUDA INIT: {info}")
    return info


def can_use_cuda_for_transcribe(debug_callback=None) -> Tuple[bool, Dict[str, Any]]:
    info = initialize_cuda_runtime(debug_callback=debug_callback)
    return info["ready"], info


def get_transcriber_runtime_info() -> Dict[str, Any]:
    info = {
        "offline_mode": OFFLINE_MODE,
        "low_resource_mode": LOW_RESOURCE_MODE,
        "local_model_dir": find_local_model_dir(),
        "remote_model_name": DEFAULT_REMOTE_MODEL_NAME,
        "device": FORCE_DEVICE,
        "forced_language": FORCE_TRANSCRIBE_LANGUAGE or None,
        "compute_type": "low_resource" if LOW_RESOURCE_MODE else "normal",
        "gpu_compute_type": GPU_COMPUTE_TYPE,
        "cpu_compute_type": CPU_COMPUTE_TYPE,
        "subprocess_enabled": SUBPROCESS_ENABLED,
        "is_transcribe_child": IS_TRANSCRIBE_CHILD,
        "faster_whisper_installed": False,
        "error": "",
        "cuda_runtime_ready": False,
        "cuda_runtime_reason": "",
    }

    try:
        import faster_whisper  # noqa: F401
        info["faster_whisper_installed"] = True
    except Exception as e:
        info["error"] = str(e)

    ready, cuda_info = can_use_cuda_for_transcribe()
    info["cuda_runtime_ready"] = ready
    info["cuda_runtime_reason"] = cuda_info.get("reason", "")

    return info


def _raise_pretty_error(exc: Exception, local_model_dir: Optional[str]):
    raw = str(exc)
    lower = raw.lower()

    if "certificate_verify_failed" in lower or "self-signed certificate" in lower:
        raise RuntimeError(
            "Whisper 模型下載失敗：SSL 憑證驗證失敗。\n"
            "請改用本地模型，或修正憑證鏈。\n"
            f"目前偵測本地模型：{local_model_dir or '未找到'}"
        ) from exc

    if "cannot find the appropriate snapshot folder" in lower:
        raise RuntimeError(
            "找不到本地 Whisper 模型，也無法從 Hugging Face 下載。\n"
            "請先放好本地模型，或修正網路 / SSL 問題。"
        ) from exc

    if "no module named 'faster_whisper'" in lower:
        raise RuntimeError(
            "缺少 faster-whisper 套件。\n請先執行：pip install -r requirements.txt"
        ) from exc

    raise RuntimeError(raw) from exc


def _is_cuda_related_error(msg: str) -> bool:
    lower = (msg or "").lower()
    keywords = [
        "cuda failed",
        "cuda error",
        "cuda driver version is insufficient",
        "library cublas",
        "cublas64_12.dll",
        "cudnn",
        "no cuda-capable device is detected",
        "failed to create cublas handle",
        "cannot be loaded",
        "device='cuda'",
        "device cuda",
    ]
    return any(k in lower for k in keywords)


def _get_compute_types() -> Tuple[str, str]:
    """Return GPU and CPU compute types.

    RTX 3060 and long batch runs are more stable with int8_float16 than float16.
    Users can still override with MEDIA2TXT_GPU_COMPUTE_TYPE=float16.
    """
    if LOW_RESOURCE_MODE:
        return "int8_float16", "int8"
    return GPU_COMPUTE_TYPE, CPU_COMPUTE_TYPE


def _choose_model_source(duration_sec: Optional[float], local_model_dir: Optional[str]) -> Tuple[str, bool]:
    """
    長影片優先改用較小模型加速。
    local_only = True when using local dir.
    """
    if not local_model_dir:
        return DEFAULT_REMOTE_MODEL_NAME, False

    minutes = (duration_sec or 0) / 60.0
    if minutes >= VERY_LONG_VIDEO_MINUTES:
        medium_dir = os.path.join(BASE_DIR, "models", "faster-whisper-medium")
        small_dir = os.path.join(BASE_DIR, "models", "faster-whisper-small")
        if _is_valid_model_dir(medium_dir):
            return medium_dir, True
        if _is_valid_model_dir(small_dir):
            return small_dir, True

    return local_model_dir, True


def _load_model(source: str, *, device: str, compute_type: str, local_files_only: bool):
    from faster_whisper import WhisperModel

    kwargs = {
        "device": device,
        "compute_type": compute_type,
        "cpu_threads": max(1, (os.cpu_count() or 4) - 1),
        "num_workers": 1,
    }

    try:
        return WhisperModel(source, local_files_only=local_files_only, **kwargs)
    except TypeError:
        return WhisperModel(source, **kwargs)


def _build_try_order(local_model_dir: Optional[str], duration_sec: Optional[float], cuda_ready: bool) -> List[Tuple[str, str, str, bool]]:
    tries: List[Tuple[str, str, str, bool]] = []
    gpu_compute, cpu_compute = _get_compute_types()

    preferred_source, preferred_local_only = _choose_model_source(duration_sec, local_model_dir)

    def add(source: str, device: str, compute_type: str, local_only: bool):
        tries.append((source, device, compute_type, local_only))

    if preferred_source:
        if FORCE_DEVICE == "cuda":
            add(preferred_source, "cuda", gpu_compute, preferred_local_only)
        elif FORCE_DEVICE == "cpu":
            add(preferred_source, "cpu", cpu_compute, preferred_local_only)
        else:
            if cuda_ready:
                add(preferred_source, "cuda", gpu_compute, preferred_local_only)
            add(preferred_source, "cpu", cpu_compute, preferred_local_only)

        if OFFLINE_MODE:
            return tries

    if not OFFLINE_MODE:
        if FORCE_DEVICE == "cuda":
            add(DEFAULT_REMOTE_MODEL_NAME, "cuda", gpu_compute, False)
        elif FORCE_DEVICE == "cpu":
            add(DEFAULT_REMOTE_MODEL_NAME, "cpu", cpu_compute, False)
        else:
            if cuda_ready:
                add(DEFAULT_REMOTE_MODEL_NAME, "cuda", gpu_compute, False)
            add(DEFAULT_REMOTE_MODEL_NAME, "cpu", cpu_compute, False)

    return tries


def build_model(audio_path: str, debug_callback=None):
    local_model_dir = find_local_model_dir()
    duration_sec = _get_media_duration_seconds(audio_path)

    if OFFLINE_MODE and not local_model_dir:
        raise RuntimeError(
            "已啟用離線模式，但找不到本地 Whisper 模型。\n"
            f"請確認模型放在：{DEFAULT_LOCAL_MODEL_DIR}"
        )

    cuda_ready, cuda_info = can_use_cuda_for_transcribe(debug_callback=debug_callback)
    _dbg(debug_callback, f"[transcriber] CUDA PRECHECK: ready={cuda_ready}, reason={cuda_info.get('reason', '')}")

    tries = _build_try_order(local_model_dir, duration_sec, cuda_ready)
    if not tries:
        raise RuntimeError("沒有可用的 Whisper 模型載入策略。")

    last_error = None

    for source, device, compute_type, local_files_only in tries:
        try:
            if device == "cuda":
                initialize_cuda_runtime(debug_callback=debug_callback, force_refresh=True)

            _dbg(
                debug_callback,
                f"[transcriber] TRY LOAD: source={source}, device={device}, compute_type={compute_type}, local_only={local_files_only}"
            )
            model = _load_model(
                source,
                device=device,
                compute_type=compute_type,
                local_files_only=local_files_only,
            )
            meta = {
                "source": source,
                "device": device,
                "compute_type": compute_type,
                "local_files_only": local_files_only,
                "local_model_dir": local_model_dir,
                "duration_sec": duration_sec,
                "cuda_runtime_ready": cuda_ready,
                "cuda_runtime_reason": cuda_info.get("reason", ""),
            }
            _dbg(debug_callback, f"[transcriber] MODEL LOAD OK: {meta}")
            return model, meta
        except Exception as e:
            last_error = e
            _dbg(debug_callback, f"[transcriber] MODEL LOAD FAIL: {e}")
            if device == "cuda" and _is_cuda_related_error(str(e)):
                _dbg(debug_callback, "[transcriber] CUDA model load failed, fallback to CPU.")
                continue

    if last_error is not None:
        _raise_pretty_error(last_error, local_model_dir)

    raise RuntimeError("Whisper 模型初始化失敗，未知錯誤。")


def _choose_language(debug_callback=None) -> Optional[str]:
    if FORCE_TRANSCRIBE_LANGUAGE:
        _dbg(debug_callback, f"[transcriber] FORCE LANGUAGE: {FORCE_TRANSCRIBE_LANGUAGE}")
        return FORCE_TRANSCRIBE_LANGUAGE
    return None


def _get_transcribe_kwargs(is_music_like: bool, audio_path: str, debug_callback=None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    duration_sec = _get_media_duration_seconds(audio_path)
    long_minutes = (duration_sec / 60.0) if duration_sec else 0.0

    long_mode = duration_sec is not None and long_minutes >= LONG_VIDEO_MINUTES
    very_long_mode = duration_sec is not None and long_minutes >= VERY_LONG_VIDEO_MINUTES

    language = _choose_language(debug_callback=debug_callback)

    # Safer defaults for long GPU jobs.  beam/best_of=3 can multiply decoder
    # memory pressure and has caused native CTranslate2 crashes on Windows.
    base = {
        "beam_size": 1 if (LOW_RESOURCE_MODE or long_mode) else 2,
        "best_of": 1 if (LOW_RESOURCE_MODE or long_mode) else 2,
        "temperature": 0.0,
        "condition_on_previous_text": False if (LOW_RESOURCE_MODE or long_mode) else True,
        "vad_filter": True,
        "word_timestamps": False,
    }

    if is_music_like:
        base.update({
            "beam_size": 2,
            "best_of": 2,
            "temperature": 0.2,
            "vad_filter": False,
            "condition_on_previous_text": False,
        })

    if very_long_mode:
        base.update({
            "beam_size": 1,
            "best_of": 1,
            "condition_on_previous_text": False,
            "vad_filter": True,
        })

    meta = {
        "duration_sec": duration_sec,
        "long_mode": long_mode,
        "very_long_mode": very_long_mode,
        "language": language,
    }

    _dbg(
        debug_callback,
        f"[transcriber] TRANSCRIBE PLAN: duration_sec={duration_sec}, long_mode={long_mode}, very_long_mode={very_long_mode}, language={language}, kwargs={base}",
    )
    return base, meta


class ProgressHeartbeat:
    """
    背景心跳進度，只會把進度往前推，不倒退。
    """
    def __init__(
        self,
        progress_emitter: MonotonicProgressEmitter,
        stop_flag=None,
        debug_callback=None,
        start=12,
        end=72,
        interval=1.5,
    ):
        self.progress_emitter = progress_emitter
        self.stop_flag = stop_flag
        self.debug_callback = debug_callback
        self.current = start
        self.end = end
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread = None
        self._last_debug_ts = time.time()

    def _emit(self, value: int):
        self.progress_emitter.emit(value)
        if value > self.current:
            self.current = value

    def _run(self):
        self._emit(self.current)
        while not self._stop_event.is_set():
            if self.stop_flag and self.stop_flag.get("stop"):
                return
            if self.stop_flag and self.stop_flag.get("pause"):
                time.sleep(0.15)
                continue

            time.sleep(self.interval)

            now = time.time()
            if now - self._last_debug_ts >= 5:
                _dbg(self.debug_callback, f"[transcriber] STILL WORKING... progress~{self.current}%")
                self._last_debug_ts = now

            if self.current < self.end:
                self.current += 1
                self._emit(self.current)

    def start_run(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_run(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2)


def _wait_if_paused(stop_flag):
    while stop_flag and stop_flag.get("pause") and not stop_flag.get("stop"):
        time.sleep(0.15)


def _run_transcribe_once(
    model,
    meta: Dict[str, Any],
    audio_path: str,
    kwargs: Dict[str, Any],
    plan_meta: Dict[str, Any],
    progress_emitter: MonotonicProgressEmitter,
    stop_flag=None,
    debug_callback=None,
) -> str:
    def is_stopped() -> bool:
        return bool(stop_flag and stop_flag.get("stop"))

    if meta.get("device") == "cuda":
        cuda_ready, cuda_info = can_use_cuda_for_transcribe(debug_callback=debug_callback)
        _dbg(debug_callback, f"[transcriber] CUDA RUNTIME BEFORE TRANSCRIBE: ready={cuda_ready}, reason={cuda_info.get('reason', '')}")
        if not cuda_ready:
            raise RuntimeError(f"CUDA runtime not ready before transcribe: {cuda_info.get('reason', '')}")

    heartbeat = ProgressHeartbeat(
        progress_emitter=progress_emitter,
        stop_flag=stop_flag,
        debug_callback=debug_callback,
        start=max(12, progress_emitter.last_value),
        end=60 if plan_meta.get("very_long_mode") else (70 if plan_meta.get("long_mode") else 80),
        interval=1.5,
    )

    duration_sec = plan_meta.get("duration_sec")
    language = plan_meta.get("language")

    try:
        _wait_if_paused(stop_flag)
        heartbeat.start_run()

        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=kwargs["beam_size"],
            best_of=kwargs["best_of"],
            temperature=kwargs["temperature"],
            vad_filter=kwargs["vad_filter"],
            condition_on_previous_text=kwargs["condition_on_previous_text"],
            word_timestamps=kwargs.get("word_timestamps", False),
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
        )

        parts = []
        seg_count = 0
        last_emit_ts = time.time()

        for seg in segments:
            if is_stopped():
                heartbeat.stop_run()
                return ""

            _wait_if_paused(stop_flag)
            if is_stopped():
                heartbeat.stop_run()
                return ""

            text = (getattr(seg, "text", "") or "").strip()
            if text:
                parts.append(text)

            seg_count += 1

            seg_end = getattr(seg, "end", None)
            now = time.time()

            if duration_sec and seg_end and now - last_emit_ts >= 0.5:
                ratio = max(0.0, min(1.0, float(seg_end) / float(duration_sec)))
                if plan_meta.get("very_long_mode"):
                    dynamic_progress = 60 + int(ratio * 35)
                elif plan_meta.get("long_mode"):
                    dynamic_progress = 70 + int(ratio * 25)
                else:
                    dynamic_progress = 80 + int(ratio * 15)

                dynamic_progress = min(95, dynamic_progress)
                progress_emitter.emit(dynamic_progress)

                if dynamic_progress > heartbeat.current:
                    heartbeat.current = dynamic_progress

                last_emit_ts = now

            if seg_count % 25 == 0:
                _dbg(debug_callback, f"[transcriber] SEGMENTS READY: {seg_count}")

        heartbeat.stop_run()

    except Exception:
        heartbeat.stop_run()
        raise

    final_text = "\n".join(parts).strip()

    if not final_text:
        raise RuntimeError(
            "Whisper transcription produced empty result.\n"
            f"source={meta['source']}\n"
            f"device={meta['device']}\n"
            f"compute_type={meta['compute_type']}"
        )

    return final_text


def _build_cpu_fallback_model(meta: Dict[str, Any]):
    source = meta["source"]
    local_only = meta["local_files_only"]
    _, cpu_compute = _get_compute_types()

    model = _load_model(
        source,
        device="cpu",
        compute_type=cpu_compute,
        local_files_only=local_only,
    )
    new_meta = dict(meta)
    new_meta["device"] = "cpu"
    new_meta["compute_type"] = cpu_compute
    return model, new_meta


def _transcribe_in_process(audio_path, progress_callback=None, stop_flag=None, is_music_like=False, debug_callback=None) -> str:
    if not audio_path or not os.path.exists(audio_path):
        raise RuntimeError(f"Audio file not found: {audio_path}")

    progress_emitter = MonotonicProgressEmitter(progress_callback)

    def is_stopped() -> bool:
        return bool(stop_flag and stop_flag.get("stop"))

    if is_stopped():
        return ""

    _wait_if_paused(stop_flag)
    progress_emitter.emit(2)

    try:
        model, meta = build_model(audio_path=audio_path, debug_callback=debug_callback)
    except Exception as e:
        raise RuntimeError(str(e)) from e

    if is_stopped():
        return ""

    _wait_if_paused(stop_flag)

    _dbg(debug_callback, f"[transcriber] USING MODEL: source={meta['source']} device={meta['device']} compute_type={meta['compute_type']}")
    progress_emitter.emit(10)

    kwargs, plan_meta = _get_transcribe_kwargs(
        is_music_like=is_music_like,
        audio_path=audio_path,
        debug_callback=debug_callback,
    )

    try:
        result = _run_transcribe_once(
            model=model,
            meta=meta,
            audio_path=audio_path,
            kwargs=kwargs,
            plan_meta=plan_meta,
            progress_emitter=progress_emitter,
            stop_flag=stop_flag,
            debug_callback=debug_callback,
        )
        _dbg(debug_callback, f"[transcriber] FINAL DEVICE USED: {meta['device']}")
        progress_emitter.emit(100)
        return result

    except Exception as e:
        msg = str(e)

        if meta.get("device") == "cuda" and _is_cuda_related_error(msg):
            _dbg(debug_callback, f"[transcriber] CUDA transcribe failed, retry on CPU. detail={msg}")

            try:
                _wait_if_paused(stop_flag)
                cpu_model, cpu_meta = _build_cpu_fallback_model(meta)
                _dbg(
                    debug_callback,
                    f"[transcriber] CPU FALLBACK MODEL READY: source={cpu_meta['source']} device={cpu_meta['device']} compute_type={cpu_meta['compute_type']}"
                )

                # fallback 不重設進度，沿用 monotonic emitter，避免倒退
                progress_emitter.emit(max(progress_emitter.last_value, 12))

                result = _run_transcribe_once(
                    model=cpu_model,
                    meta=cpu_meta,
                    audio_path=audio_path,
                    kwargs=kwargs,
                    plan_meta=plan_meta,
                    progress_emitter=progress_emitter,
                    stop_flag=stop_flag,
                    debug_callback=debug_callback,
                )
                _dbg(debug_callback, f"[transcriber] FINAL DEVICE USED: {cpu_meta['device']}")
                progress_emitter.emit(100)
                return result

            except Exception as cpu_e:
                raise RuntimeError(
                    "Whisper transcription failed on GPU, and CPU fallback also failed.\n"
                    f"gpu_detail={msg}\n"
                    f"cpu_detail={cpu_e}"
                ) from cpu_e

        raise RuntimeError(
            "Whisper transcription failed.\n"
            f"source={meta['source']}\n"
            f"device={meta['device']}\n"
            f"compute_type={meta['compute_type']}\n"
            f"detail={e}"
        ) from e


_NATIVE_CRASH_CODES = {
    -1073741819: "0xC0000005 access violation",
    3221225477: "0xC0000005 access violation",
    -1073740791: "0xC0000409 stack buffer overrun",
    3221226505: "0xC0000409 stack buffer overrun",
}


def _is_native_crash_returncode(returncode: int) -> bool:
    return int(returncode or 0) in _NATIVE_CRASH_CODES


def _describe_returncode(returncode: int) -> str:
    code = int(returncode or 0)
    if code in _NATIVE_CRASH_CODES:
        return _NATIVE_CRASH_CODES[code]
    unsigned = code & 0xFFFFFFFF
    return f"exit_code={code} (0x{unsigned:08X})"


def _subprocess_device_order() -> List[str]:
    if FORCE_DEVICE == "cpu":
        return ["cpu"]
    if FORCE_DEVICE == "cuda":
        return ["cuda", "cpu"]
    ready, _ = can_use_cuda_for_transcribe()
    return ["cuda", "cpu"] if ready else ["cpu"]


def _run_transcribe_subprocess(
    audio_path: str,
    device: str,
    progress_emitter: MonotonicProgressEmitter,
    stop_flag=None,
    is_music_like: bool = False,
    debug_callback=None,
) -> Tuple[bool, str, str, int]:
    """Run native CTranslate2 work outside the Qt process.

    Returns (ok, transcript, error_text, returncode).  A native access violation
    can kill the child, while the GUI process stays alive and can retry on CPU.
    """
    work_dir = tempfile.mkdtemp(prefix="media2txt_transcribe_")
    request_path = os.path.join(work_dir, "request.json")
    result_path = os.path.join(work_dir, "result.txt")
    error_path = os.path.join(work_dir, "error.txt")

    request = {
        "audio_path": os.path.abspath(audio_path),
        "device": device,
        "is_music_like": bool(is_music_like),
        "result_path": result_path,
        "error_path": error_path,
    }
    with open(request_path, "w", encoding="utf-8") as f:
        json.dump(request, f, ensure_ascii=False, indent=2)

    env = os.environ.copy()
    env["MEDIA2TXT_TRANSCRIBE_CHILD"] = "1"
    env["MEDIA2TXT_TRANSCRIBE_SUBPROCESS"] = "0"
    env["WHISPER_DEVICE"] = device
    if device == "cuda":
        # Stable default; explicit user override is preserved.
        env.setdefault("MEDIA2TXT_GPU_COMPUTE_TYPE", GPU_COMPUTE_TYPE)
    else:
        env["MEDIA2TXT_CPU_COMPUTE_TYPE"] = CPU_COMPUTE_TYPE

    cmd = [sys.executable, "-u", "-m", "pipeline.transcribe_runner", request_path]
    _dbg(debug_callback, f"[transcriber] START CHILD: device={device} cmd={cmd}")

    process = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    lines: "queue.Queue[Optional[str]]" = queue.Queue()

    def _reader():
        try:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line.rstrip("\r\n"))
        finally:
            lines.put(None)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    reader_done = False

    try:
        while True:
            if stop_flag and stop_flag.get("stop"):
                _dbg(debug_callback, "[transcriber] STOP REQUESTED: terminate child")
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                return False, "", "Stopped by user", process.returncode or 1

            # Pause cannot safely suspend CUDA kernels.  We keep the child alive and
            # pause only UI/queue progression, matching prior behavior without killing it.
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                line = ""

            if line is None:
                reader_done = True
            elif line:
                try:
                    event = json.loads(line)
                except Exception:
                    _dbg(debug_callback, f"[transcriber-child:{device}] {line}")
                else:
                    etype = event.get("type")
                    if etype == "progress":
                        progress_emitter.emit(int(event.get("value", 0)))
                    elif etype == "debug":
                        _dbg(debug_callback, f"[transcriber-child:{device}] {event.get('message', '')}")
                    elif etype == "error":
                        _dbg(debug_callback, f"[transcriber-child:{device}] ERROR: {event.get('message', '')}")

            if process.poll() is not None and reader_done:
                break

        returncode = int(process.returncode or 0)
        if returncode == 0 and os.path.exists(result_path):
            transcript = open(result_path, "r", encoding="utf-8", errors="replace").read().strip()
            if transcript:
                return True, transcript, "", returncode
            return False, "", "Child completed but transcript was empty", returncode

        error_text = ""
        if os.path.exists(error_path):
            error_text = open(error_path, "r", encoding="utf-8", errors="replace").read().strip()
        if not error_text:
            error_text = _describe_returncode(returncode)
        return False, "", error_text, returncode
    finally:
        try:
            if process.poll() is None:
                process.kill()
        except Exception:
            pass
        try:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


def transcribe(audio_path, progress_callback=None, stop_flag=None, is_music_like=False, debug_callback=None) -> str:
    """Public API with native-crash isolation and CPU fallback.

    The previous in-process try/except cannot catch Windows 0xC0000005 because the
    entire Python process is terminated by the native library.  The default path now
    executes transcription in a child process.  If CUDA crashes, the GUI survives and
    automatically retries in a CPU child process.
    """
    if IS_TRANSCRIBE_CHILD or not SUBPROCESS_ENABLED:
        return _transcribe_in_process(
            audio_path=audio_path,
            progress_callback=progress_callback,
            stop_flag=stop_flag,
            is_music_like=is_music_like,
            debug_callback=debug_callback,
        )

    if not audio_path or not os.path.exists(audio_path):
        raise RuntimeError(f"Audio file not found: {audio_path}")

    emitter = MonotonicProgressEmitter(progress_callback)
    emitter.emit(2)
    errors = []

    for device in _subprocess_device_order():
        if stop_flag and stop_flag.get("stop"):
            return ""

        if device == "cpu" and errors:
            _dbg(debug_callback, "[transcriber] GPU child failed/crashed; retrying with CPU child.")
            emitter.emit(max(emitter.last_value, 12))

        ok, transcript, error_text, returncode = _run_transcribe_subprocess(
            audio_path=audio_path,
            device=device,
            progress_emitter=emitter,
            stop_flag=stop_flag,
            is_music_like=is_music_like,
            debug_callback=debug_callback,
        )
        if ok:
            _dbg(debug_callback, f"[transcriber] CHILD SUCCESS: device={device}")
            emitter.emit(100)
            return transcript

        detail = f"device={device}, {_describe_returncode(returncode)}, detail={error_text}"
        errors.append(detail)
        if _is_native_crash_returncode(returncode):
            _dbg(debug_callback, f"[transcriber] NATIVE CHILD CRASH DETECTED: {detail}")
        else:
            _dbg(debug_callback, f"[transcriber] CHILD FAILED: {detail}")

    raise RuntimeError(
        "Whisper transcription failed in isolated subprocesses.\n" + "\n".join(errors)
    )


if __name__ == "__main__":
    import sys

    print("=== Media2Txt Pro transcriber self-test ===")
    print("Runtime info:")
    print(get_transcriber_runtime_info())
    print()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m pipeline.transcriber <audio_or_video_file>")
        raise SystemExit(1)

    audio_file = sys.argv[1]

    try:
        result = transcribe(audio_file)
        print("=== TRANSCRIBE OK ===")
        print(result[:3000])
    except Exception as e:
        print("=== TRANSCRIBE ERROR ===")
        print(str(e))
        print(traceback.format_exc())
        raise
