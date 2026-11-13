import os
import threading
from pathlib import Path

_MODEL = None
_PROCESSOR = None
_LOAD_LOCK = threading.Lock()
_RUN_LOCK = threading.Lock()

def model_path() -> Path:
    return Path(os.getenv("DOTS_MODEL_PATH", "vendor/dots.ocr/weights/DotsMOCR"))

def status():
    path = model_path()
    return {
        "device": "cpu",
        "model_path": str(path),
        "model_exists": path.exists(),
        "loaded": _MODEL is not None,
        "note": "CPU-only mode. GPU is not used."
    }

def load_model():
    global _MODEL, _PROCESSOR
    if _MODEL is not None:
        return _MODEL, _PROCESSOR
    with _LOAD_LOCK:
        if _MODEL is not None:
            return _MODEL, _PROCESSOR
        path = model_path()
        if not path.exists():
            raise RuntimeError(
                f"Model weights not found at: {path}. Download Dots OCR weights first."
            )
        os.environ.setdefault("LOCAL_RANK", "0")
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor
        threads = int(os.getenv("DOTS_NUM_THREADS", "4"))
        torch.set_num_threads(max(1, threads))
        # bfloat16 follows the official CPU example to reduce RAM use.
        # CPU support/speed depends on the processor and PyTorch build. No GPU is used.
        model = AutoModelForCausalLM.from_pretrained(
            str(path),
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",
            device_map="cpu",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        processor = AutoProcessor.from_pretrained(
            str(path), trust_remote_code=True
        )
        model.eval()
        _MODEL, _PROCESSOR = model, processor
    return _MODEL, _PROCESSOR

def run_ocr(image_path: str) -> str:
    from qwen_vl_utils import process_vision_info
    import torch

    model, processor = load_model()
    image_path = str(Path(image_path).resolve())
    try:
        from dots_mocr.utils import dict_promptmode_to_prompt
        prompt = dict_promptmode_to_prompt.get("prompt_ocr")
    except Exception:
        prompt = None
    if not prompt:
        prompt = (
            "Read all visible text in this document image. Preserve the original language, "
            "digits, punctuation, and reading order. Do not translate. Return the extracted "
            "content in a structured format and do not invent missing text."
        )

    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": image_path},
            {"type": "text", "text": prompt}
        ]
    }]
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to("cpu")
    max_tokens = int(os.getenv("DOTS_MAX_NEW_TOKENS", "4096"))
    with _RUN_LOCK, torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            use_cache=True,
        )
    trimmed = [
        out[len(inp):] for inp, out in zip(inputs.input_ids, generated)
    ]
    decoded = processor.batch_decode(
        trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )
    return decoded[0].strip() if decoded else ""
