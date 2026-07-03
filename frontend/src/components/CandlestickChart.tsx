import { useEffect, useRef, useCallback, useState } from 'react';
import * as d3 from 'd3';
import axios from 'axios';
import { useLang } from '../LanguageContext';
import { t } from '../i18n';

interface OHLCRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Particle {
  id: string;
  d: string;   // trade_date
  s: string | null;  // sentiment
  r: string | null;  // relevance
  t: string;   // title (truncated)
  rt1: number | null; // ret_t1
}

interface HoverData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  change: number;
}

interface RangeSelection {
  startDate: string;
  endDate: string;
  priceChange?: number;
  popupX?: number;
  popupY?: number;
}

interface ArticleSelection {
  newsId: string;
  date: string;
}

interface Props {
  symbol: string;
  livePrice?: number | null;
  lockedNewsId?: string | null;
  highlightedArticleIds?: string[] | null;
  highlightColor?: string | null;
  onHover: (date: string | null, ohlc?: HoverData) => void;
  onRangeSelect?: (range: RangeSelection | null) => void;
  onArticleSelect?: (article: ArticleSelection | null) => void;
  onDayClick?: (date: string) => void;
}

// Sentiment → color mapping (A-share palette: 涨=red, 跌=green)
const SENTIMENT_COLOR: Record<string, string> = {
  positive: '#e63946',
  negative: '#2d936c',
  neutral: '#c9a96e',
};
const SENTIMENT_COLOR_DEFAULT = '#5c5750';

function getSentimentColor(s: string | null): string {
  return (s && SENTIMENT_COLOR[s]) || SENTIMENT_COLOR_DEFAULT;
}

function getParticleRadius(relevance: string | null, rt1: number | null): number {
  let r = 2;
  if (relevance === 'relevant') r += 0.8;
  if (rt1 !== null) r += Math.min(Math.abs(rt1) * 20, 1.5);
  return Math.min(r, 4.5);
}

function getParticleAlpha(relevance: string | null): number {
  return relevance === 'relevant' ? 0.7 : 0.3;
}

interface PlacedParticle extends Particle {
  px: number; // canvas x
  py: number; // canvas y
  radius: number;
  color: string;
  alpha: number;
}

type Period = '1W' | '1M' | '3M' | '1Y' | 'ALL';

const PERIOD_DAYS: Record<Period, number> = {
  '1W': 7,
  '1M': 30,
  '3M': 90,
  '1Y': 365,
  'ALL': Infinity,
};

const PERIOD_LABELS_ZH: Record<Period, string> = { '1W': '近1周', '1M': '近1月', '3M': '近3月', '1Y': '近1年', 'ALL': '全部' };
const PERIOD_LABELS_EN: Record<Period, string> = { '1W': '1W', '1M': '1M', '3M': '3M', '1Y': '1Y', 'ALL': 'All' };

export default function CandlestickChart({ symbol, livePrice, lockedNewsId: _lockedNewsId, highlightedArticleIds, highlightColor, onHover, onRangeSelect, onArticleSelect, onDayClick }: Props) {
  const { lang, theme } = useLang();
  const svgRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState<Period>('3M');
  const [hoveredArticleId, setHoveredArticleId] = useState<string | null>(null);
  const rawOhlcRef = useRef<OHLCRow[]>([]);
  const rawParticlesRef = useRef<Particle[]>([]);

  // Refs for interaction state (avoid re-renders)
  const placedRef = useRef<PlacedParticle[]>([]);
  const quadtreeRef = useRef<d3.Quadtree<PlacedParticle> | null>(null);
  const hoveredParticleRef = useRef<PlacedParticle | null>(null);
  const lockedNewsIdRef = useRef<string | null>(null);
  const highlightedIdsRef = useRef<Set<string> | null>(null);
  const highlightColorRef = useRef<string | null>(null);
  const marginRef = useRef({ top: 16, right: 40, bottom: 24, left: 48 });
  const langRef = useRef(lang);
  langRef.current = lang;
  const livePriceLineRef = useRef<{ line: d3.Selection<SVGLineElement, unknown, null, undefined>; tag: d3.Selection<SVGGElement, unknown, null, undefined>; y: d3.ScaleLinear<number, number>; basePrice: number; tagX: number } | null>(null);

  // Draw hover ring animation when article is hovered
  useEffect(() => {
    if (!hoveredArticleId) return;
    const placed = placedRef.current;
    const target = placed.find(p => p.id === hoveredArticleId);
    if (!target) return;

    // Trigger a redraw with the hovered particle for glow effect
    drawParticles(target);

    // Animate the particle scale
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;

    let startTime = performance.now();
    const duration = 300;

    function animate(currentTime: number) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const scale = 1 + 0.3 * Math.sin(progress * Math.PI);

      // Redraw all particles, but scale the hovered one
      drawParticlesAnimated(target!, scale, ctx!, dpr);

      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        drawParticles(null);
      }
    }

    requestAnimationFrame(animate);
  }, [hoveredArticleId]);

  const drawParticlesAnimated = (target: PlacedParticle, scale: number, ctx: CanvasRenderingContext2D, dpr: number) => {
    ctx.clearRect(0, 0, canvasRef.current!.width, canvasRef.current!.height);
    const placed = placedRef.current;
    for (const p of placed) {
      const isTarget = p === target;
      const radius = isTarget ? p.radius * scale : p.radius;

      ctx.beginPath();
      ctx.arc(p.px * dpr, p.py * dpr, radius * dpr, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.globalAlpha = isTarget ? 1 : 0.3;
      ctx.fill();

      if (isTarget) {
        ctx.shadowColor = p.color;
        ctx.shadowBlur = 15 * dpr;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }
    ctx.globalAlpha = 1;
  };

  useEffect(() => {
    highlightedIdsRef.current = highlightedArticleIds && highlightedArticleIds.length > 0
      ? new Set(highlightedArticleIds)
      : null;
    highlightColorRef.current = highlightColor ?? null;
    drawParticles(hoveredParticleRef.current);
  }, [highlightedArticleIds, highlightColor]);

  // Update price line position when livePrice changes
  useEffect(() => {
    const ref = livePriceLineRef.current;
    if (!ref || livePrice == null || livePrice <= 0) return;
    const newY = ref.y(livePrice);
    const color = livePrice >= ref.basePrice ? '#e63946' : '#2d936c';
    ref.line.attr('y1', newY).attr('y2', newY).attr('stroke', color);
    ref.tag.attr('transform', `translate(${ref.tagX},${newY})`);
    ref.tag.select('rect').attr('fill', color);
    ref.tag.select('text').text(`¥${livePrice.toFixed(0)}`);
  }, [livePrice]);

  const drawParticles = useCallback((highlight: PlacedParticle | null = null) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const locked = lockedNewsIdRef.current;
    const hlSet = highlightedIdsRef.current; // category highlight set
    const hlColor = highlightColorRef.current;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const placed = placedRef.current;
    for (const p of placed) {
      const isLocked = locked != null && p.id === locked;
      const isHover = p === highlight;
      const isCategoryMatch = hlSet != null && hlSet.has(p.id);
      const hasCategoryFilter = hlSet != null;

      // Category filter: hide non-matching particles entirely
      if (hasCategoryFilter && !isCategoryMatch && !isLocked && !isHover) {
        continue;
      }

      let alpha = p.alpha;
      if (isCategoryMatch && hasCategoryFilter) alpha = 1;
      if (isHover || isLocked) alpha = 1;
      ctx.globalAlpha = alpha;

      // Determine radius: category-matched gets a boost
      let radius = p.radius;
      if (isCategoryMatch && hasCategoryFilter) {
        radius = Math.max(p.radius, 3.5);
      }

      // Use category theme color for matched particles, otherwise original
      ctx.fillStyle = (isCategoryMatch && hasCategoryFilter && hlColor) ? hlColor : p.color;

      if (isHover || isLocked || (isCategoryMatch && hasCategoryFilter)) {
        const lockedGlow = getComputedStyle(document.documentElement).getPropertyValue('--accent-primary').trim() || '#c9a96e';
        const glowColor = isLocked ? lockedGlow : (isCategoryMatch && hlColor) ? hlColor : p.color;
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = (isLocked || isHover ? 14 : 8) * dpr;
      } else {
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
      }

      ctx.beginPath();
      ctx.arc(p.px * dpr, p.py * dpr, radius * dpr, 0, Math.PI * 2);
      ctx.fill();

      // Draw cyan ring for locked particle
      if (isLocked) {
        const lockedColor = getComputedStyle(document.documentElement).getPropertyValue('--accent-primary').trim() || '#c9a96e';
        ctx.shadowColor = lockedColor;
        ctx.shadowBlur = 10 * dpr;
        ctx.strokeStyle = lockedColor;
        ctx.lineWidth = 1.5 * dpr;
        ctx.beginPath();
        ctx.arc(p.px * dpr, p.py * dpr, (radius + 3) * dpr, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Draw ring for category-highlighted particles using category color
      if (isCategoryMatch && hasCategoryFilter && !isLocked) {
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.strokeStyle = hlColor ? `${hlColor}99` : 'rgba(102, 126, 234, 0.6)';
        ctx.lineWidth = 1 * dpr;
        ctx.beginPath();
        ctx.arc(p.px * dpr, p.py * dpr, (radius + 2) * dpr, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    ctx.globalAlpha = 1;
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
  }, []);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);

    Promise.all([
      axios.get<OHLCRow[]>(`/api/stocks/${symbol}/ohlc`),
      axios.get<Particle[]>(`/api/news/${symbol}/particles`),
    ])
      .then(([ohlcRes, particlesRes]) => {
        rawOhlcRef.current = ohlcRes.data;
        rawParticlesRef.current = particlesRes.data;
        drawChart(sliceByPeriod(ohlcRes.data, period), particlesRes.data);
      })
      .catch((err) => console.error('Chart error:', err))
      .finally(() => setLoading(false));
  }, [symbol]);

  // Re-render on period, theme, or lang change
  useEffect(() => {
    const ohlc = rawOhlcRef.current;
    const particles = rawParticlesRef.current;
    if (ohlc.length === 0) return;
    drawChart(sliceByPeriod(ohlc, period), particles);
  }, [period, theme, lang]);

  function sliceByPeriod(data: OHLCRow[], p: Period): OHLCRow[] {
    if (p === 'ALL') return data;
    const days = PERIOD_DAYS[p];
    const lastDate = new Date(data[data.length - 1].date);
    const cutoff = new Date(lastDate.getTime() - days * 86400000);
    return data.filter((d) => new Date(d.date) >= cutoff);
  }

  function drawChart(rawData: OHLCRow[], particles: Particle[]) {
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const container = containerRef.current;
    if (!container) return;

    // Read theme-aware chart colors from CSS variables
    const cs = getComputedStyle(container);
    const cv = (name: string) => cs.getPropertyValue(name).trim();

    const fullWidth = container.clientWidth;
    // Use getBoundingClientRect for accurate rendered height
    const rect = container.getBoundingClientRect();
    const fullHeight = rect.height > 0 ? rect.height : 600;
    const margin = marginRef.current;
    const width = fullWidth - margin.left - margin.right;
    const height = fullHeight - margin.top - margin.bottom;

    // Split chart into price area (top ~72%) and volume area (bottom ~25%)
    const priceRatio = 0.72;
    const volRatio = 0.25;
    const gapRatio = 1 - priceRatio - volRatio; // ~3% gap
    const priceHeight = height * priceRatio;
    const volHeight = height * volRatio;
    const volTop = priceHeight + height * gapRatio; // in g-space (g already translated by margin.top)

    svg.attr('width', fullWidth).attr('height', fullHeight);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    interface ChartRow {
      date: Date;
      dateStr: string;
      open: number;
      high: number;
      low: number;
      close: number;
      volume: number;
      change: number;
      limitUp: number | null;
      limitDown: number | null;
      isLimitUp: boolean;
      isLimitDown: boolean;
      ma5?: number;
      ma20?: number;
    }

    const data: ChartRow[] = rawData.map((d, i) => ({
      date: new Date(d.date),
      dateStr: d.date,
      open: +d.open,
      high: +d.high,
      low: +d.low,
      close: +d.close,
      volume: +d.volume,
      change: i > 0 ? ((+d.close - +rawData[i - 1].close) / +rawData[i - 1].close) * 100 : 0,
      limitUp: i > 0 ? +rawData[i - 1].close * 1.095 : null,
      limitDown: i > 0 ? +rawData[i - 1].close * 0.905 : null,
      isLimitUp: i > 0 ? +d.high >= +rawData[i - 1].close * 1.095 : false,
      isLimitDown: i > 0 ? +d.low <= +rawData[i - 1].close * 0.905 : false,
    }));

    // Calculate MA5 and MA20
    for (let i = 0; i < data.length; i++) {
      if (i >= 4) {
        let sum = 0;
        for (let j = i - 4; j <= i; j++) sum += data[j].close;
        data[i].ma5 = sum / 5;
      }
      if (i >= 19) {
        let sum = 0;
        for (let j = i - 19; j <= i; j++) sum += data[j].close;
        data[i].ma20 = sum / 20;
      }
    }

    // Build a lookup: dateStr → OHLC row
    const dateToOhlc = new Map<string, typeof data[0]>();
    for (const d of data) {
      dateToOhlc.set(d.dateStr, d);
    }

    // Scales
    const x = d3.scaleTime()
      .domain(d3.extent(data, (d) => d.date) as [Date, Date])
      .range([0, width]);

    const y = d3.scaleLinear()
      .domain([d3.min(data, (d) => d.low)! * 0.98, d3.max(data, (d) => d.high)! * 1.02])
      .range([priceHeight, 0]);

    const maxVol = d3.max(data, (d) => d.volume)!;
    const yVol = d3.scaleLinear()
      .domain([0, maxVol * 1.1])
      .range([volTop + volHeight, volTop]);

    // Defs for gradients and filters
    const defs = svg.append('defs');

    // Subtle glow filter for candles
    const glowFilter = defs.append('filter').attr('id', 'candle-glow');
    glowFilter.append('feGaussianBlur').attr('stdDeviation', '2').attr('result', 'blur');
    glowFilter.append('feMerge').selectAll('feMergeNode')
      .data(['blur', 'SourceGraphic']).enter()
      .append('feMergeNode').attr('in', (d) => d);

    // Volume gradient (up)
    const volGradUp = defs.append('linearGradient').attr('id', 'vol-grad-up').attr('x1', '0').attr('y1', '0').attr('x2', '0').attr('y2', '1');
    volGradUp.append('stop').attr('offset', '0%').attr('stop-color', cv('--chart-vol-up'));
    volGradUp.append('stop').attr('offset', '100%').attr('stop-color', cv('--chart-vol-up-end'));

    // Volume gradient (down)
    const volGradDown = defs.append('linearGradient').attr('id', 'vol-grad-down').attr('x1', '0').attr('y1', '0').attr('x2', '0').attr('y2', '1');
    volGradDown.append('stop').attr('offset', '0%').attr('stop-color', cv('--chart-vol-down'));
    volGradDown.append('stop').attr('offset', '100%').attr('stop-color', cv('--chart-vol-down-end'));

    // Chart background gradient
    const bgGrad = defs.append('linearGradient').attr('id', 'chart-bg').attr('x1', '0').attr('y1', '0').attr('x2', '0').attr('y2', '1');
    bgGrad.append('stop').attr('offset', '0%').attr('stop-color', cv('--chart-bg-top'));
    bgGrad.append('stop').attr('offset', '100%').attr('stop-color', cv('--chart-bg-bot'));

    // Apply background
    g.append('rect')
      .attr('x', -margin.left).attr('y', -margin.top)
      .attr('width', fullWidth).attr('height', fullHeight)
      .attr('fill', 'url(#chart-bg)');

    // Grid lines — horizontal, subtle warmth
    g.append('g')
      .attr('class', 'grid-y')
      .call(
        d3.axisLeft(y)
          .ticks(6)
          .tickSize(-width)
          .tickFormat(() => '')
      )
      .selectAll('line')
      .style('stroke', cv('--chart-grid'))
      .style('stroke-width', 1)
      .style('stroke-dasharray', '2,4');
    g.selectAll('.grid-y .domain').remove();

    // Vertical grid (time markers)
    g.append('g')
      .attr('class', 'grid-x')
      .attr('transform', `translate(0,${priceHeight})`)
      .call(
        d3.axisBottom(x)
          .ticks(6)
          .tickSize(-priceHeight)
          .tickFormat(() => '')
      )
      .selectAll('line')
      .style('stroke', cv('--chart-grid-v'))
      .style('stroke-width', 1)
      .style('stroke-dasharray', '2,4');
    g.selectAll('.grid-x .domain').remove();

    // Separator — subtle gold tint
    g.append('line')
      .attr('x1', 0).attr('x2', width)
      .attr('y1', volTop - 6).attr('y2', volTop - 6)
      .attr('stroke', cv('--chart-sep'))
      .attr('stroke-width', 0.5)
      .attr('stroke-opacity', 0.6);

    // X Axis (at the very bottom)
    g.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x).ticks(8).tickFormat((d) => {
          const dt = d instanceof Date ? d : new Date(Number(d));
          const spanDays = (data[data.length - 1].date.getTime() - data[0].date.getTime()) / 86400000;
          if (lang === 'zh') {
            if (spanDays > 365) return `${dt.getFullYear()}/${dt.getMonth() + 1}`;
            if (spanDays > 90) return `${dt.getMonth() + 1}月`;
            return `${dt.getMonth() + 1}/${dt.getDate()}`;
          }
          if (spanDays > 365) return d3.timeFormat('%b %Y')(dt);
          if (spanDays > 90) return d3.timeFormat('%b')(dt);
          return d3.timeFormat('%b %d')(dt);
        }))
      .selectAll('text')
      .style('font-size', '11px')
      .style('fill', cv('--chart-axis-text'))
      .style('font-family', '-apple-system, "PingFang SC", sans-serif');

    // Y Axis (price)
    g.append('g')
      .call(d3.axisLeft(y).ticks(6).tickFormat((d) => `¥${Number(d).toFixed(0)}`))
      .selectAll('text')
      .style('font-size', '11px')
      .style('fill', cv('--chart-axis-text-y'))
      .style('font-family', '"SF Mono", "Fira Code", monospace');

    // Volume Y axis (compact, right side)
    g.append('g')
      .attr('transform', `translate(${width},0)`)
      .call(d3.axisRight(yVol).ticks(2).tickFormat((d) => {
        const v = Number(d);
        if (v >= 1e8) return `${(v / 1e8).toFixed(1)}亿`;
        if (v >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
        return `${v}`;
      }))
      .selectAll('text')
      .style('font-size', '10px')
      .style('fill', cv('--chart-vol-text'))
      .style('font-family', '"SF Mono", "Fira Code", monospace');

    g.selectAll('.domain').style('stroke', cv('--chart-axis'));
    g.selectAll('.tick line').style('stroke', cv('--chart-axis'));

    const candleWidth = Math.max(1.5, (width / data.length) * 0.65);

    // --- Volume bars (gradient fill) ---
    g.selectAll('.vol-bar').data(data).enter().append('rect')
      .attr('class', 'vol-bar')
      .attr('x', (d) => x(d.date) - candleWidth / 2)
      .attr('y', (d) => yVol(d.volume))
      .attr('width', candleWidth)
      .attr('height', (d) => Math.max(1, yVol(0) - yVol(d.volume)))
      .attr('fill', (d) => d.close >= d.open ? 'url(#vol-grad-up)' : 'url(#vol-grad-down)')
      .attr('rx', 1);

    // --- MA lines (with glow shadow) ---
    const maLine = (field: 'ma5' | 'ma20') => d3.line<ChartRow>()
      .x((d) => x(d.date))
      .y((d) => y(d[field] ?? 0))
      .defined((d) => d[field] != null)
      .curve(d3.curveMonotoneX);

    // MA5 — gold with glow
    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', cv('--chart-ma5-glow'))
      .attr('stroke-width', 4)
      .attr('d', maLine('ma5') as unknown as string);
    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', cv('--chart-ma5'))
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.8)
      .attr('d', maLine('ma5') as unknown as string);

    // MA20 — cool neutral with subtle glow
    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', cv('--chart-ma20-glow'))
      .attr('stroke-width', 4)
      .attr('d', maLine('ma20') as unknown as string);
    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', cv('--chart-ma20'))
      .attr('stroke-width', 1.2)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-dasharray', '6,3')
      .attr('d', maLine('ma20') as unknown as string);

    // MA legend (top-left, below Y axis labels)
    const legendX = 10;
    const legendY = 4;
    const ma5Color = cv('--chart-ma5');
    const ma20Color = cv('--chart-ma20');

    g.append('line').attr('x1', legendX).attr('x2', legendX + 16).attr('y1', legendY).attr('y2', legendY)
      .attr('stroke', ma5Color).attr('stroke-width', 1.5).attr('stroke-opacity', 0.8);
    g.append('text').attr('x', legendX + 20).attr('y', legendY + 4)
      .attr('fill', ma5Color).attr('font-size', '10px').attr('font-family', 'inherit')
      .text('MA5');

    g.append('line').attr('x1', legendX).attr('x2', legendX + 16).attr('y1', legendY + 14).attr('y2', legendY + 14)
      .attr('stroke', ma20Color).attr('stroke-width', 1.2).attr('stroke-opacity', 0.6).attr('stroke-dasharray', '6,3');
    g.append('text').attr('x', legendX + 20).attr('y', legendY + 18)
      .attr('fill', ma20Color).attr('font-size', '10px').attr('font-family', 'inherit')
      .text('MA20');

    // Current price line (latest close)
    const lastBar = data[data.length - 1];
    const lastCloseY = y(lastBar.close);
    const lastCloseColor = lastBar.close >= lastBar.open ? cv('--chart-body-up') : cv('--chart-body-down');
    const priceLine = g.append('line')
      .attr('x1', 0).attr('x2', width)
      .attr('y1', lastCloseY).attr('y2', lastCloseY)
      .attr('stroke', lastCloseColor)
      .attr('stroke-width', 0.6)
      .attr('stroke-dasharray', '3,3')
      .attr('stroke-opacity', 0.5);
    const priceTag = g.append('g').attr('transform', `translate(${width},${lastCloseY})`);
    priceTag.append('rect')
      .attr('x', 0).attr('y', -8)
      .attr('width', 52).attr('height', 16)
      .attr('rx', 3)
      .attr('fill', lastCloseColor);
    priceTag.append('text')
      .attr('x', 26).attr('dy', 4)
      .attr('text-anchor', 'middle')
      .attr('fill', '#fff')
      .attr('font-size', '10px')
      .attr('font-family', '"SF Mono", "Fira Code", monospace')
      .text(`¥${lastBar.close.toFixed(0)}`);
    livePriceLineRef.current = { line: priceLine, tag: priceTag, y, basePrice: lastBar.open, tagX: width };

    // Candlesticks
    const candles = g.selectAll('.candle').data(data).enter().append('g').attr('class', 'candle');

    // Wicks — thin with slight opacity
    candles.append('line')
      .attr('x1', (d) => x(d.date))
      .attr('x2', (d) => x(d.date))
      .attr('y1', (d) => y(d.high))
      .attr('y2', (d) => y(d.low))
      .attr('stroke', (d) => (d.close >= d.open ? cv('--chart-wick-up') : cv('--chart-wick-down')))
      .attr('stroke-width', 1);

    // Bodies — rounded corners, subtle glow for strong moves
    candles.append('rect')
      .attr('x', (d) => x(d.date) - candleWidth / 2)
      .attr('y', (d) => y(Math.max(d.open, d.close)))
      .attr('width', candleWidth)
      .attr('height', (d) => Math.max(1, Math.abs(y(d.open) - y(d.close))))
      .attr('fill', (d) => (d.close >= d.open ? cv('--chart-body-up') : cv('--chart-body-down')))
      .attr('rx', Math.min(2, candleWidth * 0.2))
      .attr('stroke', (d) => d.isLimitUp || d.isLimitDown ? cv('--chart-limit') : 'none')
      .attr('stroke-width', 2)
      .attr('filter', (d) => (d.change > 3 || d.change < -3) ? 'url(#candle-glow)' : 'none');

    // Limit-up marker — gold diamond
    candles.filter((d) => d.isLimitUp)
      .append('text')
      .attr('x', (d) => x(d.date))
      .attr('y', (d) => y(d.high) - 5)
      .attr('text-anchor', 'middle')
      .attr('font-size', '9px')
      .attr('fill', cv('--chart-limit'))
      .text('◆');

    // Limit-down marker — gold diamond
    candles.filter((d) => d.isLimitDown)
      .append('text')
      .attr('x', (d) => x(d.date))
      .attr('y', (d) => y(d.low) + 12)
      .attr('text-anchor', 'middle')
      .attr('font-size', '9px')
      .attr('fill', cv('--chart-limit'))
      .text('◆');

    // --- Place particles overlaid on K-line ---
    // Group particles by trade_date
    const particlesByDate = new Map<string, Particle[]>();
    for (const p of particles) {
      const arr = particlesByDate.get(p.d) || [];
      arr.push(p);
      particlesByDate.set(p.d, arr);
    }

    const placed: PlacedParticle[] = [];
    // Particle vertical spacing in pixels
    const pSpacing = Math.max(4.5, Math.min(7, height / 80));

    for (const [dateStr, pArr] of particlesByDate) {
      const ohlc = dateToOhlc.get(dateStr);
      if (!ohlc) continue;

      const cx = x(ohlc.date);

      // Sort: relevant first, then by |ret_t1| descending
      pArr.sort((a, b) => {
        const ra = a.r === 'relevant' ? 0 : 1;
        const rb = b.r === 'relevant' ? 0 : 1;
        if (ra !== rb) return ra - rb;
        return Math.abs(b.rt1 || 0) - Math.abs(a.rt1 || 0);
      });

      // Stack particles downward from the close price (only in price area)
      const maxPerDay = 6;
      for (let i = 0; i < Math.min(pArr.length, maxPerDay); i++) {
        const p = pArr[i];
        const radius = getParticleRadius(p.r, p.rt1);
        const candleLowY = y(ohlc.low);
        const py = margin.top + candleLowY + 6 + i * pSpacing;

        // Don't render if beyond price area (before volume zone)
        if (py > margin.top + priceHeight - 4) break;

        placed.push({
          ...p,
          px: margin.left + cx,
          py,
          radius,
          color: getSentimentColor(p.s),
          alpha: getParticleAlpha(p.r),
        });
      }
    }

    placedRef.current = placed;

    // Build quadtree for hit testing
    quadtreeRef.current = d3.quadtree<PlacedParticle>()
      .x((d) => d.px)
      .y((d) => d.py)
      .addAll(placed);

    // --- Setup Canvas ---
    const canvas = canvasRef.current;
    if (canvas) {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = fullWidth * dpr;
      canvas.height = fullHeight * dpr;
      canvas.style.width = `${fullWidth}px`;
      canvas.style.height = `${fullHeight}px`;
      drawParticles();
    }

    // --- Crosshair elements ---
    const crossV = g.append('line')
      .style('stroke', cv('--chart-crosshair'))
      .style('stroke-width', 0.5)
      .style('stroke-dasharray', '4,3')
      .style('display', 'none')
      .style('pointer-events', 'none');

    const crossH = g.append('line')
      .style('stroke', cv('--chart-crosshair'))
      .style('stroke-width', 0.5)
      .style('stroke-dasharray', '4,3')
      .style('display', 'none')
      .style('pointer-events', 'none');

    // Price label on Y axis
    const priceLabel = g.append('g').style('display', 'none');
    priceLabel.append('rect')
      .attr('fill', cv('--chart-label-bg'))
      .attr('rx', 3)
      .attr('width', 46)
      .attr('height', 18);
    priceLabel.append('text')
      .attr('fill', cv('--chart-label-text'))
      .attr('font-size', '12px')
      .attr('text-anchor', 'middle')
      .attr('dy', '13px');

    // Date label on X axis
    const dateLabel = g.append('g').style('display', 'none');
    dateLabel.append('rect')
      .attr('fill', cv('--chart-label-bg'))
      .attr('rx', 3)
      .attr('width', 75)
      .attr('height', 20);
    dateLabel.append('text')
      .attr('fill', cv('--chart-label-text'))
      .attr('font-size', '13px')
      .attr('text-anchor', 'middle')
      .attr('dy', '14px');

    // Bisector for snapping to nearest date
    const bisect = d3.bisector<typeof data[0], Date>((d) => d.date).left;

    function snapToData(px: number) {
      const xDate = x.invert(px);
      const idx = bisect(data, xDate, 1);
      const d0 = data[idx - 1];
      const d1 = data[idx];
      if (!d0) return data[0];
      return d1 && xDate.getTime() - d0.date.getTime() > d1.date.getTime() - xDate.getTime() ? d1 : d0;
    }

    // --- Particle hit testing ---
    function findParticle(mouseX: number, mouseY: number): PlacedParticle | null {
      const qt = quadtreeRef.current;
      if (!qt) return null;
      const searchRadius = 8;
      let closest: PlacedParticle | null = null;
      let closestDist = searchRadius;
      const hlSet = highlightedIdsRef.current;
      const locked = lockedNewsIdRef.current;

      qt.visit((node, x0, y0, x1, y1) => {
        if (!('data' in node)) {
          return x0 > mouseX + searchRadius || x1 < mouseX - searchRadius ||
                 y0 > mouseY + searchRadius || y1 < mouseY - searchRadius;
        }
        let leaf: typeof node & { next?: typeof node } | undefined = node as typeof node & { next?: typeof node };
        while (leaf) {
          const p = leaf.data;
          // Skip particles hidden by category filter
          if (hlSet != null && !hlSet.has(p.id) && p.id !== locked) {
            leaf = leaf.next;
            continue;
          }
          const dx = p.px - mouseX;
          const dy = p.py - mouseY;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < closestDist) {
            closestDist = dist;
            closest = p;
          }
          leaf = leaf.next;
        }
        return false;
      });

      return closest;
    }

    // D3 Brush for range selection
    let brushMoving = false;
    const brush = d3.brushX<unknown>()
      .extent([[0, 0], [width, priceHeight]])
      .on('end', function (event) {
        if (brushMoving) return; // guard against re-entrancy from brush.move
        if (!event.selection) {
          // Click (not drag) — find similar days or toggle lock
          if (event.sourceEvent) {
            const [mx] = d3.pointer(event.sourceEvent, g.node());
            const d = snapToData(mx);
            const [absX, absY] = d3.pointer(event.sourceEvent, container);
            const hit = findParticle(absX, absY);
            if (hit) {
              onArticleSelect?.({ newsId: hit.id, date: hit.d });
            } else {
              // Click on background: unlock any locked article, then show similar days
              onArticleSelect?.(null);
              onDayClick?.(d.dateStr);
            }
          }
          return;
        }
        const [x0, x1] = event.selection as [number, number];
        const d0 = snapToData(x0);
        const d1 = snapToData(x1);
        if (d0.dateStr === d1.dateStr) {
          brushMoving = true;
          d3.select(this).call(brush.move, null);
          brushMoving = false;
          return;
        }
        brushMoving = true;
        d3.select(this).call(brush.move, [x(d0.date), x(d1.date)]);
        brushMoving = false;
        const priceChange = ((d1.close - d0.open) / d0.open) * 100;
        // Position popup near the right edge of the selection, within the chart container
        const popupX = margin.left + x(d1.date) + 8;
        const popupY = margin.top + Math.min(y(d0.close), y(d1.close)) - 20;
        onRangeSelect?.({ startDate: d0.dateStr, endDate: d1.dateStr, priceChange, popupX, popupY });
      });

    const brushG = g.append('g')
      .attr('class', 'brush')
      .call(brush);

    brushG.selectAll('.selection')
      .attr('fill', cv('--chart-brush'))
      .attr('fill-opacity', 0.15)
      .attr('stroke', cv('--chart-brush'))
      .attr('stroke-width', 1);

    // Hover events on the brush overlay
    brushG.select('.overlay')
      .style('cursor', 'crosshair')
      .on('mousemove.hover', function (event) {
        const [mx, my] = d3.pointer(event);
        const d = snapToData(mx);
        const cx = x(d.date);
        const priceAtY = y.invert(my);

        // Vertical crosshair
        crossV.attr('x1', cx).attr('x2', cx).attr('y1', 0).attr('y2', height).style('display', null);
        crossH.attr('x1', 0).attr('x2', width).attr('y1', my).attr('y2', my).style('display', null);

        // Only show crosshair in price area
        if (my > priceHeight) {
          crossH.style('display', 'none');
          priceLabel.style('display', 'none');
        }

        // Price label
        priceLabel.style('display', null)
          .attr('transform', `translate(${-46},${my - 9})`);
        priceLabel.select('text')
          .attr('x', 23)
          .text(`¥${priceAtY.toFixed(2)}`);

        // Date label
        dateLabel.style('display', null)
          .attr('transform', `translate(${cx - 37.5},${height})`);
        dateLabel.select('text')
          .attr('x', 37.5)
          .text(d.dateStr);

        // Emit hover for OHLC
        onHover(d.dateStr, {
          date: d.dateStr,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
          change: d.change,
        });

        // Check particle hover
        const [absX, absY] = d3.pointer(event, container);
        const hit = findParticle(absX, absY);

        if (hit !== hoveredParticleRef.current) {
          hoveredParticleRef.current = hit;
          setHoveredArticleId(hit?.id ?? null);
          drawParticles(hit);

          const tooltip = tooltipRef.current;
          if (tooltip) {
            if (hit) {
              const retStr = hit.rt1 !== null ? `${(hit.rt1 * 100).toFixed(2)}%` : '-';
              const retColor = hit.rt1 !== null ? (hit.rt1 >= 0 ? '#e63946' : '#2d936c') : '#5c5750';
              const currentLang = langRef.current;
              const sentimentLabel = hit.s ? t(`cat.${hit.s}`, currentLang) || hit.s : t('chart.unknown', currentLang);
              tooltip.innerHTML = `
                <div class="pt-title">${hit.t}</div>
                <div class="pt-meta">
                  <span class="pt-sentiment" style="color:${hit.color}">${sentimentLabel}</span>
                  <span class="pt-ret" style="color:${retColor}">T+1: ${retStr}</span>
                </div>
              `;
              tooltip.style.display = 'block';
              const tipW = 280; // max-width of tooltip
              const onRight = hit.px < fullWidth / 2;
              const tipX = onRight ? hit.px + 12 : hit.px - tipW - 12;
              const tipY = hit.py - 40;
              tooltip.style.left = `${Math.max(4, tipX)}px`;
              tooltip.style.top = `${Math.max(4, tipY)}px`;
            } else {
              tooltip.style.display = 'none';
            }
          }
        }
      })
      .on('mouseleave.hover', function () {
        crossV.style('display', 'none');
        crossH.style('display', 'none');
        priceLabel.style('display', 'none');
        dateLabel.style('display', 'none');
        onHover(null);

        if (hoveredParticleRef.current) {
          hoveredParticleRef.current = null;
          drawParticles();
        }
        const tooltip = tooltipRef.current;
        if (tooltip) tooltip.style.display = 'none';
      });
  }

  const periodLabels = lang === 'zh' ? PERIOD_LABELS_ZH : PERIOD_LABELS_EN;

  return (
    <div ref={containerRef} className="chart-container">
      {loading && <div className="chart-loading">{t('chart.loading', lang)}</div>}
      <div className="chart-period-bar">
        {(['1W', '1M', '3M', '1Y', 'ALL'] as Period[]).map((p) => (
          <button
            key={p}
            className={`chart-period-btn${period === p ? ' active' : ''}`}
            onClick={() => setPeriod(p)}
          >
            {periodLabels[p]}
          </button>
        ))}
      </div>
      <svg ref={svgRef}></svg>
      <canvas
        ref={canvasRef}
        className="particle-layer"
      />
      <div ref={tooltipRef} className="particle-tooltip" style={{ display: 'none' }} />
    </div>
  );
}