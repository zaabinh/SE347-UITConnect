"""Repeatable local/Render verification benchmark; creates synthetic images, no R2/DB."""

import argparse
import json
import platform
from io import BytesIO
from time import perf_counter, process_time

from PIL import Image, __version__ as pillow_version

from app.modules.media.policy import MAX_PIXELS
from app.modules.media.verification import verify_image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=3, choices=range(1, 21))
    args = parser.parse_args()
    results = []
    for width, height in ((1200, 800), (4000, 2000)):
        for fmt, mime, suffix in (("JPEG", "image/jpeg", "jpg"), ("PNG", "image/png", "png")):
            # Synthetic gradient; production acceptance also needs real high-entropy samples.
            with Image.linear_gradient("L").resize((width, height)).convert("RGB") as source:
                buffer = BytesIO()
                source.save(buffer, format=fmt)
                data = buffer.getvalue()
            elapsed = []
            cpu_start = process_time()
            for _ in range(args.iterations):
                start = perf_counter()
                result = verify_image(data, filename=f"benchmark.{suffix}",
                                      content_type=mime, declared_size=len(data))
                elapsed.append(perf_counter() - start)
            results.append({"format": fmt, "width": width, "height": height,
                            "input_bytes": len(data), "output_bytes": len(result.data),
                            "wall_seconds": elapsed, "cpu_seconds": process_time() - cpu_start})
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = peak if platform.system() == "Darwin" else peak * 1024
    except ImportError:
        peak_bytes = None
    print(json.dumps({"platform": platform.platform(), "pillow": pillow_version,
                      "max_pixels": MAX_PIXELS, "concurrency": 1, "peak_process_rss_bytes": peak_bytes,
                      "results": results}, indent=2))


if __name__ == "__main__":
    main()
