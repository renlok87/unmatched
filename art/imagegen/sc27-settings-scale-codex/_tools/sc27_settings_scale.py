"""SC-27: five applied-scale examples; unchanged family renderer."""
import re
from sc24_pause import Viewport, interface_rows
import package_support as support


def specifications():
    combinations = ((75, '1080p', 75), (100, '1080p', 100),
                    (150, '1080p', 150), (100, '720p', 100), (150, '720p', 150))
    return [
        (f'scale-{value}', resolution, applied,
         Viewport(1920, 1080, 1.0, .75) if value == 75 else Viewport.preset(resolution, applied), {
             'state': 'game', 'background': 'marmoreal', 'open_tab': 'interface',
             'rows': interface_rows(scale=value, minimum=100 if resolution == '720p' else 75,
                                    range_note=True),
         })
        for value, resolution, applied in combinations
    ]


if __name__ == '__main__':
    # Each combination has a unique resolution/applied-scale pair: no state suffix is needed.
    original_overlay = support.overlay
    def named_overlay(viewport, components, path):
        path = path.with_name(re.sub(r'-scale-\d+(?=\.png$)', '', path.name))
        return original_overlay(viewport, components, path)
    support.overlay = named_overlay
    support.run_package(27, specifications())
