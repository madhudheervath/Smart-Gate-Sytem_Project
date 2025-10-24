from sqlalchemy.orm import Session
from models import User, PassRequest, ScanLog
from datetime import datetime, timezone, timedelta
import asyncio

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    """Get current time in IST timezone"""
    return datetime.now(IST)

def log_scan(db: Session, pass_id: int, student_id: int, scanner_id: int, result: str, details: str="", pass_type: str="entry"):
    scan_log = ScanLog(pass_id=pass_id, student_id=student_id, scanner_id=scanner_id, result=result, details=details, pass_type=pass_type)
    db.add(scan_log)
    db.commit()
    db.refresh(scan_log)
    
    # Broadcast to real-time monitoring (if enabled)
    try:
        import realtime_logs
        student = db.query(User).filter(User.id == student_id).first()
        
        scan_data = {
            "id": scan_log.id,
            "student_id": student.student_id if student else "Unknown",
            "student_name": student.name if student else "Unknown",
            "timestamp": scan_log.scan_time.isoformat(),
            "time": scan_log.scan_time.strftime("%I:%M %p"),
            "date": scan_log.scan_time.strftime("%B %d, %Y"),
            "scan_type": scan_log.pass_type,
            "result": scan_log.result,
            "gate": "Main Gate",
            "details": scan_log.details
        }
        
        # Create a new event loop if needed and broadcast
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(realtime_logs.broadcast_new_scan(scan_data))
            else:
                loop.run_until_complete(realtime_logs.broadcast_new_scan(scan_data))
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(realtime_logs.broadcast_new_scan(scan_data))
            loop.close()
    except Exception as e:
        print(f"Failed to broadcast scan: {e}")
    
    return scan_log

def mark_used(db: Session, pass_obj: PassRequest, scanner_id: int):
    pass_obj.status = "used"
    pass_obj.used_time = now_ist()
    pass_obj.used_by = scanner_id
    db.commit()
    db.refresh(pass_obj)
    return pass_obj

