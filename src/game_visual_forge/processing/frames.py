from __future__ import annotations

from typing import Any

from game_visual_forge.errors import ErrorCode, ForgeError


def split_grid(image: Any, *, rows: int, columns: int, frame_count: int) -> tuple[Any, ...]:
    width, height = image.size
    if width % columns or height % rows:
        raise ForgeError(
            ErrorCode.INVALID_GRID,
            "image dimensions must divide evenly by the configured grid",
            recoverable=True,
            context={"width": width, "height": height, "rows": rows, "columns": columns},
        )
    cell_width, cell_height = width // columns, height // rows
    frames = []
    for index in range(frame_count):
        row, column = divmod(index, columns)
        frame = image.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height))
        if frame.getchannel("A").getbbox() is None:
            raise ForgeError(ErrorCode.INVALID_FRAME, "sprite frame is empty", recoverable=True, context={"frame_index": index})
        frames.append(frame)
    return tuple(frames)


def trim_alpha(frame: Any) -> Any:
    bounds = frame.getchannel("A").getbbox()
    if bounds is None:
        raise ForgeError(ErrorCode.INVALID_FRAME, "sprite frame is empty", recoverable=True)
    return frame.crop(bounds)
