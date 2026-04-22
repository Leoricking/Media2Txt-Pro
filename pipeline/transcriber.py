import os
import ctypes


MODEL_CACHE = {}
DEVICE = "cpu"
DLL_DIR_HANDLES = []


def _candidate_cuda_dirs():
    candidates = []

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    possible = [
        os.path.join(local_appdata, "Programs", "Ollama", "lib", "ollama", "cuda_v12"),
        os.path.join(appdata, "anythingllm-desktop", "storage", "engines", "ollama", "lib", "ollama", "cuda_v12"),
        os.path.join(userprofile, "AppData", "Local", "Programs", "Ollama", "lib", "ollama", "cuda_v12"),
        os.path.join(userprofile, "AppData", "Roaming", "anythingllm-desktop", "storage", "engines", "ollama", "lib", "ollama", "cuda_v12"),
    ]

    seen = set()
    for p in possible:
        if os.path.isdir(p) and p not in seen:
            candidates.append(p)
            seen.add(p)

    return candidates


def _register_windows_cuda_dirs():
    global DLL_DIR_HANDLES

    if os.name != "nt":
        return

    for dll_dir in _candidate_cuda_dirs():
        try:
            handle = os.add_dll_directory(dll_dir)
            DLL_DIR_HANDLES.append(handle)
            print(f"✅ 已加入 DLL 路徑: {dll_dir}")
        except Exception as e:
            print(f"⚠️ 無法加入 DLL 路徑: {dll_dir}")
            print(e)


def _cuda_runtime_ready() -> bool:
    if os.name != "nt":
        return False

    _register_windows_cuda_dirs()

    required_dlls = [
        "cublas64_12.dll",
    ]

    for dll_name in required_dlls:
        try:
            ctypes.WinDLL(dll_name)
        except Exception as e:
            print(f"⚠️ 缺少或無法載入 DLL: {dll_name}")
            print(e)
            return False

    return True


def _choose_model_name(is_music_like: bool, prefer_gpu: bool) -> str:
    if is_music_like:
        return "medium" if prefer_gpu else "small"
    return "base"


def _load_model(is_music_like: bool, prefer_gpu: bool = True):
    global DEVICE, MODEL_CACHE

    from faster_whisper import WhisperModel

    model_name = _choose_model_name(is_music_like, prefer_gpu)
    cache_key = ("cuda" if prefer_gpu else "cpu", model_name)

    if cache_key in MODEL_CACHE:
        DEVICE = "cuda" if prefer_gpu else "cpu"
        return MODEL_CACHE[cache_key]

    if prefer_gpu and _cuda_runtime_ready():
        try:
            print(f"⚡ 嘗試 GPU 模式... model={model_name}")
            model = WhisperModel(
                model_name,
                device="cuda",
                compute_type="float16",
                download_root="models",
            )
            MODEL_CACHE[cache_key] = model
            DEVICE = "cuda"
            print("✅ GPU 初始化成功")
            return model
        except Exception as e:
            print("⚠️ GPU 初始化失敗，改用 CPU")
            print(e)
    else:
        if prefer_gpu:
            print("⚠️ 未找到完整可用的 CUDA runtime，改用 CPU")

    cpu_key = ("cpu", _choose_model_name(is_music_like, False))
    if cpu_key in MODEL_CACHE:
        DEVICE = "cpu"
        return MODEL_CACHE[cpu_key]

    model = WhisperModel(
        _choose_model_name(is_music_like, False),
        device="cpu",
        compute_type="int8",
        download_root="models",
    )
    MODEL_CACHE[cpu_key] = model
    DEVICE = "cpu"
    print(f"✅ 使用 CPU 模式 model={_choose_model_name(is_music_like, False)}")
    return model


def transcribe(audio: str, progress_cb, stop_flag, is_music_like: bool = False) -> str:
    global DEVICE

    model = _load_model(is_music_like=is_music_like, prefer_gpu=True)

    transcribe_kwargs = {
        "language": None,
        "vad_filter": False if is_music_like else True,
        "beam_size": 8 if is_music_like else 5,
        "condition_on_previous_text": False if is_music_like else True,
        "word_timestamps": False,
        "task": "transcribe",
    }

    try:
        segments, _ = model.transcribe(audio, **transcribe_kwargs)
        segs = list(segments)

    except Exception as e:
        if DEVICE == "cuda":
            print("❌ GPU 推論失敗，自動切回 CPU")
            print(e)

            model = _load_model(is_music_like=is_music_like, prefer_gpu=False)
            segments, _ = model.transcribe(audio, **transcribe_kwargs)
            segs = list(segments)
        else:
            raise

    total = len(segs) or 1
    texts = []

    for i, seg in enumerate(segs):
        if stop_flag.get("stop"):
            raise Exception("使用者中止")

        text = seg.text.strip()
        if text:
            texts.append(text)

        progress_cb(int((i + 1) / total * 100))

    return "\n".join(texts).strip()