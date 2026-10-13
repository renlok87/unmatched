/**
 * Link between the Heroes collection and the art hub (dev server only: /__art-hub/hero, /__art-hub/heroes).
 * Figures are tied to a hero by Hero.name in docs/art-pipeline/hero-links.json.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Card, Collapse, Empty, Image, Result, Space, Spin, Tag, Tooltip, Typography } from 'antd';
import { PictureOutlined } from '@ant-design/icons';
import { gql } from 'urql';
import { client } from '../../providers/dataProvider';
import type { HeroFigureSummary, LookdevHeroView, Vocabulary } from '../../../art-hub/types';
import { ART_HUB_API, IS_DEV, fileUrl } from '../art-hub/api';
import { ArtHubUiContext, type ArtHubUi } from '../art-hub/components/common';
import { HeroLookdev, ROLE_LABEL, VERDICT_COLOR } from '../art-hub/sections/LookdevSection';

const { Text } = Typography;

export const artHubFigurePath = (key: string) => `/art-hub?item=lookdev&hero=${encodeURIComponent(key)}`;

async function getJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', signal });
  if (!res.ok || !(res.headers.get('content-type') ?? '').includes('json')) throw new Error(`${url}: ${res.status}`);
  return (await res.json()) as T;
}

/** Hero.name (lower case) → linked art-hub figures; empty outside the dev server. */
export function useHeroArtLinks(): Record<string, HeroFigureSummary[]> {
  const [links, setLinks] = useState<Record<string, HeroFigureSummary[]>>({});
  useEffect(() => {
    if (!IS_DEV) return undefined;
    const ctrl = new AbortController();
    getJson<{ heroes: Record<string, HeroFigureSummary[]> }>(`${ART_HUB_API}/heroes`, ctrl.signal)
      .then((d) => setLinks(d.heroes))
      .catch(() => undefined);
    return () => ctrl.abort();
  }, []);
  return links;
}

const FigureFacts: React.FC<{ f: HeroFigureSummary }> = ({ f }) => (
  <Space size={4} wrap>
    <Tag color={f.role === 'hero' ? 'geekblue' : 'default'}>{ROLE_LABEL[f.role]}</Tag>
    <Tag color="blue">{f.stage}</Tag>
    {f.verdict ? <Tag color={VERDICT_COLOR[f.verdict] ?? 'default'}>{f.verdict}</Tag> : null}
    {f.score !== undefined ? <Text>{f.score.toFixed(1)}</Text> : null}
    {f.secondAcceptor ? <Tag color="gold">нужен 2-й приёмщик</Tag> : null}
  </Space>
);

/** Heroes list cell: linked figures as compact tags pointing at their art-hub pages. */
export const HeroArtTags: React.FC<{ figures?: HeroFigureSummary[] }> = ({ figures }) =>
  figures?.length ? (
    <Space size={[4, 4]} wrap onClick={(e) => e.stopPropagation()}>
      {figures.map((f) => (
        <Tooltip key={f.key} title={`${ROLE_LABEL[f.role]} · ${f.stage}${f.verdict ? ` · ${f.verdict}` : ''}${f.score !== undefined ? ` ${f.score.toFixed(1)}` : ''}`}>
          <Link to={artHubFigurePath(f.key)}>
            <Tag icon={<PictureOutlined />} color={f.verdict === 'pass' ? 'green' : f.role === 'hero' ? 'blue' : 'default'}>
              {f.name}
            </Tag>
          </Link>
        </Tooltip>
      ))}
    </Space>
  ) : (
    <Text type="secondary">—</Text>
  );

interface HeroFiguresResponse {
  vocab: Vocabulary;
  figures: LookdevHeroView[];
  summary: HeroFigureSummary[];
}

/** Hero page block: every art-hub figure of this hero (and its sidekicks) with the full look-dev view. */
export const HeroArtHubPanel: React.FC<{ heroName?: string }> = ({ heroName }) => {
  const navigate = useNavigate();
  const [state, setState] = useState<{ data?: HeroFiguresResponse; error?: string; loading: boolean }>({ loading: IS_DEV });
  useEffect(() => {
    if (!IS_DEV || !heroName) return undefined;
    const ctrl = new AbortController();
    setState({ loading: true });
    getJson<HeroFiguresResponse>(`${ART_HUB_API}/hero?${new URLSearchParams({ name: heroName })}`, ctrl.signal)
      .then((data) => setState({ data, loading: false }))
      .catch((err: unknown) => {
        if (!(err instanceof DOMException && err.name === 'AbortError')) setState({ error: String(err), loading: false });
      });
    return () => ctrl.abort();
  }, [heroName]);

  const ui = useMemo<ArtHubUi | null>(
    () =>
      state.data
        ? {
            vocab: state.data.vocab,
            previewText: (f) => window.open(fileUrl(f), '_blank', 'noreferrer'),
            view3D: (f) => window.open(fileUrl(f), '_blank', 'noreferrer'),
            openPage: (id, tab) => navigate(`/art-hub?${new URLSearchParams({ item: id, ...(tab ? { tab } : {}) })}`),
          }
        : null,
    [state.data, navigate],
  );

  const title = (
    <Space>
      <PictureOutlined />
      <span>Арт-хаб{state.data ? ` (${state.data.figures.length})` : ''}</span>
      <Link to="/art-hub?item=lookdev">таблица look-dev</Link>
    </Space>
  );
  if (!IS_DEV) {
    return (
      <Card size="small" title={title}>
        <Text type="secondary">Данные арт-хаба доступны только на dev-сервере админки.</Text>
      </Card>
    );
  }
  if (state.loading) {
    return (
      <Card size="small" title={title}>
        <Spin />
      </Card>
    );
  }
  if (state.error || !state.data || !ui) {
    return (
      <Card size="small" title={title}>
        <Alert type="warning" showIcon message="Арт-хаб не ответил" description={state.error} />
      </Card>
    );
  }
  const { figures, summary } = state.data;
  return (
    <Card size="small" title={title} data-testid="hero-art-hub">
      {figures.length ? (
        <ArtHubUiContext.Provider value={ui}>
          <Collapse
            size="small"
            items={figures.map((fig, i) => {
              const s = summary[i]!;
              return {
                key: fig.key,
                label: (
                  <Space wrap>
                    {s.thumb ? (
                      <span onClick={(e) => e.stopPropagation()}>
                        <Image src={fileUrl(s.thumb)} width={40} height={52} style={{ objectFit: 'contain', background: '#f5f5f5' }} alt={s.name} />
                      </span>
                    ) : null}
                    <Text strong>{s.name}</Text>
                    <FigureFacts f={s} />
                    {s.note ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {s.note}
                      </Text>
                    ) : null}
                    <span onClick={(e) => e.stopPropagation()}>
                      <Link to={artHubFigurePath(fig.key)}>в арт-хабе</Link>
                    </span>
                  </Space>
                ),
                children: <HeroLookdev hero={fig} showTitle={false} />,
              };
            })}
          />
        </ArtHubUiContext.Provider>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span>
              Фигур этого героя в арт-хабе нет. Связи — <Text code>docs/art-pipeline/hero-links.json</Text>
            </span>
          }
        />
      )}
    </Card>
  );
};

const HERO_BY_NAME = gql`
  query HeroByName($search: String) {
    heroList(page: 1, limit: 50, search: $search) {
      items {
        id
        name
      }
    }
  }
`;

/** /heroes/by-name/:name — resolves the unique Hero.name (art-hub links) to the hero page. */
export const HeroByName: React.FC = () => {
  const { name = '' } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string>();
  useEffect(() => {
    let alive = true;
    client
      .query(HERO_BY_NAME, { search: name })
      .toPromise()
      .then((res) => {
        if (!alive) return;
        if (res.error) throw res.error;
        const items: { id: string; name: string }[] = res.data?.heroList?.items ?? [];
        const hit = items.find((h) => h.name.toLowerCase() === name.toLowerCase());
        if (hit) navigate(`/heroes/show/${hit.id}`, { replace: true });
        else setError(`Героя «${name}» в коллекции Heroes нет`);
      })
      .catch((err: unknown) => alive && setError(err instanceof Error ? err.message : String(err)));
    return () => {
      alive = false;
    };
  }, [name, navigate]);
  return error ? (
    <Result status="404" title="Герой не найден" subTitle={error} extra={<Link to="/heroes">к списку героев</Link>} />
  ) : (
    <Spin style={{ display: 'block', margin: '48px auto' }} />
  );
};
