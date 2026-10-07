"""SC-26: the Interface tab in RU, EN and expanded pseudo-Russian."""
from sc24_pause import Viewport, interface_rows
from package_support import run_package


def specifications():
    return [
        (language, resolution, scale, Viewport.preset(resolution, scale), {
            'state': 'game', 'background': 'sarpedon', 'open_tab': 'interface',
            'language': language, 'rows': interface_rows(language=language),
        })
        for language in ('ru', 'en', 'pseudo')
        for resolution, scale in (('1080p', 100), ('1080p', 150), ('720p', 100), ('720p', 150))
    ]


if __name__ == '__main__':
    run_package(26, specifications())
