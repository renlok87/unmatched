import React from 'react';
import './RatingChart.css';

export interface RatingHistoryPoint {
  date: string;
  rating: number;
  gameId: string;
}

interface RatingChartProps {
  data: RatingHistoryPoint[];
  period: 'week' | 'month' | 'all';
  peakRating?: number;
}

export const RatingChart: React.FC<RatingChartProps> = ({ data, period: _period, peakRating }) => {
  if (!data || data.length === 0) {
    return (
      <div className="rating-chart rating-chart--empty">
        <p className="rating-chart__empty-text">Нет данных о рейтинге</p>
      </div>
    );
  }

  const ratings = data.map((d) => d.rating);
  const minRating = Math.min(...ratings) - 50;
  const maxRating = Math.max(...ratings) + 50;
  const range = maxRating - minRating;

  const points = data.map((point, index) => {
    const x = (index / (data.length - 1)) * 100;
    const y = 100 - ((point.rating - minRating) / range) * 100;
    return { x, y, ...point };
  });

  const pathData = points
    .map((point, index) => {
      if (index === 0) {
        return `M ${point.x} ${point.y}`;
      }
      const prev = points[index - 1];
      const cpX = (prev.x + point.x) / 2;
      return `C ${cpX} ${prev.y}, ${cpX} ${point.y}, ${point.x} ${point.y}`;
    })
    .join(' ');

  const areaData = `${pathData} L ${points[points.length - 1].x} 100 L ${points[0].x} 100 Z`;

  const peakPoint = peakRating
    ? points.find((p) => p.rating === peakRating) || points[points.length - 1]
    : points[points.length - 1];

  return (
    <div className="rating-chart">
      <div className="rating-chart__header">
        <h3 className="rating-chart__title">Рейтинг</h3>
        <div className="rating-chart__current">
          <span className="rating-chart__current-value">{data[data.length - 1].rating}</span>
          <span className="rating-chart__current-label">ELO</span>
        </div>
      </div>

      <div className="rating-chart__container">
        <svg
          className="rating-chart__svg"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="ratingGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="rgba(99, 102, 241, 0.3)" />
              <stop offset="100%" stopColor="rgba(99, 102, 241, 0)" />
            </linearGradient>
          </defs>

          <path
            className="rating-chart__area"
            d={areaData}
            fill="url(#ratingGradient)"
          />

          <path
            className="rating-chart__line"
            d={pathData}
            fill="none"
            stroke="var(--color-primary)"
            strokeWidth="0.5"
          />

          {points.map((point) => (
            <circle
              key={point.gameId}
              className="rating-chart__point"
              cx={point.x}
              cy={point.y}
              r="1"
            />
          ))}

          {peakPoint && (
            <circle
              className="rating-chart__peak-point"
              cx={peakPoint.x}
              cy={peakPoint.y}
              r="1.5"
            />
          )}
        </svg>
      </div>

      <div className="rating-chart__legend">
        <div className="rating-chart__legend-item">
          <div className="rating-chart__legend-dot rating-chart__legend-dot--current" />
          <span>Текущий</span>
        </div>
        {peakRating && (
          <div className="rating-chart__legend-item">
            <div className="rating-chart__legend-dot rating-chart__legend-dot--peak" />
            <span>Пик: {peakRating}</span>
          </div>
        )}
      </div>
    </div>
  );
};