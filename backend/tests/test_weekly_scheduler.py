from datetime import date

from backend.app.scheduler.scheduler import MaintenanceScheduler


def test_weekly_scheduler():
    scheduler = MaintenanceScheduler()

    result = scheduler.schedule(
        target_date=date(2026, 9, 7),
        schedule_type="weekly",
    )

    for item in result.scheduled_items:
        if item.assigned_slot:
            print(
                item.request_id,
                item.assigned_slot.service_date,
                item.assigned_slot.start_time,
                item.assigned_slot.end_time,
            )