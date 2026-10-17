from __future__ import annotations

import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FILES = ("config.json", "model.bin", "tokenizer.json")


@dataclass(frozen=True)
class ModelInfo:
    id: str
    label: str
    size_mb: int
    description: str

    @property
    def size_label(self) -> str:
        return f"{self.size_mb / 1000:.1f} GB".replace(".", ",") if self.size_mb >= 1000 else f"{self.size_mb} MB"


# Só modelos multilíngues: as variantes `.en` e `distil-*` não transcrevem português.
CATALOG: tuple[ModelInfo, ...] = (
    ModelInfo("small", "Small", 484, "Rápido, qualidade razoável."),
    ModelInfo("medium", "Medium", 1530, "Boa qualidade, 2 a 3x mais lento que o Small."),
    ModelInfo("large-v3-turbo", "Large v3 Turbo", 1620, "Recomendado: quase a qualidade do Large v3, bem mais rápido."),
    ModelInfo("large-v3", "Large v3", 3090, "Melhor qualidade, o mais lento."),
)


def get_model_info(model_id: str) -> ModelInfo:
    return next((m for m in CATALOG if m.id == model_id), ModelInfo(model_id, model_id, 0, ""))


def model_dir(models_root: Path, model_id: str) -> Path:
    return models_root / f"faster-whisper-{model_id}"


def is_downloaded(models_root: Path, model_id: str) -> bool:
    path = model_dir(models_root, model_id)
    return all((path / name).is_file() for name in REQUIRED_FILES)


def delete_model(models_root: Path, model_id: str) -> None:
    shutil.rmtree(model_dir(models_root, model_id), ignore_errors=True)


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def download(
    models_root: Path,
    model_id: str,
    on_progress: Callable[[int, int], None] | None = None,
    poll_interval_s: float = 0.5,
) -> Path:
    """Baixa o modelo do Hugging Face. Só deve ser chamado com consentimento explícito.

    Downloads interrompidos são retomados na próxima tentativa.
    """
    from faster_whisper.utils import download_model

    target = model_dir(models_root, model_id)
    total = get_model_info(model_id).size_mb * 1_000_000
    done = threading.Event()
    error: list[BaseException] = []

    def run() -> None:
        try:
            download_model(model_id, output_dir=str(target))
        except BaseException as exc:
            error.append(exc)
        finally:
            done.set()

    threading.Thread(target=run, daemon=True).start()
    while not done.wait(poll_interval_s):
        if on_progress:
            on_progress(_dir_size(target), total)
    if error:
        raise error[0]
    if on_progress:
        on_progress(total, total)
    shutil.rmtree(target / ".cache", ignore_errors=True)
    return target
