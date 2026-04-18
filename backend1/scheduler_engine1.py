"""
STEP 1: scheduler_engine1.py - Core Simulation Engine
This file contains pure algorithms with NO web code.
It can be tested standalone in Python without Flask or Streamlit.
"""

# IMPORTS - What we need from Python
from datetime import datetime, timedelta  # For time calculations
from dataclasses import dataclass          # For creating organized data containers
from typing import List, Dict, Optional    # For type hints
import random                              # For randomness in simulation


# ============================================================================
# CONFIGURATION - The "Rules" of the System (Define once, reference everywhere)
# ============================================================================

# PRIORITY_WEIGHTS: When calculating priority, how much does each factor matter?
# Total adds up to 1.0 (100%)
PRIORITY_WEIGHTS = {
    'urgency': 0.40,        # 40% - How urgent is this request?
    'requester_type': 0.25, # 25% - Who's requesting? (graduating student > regular student)
    'waiting_time': 0.20,   # 20% - How long have they waited? (fairness)
    'document_type': 0.15   # 15% - How complex is the document?
}

# REQUESTER_PRIORITY: Different types of requesters have different importance (1-10 scale)
REQUESTER_PRIORITY = {
    'Graduating Student': 10,    # Most urgent (needs to graduate)
    'Enrolling Student': 8,      # Important (needs to enroll)
    'Faculty': 7,                # Somewhat important
    'Alumni': 5,                 # Less urgent
    'Regular Student': 3         # Can wait longer
}

# DOCUMENT_COMPLEXITY: Some documents take longer (multiplier on base time in HOURS)
DOCUMENT_COMPLEXITY = {
    'Transcript of Records': 3,         # Takes 3 hrs
    'Certificate of Enrollment': 2,     # Takes 2 hrs
    'Honorable Dismissal': 4,          # Takes 4 hrs
    'Certification': 1                  # Takes 1 hrs
}

# COLLEGES: List of all colleges in the system
COLLEGES = ['COE', 'CAS', 'CBA', 'CEGE', 'CS', 'IE']

# COLLEGE_POPULATION: Realistic student population distribution (percentage)
# COE and CAS have most students, smaller colleges have fewer
COLLEGE_POPULATION = {
    'COE': 0.25,      # 25% - Engineering (largest)
    'CAS': 0.25,      # 25% - Arts & Sciences
    'CBA': 0.18,      # 18% - Business
    'CEGE': 0.15,     # 15% - Education
    'CS': 0.12,       # 12% - Computer Science
    'IE': 0.05        # 5% - Institute (smallest)
}


# ============================================================================
# STEP 2: DocumentRequest Class
# Represents ONE student's document request
# ============================================================================

@dataclass
class DocumentRequest:
    """
    Represents a single document request from a student.
    
    INITIAL FIELDS (set when request arrives):
    - request_id: Unique ID like "REQ0001"
    - college: Which college (COE, CAS, etc)
    - document_type: Type of document (Transcript, Certificate, etc)
    - urgency: How urgent (1-10 scale)
    - requester_type: Type of requester (Graduating Student, Regular, etc)
    - submission_time: When student submitted the request
    
    PROCESSING FIELDS (set as request is processed):
    - priority_score: Calculated priority (0-1, only used by Weighted Priority scheduler)
    - assignment_time: When staff member was assigned to it
    - completion_time: When the request was completed
    - assigned_staff: Which staff member handled it
    """
    
    # Initial fields (required when creating)
    request_id: str
    college: str
    document_type: str
    urgency: int              # 1-10 scale
    requester_type: str
    submission_time: datetime
    
    # Processing fields (set later, start empty)
    priority_score: float = 0.0
    assignment_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    assigned_staff: Optional[str] = None
    
    def calculate_priority(self, current_time: datetime) -> float:
        """
        Calculate priority score at a specific point in time.
        
        WHY DOES IT TAKE current_time?
        Priority increases over time as request waits longer (fairness).
        A new request might have low priority, but after 2 hours, it goes up.
        
        HOW DOES IT WORK?
        1. Normalize each factor to 0-1 scale
        2. Multiply by its weight from PRIORITY_WEIGHTS
        3. Sum them up
        
        WHEN IS THIS CALLED?
        - Only by WeightedPriorityScheduler
        - FCFS scheduler never calls this
        
        Returns: Float between 0-1 (higher = more important)
        """
        
        # Factor 1: How urgent is the request itself? (1-10 scale)
        urgency_norm = self.urgency / 10.0
        # Example: urgency=9 → 0.9
        
        # Factor 2: What type of requester? (from REQUESTER_PRIORITY)
        requester_norm = REQUESTER_PRIORITY.get(self.requester_type, 3) / 10.0
        # Example: "Graduating Student"→10/10=1.0, "Regular Student"→3/10=0.3
        
        # Factor 3: How long have they been waiting? (increases fairness)
        waiting_minutes = (current_time - self.submission_time).total_seconds() / 60
        waiting_norm = min(waiting_minutes / 120.0, 1.0)  # Cap at 120 min
        # Example: waiting 120 min → 1.0 (high priority for fairness)
        # Example: waiting 60 min → 0.5
        
        # Factor 4: How complex is the document? (inverse - easier docs boost priority)
        doc_complexity = DOCUMENT_COMPLEXITY.get(self.document_type, 1.0)
        doc_norm = 1.0 / doc_complexity
        # Example: Transcript (1.5) → 1/1.5=0.67
        # Example: Certification (0.8) → 1/0.8=1.25 (simpler, gets boost)
        
        # Combine all factors with weights
        # This weighted sum formula is what makes priority balanced
        self.priority_score = (
            PRIORITY_WEIGHTS['urgency'] * urgency_norm +
            PRIORITY_WEIGHTS['requester_type'] * requester_norm +
            PRIORITY_WEIGHTS['waiting_time'] * waiting_norm +
            PRIORITY_WEIGHTS['document_type'] * doc_norm
        )
        return self.priority_score
    
    def get_waiting_time_minutes(self) -> float:
        """
        Calculate how long this request waited in queue.
        
        FORMULA: waiting_time = assignment_time - submission_time
        
        WHY THIS METRIC?
        For FCFS: Shows if fairness is working (all similar wait times)
        For Priority: Shows if urgency is helping (urgent waits less)
        
        Returns: Minutes spent in queue before being assigned
        """
        if self.assignment_time and self.submission_time:
            return (self.assignment_time - self.submission_time).total_seconds() / 60
        return 0.0
    
    def get_turnaround_time_minutes(self) -> float:
        """
        Calculate total time from submission to completion.
        
        FORMULA: turnaround_time = completion_time - submission_time
        
        WHY THIS METRIC?
        Shows TOTAL efficiency including both queue time + processing time.
        
        Example:
        - Submitted: 12:00
        - Assigned: 12:05 (5 min waiting)
        - Completed: 12:17 (12 min processing)
        - Turnaround: 17 minutes (5 + 12)
        
        Returns: Total minutes from submission to completion
        """
        if self.completion_time and self.submission_time:
            return (self.completion_time - self.submission_time).total_seconds() / 60
        return 0.0


# ============================================================================
# STEP 3: StaffMember Class
# Represents ONE registrar staff member
# ============================================================================

@dataclass
class StaffMember:
    """
    Represents a single staff member at the registrar office.
    
    IDENTITY FIELDS (fixed):
    - staff_id: Unique ID like "STAFF001"
    - name: Name of staff member
    - college_affiliation: Which college they primarily serve (COE, CAS, etc)
    
    AVAILABILITY FIELDS (changes during simulation):
    - next_available_time: When will this staff member be free?
    - is_available: Are they working today? (False if absent)
    - total_assigned: How many requests have they processed?
    - quota_limit: Max requests per day (default 20, configurable)
    """
    
    # Identity fields (fixed)
    staff_id: str
    name: str
    college_affiliation: str
    
    # Availability fields (change during simulation)
    next_available_time: datetime = None
    is_available: bool = True
    total_assigned: int = 0
    quota_limit: int = 20  # Max requests per day (configurable, default 20)
    
    def __post_init__(self):
        """
        WHY THIS METHOD?
        Runs automatically AFTER __init__ to set default values.
        
        If next_available_time wasn't provided, set it to now
        (staff can start working immediately at simulation start)
        """
        if self.next_available_time is None:
            self.next_available_time = datetime.now()
    
    def can_accept(self, current_time: datetime) -> bool:
        """
        Can this staff member accept a new request RIGHT NOW?
        
        Returns True ONLY if:
        1. They are available (is_available = True)
           - FALSE if they called in sick (staff_absence scenario)
        2. Current time >= their next_available_time
           - FALSE if they're still busy with previous request
        
        USAGE:
        This is called by allocators to see if a staff member
        can handle the next request in the queue.
        
        Example:
        - Staff is processing until 12:30
        - next_available_time = 12:30
        - At 12:25: can_accept() returns False (still busy)
        - At 12:30: can_accept() returns True (free now!)
        - At 12:35: can_accept() returns True (still free)
        """
        return self.is_available and current_time >= self.next_available_time
    
    def assign_request(self, assignment_time: datetime, processing_time: timedelta):
        """
        Called when assigning a request to this staff member.
        
        Updates:
        1. total_assigned: Increment workload counter
        2. next_available_time: Mark them as busy until this time
        
        EXAMPLE:
        - Current time: 12:00 (request being assigned now)
        - Document type: "Transcript" (complexity 1.5)
        - Base processing time: 3 minutes
        - Actual processing time: 1.5 * 3 = 4.5 minutes (with randomness: ±20%)
        
        So we call: assign_request(assignment_time=12:00, processing_time=4.5 min)
        
        Result:
        - total_assigned increases by 1 (they've handled 1 more request)
        - next_available_time becomes 12:04:30 (they'll be free then)
        
        WHY THIS MATTERS?
        When next request comes, allocator checks can_accept()
        If next_available_time hasn't passed, staff can't take it yet
        This prevents double-booking and models realistic processing
        """
        self.total_assigned += 1
        self.next_available_time = assignment_time + processing_time
    
    def can_accept_quota(self) -> bool:
        """
        Check if this staff member is under their daily quota.
        
        RETURNS: True if they can accept more work today, False if quota reached
        
        WHY SEPARATE METHOD?
        - can_accept() checks: "Are you free RIGHT NOW?"
        - can_accept_quota() checks: "Have you hit your daily limit?"
        
        These are TWO DIFFERENT CONSTRAINTS:
        1. Time-based: When are you free? (can_accept)
        2. Quota-based: Have you done enough today? (can_accept_quota)
        
        USED BY: Allocators (CollegeBasedAllocator, WorkloadBasedAllocator, PooledAllocator)
        SKIPPED BY: QuotaFreeAllocator (no quota limit)
        
        EXAMPLE:
        - Staff has quota_limit = 20
        - After 20 requests: can_accept_quota() returns False
        - Additional requests wait or transfer to other staff
        """
        return self.total_assigned < self.quota_limit


# ============================================================================
# STEP 4: FCFSScheduler Class
# First-Come-First-Served: Process requests in arrival order
# ============================================================================

class FCFSScheduler:
    """
    FCFS Scheduler - Processes requests in the order they arrived.
    
    PHILOSOPHY:
    "First person to arrive gets served first, second person second, etc."
    Like a line at the bank: you wait your turn, oldest customer first.
    
    PROS:
    - Simple to understand and implement
    - Fair: everyone gets served in order
    - Predictable: people know when their turn is coming
    
    CONS:
    - Doesn't account for urgency
    - Graduating student waits same as regular student
    - Urgent requests don't jump the line
    
    METRIC IMPACT:
    - Avg Waiting Time: Shows if system is responsive (is anyone waiting forever?)
    - Fairness: All customers wait similar times (no one gets priority)
    """
    
    def __init__(self):
        """Initialize with empty queue"""
        self.queue: List[DocumentRequest] = []
    
    def add_request(self, request: DocumentRequest):
        """
        Add a new request to the queue.
        
        CALLED BY: SimulationEngine when a new request arrives
        
        EXAMPLE:
        - REQ0001 arrives → add_request(REQ0001)
        - REQ0002 arrives → add_request(REQ0002)
        Later, when we process: REQ0001 goes first (was oldest)
        """
        self.queue.append(request)
    
    def get_all_sorted(self) -> List[DocumentRequest]:
        """
        Return all requests sorted by submission_time (oldest first).
        
        RETURNS:
        List of DocumentRequest objects sorted by:
        - submission_time: ascending (oldest first)
        
        CLEARS THE QUEUE:
        After returning, empties the queue to avoid duplicates
        
        EXAMPLE:
        Queue contains:
        - REQ0001: submitted 12:00
        - REQ0003: submitted 12:05
        - REQ0002: submitted 12:02
        
        Returns: [REQ0001, REQ0002, REQ0003] (in time order)
        Queue becomes: [] (empty)
        
        WHY SORT BY SUBMISSION_TIME?
        That's how FCFS works - whoever submitted first gets scheduled first.
        This is the ONE criterion FCFS cares about.
        
        CONTRAST WITH WeightedPriority:
        - Weighted Priority would sort by priority_score (calculated from multiple factors)
        - Weighted Priority considers urgency, requester type, waiting time, doc complexity
        - FCFS: Only looks at submission_time, nothing else
        """
        sorted_queue = sorted(self.queue, key=lambda r: r.submission_time)
        self.queue.clear()
        return sorted_queue


# ============================================================================
# STEP 5: The 4 Allocators (Assignment Strategies)
# These decide: "Which staff member should handle this request?"
# ============================================================================

class BaseAllocator:
    """
    Base class that all allocators inherit from.
    
    WHY A BASE CLASS?
    - Defines the interface all allocators must follow
    - All must have assign(request, current_time) method
    - Ensures they all work the same way when called by SimulationEngine
    
    PATTERN: Strategy Pattern
    - Different allocator subclasses = different strategies
    - All can be swapped in/out without changing SimulationEngine code
    """
    
    def __init__(self, staff_pool: List[StaffMember]):
        """
        Initialize allocator with the staff pool.
        
        ARG: staff_pool - List of all available staff members
        All allocators need to know about staff to make assignments
        """
        self.staff_pool = staff_pool
    
    def assign(self, request: DocumentRequest, current_time: datetime, quota_tracker: Dict = None) -> Optional[StaffMember]:
        """
        Find and return a staff member to handle this request.
        
        RETURNS:
        - StaffMember object if someone is available
        - None if nobody is available right now
        
        This is called by SimulationEngine for EACH request
        """
        raise NotImplementedError


# ============================================================================
# ALLOCATOR 1: CollegeBasedAllocator
# Strategy: Assign to staff from the SAME COLLEGE (if available)
# ============================================================================

class CollegeBasedAllocator(BaseAllocator):
    """
    STRATEGY: Prefer staff from the same college as the request.
    
    LOGIC:
    1. Find all staff from the request's college who are available
    2. Pick one randomly from candidates
    3. If no same-college staff available, return None
    
    PROS:
    - Staff know their college's procedures and students
    - College-specific expertise is preserved
    - Requests stay within department
    
    CONS:
    - If COE is busy but CAS is idle, COE request waits
    - Long queues for popular colleges
    - Can't balance workload across departments
    
    BEST FOR:
    - Specialized work per college
    - Maintaining college-specific procedures
    - When cross-college help isn't possible
    """
    
    def assign(self, request: DocumentRequest, current_time: datetime, quota_tracker: Dict = None, req_day: int = None) -> Optional[StaffMember]:
        """
        Find an available staff member from the same college.
        
        CONSTRAINTS CHECKED:
        1. Same college: s.college_affiliation == request.college
        2. Available now: s.is_available
        3. Under quota: s.can_accept_quota() - NOT over the 20 limit
        
        SELECTION: random.choice() if multiple candidates
        
        BEHAVIOR WHEN STAFF HITS QUOTA (20 requests/day):
        - NO FALLBACK: Returns None if all same-college staff at quota
        - Customer WAITS IN QUEUE until staff finishes one request
        - As staff processes and total_assigned decreases... WAIT, no
        - total_assigned INCREASES, not decreases
        
        ACTUALLY:
        - When staff hits quota limit, can_accept_quota() = False
        - New requests for this college CANNOT be assigned to this staff
        - They stay in queue
        - Other same-college staff might be available (under quota)
        - If ALL same-college staff are at quota, everyone waits
        
        This is STRICT COLLEGE-BASED with QUOTA ENFORCEMENT
        """
        candidates = [
            s for s in self.staff_pool 
            if s.college_affiliation == request.college 
            and s.is_available
            and (
                quota_tracker is None or 
                quota_tracker.get(s.staff_id, {}).get(req_day, 0) < s.quota_limit
                )
                ]
        
        if candidates:
            return min(candidates, key=lambda s: s.next_available_time)
        
        return None


# ============================================================================
# ALLOCATOR 2: WorkloadBasedAllocator
# Strategy: Prefer same college, but flexible - balance workload
# ============================================================================

class WorkloadBasedAllocator(BaseAllocator):
    """
    STRATEGY: Balance workload across staff.
    
    TWO-TIER LOGIC:
    1. FIRST CHOICE: Find least-busy staff from same college
    2. FALLBACK: If no same-college staff, find least-busy from ANYONE
    
    PROS:
    - Balances workload (no one gets overloaded)
    - Respects college specialization when possible
    - Flexible fallback when needed
    - More realistic for cross-college help
    
    CONS:
    - Slightly more complex logic
    - Might separate students from their college staff
    
    BEST FOR:
    - General registrar operations
    - Balancing team workload
    - When flexibility matters
    
    METRIC RESULT:
    - More balanced staff_load (everyone does ~same requests)
    - More consistent avg_waiting_time
    """
    
    def assign(self, request: DocumentRequest, current_time: datetime, quota_tracker: Dict = None, req_day: int = None) -> Optional[StaffMember]:
        """
        Two-tier assignment with QUOTA ENFORCEMENT and FLEXIBLE FALLBACK.
        
        TIER 1: Find available, under-quota staff from same college
        - FILTER: Same college AND available AND under quota (20 limit)
        - SELECTION: min() by total_assigned (least busy)
        - RETURN if found
        
        TIER 2: If Tier 1 fails, try ANYONE from any college (still quota-checked)
        - FILTER: Available AND under quota (doesn't matter college)
        - SELECTION: min() by total_assigned (least busy)
        - RETURN if found
        
        BEHAVIOR:
        - Respects college affiliation preference (tries Tier 1 first)
        - But when staff hit quota, TRANSFERS to less-busy staff from other colleges
        - Balances workload while respecting quotas
        - Customers can get served faster (don't wait in queue)
        
        BUSINESS LOGIC:
        "We prefer college specialists, but if they're overloaded, we'll use anyone available"
        """
        
        # TIER 1: Same-college, under-quota staff
        college_staff = [
            s for s in self.staff_pool 
            if s.college_affiliation == request.college 
            and s.is_available
            and (
                quota_tracker is None or 
                quota_tracker.get(s.staff_id, {}).get(req_day, 0) < s.quota_limit
                )  # NEW: Check quota
                    ]
        
        if college_staff:
            return min(college_staff, key=lambda s: s.total_assigned)
        
        # TIER 2: ANY college, under-quota staff (flexible fallback)
        available = [
            s for s in self.staff_pool 
            if s.is_available
            and (
                quota_tracker is None or 
                quota_tracker.get(s.staff_id, {}).get(req_day, 0) < s.quota_limit
            )  # NEW: Check quota
        ]
        
        # TIER 3: Nobody available and under quota
        if available:
            return min(available, key=lambda s: s.total_assigned)
        
        return None


# ============================================================================
# ALLOCATOR 3: PooledAllocator
# Strategy: Pool all staff together - assign to whoever's free soonest
# ============================================================================

class PooledAllocator(BaseAllocator):
    """
    STRATEGY: No college boundaries. Pool all staff and assign to
    whoever becomes available SOONEST.
    
    LOGIC:
    1. Find all available staff (from ANY college)
    2. Pick the one with earliest next_available_time
    
    PROS:
    - Minimizes wait time (requests get processed ASAP)
    - No college bottlenecks
    - Simplest to implement
    - Most efficient throughput
    
    CONS:
    - Loses college specialization
    - Students served by random college staff
    
    BEST FOR:
    - Maximizing throughput
    - Minimizing wait times
    - When all staff are interchangeable
    - General registrar operations
    
    METRIC RESULT:
    - Lowest avg_waiting_time (nobody waits long)
    - Highest throughput (processes most requests)
    """
    
    def assign(self, request: DocumentRequest, current_time: datetime, quota_tracker: Dict = None, req_day: int = None) -> Optional[StaffMember]:
        """
        Find available, under-quota staff and picking whoever becomes free soonest.
        
        CONSTRAINTS:
        1. Must be available now: can_accept(current_time)
        2. Must be under quota: can_accept_quota() - NOT over 20 limit
        3. Selection: Pick whoever has earliest next_available_time
        
        BEHAVIOR:
        - No college boundaries (don't care about college_affiliation)
        - Pure efficiency and workload balancing
        - Quota prevents burnout across entire team
        - When anyone hits quota, system can't process more (everyone waits)
        
        WHY "EARLIEST next_available_time"?
        - If multiple staff available now, some will become busy soon
        - Pick truly-available staff (lowest next_available_time)
        - Leaves other staff free for next requests
        - Optimizes queue flow
        """
        available = [
            s for s in self.staff_pool 
            if s.is_available
            and (
                quota_tracker is None or 
                quota_tracker.get(s.staff_id, {}).get(req_day, 0) < s.quota_limit
            )  # NEW: Check quota
        ]
        
        
        if available:
            return min(available, key=lambda s: s.next_available_time)
        
        return None


# ============================================================================
# ALLOCATOR 4: QuotaFreeAllocator
# Strategy: Same as Pooled (no quotas/boundaries)
# ============================================================================

class QuotaFreeAllocator(BaseAllocator):
    """
    STRATEGY: College-specialist WITHOUT quota limits.
    
    LOGIC:
    - Prefer staff from same college (specialist approach)
    - NO quota enforcement (unlimited daily capacity)
    - Pick least busy (by next_available_time)
    
    PROS:
    - Maintains college specialization
    - Unlimited flexibility (can handle surge)
    - Useful for testing or flexible staff
    
    CONTRAST:
    - PooledAllocator = no college boundaries, HAS quota
    - QuotaFreeAllocator = college boundaries, NO quota
    
    USE CASE:
    "What if certain staff can work unlimited hours?"
    Or: "What if we removed daily limits for high-priority staff?"
    """
    
    def assign(self, request: DocumentRequest, current_time: datetime, quota_tracker: Dict = None, req_day : int = None) -> Optional[StaffMember]:
        """
        Find available college-specialist staff with NO quota limit.
        
        LOGIC:
        - Same college: s.college_affiliation == request.college
        - Available now: s.is_available
        - NO quota check - unlimited capacity
        - Selection: Least busy (by next_available_time)
        """
        candidates = [
            s for s in self.staff_pool 
            if s.college_affiliation == request.college 
            and s.is_available
            # NO quota check - absolutely UNLIMITED
        ]
        
        if candidates:
            # Pick least busy (whoever has earliest next_available_time)
            return min(candidates, key=lambda s: s.next_available_time)
        
        return None


# ============================================================================
# STEP 6: SimulationEngine - The Main Orchestrator
# Ties everything together: staff, scheduler, allocator, requests
# ============================================================================

class SimulationEngine:
    """
    MAIN SIMULATION ENGINE - Coordinates the entire simulation.
    
    RESPONSIBILITIES:
    1. Create staff pool (with configurable size and quota)
    2. Create scheduler (FCFS or Weighted Priority)
    3. Create allocator (College-Based, Workload-Based, Pooled, Quota-Free)
    4. Generate synthetic requests (with scenario variations)
    5. Run the main loop: sort → assign → process → calculate metrics
    6. Track queue and metrics for evaluation
    
    FLOW:
    engine = SimulationEngine(scheduler_type, allocator_type, staff_config)
    results = engine.run(scenario, duration_min)
    """
    
    def __init__(
        self, 
        scheduler_type: str, 
        allocator_type: str, 
        staff_config: Optional[Dict] = None,
        random_seed: Optional[int] = None
    ):
        """
        Initialize the simulation engine.
        
        ARGS:
        - scheduler_type: "FCFS" or "WEIGHTED"
        - allocator_type: "college_based", "workload_based", "pooled", "quota_free"
        - staff_config: Dict with optional customizations
            - "enable_custom_staff": bool
            - "num_staff": int (default 6)
            - "quota_limit": int (default 20, per staff per day)
        
        EXAMPLE:
        engine = SimulationEngine(
            scheduler_type="FCFS",
            allocator_type="college_based",
            staff_config={
                "enable_custom_staff": True,
                "num_staff": 8,
                "quota_limit": 25
            }
        )
        """
        
        # STEP 1: Parse staff configuration
        num_staff = 6  # Default
        quota_limit = 20  # Default
        
        if staff_config:
            if staff_config.get('enable_custom_staff'):
                num_staff = staff_config.get('num_staff', 6)
            if 'quota_limit' in staff_config:
                quota_limit = staff_config.get('quota_limit', 20)

        if random_seed is None:
            random_seed = random.randint(1, 2_147_483_647)  # Generate if not provided
        self.random_seed = int(random_seed)
        self.rng = random.Random(self.random_seed)  # Create seeded RNG
        
        # STEP 2: Create staff pool with configured quota
        self.staff_pool = self._generate_staff_pool(num_staff, quota_limit)
        print(f"✅ Staff pool created: {num_staff} members (quota: {quota_limit}/day)")
        
        # STEP 3: Set scheduler type
        self.scheduler_type = scheduler_type.upper()
        print(f"✅ Scheduler: {self.scheduler_type}")
        
        # STEP 4: Create allocator
        self.allocator = self._create_allocator(allocator_type)
        self.allocator_type = allocator_type.lower()
        print(f"✅ Allocator: {allocator_type}")
        
        # STEP 5: Initialize tracking variables
        self.scheduler = FCFSScheduler()  # Will use this to queue requests
        self.completed: List[DocumentRequest] = []
        self.waiting_queue: List[DocumentRequest] = []  # For visualization
        self.in_progress: List[DocumentRequest] = []     # Currently being processed
        self.start_time = datetime.now()
        self.scenario = "baseline"
        self.event_log: List[Dict] = []
        self._event_seq = 0

    def _log_event(self, event_time: datetime, event_type: str, 
                   request: Optional[DocumentRequest] = None, 
                   staff: Optional[StaffMember] = None, 
                   details: str = "", extra: Optional[Dict] = None):
        """Log a simulation event for debugging and frontend playback."""
        self._event_seq += 1
        payload = {
            "sequence": self._event_seq,
            "time": event_time.isoformat(),
            "event_type": event_type,
            "request_id": request.request_id if request else None,
            "college": request.college if request else None,
            "document_type": request.document_type if request else None,
            "staff_id": staff.staff_id if staff else None,
            "details": details
        }
        if request:
            payload["priority_score"] = round(request.priority_score, 4)
        if extra:
            payload.update(extra)
        self.event_log.append(payload)
    
    def _init_all_staff(self) -> List[StaffMember]:
        """
        Create ALL possible staff members (one per college).
        Used to calculate absent staff.
        """
        staff = []
        names = [
            "Maria Santos", "Juan Dela Cruz", "Ana Reyes", "Carlos Lim",
            "Luisa Gomez", "Ramon Aquino", "Elena Cruz", "Miguel Torres"
        ]
        
        for i, college in enumerate(COLLEGES):
            staff.append(StaffMember(
                staff_id=f"STAFF{i+1:03d}",
                name=names[i % len(names)],
                college_affiliation=college,
                quota_limit=20
            ))
        return staff
    
    def _generate_staff_pool(self, num_staff: int, quota_limit: int) -> List[StaffMember]:
        """
        Create synthetic staff members.
        
        ARGS:
        - num_staff: How many staff to create (1-6, one per college)
        - quota_limit: Daily quota per staff member
        
        CREATES:
        - Names from predefined list
        - College affiliations from COLLEGES list (first num_staff colleges)
        - Quota limit for each
        """
        staff = []
        names = [
            "Maria Santos", "Juan Dela Cruz", "Ana Reyes", "Carlos Lim",
            "Luisa Gomez", "Ramon Aquino", "Elena Cruz", "Miguel Torres"
        ]
        
        for i in range(min(num_staff, len(COLLEGES))):
            staff.append(StaffMember(
                staff_id=f"STAFF{i+1:03d}",
                name=names[i % len(names)],
                college_affiliation=COLLEGES[i],  # Assign to each college in order
                quota_limit=quota_limit  # Set quota for this staff
            ))
        return staff
    
    def _create_allocator(self, allocator_type: str) -> BaseAllocator:
        """
        Create the appropriate allocator based on type string.
        
        MAPPING:
        - "college_based" → CollegeBasedAllocator
        - "workload_based" → WorkloadBasedAllocator
        - "pooled" → PooledAllocator
        - "quota_free" → QuotaFreeAllocator
        
        DEFAULT: CollegeBasedAllocator if unknown type
        """
        allocators = {
            "college_based": CollegeBasedAllocator(self.staff_pool),
            "workload_based": WorkloadBasedAllocator(self.staff_pool),
            "pooled": PooledAllocator(self.staff_pool),
            "quota_free": QuotaFreeAllocator(self.staff_pool)
        }
        return allocators.get(allocator_type, CollegeBasedAllocator(self.staff_pool))
    
    def _generate_requests(self, custom_config: Dict = None) -> List[DocumentRequest]:
        """
        Generate synthetic requests using SLIDER-BASED configuration.
        Fixed scenarios removed. Everything is now dynamically controlled.
        """
        config = custom_config or {}
        requests = []
        
        # 1. Extract slider values (with safe defaults)
        total_requests = config.get('total_requests', 200)
        urgency_base = config.get('urgency_base', 5)
        imbalance_factor = config.get('imbalance_factor', 0) / 100.0  # 0.0 to 1.0
        
        # 2. College distribution with dynamic imbalance
        college_list = list(COLLEGE_POPULATION.keys())
        college_weights = list(COLLEGE_POPULATION.values())
        
        if imbalance_factor > 0:
            # Boost COE weight proportionally, then renormalize
            coe_idx = college_list.index('COE')
            college_weights[coe_idx] += imbalance_factor * 0.3
            total_w = sum(college_weights)
            college_weights = [w / total_w for w in college_weights]
            
        # 3. Dynamic urgency range based on slider base (1-10)
        if urgency_base >= 8:
            urgency_range = list(range(urgency_base, 11))      # High only
        elif urgency_base <= 3:
            urgency_range = list(range(1, urgency_base + 2))   # Low only
        else:
            urgency_range = list(range(max(1, urgency_base-2), min(10, urgency_base+3)))
            
        doc_types = list(DOCUMENT_COMPLEXITY.keys())
        requester_types = list(REQUESTER_PRIORITY.keys())
        
        # 4. Time distribution (60% morning, 20% afternoon, 20% evening)
        morning_count = int(total_requests * 0.6)
        afternoon_count = int(total_requests * 0.2)
        evening_count = total_requests - morning_count - afternoon_count
        
        current_request_id = 0
        
        # Helper to avoid code duplication
        def _add_requests(count: int, start_hour: float, end_hour: float):
            nonlocal current_request_id
            for _ in range(count):
                hours_in_day = self.rng.uniform(start_hour, end_hour)
                submission_time = self.start_time + timedelta(hours=hours_in_day)
                college = self.rng.choices(college_list, weights=college_weights, k=1)[0]
                requests.append(DocumentRequest(
                    request_id=f"REQ{current_request_id:04d}",
                    college=college,
                    document_type=self.rng.choice(doc_types),
                    urgency=self.rng.choice(urgency_range),
                    requester_type=self.rng.choice(requester_types),
                    submission_time=submission_time
                ))
                current_request_id += 1
                
        _add_requests(morning_count, 8, 10)
        _add_requests(afternoon_count, 14, 16)
        _add_requests(evening_count, 16, 24)
        
        return requests
    
    def _approximate_real_days(self) -> str:
        """
        Convert scenario to approximate real-world context.
        
        Since simulation uses realistic day-based durations,
        this just shows what the scenario represents.
        """
        scenario_requests = {
            "baseline": 200,
            "peak_urgency": 280,
            "workload_imbalance": 240
        }.get(self.scenario, 200)
        
        return f"({scenario_requests} requests arriving in one day)"
    
    def run(self, custom_config: Dict = None) -> Dict:
        """
        SIMULATION ENGINE - Now uses allocators with working hours & daily quota.
        """
        print(f"\n{'='*70}")
        print(f"🎬 STARTING SIMULATION: {custom_config}")
        print(f"   Staff available: {len(self.staff_pool)}/{len(COLLEGES)}")
        real_equiv = self._approximate_real_days()
        print(f"   Day 0: {real_equiv}")
        print(f"{'='*70}")
    
    # ✅ KEEP: Reset state
        self.scenario = custom_config.get('scenario', 'custom') if custom_config else 'custom'
        self.completed = []
        self.waiting_queue = []
        self.start_time = self.start_time.replace(hour=8, minute=0, second=0, microsecond=0)

        for staff in self.staff_pool:
            staff.next_available_time = self.start_time
    
    # ✅ KEEP: Generate & sort requests
        print(f"\n📋 Step 1: Generating requests...")
        requests = self._generate_requests(custom_config)
        print(f"   Total requests arriving: {len(requests)}")
    
        print(f"\n🔄 Step 2: Sorting requests (FCFS)...")
        sorted_requests = sorted(requests, key=lambda r: r.submission_time)
    
    # 🔑 NEW: Daily quota tracker per staff (not per college!)
        quota_tracker: Dict[str, Dict[int, int]] = {}  # {staff_id: {day_idx: count}}
    
        print(f"\n⚙️  Step 3: Assigning requests via {self.allocator_type} allocator...")

         # Log all arrivals first
        for req in sorted_requests:
            self._log_event(req.submission_time, "ARRIVAL", request=req, details="request_submitted")
    
        for idx, req in enumerate(sorted_requests):
            # 🔑 CRITICAL: Ask the ALLOCATOR for assignment (this is what makes strategies work)
            req_day = int((req.submission_time - self.start_time).total_seconds() // 86400)
            staff = self.allocator.assign(req, self.start_time, quota_tracker, req_day)
            if staff is None:
                self.waiting_queue.append(req)
                self._log_event(req.submission_time, "WAITING", request=req, details="no_eligible_staff")
                continue
            
            # Calculate assignment time (respect working hours)
            assign_time = max(req.submission_time, staff.next_available_time)
            assign_time = self._snap_to_work_hours(assign_time)


            # 2. 🔑 QUOTA OVERFLOW: If quota full for this day, defer to next day 8 AM (ONLY ONCE)
            assign_day = int((assign_time - self.start_time).total_seconds() // 86400)
            if quota_tracker.get(staff.staff_id, {}).get(assign_day, 0) >= staff.quota_limit:
                # Quota full → defer to next business day at 8 AM
                assign_day += 1
                assign_time = self.start_time + timedelta(days=assign_day, hours=8)
                assign_time = self._snap_to_work_hours(assign_time)
        
            # Processing time with variation
            base_hours = DOCUMENT_COMPLEXITY.get(req.document_type, 1.0)
            proc_hours = self.rng.uniform(base_hours * 0.8, base_hours * 1.2)

        
            # ✅ USE WORKING HOURS HELPER (8 AM - 5 PM)
            comp_time = self._process_with_work_hours(assign_time, proc_hours / 24.0)
        
            # Update request & staff state
            req.assignment_time = assign_time
            req.completion_time = comp_time
            req.assigned_staff = staff.staff_id
            staff.next_available_time = comp_time
            staff.total_assigned += 1  # For "least loaded" selection in allocators
        
            quota_tracker.setdefault(staff.staff_id, {})[assign_day] = \
                quota_tracker.get(staff.staff_id, {}).get(assign_day, 0) + 1
        
            self.completed.append(req)

            queue_wait_h = (assign_time - req.submission_time).total_seconds() / 3600.0
            self._log_event(assign_time, "ASSIGN", request=req, staff=staff, 
                           details=self.allocator_type,
                           extra={"queue_wait_hours": round(queue_wait_h, 2), "processing_hours": round(proc_hours, 2)})
            self._log_event(comp_time, "COMPLETE", request=req, staff=staff, details="processing_finished")
            
            if (idx + 1) % 20 == 0 or idx == 0 or idx == len(sorted_requests) - 1:
                print(f"   [{idx+1:3d}/{len(sorted_requests)}] {req.college}: → {staff.staff_id} "
                      f"(Queue: {queue_wait_h:.1f}h, Process: {proc_hours:.2f}h)")
    
    # ✅ KEEP: Metrics & absent staff
        print(f"\n📊 Step 4: Calculating metrics...")
        metrics = self._calculate_metrics()
    
        full_staff = self._init_all_staff()
        current_ids = {s.staff_id for s in self.staff_pool}
        metrics['absent_staff'] = [s.staff_id for s in full_staff if s.staff_id not in current_ids]
        metrics['waiting_queue'] = self.waiting_queue
    
        print(f"\n{'='*70}")
        print(f"✅ COMPLETE: {len(self.completed)} processed, {len(self.waiting_queue)} waiting")
        if metrics['absent_staff']:
            print(f"⚠️  Absent: {', '.join(metrics['absent_staff'])}")
        print(f"{'='*70}\n")
    
        return metrics
    def _snap_to_work_hours(self, dt: datetime) -> datetime:
        """Snap to 8 AM if before work, or next day 8 AM if after 5 PM"""
        if dt.hour < 8:
            return dt.replace(hour=8, minute=0, second=0, microsecond=0)
        if dt.hour >= 17:
            return (dt + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        return dt

    def _process_with_work_hours(self, start: datetime, duration_days: float) -> datetime:
        """Add processing time respecting 8 AM - 5 PM work window"""
        hours_left = duration_days
        current = start
        while hours_left > 0.01:
            work_available = max(0, 17 - current.hour)
            if work_available == 0:
                current = current.replace(hour=8) + timedelta(days=1)
                work_available = 9
            work = min(work_available, hours_left)
            current += timedelta(hours=work)
            hours_left -= work
        return current
    
    def _calculate_metrics(self) -> Dict:
        """
        Calculate performance metrics from completed requests.
        
        METRICS CALCULATED:
        1. avg_waiting_time: Average queue time before assignment (in hours)
        2. avg_turnaround: Average total time from submission to completion (in days)
        3. total_days_elapsed: How many days until ALL requests finished
        4. throughput: Requests per day
        5. staff_load: How many requests each staff processed
        
        INTERPRETATION:
        - Lower avg_waiting_time = responsive scheduler
        - Lower avg_turnaround = efficient system
        - Higher throughput = more requests per day
        - Balanced staff_load = fair allocation
        """
        
        if not self.completed:
            return {
                "avg_waiting_time": 0,
                "avg_turnaround": 0,
                "total_days_elapsed": 0,
                "throughput": 0,
                "total_processed": 0,
                "staff_load": {s.staff_id: 0 for s in self.staff_pool},
                "scenario": self.scenario
            }
        
        # Calculate metrics
        # WAITING TIME: from submission to assignment (in hours/minutes)
        waiting_times_hours = [
            req.get_waiting_time_minutes() / 60 for req in self.completed
        ]
        
        # TURNAROUND TIME: from submission to completion (in days)
        turnaround_times_days = [
            (req.completion_time - req.submission_time).total_seconds() / 86400 
            for req in self.completed
        ]
        
        # TOTAL ELAPSED DAYS: from first submission to last completion
        if self.completed:
            first_submission = min(r.submission_time for r in self.completed)
            last_completion = max(r.completion_time for r in self.completed)
            total_days_elapsed = (last_completion - first_submission).total_seconds() / 86400
        else:
            total_days_elapsed = 0
        
        # THROUGHPUT: requests per day
        throughput = len(self.completed) / max(total_days_elapsed, 1)
        
        # STAFF LOAD: count how many requests each staff member processed
        staff_load = {s.staff_id: 0 for s in self.staff_pool}
        for req in self.completed:
            if req.assigned_staff in staff_load:
                staff_load[req.assigned_staff] += 1
        
        metrics = {
            "avg_waiting_time_hours": round(sum(waiting_times_hours) / len(waiting_times_hours), 2),
            "avg_turnaround_days": round(sum(turnaround_times_days) / len(turnaround_times_days), 2),
            "total_days_elapsed": round(total_days_elapsed, 2),
            "throughput_req_per_day": round(throughput, 2),
            "total_processed": len(self.completed),
            "staff_load": staff_load,
            "scenario": self.scenario
        }
        
        self.event_log.sort(key=lambda e: e["time"])
        
        metrics.update({
            "seed_used": self.random_seed,  
                    })
        metrics["event_log"] = self.event_log
        
        return metrics


# Backward-compatible alias for code that imported SimulationEngine1.
SimulationEngine1 = SimulationEngine

