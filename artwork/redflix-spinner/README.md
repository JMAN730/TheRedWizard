# Redflix busy spinner (work in progress)

Animated version of the Red Light neon icon, intended as the busy/loading
spinner for the Redflix build skin (`DialogBusy.xml`).

## Files

- `icon.png` — source artwork (512x512 static neon icon)
- `make_spin3d.py` — chosen animation: 3D coin spin with thick metal edge,
  outputs `g_spin3d.gif` (40 frames, 40ms/frame)
- `make_spin_previews.py` — earlier flat-spin variants (continuous spin,
  flip-pause, vertical tumble)
- `make_spinner_previews.py` — earlier glow-only variants (pulse, flicker,
  glow sweep)
- `preview.html` — side-by-side browser preview of all variants (regenerate
  the GIFs first; only the chosen one is committed)
- `g_spin3d.gif` — chosen animation, rendered

## Regenerate

```
python make_spin3d.py
```

Requires Pillow + numpy.

## Next steps

- Render transparent PNG frame sequence (256x256) instead of GIF
- Drop-in `DialogBusy.xml` (multiimage control, timeperimage=40) for the
  Redflix build skin once the skin is confirmed
