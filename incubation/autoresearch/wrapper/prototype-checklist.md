# Prototype checklist

## First wrapper milestone

- [ ] Point the wrapper at a local `autoresearch` checkout
- [ ] Capture baseline contents of `train.py`
- [ ] Execute one configured command
- [ ] Save `stdout.txt` and `stderr.txt`
- [ ] Generate `patch.diff`
- [ ] Parse `val_bpb`
- [ ] Emit `artifact.json`
- [ ] Classify outcome

## Nice-to-have after the first milestone

- [ ] Track parent run / baseline lineage
- [ ] Compare metric to prior baseline automatically
- [ ] Capture git commit SHA when available
- [ ] Record hardware metadata more completely
- [ ] Add a minimal review script for browsing emitted artifacts

## Exit signal for moving beyond incubation

- [ ] The wrapper produces useful evidence across multiple local runs
- [ ] The artifact shape feels stable enough to compare across experiments
- [ ] We understand whether wrapper-only is sufficient or task packaging is warranted
- [ ] We can explain the value clearly in writing with prototype evidence
