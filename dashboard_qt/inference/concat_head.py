"""Custom dual-head YOLO layer (fire + COCO) — moved out of the old dash.py.

Lives ONLY inside the inference child process; the UI process never imports
torch. ``install()`` monkey-patches the class into ultralytics so checkpoint
deserialization finds it without modifying the installed package.
"""

from __future__ import annotations


def install() -> None:
    import torch
    import torch.nn as nn

    class ConcatHead(nn.Module):
        """Concatenation layer for two Detect heads (e.g. 80-class + 1-class)."""

        def __init__(self, nc1=80, nc2=1, ch=()):
            super().__init__()
            self.nc1 = nc1
            self.nc2 = nc2

        def forward(self, x):
            if isinstance(x[0], tuple):
                preds1 = x[0][0]
                preds2 = x[1][0]
            elif isinstance(x[0], list):
                return [torch.cat((x0, x1), dim=1) for x0, x1 in zip(x[0], x[1])]
            else:
                preds1 = x[0]
                preds2 = x[1]

            preds = torch.cat((preds1[:, :4, :], preds2[:, :4, :]), dim=2)

            shape = list(preds1.shape)
            shape[-1] *= 2
            preds1_ext = torch.zeros(shape, device=preds1.device, dtype=preds1.dtype)
            preds1_ext[..., : preds1.shape[-1]] = preds1

            shape = list(preds2.shape)
            shape[-1] *= 2
            preds2_ext = torch.zeros(shape, device=preds2.device, dtype=preds2.dtype)
            preds2_ext[..., preds2.shape[-1]:] = preds2

            preds = torch.cat((preds, preds1_ext[:, 4:, :]), dim=1)
            preds = torch.cat((preds, preds2_ext[:, 4:, :]), dim=1)

            if isinstance(x[0], tuple):
                return (preds, x[0][1])
            return preds

    import ultralytics.nn.modules.conv as conv_module
    conv_module.ConcatHead = ConcatHead
