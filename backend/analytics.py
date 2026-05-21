"""
SecureGate Analytics Module  —  Pandas-based
Provides peak-hour, 30-day trend, GPS compliance, and CSV export analytics.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
from sqlalchemy.orm import Session

from models import ScanLog, PassRequest


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scan_df(db: Session, days: int) -> pd.DataFrame:
    """Load scan_logs from the last *days* days into a DataFrame."""
    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(
            ScanLog.id,
            ScanLog.scan_time,
            ScanLog.pass_type,
            ScanLog.result,
            ScanLog.emergency,
        )
        .filter(ScanLog.scan_time >= since)
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=["id", "scan_time", "pass_type", "result", "emergency"])
    df = pd.DataFrame(rows, columns=["id", "scan_time", "pass_type", "result", "emergency"])
    df["scan_time"] = pd.to_datetime(df["scan_time"])
    return df


def _pass_df(db: Session, days: int) -> pd.DataFrame:
    """Load passes from the last *days* days into a DataFrame."""
    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(
            PassRequest.id,
            PassRequest.request_time,
            PassRequest.pass_type,
            PassRequest.status,
            PassRequest.location_verified,
        )
        .filter(PassRequest.request_time >= since)
        .all()
    )
    if not rows:
        return pd.DataFrame(
            columns=["id", "request_time", "pass_type", "status", "location_verified"]
        )
    df = pd.DataFrame(
        rows, columns=["id", "request_time", "pass_type", "status", "location_verified"]
    )
    df["request_time"] = pd.to_datetime(df["request_time"])
    return df


# ---------------------------------------------------------------------------
# Public analytics functions
# ---------------------------------------------------------------------------

def peak_hours(db: Session, days: int = 30) -> Dict:
    """
    Peak access hours analysis.
    Returns hourly entry/exit counts and the busiest hour with scan volume.
    """
    df = _scan_df(db, days)
    success_df = df[df["result"] == "success"].copy()

    labels = [f"{h:02d}:00" for h in range(24)]
    entry_counts = [0] * 24
    exit_counts = [0] * 24

    if not success_df.empty:
        success_df["hour"] = success_df["scan_time"].dt.hour
        for h in range(24):
            hour_df = success_df[success_df["hour"] == h]
            entry_counts[h] = int((hour_df["pass_type"] == "entry").sum())
            exit_counts[h] = int((hour_df["pass_type"] == "exit").sum())

    totals = [entry_counts[h] + exit_counts[h] for h in range(24)]
    peak_hour_idx = totals.index(max(totals)) if any(totals) else 8
    peak_hour_label = labels[peak_hour_idx]
    peak_volume = totals[peak_hour_idx]

    return {
        "labels": labels,
        "entries": entry_counts,
        "exits": exit_counts,
        "totals": totals,
        "peak_hour": peak_hour_label,
        "peak_volume": peak_volume,
        "period_days": days,
    }


def daily_trend(db: Session, days: int = 30) -> Dict:
    """
    30-day daily entry/exit trend with moving average.
    """
    df = _scan_df(db, days)
    success_df = df[df["result"] == "success"].copy()

    date_range = pd.date_range(end=pd.Timestamp.now().normalize(), periods=days, freq="D")
    labels: List[str] = [d.strftime("%b %d") for d in date_range]
    entry_counts = [0] * days
    exit_counts = [0] * days

    if not success_df.empty:
        success_df["date"] = success_df["scan_time"].dt.normalize()
        for i, d in enumerate(date_range):
            day_df = success_df[success_df["date"] == d]
            entry_counts[i] = int((day_df["pass_type"] == "entry").sum())
            exit_counts[i] = int((day_df["pass_type"] == "exit").sum())

    # 7-day simple moving average for trend line
    totals = [entry_counts[i] + exit_counts[i] for i in range(days)]
    sma7 = []
    for i in range(days):
        window = totals[max(0, i - 6): i + 1]
        sma7.append(round(sum(window) / len(window), 1))

    return {
        "labels": labels,
        "entries": entry_counts,
        "exits": exit_counts,
        "totals": totals,
        "sma7": sma7,
        "period_days": days,
    }


def compliance_summary(db: Session, days: int = 30) -> Dict:
    """
    GPS compliance rate for instant passes and overall entry/exit ratio.
    """
    df = _scan_df(db, days)
    passes_df = _pass_df(db, days)

    entries = int((df[(df["result"] == "success") & (df["pass_type"] == "entry")]).shape[0])
    exits = int((df[(df["result"] == "success") & (df["pass_type"] == "exit")]).shape[0])
    total_success = entries + exits
    total_scans = int(df.shape[0])
    success_rate = round(total_success / total_scans * 100, 1) if total_scans else 0.0

    total_passes = int(passes_df.shape[0])
    location_verified = int(passes_df["location_verified"].sum()) if not passes_df.empty else 0
    gps_compliance_rate = (
        round(location_verified / total_passes * 100, 1) if total_passes else 0.0
    )

    entry_exit_ratio = round(entries / exits, 2) if exits > 0 else None

    return {
        "entries": entries,
        "exits": exits,
        "entry_exit_ratio": entry_exit_ratio,
        "success_rate": success_rate,
        "gps_compliance_rate": gps_compliance_rate,
        "location_verified_passes": location_verified,
        "total_passes": total_passes,
        "period_days": days,
    }


def export_csv(db: Session, days: int = 30) -> str:
    """
    Export scan log data as CSV string.
    Columns: timestamp, date, hour, pass_type, result, emergency
    """
    df = _scan_df(db, days)
    if df.empty:
        return "timestamp,date,hour,pass_type,result,emergency\n"

    df["date"] = df["scan_time"].dt.strftime("%Y-%m-%d")
    df["hour"] = df["scan_time"].dt.hour
    df["timestamp"] = df["scan_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["emergency"] = df["emergency"].fillna(False).astype(bool)

    export_df = df[["timestamp", "date", "hour", "pass_type", "result", "emergency"]]
    return export_df.to_csv(index=False)
