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
    'buy':   '#00d084',
    'sell':  '#ff4757',
    'cci':   '#ffd93d',
    'mfi':   '#a29bfe',
    'cmo':   '#74b9ff',
    'entry': '#ffeb3b',
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


def generate_chart_cmcwinner(df_raw, pair, action, entry, tp1, tp2, sl, cci_val, mfi_val, cmo_val):
    """
    Generate CMCWinner chart with 4 panels:
    1. Candlestick + Entry/TP/SL lines
    2. Volume
    3. CCI (with -100/+100 zones)
    4. MFI + CMO overlay
    """
    try:
        df = df_raw.tail(80).copy()
        df.index = pd.to_datetime(df['t'], unit='ms')
        x = range(len(df))

        fig = plt.figure(figsize=(12, 11), facecolor=COLORS['bg'])
        gs = fig.add_gridspec(4, 1, height_ratios=[3, 0.8, 1.2, 1.2], hspace=0.08)

        ax1 = fig.add_subplot(gs[0])  # Candles
        ax2 = fig.add_subplot(gs[1])  # Volume
        ax3 = fig.add_subplot(gs[2])  # CCI
        ax4 = fig.add_subplot(gs[3])  # MFI + CMO

        for ax in [ax1, ax2, ax3, ax4]:
            ax.set_facecolor(COLORS['bg'])

        # ============ Panel 1: Candlestick ============
        _plot_candles(ax1, df)

        # Signal levels
        ax1.axhline(y=entry, color=COLORS['entry'], linestyle='-', linewidth=2, alpha=0.9, label=f'Entry ${entry:,.4f}')
        ax1.axhline(y=tp1, color=COLORS['buy'], linestyle='--', linewidth=1.5, alpha=0.8, label=f'TP1 ${tp1:,.4f} (+3%)')
        ax1.axhline(y=tp2, color=COLORS['buy'], linestyle='--', linewidth=1.5, alpha=0.6, label=f'TP2 ${tp2:,.4f} (+5%)')
        ax1.axhline(y=sl, color=COLORS['sell'], linestyle='--', linewidth=1.5, alpha=0.8, label=f'SL ${sl:,.4f} (-5%)')

        if action == 'LONG':
            ax1.fill_between(x, sl, entry, alpha=0.06, color='red')
            ax1.fill_between(x, entry, tp2, alpha=0.06, color='green')
        else:
            ax1.fill_between(x, entry, sl, alpha=0.06, color='red')
            ax1.fill_between(x, tp2, entry, alpha=0.06, color='green')

        # Entry arrow
        arrow_y = entry
        ax1.annotate(
            '▶ ENTRY', xy=(len(df)-2, arrow_y),
            fontsize=10, fontweight='bold',
            color=COLORS['buy'] if action == 'LONG' else COLORS['sell'],
            ha='right', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=COLORS['bg'], edgecolor=COLORS['entry'], alpha=0.9)
        )

        # ============ Panel 2: Volume ============
        vol_colors = [COLORS['up'] if df['c'].iloc[i] >= df['o'].iloc[i] else COLORS['down'] for i in range(len(df))]
        ax2.bar(x, df['v'].values, color=vol_colors, alpha=0.7)
        ax2.set_ylabel('Vol', color=COLORS['text'], fontsize=8)

        # ============ Panel 3: CCI ============
        if 'cci' in df.columns:
            cci_vals = df['cci'].values
            ax3.plot(x, cci_vals, color=COLORS['cci'], linewidth=1.5, label='CCI(20)')
            ax3.axhline(y=100, color=COLORS['sell'], linestyle='--', alpha=0.5, linewidth=0.8)
            ax3.axhline(y=-100, color=COLORS['buy'], linestyle='--', alpha=0.5, linewidth=0.8)
            ax3.axhline(y=0, color=COLORS['text'], linestyle='-', alpha=0.2, linewidth=0.5)

            # Shade overbought/oversold zones
            ax3.fill_between(x, 100, np.maximum(cci_vals, 100), alpha=0.15, color='red')
            ax3.fill_between(x, -100, np.minimum(cci_vals, -100), alpha=0.15, color='green')

            ax3.set_ylabel('CCI', color=COLORS['cci'], fontsize=9, fontweight='bold')
            ax3.legend(loc='upper left', facecolor=COLORS['bg'], edgecolor=COLORS['grid'], labelcolor=COLORS['text'], fontsize=7)

        # ============ Panel 4: MFI + CMO ============
        if 'mfi' in df.columns and 'cmo' in df.columns:
            ax4.plot(x, df['mfi'].values, color=COLORS['mfi'], linewidth=1.5, label='MFI(14)')
            ax4.axhline(y=80, color=COLORS['sell'], linestyle='--', alpha=0.4, linewidth=0.8)
            ax4.axhline(y=20, color=COLORS['buy'], linestyle='--', alpha=0.4, linewidth=0.8)
            ax4.set_ylim(-5, 105)
            ax4.set_ylabel('MFI', color=COLORS['mfi'], fontsize=9, fontweight='bold')

            # CMO on twin axis
            ax4_twin = ax4.twinx()
            ax4_twin.plot(x, df['cmo'].values, color=COLORS['cmo'], linewidth=1.5, label='CMO(14)', alpha=0.85)
            ax4_twin.axhline(y=50, color=COLORS['sell'], linestyle=':', alpha=0.3, linewidth=0.8)
            ax4_twin.axhline(y=-50, color=COLORS['buy'], linestyle=':', alpha=0.3, linewidth=0.8)
            ax4_twin.set_ylim(-105, 105)
            ax4_twin.set_ylabel('CMO', color=COLORS['cmo'], fontsize=9, fontweight='bold')
            ax4_twin.tick_params(colors=COLORS['text'])
            ax4_twin.legend(loc='upper right', facecolor=COLORS['bg'], edgecolor=COLORS['grid'], labelcolor=COLORS['text'], fontsize=7)

            ax4.legend(loc='upper left', facecolor=COLORS['bg'], edgecolor=COLORS['grid'], labelcolor=COLORS['text'], fontsize=7)

        # ============ Title & Info Box ============
        emoji = '🟢 LONG' if action == 'LONG' else '🔴 SHORT'
        ax1.set_title(f'{pair} — 15m | {emoji} | CMCWinner Strategy', color=COLORS['text'], fontsize=13, fontweight='bold', pad=10)
        ax1.legend(loc='upper left', facecolor=COLORS['bg'], edgecolor=COLORS['grid'], labelcolor=COLORS['text'], fontsize=8)

        # Info box with indicator values
        info_text = f'CCI: {cci_val} | MFI: {mfi_val} | CMO: {cmo_val}'
        ax1.text(
            0.98, 0.02, info_text,
            transform=ax1.transAxes, fontsize=9,
            color=COLORS['text'], ha='right', va='bottom',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=COLORS['bg'], edgecolor=COLORS['entry'], alpha=0.9)
        )

        # Styling
        for ax in [ax1, ax2, ax3, ax4]:
            ax.tick_params(colors=COLORS['text'])
            ax.grid(True, alpha=0.15, color=COLORS['grid'])

        plt.setp(ax1.get_xticklabels(), visible=False)
        plt.setp(ax2.get_xticklabels(), visible=False)
        plt.setp(ax3.get_xticklabels(), visible=False)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=130, facecolor=COLORS['bg'], edgecolor='none', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    except Exception as e:
        print(f"Chart error: {e}")
        return None


# Keep backward compatibility
def generate_chart_v1(df_raw, pair, action, entry, tp1, tp2, sl):
    """Legacy chart (not used by CMCWinner but kept for compat)"""
    return generate_chart_cmcwinner(df_raw, pair, action, entry, tp1, tp2, sl, 0, 0, 0)
