import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io


COLORS = {
    'bg':    '#0d1117',
    'grid':  '#21262d',
    'up':    '#00d084',
    'down':  '#ff4757',
    'text':  '#c9d1d9',
    'ema25': '#ff6b6b',
    'ema75': '#4ecdc4',
    'ema140':'#45b7d1',
    'buy':   '#00d084',
    'sell':  '#ff4757',
}


def _plot_candles(ax, df):
    for i, (_, row) in enumerate(df.iterrows()):
        color = COLORS['up'] if row['c'] >= row['o'] else COLORS['down']
        height = abs(row['c'] - row['o'])
        bottom = min(row['c'], row['o'])
        ax.bar(i, max(height, row['c'] * 0.0001), 0.6, bottom=bottom, color=color, alpha=0.85)
        ax.plot([i, i], [row['l'], row['h']], color=color, linewidth=0.8)

    step = max(1, len(df) // 8)
    ticks = list(range(0, len(df), step))
    labels = [df.index[i].strftime('%m/%d %H:%M') for i in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=7, color=COLORS['text'])


def generate_chart_v1(df_raw, pair, action, entry, tp1, tp2, sl):
    """
    Generate chart untuk bot v1.
    df_raw: DataFrame dengan kolom t, o, h, l, c, v, ema25, ema75, ema140, rsi, stoch_k
    """
    try:
        df = df_raw.tail(80).copy()
        df.index = pd.to_datetime(df['t'], unit='ms')

        fig = plt.figure(figsize=(12, 9), facecolor=COLORS['bg'])
        gs  = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)

        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1])
        ax3 = fig.add_subplot(gs[2])

        for ax in [ax1, ax2, ax3]:
            ax.set_facecolor(COLORS['bg'])

        # Candles
        _plot_candles(ax1, df)
        x = range(len(df))

        # EMAs
        ax1.plot(x, df['ema25'].values,  color=COLORS['ema25'],  linewidth=1.5, label='EMA25')
        ax1.plot(x, df['ema75'].values,  color=COLORS['ema75'],  linewidth=1.5, label='EMA75')
        ax1.plot(x, df['ema140'].values, color=COLORS['ema140'], linewidth=2.0, label='EMA140')

        # Signal levels
        entry_color = COLORS['buy'] if action == 'LONG' else COLORS['sell']
        ax1.axhline(y=entry, color='#ffeb3b',      linestyle='-',  linewidth=2, alpha=0.9, label=f'Entry ${entry:,.4f}')
        ax1.axhline(y=tp1,   color=COLORS['buy'],  linestyle='--', linewidth=1.5, alpha=0.8, label=f'TP1 ${tp1:,.4f}')
        ax1.axhline(y=tp2,   color=COLORS['buy'],  linestyle='--', linewidth=1.5, alpha=0.8, label=f'TP2 ${tp2:,.4f}')
        ax1.axhline(y=sl,    color=COLORS['sell'], linestyle='--', linewidth=1.5, alpha=0.8, label=f'SL ${sl:,.4f}')

        if action == 'LONG':
            ax1.fill_between(x, sl,    entry, alpha=0.06, color='red')
            ax1.fill_between(x, entry, tp2,   alpha=0.06, color='green')
        else:
            ax1.fill_between(x, entry, sl,    alpha=0.06, color='red')
            ax1.fill_between(x, tp2,   entry, alpha=0.06, color='green')

        # Volume
        vol_colors = [COLORS['up'] if df['c'].iloc[i] >= df['o'].iloc[i] else COLORS['down'] for i in range(len(df))]
        ax2.bar(x, df['v'].values, color=vol_colors, alpha=0.7)
        ax2.set_ylabel('Volume', color=COLORS['text'], fontsize=9)

        # RSI
        ax3.plot(x, df['rsi'].values, color='#ffd93d', linewidth=1.5, label='RSI')
        ax3.axhline(y=70, color='red',   linestyle='--', alpha=0.5)
        ax3.axhline(y=30, color='green', linestyle='--', alpha=0.5)
        ax3.fill_between(x, 30, 70, alpha=0.05, color='gray')
        ax3.set_ylim(0, 100)
        ax3.set_ylabel('RSI', color=COLORS['text'], fontsize=9)

        # Stoch overlay on RSI panel
        if 'stoch_k' in df.columns:
            ax3_twin = ax3.twinx()
            ax3_twin.plot(x, df['stoch_k'].values, color='#a29bfe', linewidth=1, alpha=0.7, label='Stoch K')
            ax3_twin.set_ylim(0, 100)
            ax3_twin.tick_params(colors=COLORS['text'])

        # Title & styling
        emoji = '🟢 LONG' if action == 'LONG' else '🔴 SHORT'
        ax1.set_title(f'{pair} — 30m | {emoji} | Bot v1', color=COLORS['text'], fontsize=13, fontweight='bold', pad=10)
        ax1.legend(loc='upper left', facecolor=COLORS['bg'], edgecolor=COLORS['grid'], labelcolor=COLORS['text'], fontsize=8)

        for ax in [ax1, ax2, ax3]:
            ax.tick_params(colors=COLORS['text'])
            ax.grid(True, alpha=0.15, color=COLORS['grid'])

        plt.setp(ax1.get_xticklabels(), visible=False)
        plt.setp(ax2.get_xticklabels(), visible=False)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=130, facecolor=COLORS['bg'], edgecolor='none', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    except Exception as e:
        print(f"Chart error: {e}")
        return None
