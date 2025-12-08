"""
Dynamic Time Slot Availability Service.

This service calculates available time slots on-the-fly based on:
- Shop schedule (hours, slot intervals)
- Service duration
- Staff availability (booking conflicts)
"""
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import List, Optional
from uuid import UUID

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.bookings.models import Booking
from apps.schedules.models import ShopSchedule
from apps.services.models import Service
from apps.staff.models import StaffMember, StaffService
from apps.core.utils.constants import (
    BOOKING_STATUS_PENDING,
    BOOKING_STATUS_CONFIRMED,
)


# Map day names to Python weekday integers
DAYS_MAP = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}

# Reverse mapping
WEEKDAY_TO_DAY = {v: k for k, v in DAYS_MAP.items()}


@dataclass
class BusyInterval:
    """Represents a time interval when a staff member is busy."""
    staff_id: UUID
    start: datetime
    end: datetime


@dataclass
class AvailableSlot:
    """Represents an available time slot with eligible staff."""
    start_time: datetime
    end_time: datetime
    available_staff_ids: List[UUID] = field(default_factory=list)
    
    @property
    def available_staff_count(self) -> int:
        return len(self.available_staff_ids)


class AvailabilityService:
    """
    Dynamic time slot availability calculator.
    
    Computes available slots on-the-fly based on:
    - Shop schedule (hours, slot intervals)
    - Service duration
    - Staff availability (booking conflicts)
    
    Example usage:
        service = AvailabilityService(
            service_id=uuid,
            target_date=date(2024, 12, 10),
            buffer_minutes=15
        )
        slots = service.get_available_slots()
    """
    
    def __init__(
        self,
        service_id: UUID,
        target_date: date,
        buffer_minutes: Optional[int] = None,
        slot_interval_override: Optional[int] = None
    ):
        """
        Initialize the availability service.
        
        Args:
            service_id: UUID of the service to check availability for
            target_date: The date to check availability
            buffer_minutes: Override for minimum minutes from now (uses service.buffer_minutes if None)
            slot_interval_override: Override for slot interval (uses service.duration_minutes if None)
        """
        self.service_id = service_id
        self.target_date = target_date
        self._buffer_minutes_override = buffer_minutes
        self.slot_interval_override = slot_interval_override
        
        # Fetched data (lazy loaded)
        self._service: Optional[Service] = None
        self._shop_schedule: Optional[ShopSchedule] = None
        self._eligible_staff: Optional[QuerySet[StaffMember]] = None
        self._busy_intervals: Optional[List[BusyInterval]] = None
    
    @property
    def service(self) -> Service:
        """Fetch and cache the service instance."""
        if self._service is None:
            self._service = Service.objects.select_related('shop').get(
                id=self.service_id,
                is_active=True
            )
        return self._service
    
    @property
    def shop(self):
        """Get the shop from the service."""
        return self.service.shop
    
    @property
    def service_duration(self) -> int:
        """Service duration in minutes."""
        return self.service.duration_minutes
    
    @property
    def buffer_minutes(self) -> int:
        """
        Get buffer minutes.
        
        Priority:
        1. Override passed in request
        2. Service's buffer_minutes if set (> 0)
        3. Default: 0 (no buffer)
        """
        if self._buffer_minutes_override is not None:
            return self._buffer_minutes_override
        # Use service-specific buffer_minutes if set, otherwise 0
        service_buffer = getattr(self.service, 'buffer_minutes', 0) or 0
        return service_buffer
    
    def get_available_slots(self) -> List[AvailableSlot]:
        """
        Main entry point - calculate and return available time slots.
        
        Returns:
            List of AvailableSlot objects, each containing:
            - start_time: Slot start datetime
            - end_time: Slot end datetime
            - available_staff_ids: List of staff UUIDs who can take this slot
            - available_staff_count: Number of available staff
        """
        # Step 1: Get shop schedule for target date
        schedule = self._get_shop_schedule()
        if schedule is None or not schedule.is_active:
            return []  # Shop is closed
        
        # Step 2: Get eligible staff for this service
        eligible_staff = self._get_eligible_staff()
        if not eligible_staff.exists():
            return []  # No staff can perform this service
        
        # Step 3: Get busy intervals (booking conflicts)
        busy_intervals = self._get_busy_intervals(eligible_staff)
        
        # Step 4: Generate time grid and check availability
        available_slots = self._calculate_availability(
            schedule=schedule,
            eligible_staff=eligible_staff,
            busy_intervals=busy_intervals
        )
        
        return available_slots
    
    def _get_shop_schedule(self) -> Optional[ShopSchedule]:
        """
        Fetch the ShopSchedule for the target date's day of week.
        
        Returns:
            ShopSchedule if found and active, None otherwise
        """
        if self._shop_schedule is not None:
            return self._shop_schedule
        
        # Get day of week name from target date
        day_of_week = WEEKDAY_TO_DAY.get(self.target_date.weekday())
        
        try:
            self._shop_schedule = ShopSchedule.objects.get(
                shop=self.shop,
                day_of_week=day_of_week,
                is_active=True
            )
        except ShopSchedule.DoesNotExist:
            self._shop_schedule = None
        
        return self._shop_schedule
    
    def _get_eligible_staff(self) -> QuerySet[StaffMember]:
        """
        Find all active staff members who can perform this service.
        
        Staff eligibility logic:
        - If service HAS assigned staff → Only those staff members
        - If service has NO assigned staff → EMPTY (no staff available)
        
        Returns:
            QuerySet of eligible StaffMember objects
        """
        if self._eligible_staff is not None:
            return self._eligible_staff
        
        # Check if this service has any staff assigned
        from apps.staff.models import StaffService
        has_assigned_staff = StaffService.objects.filter(
            service_id=self.service_id
        ).exists()
        
        if has_assigned_staff:
            # Service has assigned staff - only show those staff
            self._eligible_staff = StaffMember.objects.filter(
                shop=self.shop,
                is_active=True,
                services__id=self.service_id
            ).distinct()
        else:
            # Service has no assigned staff - return empty queryset
            # This enforces that all services must have staff explicitly assigned
            self._eligible_staff = StaffMember.objects.none()
        
        return self._eligible_staff
    
    def _get_busy_intervals(
        self, 
        eligible_staff: QuerySet[StaffMember]
    ) -> List[BusyInterval]:
        """
        Query bookings AND manually created TimeSlots to find staff busy intervals.
        
        This method considers:
        1. Existing Bookings (pending/confirmed) for the target date
        2. Manually created TimeSlots marked as 'booked' or 'blocked'
        
        Args:
            eligible_staff: QuerySet of staff to check conflicts for
            
        Returns:
            List of BusyInterval objects representing when staff are busy
        """
        if self._busy_intervals is not None:
            return self._busy_intervals
        
        self._busy_intervals = []
        
        # Get all bookings for eligible staff on target date
        # Only consider pending or confirmed bookings
        active_statuses = [BOOKING_STATUS_PENDING, BOOKING_STATUS_CONFIRMED]
        
        bookings = Booking.objects.filter(
            staff_member__in=eligible_staff,
            booking_datetime__date=self.target_date,
            status__in=active_statuses
        ).select_related('service', 'time_slot')
        
        # Convert bookings to busy intervals
        for booking in bookings:
            # Calculate booking end time from service duration
            booking_start = booking.booking_datetime
            booking_duration = booking.service.duration_minutes
            booking_end = booking_start + timedelta(minutes=booking_duration)
            
            self._busy_intervals.append(BusyInterval(
                staff_id=booking.staff_member_id,
                start=booking_start,
                end=booking_end
            ))
        
        # Also check for manually created TimeSlots that are booked/blocked
        # These represent special reservations or blocked times
        from apps.schedules.models import TimeSlot
        
        blocked_slots = TimeSlot.objects.filter(
            schedule__shop=self.shop,
            start_datetime__date=self.target_date,
            status__in=['booked', 'blocked']
        ).select_related('staff_member')
        
        for slot in blocked_slots:
            if slot.staff_member and slot.staff_member_id in [s.id for s in eligible_staff]:
                # This slot is specifically blocked for this staff member
                self._busy_intervals.append(BusyInterval(
                    staff_id=slot.staff_member_id,
                    start=slot.start_datetime,
                    end=slot.end_datetime
                ))
            elif not slot.staff_member:
                # Slot is blocked for ALL staff (shop-wide block)
                for staff in eligible_staff:
                    self._busy_intervals.append(BusyInterval(
                        staff_id=staff.id,
                        start=slot.start_datetime,
                        end=slot.end_datetime
                    ))
        
        return self._busy_intervals
    
    def _calculate_availability(
        self,
        schedule: ShopSchedule,
        eligible_staff: QuerySet[StaffMember],
        busy_intervals: List[BusyInterval]
    ) -> List[AvailableSlot]:
        """
        Core availability calculation loop.
        
        For each potential slot:
        1. Check if slot fits within shop hours
        2. Check if slot is in the past (with buffer)
        3. Find staff who are not busy during this slot
        4. If at least one staff member is free, slot is available
        
        Args:
            schedule: The shop schedule for the target day
            eligible_staff: Staff who can perform the service
            busy_intervals: List of busy time intervals
            
        Returns:
            List of available slots with their available staff
        """
        available_slots = []
        
        # Determine slot interval - use service duration (not shop slot_duration!)
        # This ensures slots don't overlap for longer services
        slot_interval = self.slot_interval_override or self.service_duration
        
        # Create datetime objects for shop hours on target date
        shop_open = datetime.combine(self.target_date, schedule.start_time)
        shop_close = datetime.combine(self.target_date, schedule.end_time)
        
        # Localize to shop's timezone instead of default UTC
        import pytz
        try:
            shop_tz = pytz.timezone(self.shop.timezone)
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            # Fallback to UTC if timezone is invalid or not set
            shop_tz = pytz.UTC
        
        # Localize naive datetimes to shop timezone
        if timezone.is_naive(shop_open):
            shop_open = shop_tz.localize(shop_open)
        if timezone.is_naive(shop_close):
            shop_close = shop_tz.localize(shop_close)
        
        # Calculate minimum allowed slot time (now + buffer) if target is today
        # Use UTC for consistency with shop hours
        now = timezone.now()
        now_date_utc = now.date()  # This is already UTC since Django's now() returns UTC
        min_slot_time = None
        if self.target_date == now_date_utc:
            min_slot_time = now + timedelta(minutes=self.buffer_minutes)
        
        # Get list of eligible staff IDs for quick lookup
        eligible_staff_ids = set(eligible_staff.values_list('id', flat=True))
        
        # Generate time grid and check each slot
        current_slot_start = shop_open
        
        while current_slot_start < shop_close:
            # Calculate slot end based on service duration (not slot interval!)
            slot_end = current_slot_start + timedelta(minutes=self.service_duration)
            
            # Hard Constraint 1: Slot must end within shop hours
            if slot_end > shop_close:
                break  # No more valid slots
            
            # Hard Constraint 2: Slot must not be in the past
            if min_slot_time and current_slot_start < min_slot_time:
                current_slot_start += timedelta(minutes=slot_interval)
                continue
            
            # Soft Constraint: Find available staff for this slot
            available_staff_ids = self._find_available_staff(
                slot_start=current_slot_start,
                slot_end=slot_end,
                eligible_staff_ids=eligible_staff_ids,
                busy_intervals=busy_intervals
            )
            
            # If at least one staff member is available, add the slot
            if available_staff_ids:
                available_slots.append(AvailableSlot(
                    start_time=current_slot_start,
                    end_time=slot_end,
                    available_staff_ids=available_staff_ids
                ))
            
            # Move to next potential slot start
            current_slot_start += timedelta(minutes=slot_interval)
        
        return available_slots
    
    def _find_available_staff(
        self,
        slot_start: datetime,
        slot_end: datetime,
        eligible_staff_ids: set,
        busy_intervals: List[BusyInterval]
    ) -> List[UUID]:
        """
        Find staff members who are available for a specific time slot.
        
        Overlap Formula: max(slot_start, booking_start) < min(slot_end, booking_end)
        
        Args:
            slot_start: Start time of the slot
            slot_end: End time of the slot
            eligible_staff_ids: Set of staff IDs who can do the service
            busy_intervals: List of busy intervals to check against
            
        Returns:
            List of staff UUIDs who are free during this slot
        """
        # Start with all eligible staff as potentially available
        available_ids = set(eligible_staff_ids)
        
        # Remove staff who have overlapping bookings
        for interval in busy_intervals:
            if interval.staff_id not in available_ids:
                continue  # Already removed
            
            # Check for overlap using the overlap formula
            # Overlap exists if: max(slot_start, booking_start) < min(slot_end, booking_end)
            overlap_start = max(slot_start, interval.start)
            overlap_end = min(slot_end, interval.end)
            
            if overlap_start < overlap_end:
                # There's an overlap - staff is busy
                available_ids.discard(interval.staff_id)
        
        return list(available_ids)
    
    def get_shop_hours(self) -> Optional[dict]:
        """
        Get shop hours for the target date.
        
        Returns:
            Dict with start_time, end_time, slot_duration_minutes or None if closed
        """
        schedule = self._get_shop_schedule()
        if not schedule:
            return None
        
        return {
            'start_time': schedule.start_time.isoformat(),
            'end_time': schedule.end_time.isoformat(),
            'slot_duration_minutes': schedule.slot_duration_minutes,
            'day_of_week': schedule.day_of_week
        }
    
    def is_shop_open(self) -> bool:
        """Check if the shop is open on the target date."""
        schedule = self._get_shop_schedule()
        return schedule is not None and schedule.is_active
