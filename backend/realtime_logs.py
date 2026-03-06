"""
Real-Time Entry/Exit Logging System
Provides analytics, WebSocket support, and real-time monitoring
"""

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from models import ScanLog, User, PassRequest
import json

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ Admin connected to real-time logs. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"❌ Admin disconnected. Remaining connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected admins"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")

# Global connection manager
manager = ConnectionManager()


def _start_of_day(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)

def get_recent_logs(db: Session, limit: int = 100, offset: int = 0) -> List[Dict]:
    """Get recent scan logs with student information"""

    logs = db.query(ScanLog, User).join(
        User, ScanLog.student_id == User.id
    ).order_by(ScanLog.scan_time.desc()).limit(limit).offset(offset).all()

    result = []
    for log, student in logs:
        # Check if emergency flag exists (column might not exist in older databases)
        is_emergency = False
        try:
            is_emergency = getattr(log, 'emergency', False) or False
        except:
            is_emergency = False
        
        result.append({
            "id": log.id,
            "student_id": student.student_id if student else "Unknown",
            "student_name": student.name if student else "Unknown",
            "timestamp": log.scan_time.isoformat(),
            "time": log.scan_time.strftime("%I:%M %p"),
            "date": log.scan_time.strftime("%B %d, %Y"),
            "scan_type": log.pass_type,  # 'entry' or 'exit'
            "result": log.result,  # 'success', 'expired', etc.
            "gate": "Emergency Exit" if is_emergency else "Main Gate",
            "details": log.details,
            "emergency": is_emergency
        })
    
    return result

def get_log_statistics(db: Session, days: int = 7) -> Dict:
    """Get statistics for the last N days"""

    now = datetime.now()
    period_start = _start_of_day(now - timedelta(days=max(days - 1, 0)))

    # Total scans
    total_scans = db.query(ScanLog).filter(
        ScanLog.scan_time >= period_start
    ).count()

    # Successful scans
    successful_scans = db.query(ScanLog).filter(
        and_(
            ScanLog.scan_time >= period_start,
            ScanLog.result == "success"
        )
    ).count()

    # Successful entry vs exit counts for the full period
    entries_period = db.query(ScanLog).filter(
        and_(
            ScanLog.scan_time >= period_start,
            ScanLog.pass_type == "entry",
            ScanLog.result == "success",
        )
    ).count()

    exits_period = db.query(ScanLog).filter(
        and_(
            ScanLog.scan_time >= period_start,
            ScanLog.pass_type == "exit",
            ScanLog.result == "success",
        )
    ).count()

    # Current students in campus (entries - exits today)
    today_start = _start_of_day(now)

    today_entries = db.query(ScanLog).filter(
        and_(
            ScanLog.scan_time >= today_start,
            ScanLog.pass_type == "entry",
            ScanLog.result == "success"
        )
    ).count()
    
    today_exits = db.query(ScanLog).filter(
        and_(
            ScanLog.scan_time >= today_start,
            ScanLog.pass_type == "exit",
            ScanLog.result == "success"
        )
    ).count()
    
    students_in_campus = max(0, today_entries - today_exits)
    
    return {
        "total_scans": total_scans,
        "successful_scans": successful_scans,
        "failed_scans": total_scans - successful_scans,
        "entries": entries_period,
        "exits": exits_period,
        "entries_today": today_entries,
        "exits_today": today_exits,
        "students_in_campus": students_in_campus,
        "success_rate": round((successful_scans / total_scans * 100) if total_scans > 0 else 0, 1),
        "period_days": days,
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": today_start.strftime("%Y-%m-%d"),
    }

def get_hourly_stats(db: Session, date: Optional[datetime] = None) -> Dict:
    """Get hourly entry/exit statistics for a specific day"""
    
    if date is None:
        date = datetime.now()
    
    start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    
    # Get all scans for the day
    scans = db.query(ScanLog).filter(
        and_(
            ScanLog.scan_time >= start_of_day,
            ScanLog.scan_time < end_of_day,
            ScanLog.result == "success"
        )
    ).all()
    
    # Group by hour
    hourly_data = {hour: {"entries": 0, "exits": 0} for hour in range(24)}
    
    for scan in scans:
        hour = scan.scan_time.hour
        if scan.pass_type == "entry":
            hourly_data[hour]["entries"] += 1
        else:
            hourly_data[hour]["exits"] += 1
    
    # Format for Chart.js
    labels = [f"{h:02d}:00" for h in range(24)]
    entry_data = [hourly_data[h]["entries"] for h in range(24)]
    exit_data = [hourly_data[h]["exits"] for h in range(24)]
    
    return {
        "labels": labels,
        "entries": entry_data,
        "exits": exit_data,
        "date": date.strftime("%Y-%m-%d")
    }

def get_daily_stats(db: Session, days: int = 7) -> Dict:
    """Get daily statistics for the last N days"""

    today_start = _start_of_day(datetime.now())
    start_date = today_start - timedelta(days=max(days - 1, 0))
    end_date = today_start + timedelta(days=1)

    daily_data = {}

    # Initialize all days
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        daily_data[date_str] = {"entries": 0, "exits": 0}

    # Get scans
    scans = db.query(ScanLog).filter(
        and_(
            ScanLog.scan_time >= start_date,
            ScanLog.scan_time < end_date,
            ScanLog.result == "success"
        )
    ).all()

    for scan in scans:
        date_str = scan.scan_time.strftime("%Y-%m-%d")
        if date_str in daily_data:
            if scan.pass_type == "entry":
                daily_data[date_str]["entries"] += 1
            else:
                daily_data[date_str]["exits"] += 1
    
    # Format for Chart.js
    sorted_dates = sorted(daily_data.keys())
    labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in sorted_dates]
    entry_data = [daily_data[d]["entries"] for d in sorted_dates]
    exit_data = [daily_data[d]["exits"] for d in sorted_dates]
    
    return {
        "labels": labels,
        "entries": entry_data,
        "exits": exit_data,
        "date_range": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": today_start.strftime("%Y-%m-%d"),
        }
    }

def get_top_active_students(db: Session, days: int = 7, limit: int = 10) -> List[Dict]:
    """Get most active students (by scan count)"""
    
    start_date = datetime.now() - timedelta(days=days)
    
    # Query to count scans per student
    student_counts = db.query(
        User.student_id,
        User.name,
        func.count(ScanLog.id).label('scan_count')
    ).join(
        ScanLog, ScanLog.student_id == User.id
    ).filter(
        ScanLog.scan_time >= start_date
    ).group_by(
        User.id, User.student_id, User.name
    ).order_by(
        func.count(ScanLog.id).desc()
    ).limit(limit).all()
    
    return [
        {
            "student_id": sc.student_id,
            "name": sc.name,
            "scan_count": sc.scan_count
        }
        for sc in student_counts
    ]

async def broadcast_new_scan(scan_data: Dict):
    """Broadcast new scan to all connected admins"""
    await manager.broadcast({
        "type": "new_scan",
        "data": scan_data
    })

def search_logs(db: Session, 
                student_id: Optional[str] = None,
                date_from: Optional[datetime] = None,
                date_to: Optional[datetime] = None,
                scan_type: Optional[str] = None,
                result: Optional[str] = None,
                limit: int = 100) -> List[Dict]:
    """Search logs with filters"""
    
    query = db.query(ScanLog).join(User, ScanLog.student_id == User.id)

    if student_id:
        search_term = f"%{student_id}%"
        query = query.filter(
            or_(
                User.student_id.ilike(search_term),
                User.name.ilike(search_term),
            )
        )

    if date_from:
        query = query.filter(ScanLog.scan_time >= date_from)

    if date_to:
        query = query.filter(ScanLog.scan_time <= date_to)

    if scan_type:
        query = query.filter(ScanLog.pass_type == scan_type)

    if result:
        query = query.filter(ScanLog.result == result)

    logs = query.order_by(ScanLog.scan_time.desc()).limit(limit).all()

    result = []
    for log in logs:
        student = db.query(User).filter(User.id == log.student_id).first()
        is_emergency = False
        try:
            is_emergency = getattr(log, 'emergency', False) or False
        except:
            is_emergency = False

        result.append({
            "id": log.id,
            "student_id": student.student_id if student else "Unknown",
            "student_name": student.name if student else "Unknown",
            "timestamp": log.scan_time.isoformat(),
            "time": log.scan_time.strftime("%I:%M %p"),
            "date": log.scan_time.strftime("%B %d, %Y"),
            "scan_type": log.pass_type,
            "result": log.result,
            "gate": "Emergency Exit" if is_emergency else "Main Gate",
            "details": log.details,
            "emergency": is_emergency,
        })

    return result
