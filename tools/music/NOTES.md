# Dino Loop: original Amiga-style chiptune for Dinosaur vs Bees

- Format: XM (FastTracker 2), 6 channels, 6 instruments, all synthesised in Python (`../make.py`), no samples from anywhere
- Tempo: 136 BPM (speed 6, 4 rows per beat), linear frequency table
- Key: C major, with A minor colour in the B section
- Length: 8 orders, 32 bars, about 56.5 s. Restart position 0, so it loops seamlessly
- Structure: A (P0 C-Am-F-G, P1 C-Am-Dm-G) | B (P2 Am-F-C-G, P3 F-G-Em-E) | A again (P0, P1) | B' (P4 F-G-C-Am, P5 Dm-Bb-G-G turnaround plus a snare fill back into the top)

## Channels
1. Lead: 25% pulse. Catchy chord-tone melody with vibrato (4xy) on held notes, vibrato plus volume slide down (6xy) on long tails, and occasional tone portamento (3xx) slides
2. Arp: square wave. Fast 0xy arpeggio chords (037 minor, 047 major), retriggered each beat, with a volume slide (Axy) and a short decay envelope
3. Bass: saw. Octave-jumping 8th notes (low/high root, fifth pickup), with an Axy slide on the off-beats and a decay envelope
4. Kick: synthesised pitch-dropping sine
5. Snare: noise plus a 190 Hz tone body. Fill at the end of P5
6. Hats: high-passed noise. 8ths in the A sections, 16ths in the B sections

## Files
- dino_loop.xm: the module
- dino_loop_render.wav / .ogg: exactly one loop (libopenmpt render via ffmpeg; the release tail is folded into the start so it loops cleanly)
- dino_loop_render_2x.wav / .ogg: two passes back to back, to show the seam

Render check: peak −1.4 dBFS after normalising, no clipped samples, RMS about −14 dBFS. The jump at the loop point is 431 LSB, against a typical 99th-percentile sample step of about 7800, so there's no click.
