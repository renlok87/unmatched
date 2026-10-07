"""SC-29: Interface defaults and the HB-42 END TURN key-hint sample."""
from sc24_pause import Viewport, interface_rows
from package_support import run_package


def specifications():
    return [
        ('interface-hints', resolution, scale, Viewport.preset(resolution, scale), {
            'state': 'game', 'background': 'marmoreal', 'open_tab': 'interface',
            'rows': interface_rows(hints=True),
        })
        for resolution, scale in (('1080p', 100), ('1080p', 150), ('720p', 100), ('720p', 150))
    ]


if __name__ == '__main__':
    run_package(29, specifications())
