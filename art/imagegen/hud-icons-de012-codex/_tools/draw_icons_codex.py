"""Isolated DE-012 proposal using the local, immutable v3 generator snapshot.

No runtime integrations. All exports are written by build_review.py inside this folder.
"""
import draw_icons_v3_snapshot as v3

CANDIDATES = dict(v3.CANDIDATES)


def draw_fallen(ctx, sp, layer=None):
    # Same outer heart geometry. Blackened center and a smaller X preserve the lobes.
    if layer in (None, 'heart'):
        def core():
            v3.heart_path(ctx, *v3.HEART_C)
        v3.inset_fill(ctx, core, -(sp.E + sp.K), v3.C['keyline'])
        v3.inset_fill(ctx, core, -sp.E, v3.C['dim'])
        v3.inset_fill(ctx, core, sp.pxu(1.0), v3.C['body'])
    if layer in (None, 'cross'):
        v3.glyph(ctx, sp, *v3.FALLEN_X,
                 lambda: v3.g_x(ctx, sp, half=4.0, w=sp.pxu(2.5), col=v3.C['error']))


def draw_slot(ctx, sp, layer=None):
    # One active rim replaces the target-like pair of concentric rings.
    r = 16 - sp.M
    if layer in (None, 'ring'):
        v3.circle(ctx, 16, 16, r)
        v3.fill(ctx, v3.C['keyline'])
        v3.circle(ctx, 16, 16, r-sp.K)
        v3.fill(ctx, v3.C['ring.orange'])
        v3.circle(ctx, 16, 16, r-sp.K-sp.pxu(1.5))
        v3.fill(ctx, v3.C['keyline'])
        v3.circle(ctx, 16, 16, r-2*sp.K-sp.pxu(1.5))
        v3.fill(ctx, v3.C['body'])
        # A filled dim ghost distinguishes the tracker from a portrait ring,
        # without the competing second outline of the baseline slot.
        v3.circle(ctx, 16, 16, sp.pxu(6.5))
        ctx.set_source_rgba(*v3.C['dim'], .35)
        ctx.fill()


def draw_stamp(ctx, sp):
    v3.glyph(ctx, sp, 16, 16,
             lambda: v3.g_x(ctx, sp, half=9.0, w=sp.pxu(3.5), col=v3.C['error']))


CANDIDATES['resource-hp-fallen'] = (draw_fallen, {}, False)
CANDIDATES['marker-action-slot-de'] = (draw_slot, {}, False)
CANDIDATES['marker-x-stamp'] = (draw_stamp, {}, False)


def render(name, size, **kwargs):
    fn, defaults, wide = CANDIDATES[name]
    sp = v3.Spec(size)
    surf, ctx = v3.surface(size*2 if wide else size, size)
    ctx.scale(sp.k, sp.k)
    fn(ctx, sp, **(defaults | kwargs))
    return v3.to_pil(surf)
