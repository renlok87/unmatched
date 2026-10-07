"""SC-28: animation-speed and reduced-motion defaults, without shake UI."""
from sc24_pause import Viewport, game_rows
from package_support import run_package


def specifications():
    return [
        ('game', resolution, scale, Viewport.preset(resolution, scale), {
            'state': 'game', 'background': 'sarpedon', 'open_tab': 'game', 'rows': game_rows(),
        })
        for resolution, scale in (('1080p', 100), ('1080p', 150), ('720p', 100), ('720p', 150))
    ]


if __name__ == '__main__':
    run_package(28, specifications())
