"""CRNN model for DataMatrix content recognition.

Architecture:
  CNN:    4 convolutional blocks extract spatial features
  Reshape: collapse height → sequence of column vectors
  BiLSTM: 2-layer bidirectional LSTM models the character sequence
  Linear: project to vocabulary logits
  CTC:    Connectionist Temporal Classification loss (training)

Input:  (B, 1, IMG_H, IMG_W)  grayscale, resized to 32×256
Output: (T, B, VOCAB_SIZE)    log-softmax for CTC loss

Vocabulary (96 tokens):
  index 0         = CTC blank
  index 1–95      = printable ASCII 0x20 (space) … 0x7E (~)

Training:
  python -m training.train_recognizer

Inference:
  python -m training.export_recognizer   # → models/datamatrix_crnn.onnx
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

# Fixed input resolution
IMG_H: int = 32
IMG_W: int = 256

# Vocabulary
_PRINTABLE_RANGE = range(32, 127)  # ASCII 0x20–0x7E (95 chars)
VOCAB_SIZE: int = 1 + len(_PRINTABLE_RANGE)  # 96  (blank + 95 printable)


def build_vocab() -> list[str]:
    """Return the full CTC vocabulary.

    Index 0 is the CTC blank token.
    Indices 1-95 are printable ASCII characters (space through tilde).
    """
    return ["<blank>"] + [chr(i) for i in _PRINTABLE_RANGE]


def char_to_idx(char: str, vocab: list[str]) -> int:
    """Map a character to its vocabulary index (1-indexed, 0 = blank)."""
    try:
        return vocab.index(char)
    except ValueError:
        return 0  # unknown → blank (will be ignored by CTC)


def greedy_ctc_decode(logits: "torch.Tensor", vocab: list[str]) -> str:
    """Greedy CTC decoding for a single sequence.

    Args:
        logits: (T, vocab_size) tensor of log-softmax outputs.
        vocab:  Vocabulary list returned by build_vocab().

    Returns:
        Decoded string (blank tokens and consecutive duplicates collapsed).
    """
    preds = logits.argmax(dim=-1).cpu().tolist()  # (T,)
    chars: list[str] = []
    prev = -1
    for p in preds:
        if p != prev:
            if p != 0:  # skip blank
                chars.append(vocab[p])
            prev = p
    return "".join(chars)


class _ConvBlock(nn.Module):
    """Conv2d → BatchNorm2d → ReLU → optional MaxPool."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        pool: tuple[int, int] | None = None,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = [
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        ]
        if pool is not None:
            layers.append(nn.MaxPool2d(kernel_size=pool, stride=pool))
        self.block = nn.Sequential(*layers)

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        return self.block(x)


class CRNN(nn.Module):
    """Convolutional Recurrent Neural Network for DataMatrix recognition.

    Input shape:   (B, 1, IMG_H=32, IMG_W=256)
    Output shape:  (T=64, B, VOCAB_SIZE=96)  — log-softmax, ready for CTC loss.

    Feature map dimensions after each conv block:
      Block 1 pool(2,2): (B, 64,  16, 128)
      Block 2 pool(2,2): (B, 128,  8,  64)
      Block 3 pool(2,1): (B, 256,  4,  64)   ← height-only pool
      Block 4 pool(2,1): (B, 512,  2,  64)   ← height-only pool
      AdaptiveAvgPool:   (B, 512,  1,  64)   ← collapse height to 1
      Permute → LSTM:    (T=64, B, 512)
    """

    def __init__(
        self,
        vocab_size: int = VOCAB_SIZE,
        hidden_size: int = 256,
    ) -> None:
        super().__init__()

        # CNN feature extractor
        self.cnn = nn.Sequential(
            _ConvBlock(1,   64,  pool=(2, 2)),  # (B, 64,  16, 128)
            _ConvBlock(64,  128, pool=(2, 2)),  # (B, 128,  8,  64)
            _ConvBlock(128, 256, pool=(2, 1)),  # (B, 256,  4,  64)
            _ConvBlock(256, 512, pool=(2, 1)),  # (B, 512,  2,  64)
        )

        # Collapse height → 1 so width becomes the sequence axis
        self.height_pool = nn.AdaptiveAvgPool2d((1, None))  # (B, 512, 1, W')

        # Bidirectional LSTM sequence model
        self.lstm = nn.LSTM(
            input_size=512,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=False,   # expects (T, B, C)
            bidirectional=True,
            dropout=0.2,
        )

        # Output projection to vocabulary
        self.fc = nn.Linear(hidden_size * 2, vocab_size)

    def forward(self, x: "torch.Tensor") -> "torch.Tensor":
        """Forward pass.

        Args:
            x: (B, 1, H, W) float32 image tensor, values in [0, 1].

        Returns:
            log_probs: (T, B, vocab_size) log-softmax, suitable for
                       ``torch.nn.CTCLoss``.
        """
        feat = self.cnn(x)               # (B, C, H', W')
        feat = self.height_pool(feat)    # (B, C, 1, W')
        feat = feat.squeeze(2)           # (B, C, W')
        feat = feat.permute(2, 0, 1)     # (W', B, C) = (T, B, C)

        seq, _ = self.lstm(feat)         # (T, B, hidden*2)
        logits = self.fc(seq)            # (T, B, vocab_size)
        return F.log_softmax(logits, dim=-1)

    @property
    def output_time_steps(self) -> int:
        """Number of output time steps for a standard (32, 256) input image."""
        return IMG_W // 4  # 64

    @staticmethod
    def from_pretrained(checkpoint_path: str, device: str = "cpu") -> "CRNN":
        """Load a saved model checkpoint.

        Args:
            checkpoint_path: Path to ``*.pt`` checkpoint saved by
                             ``training/train_recognizer.py``.
            device:          Torch device string (``"cpu"`` or ``"cuda"``).

        Returns:
            Loaded CRNN model in eval mode.
        """
        checkpoint = torch.load(checkpoint_path, map_location=device)
        vocab_size = checkpoint.get("vocab_size", VOCAB_SIZE)
        hidden_size = checkpoint.get("hidden_size", 256)
        model = CRNN(vocab_size=vocab_size, hidden_size=hidden_size)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        return model
