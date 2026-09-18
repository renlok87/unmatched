export function parseManeuverCompletion(input: string): {
  boostRef: string | null;
  moves: Array<{ fighterRef: string; path: Array<{ x: number; y: number }> }>;
} {
  const tokens = input.trim().split(/\s+/);
  const boost = tokens.shift();
  if (!boost) throw new Error('maneuver done <boost|-> [f0 x,y ... ; f1 x,y ...]');
  const routes = tokens.join(' ').trim();
  const moves = routes ? routes.split(';').map(route => {
    const [fighterRef, ...points] = route.trim().split(/\s+/);
    if (!fighterRef || !points.length) throw new Error('Для каждого бойца укажите непустой путь x,y');
    const path = points.map(point => {
      if (!/^-?\d+,-?\d+$/.test(point)) throw new Error(`Плохая точка пути: ${point}`);
      const [x, y] = point.split(',').map(Number);
      return { x: x!, y: y! };
    });
    return { fighterRef, path };
  }) : [];
  return { boostRef: boost === '-' ? null : boost, moves };
}
