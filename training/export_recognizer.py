"""Export trained CRNN recogniser to ONNX for Raspberry Pi 5 deployment.

The exported ``.onnx`` file is loaded at inference time by
``backend/decoding/nn_decoder.py`` via ``onnxruntime`` — no PyTorch
required on the Pi.

Usage::

    python -m training.export_recognizer \\
        --model runs/recognize/datamatrix_crnn_v1/weights/best.pt \\
        --output models/datamatrix_crnn.onnx

Then update ``config/default.yaml``::

    nn_decoding:
      crnn_model_path: "./models/datamatrix_crnn.onnx"

Requirements::

    pip install torch onnx onnxruntime
"""

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    import numpy as np

from .models.crnn import CRNN, IMG_H, IMG_W, VOCAB_SIZE


def export_to_onnx(
    checkpoint_path: str,
    output_path: str,
    opset_version: int = 17,
    verify: bool = True,
) -> None:
    """Load a PyTorch CRNN checkpoint and export it to ONNX.

    Args:
        checkpoint_path: Path to ``best.pt`` saved by ``train_recognizer.py``.
        output_path:     Destination ``.onnx`` file.
        opset_version:   ONNX opset (default: 17, required for LSTM support).
        verify:          Run a quick shape-check with ``onnxruntime`` after export.
    """
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    vocab_size = checkpoint.get("vocab_size", VOCAB_SIZE)
    hidden_size = checkpoint.get("hidden_size", 256)

    model = CRNN(vocab_size=vocab_size, hidden_size=hidden_size)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    dummy_input = torch.zeros(1, 1, IMG_H, IMG_W)  # (B=1, C=1, H, W)

    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        opset_version=opset_version,
        input_names=["image"],
        output_names=["log_probs"],
        dynamic_axes={
            "image":     {0: "batch_size"},
            "log_probs": {0: "time_steps", 1: "batch_size"},
        },
        do_constant_folding=True,
    )
    print(f"ONNX model saved to: {output_path}")

    if verify:
        _verify_onnx(output_path, dummy_input.numpy())


def _verify_onnx(onnx_path: str, dummy_input: "np.ndarray") -> None:
    """Quick sanity-check: run dummy inference with onnxruntime."""
    try:
        import numpy as np  # noqa: F401 — confirms numpy is available at runtime
        import onnxruntime as ort  # type: ignore[import]
    except ImportError:
        print("onnxruntime not installed — skipping verification.")
        return

    import onnx  # type: ignore[import]

    model = onnx.load(onnx_path)
    onnx.checker.check_model(model)

    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: dummy_input})

    T, B, V = output[0].shape
    print(f"Verification passed — output shape: (T={T}, B={B}, vocab={V})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CRNN recogniser to ONNX")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to trained CRNN checkpoint (best.pt)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/datamatrix_crnn.onnx",
        help="Destination ONNX file (default: models/datamatrix_crnn.onnx)",
    )
    parser.add_argument(
        "--opset",
        type=int,
        default=17,
        help="ONNX opset version (default: 17)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip post-export verification",
    )
    args = parser.parse_args()

    export_to_onnx(
        checkpoint_path=args.model,
        output_path=args.output,
        opset_version=args.opset,
        verify=not args.no_verify,
    )


if __name__ == "__main__":
    main()
