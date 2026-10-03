# ML (phase 3)

1. Generate labelled datasets with `python -m simulator --config configs/<faults>.yaml`.
2. Explore them in a notebook, build window features (mean, std, slope, compressor duty cycle, energy per cycle...).
3. Train an Isolation Forest on *normal* data only; evaluate precision/recall on the faults.
4. Scoring service: reads the latest window from InfluxDB, writes `anomaly_score` back.
5. Later: classify the fault type (supervised).
