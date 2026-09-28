"""QA-010 evidence tooling (grayscale/deuteranopia derivatives, luma stats,
C-9 layer contrast, HUD plate vs reachable cells, icon contrast, checklist).

1.1.0: c9 on proxy layer masks is never normative (result "proxy", exit 3);
checklist binds every automatic value to frames.K*.path; plate returns
insufficient_input when nothing was checked (empty selection, zero-size or
off-screen plate, all selected cells off-screen).

Image modules need numpy + Pillow. Trace, projection, geometry, plate, layers and
checklist modules are stdlib-only so they run without the imaging stack.
"""

VERSION = "qa010-tools 1.1.0"
