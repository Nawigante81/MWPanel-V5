from __future__ import annotations

from typing import Any, Dict, List


def normalize_images(images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for idx, img in enumerate(sorted(images, key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))):
        file_url = img.get("file_url")
        if not file_url:
            continue
        out.append({
            "file_url": file_url,
            "is_cover": bool(img.get("is_cover", False)),
            "sort_order": int(img.get("sort_order") or idx),
        })
    if out and not any(i["is_cover"] for i in out):
        out[0]["is_cover"] = True
    return out
