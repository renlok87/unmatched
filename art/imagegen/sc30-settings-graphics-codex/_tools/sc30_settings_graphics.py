"""SC-30: High quality preset with the fixed screen-percentage/FPS note."""
from sc24_pause import Viewport, graphics_rows
from package_support import run_package


def specifications():
    return [
        ('graphics', resolution, scale, Viewport.preset(resolution, scale), {
            'state': 'game', 'background': 'sarpedon', 'open_tab': 'graphics', 'rows': graphics_rows(),
        })
        for resolution, scale in (('1080p', 100), ('1080p', 150), ('720p', 100), ('720p', 150))
    ]


if __name__ == '__main__':
    run_package(30, specifications())
