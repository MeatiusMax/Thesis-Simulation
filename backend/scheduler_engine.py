"""
SIMPLIFIED: Guaranteed-completion simulation with realistic waiting times
- No complex event loops = no timeouts
- Still models queueing behavior properly
- Produces non-zero waiting times
"""
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

# ===== CONFIGURATION =====
PRIORITY_WEIGHTS = {
    'urgency': 0.40,
    'requester_type': 0.25,
    'waiting_time': 0.20,
    'document_type': 0.15
}

REQUESTER_PRIORITY = {
    'Graduating Student': 10,
    'Enrolling Student': 8,
    'Faculty': 7,
    'Alumni': 5,
    'Regular Student': 3
}

DOCUMENT_COMPLEXITY = {
    'Transcript of Records': 1.5,
    'Certificate of Enrollment': 1.0,
    'Honorable Dismissal': 1.2,
    'Certification': 0.8
}

COLLEGES = ['COE', 'CAS', 'CBA', 'CEGE', 'CS', 'IE']

# ===== DATA MODELS =====
@dataclass
class DocumentRequest:
    request_id: str
    college: str
    document_type: str
    urgency: int
    requester_type: str
    submission_time: datetime
    priority_score: float = 0.0
    assignment_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    assigned_staff: Optional[str] = None
    
    def calculate_priority(self, current_time: datetime) -> float:
        urgency_norm = self.urgency / 10.0
        requester_norm = REQUESTER_PRIORITY.get(self.requester_type, 3) / 10.0
        waiting_minutes = (current_time - self.submission_time).total_seconds() / 60
        waiting_norm = min(waiting_minutes / 120.0, 1.0)
        doc_complexity = DOCUMENT_COMPLEXITY.get(self.document_type, 1.0)
        doc_norm = 1.0 / doc_complexity
        
        self.priority_score = (
            PRIORITY_WEIGHTS['urgency'] * urgency_norm +
            PRIORITY_WEIGHTS['requester_type'] * requester_norm +
            PRIORITY_WEIGHTS['waiting_time'] * waiting_norm +
            PRIORITY_WEIGHTS['document_type'] * doc_norm
        )
        return self.priority_score
    
    def get_waiting_time_minutes(self) -> float:
        if self.assignment_time and self.submission_time:
            return (self.assignment_time - self.submission_time).total_seconds() / 60
        return 0.0
    
    def get_turnaround_time_minutes(self) -> float:
        if self.completion_time and self.submission_time:
            return (self.completion_time - self.submission_time).total_seconds() / 60
        return 0.0

@dataclass
class StaffMember:
    staff_id: str
    name: str
    college_affiliation: str
    next_available_time: datetime = None
    total_assigned: int = 0
    is_available: bool = True
    
    def __post_init__(self):
        if self.next_available_time is None:
            self.next_available_time = datetime.now()
    
    def can_accept(self, current_time: datetime) -> bool:
        return self.is_available and current_time >= self.next_available_time
    
    def assign_request(self, assignment_time: datetime, processing_time: timedelta):
        self.total_assigned += 1
        self.next_available_time = assignment_time + processing_time

# ===== SCHEDULERS (Simplified - FCFS only for now) =====
class FCFSScheduler:
    """Simple FCFS scheduler - processes requests in arrival order"""
    def __init__(self):
        self.queue: List[DocumentRequest] = []
    
    def add_request(self, request: DocumentRequest):
        self.queue.append(request)
    
    def get_all(self) -> List[DocumentRequest]:
        requests = self.queue[:]
        self.queue.clear()
        return requests
    
class WeightedPriorityScheduler:
    """Weighted Priority scheduler - processes requests based on calculated priority"""
    def __init__(self):
        self.queue: List[DocumentRequest] = []
    
    def add_request(self, request: DocumentRequest):
        self.queue.append(request)
    
    def get_all(self) -> List[DocumentRequest]:
        # Sort by priority score (descending)
        sorted_queue = sorted(self.queue, key=lambda r: r.priority_score, reverse=True)
        self.queue.clear()
        return sorted_queue
    
# ===== ALLOCATORS =====
class BaseAllocator:
    def __init__(self, staff_pool: List[StaffMember]):
        self.staff_pool = staff_pool
    
    def assign(self, request: DocumentRequest, submission_time: datetime) -> Optional[StaffMember]:
        raise NotImplementedError

class CollegeBasedAllocator(BaseAllocator):
    def assign(self, request: DocumentRequest, submission_time: datetime) -> Optional[StaffMember]:
        candidates = [s for s in self.staff_pool 
                     if s.college_affiliation == request.college and s.is_available]
        return random.choice(candidates) if candidates else None

class WorkloadBasedAllocator(BaseAllocator):
    def assign(self, request: DocumentRequest, submission_time: datetime) -> Optional[StaffMember]:
        college_staff = [s for s in self.staff_pool 
                        if s.college_affiliation == request.college and s.is_available]
        if college_staff:
            return min(college_staff, key=lambda s: s.total_assigned)
        
        available = [s for s in self.staff_pool if s.is_available]
        return min(available, key=lambda s: s.total_assigned) if available else None

class PooledAllocator(BaseAllocator):
    def assign(self, request: DocumentRequest, submission_time: datetime) -> Optional[StaffMember]:
        available = [s for s in self.staff_pool if s.is_available]
        # Select staff who will be available soonest
        return min(available, key=lambda s: max(s.next_available_time, submission_time)) if available else None

class QuotaFreeAllocator(BaseAllocator):
    def assign(self, request: DocumentRequest, submission_time: datetime) -> Optional[StaffMember]:
        available = [s for s in self.staff_pool if s.is_available]
        return min(available, key=lambda s: max(s.next_available_time, submission_time)) if available else None

# ===== SIMPLIFIED SIMULATION ENGINE =====
class SimulationEngine:
    """
    Simulation Engine supporting:
    - FCFS scheduler
    - Weighted Priority scheduler
    - Multiple allocators
    - Scenario-based synthetic request generation
    """
    def __init__(self, scheduler_type: str, allocator_type: str):
        # Scheduler type: 'FCFS' or 'Weighted'
        self.scheduler_type = scheduler_type.upper()
        self.staff_pool = self._init_staff()
        self.allocator = self._create_allocator(allocator_type)
        self.completed: List[DocumentRequest] = []
        self.start_time = datetime.now()
        self.scenario = "baseline"

    # Initialize synthetic staff pool
    def _init_staff(self) -> List[StaffMember]:
        return [
            StaffMember("STAFF001", "Maria Santos", "COE"),
            StaffMember("STAFF002", "Juan Dela Cruz", "CAS"),
            StaffMember("STAFF003", "Ana Reyes", "CBA"),
            StaffMember("STAFF004", "Carlos Lim", "CEGE"),
            StaffMember("STAFF005", "Luisa Gomez", "CS"),
            StaffMember("STAFF006", "Ramon Aquino", "IE"),
        ]

    # Create allocator object
    def _create_allocator(self, allocator_type: str) -> BaseAllocator:
        allocators = {
            "college_based": CollegeBasedAllocator(self.staff_pool),
            "workload_based": WorkloadBasedAllocator(self.staff_pool),
            "pooled": PooledAllocator(self.staff_pool),
            "quota_free": QuotaFreeAllocator(self.staff_pool)
        }
        return allocators.get(allocator_type, CollegeBasedAllocator(self.staff_pool))

    # Generate synthetic requests based on scenario
    def _generate_requests(self, scenario: str, duration_min: int) -> List[DocumentRequest]:
        self.scenario = scenario
        requests = []

        total_requests = {
            "baseline": 80,
            "staff_absence": 70,
            "peak_urgency": 100,
            "workload_imbalance": 90
        }.get(scenario, 80)

        # Example scenario adjustments
        if scenario == "staff_absence":
            self.staff_pool[2].is_available = False
        urgency_range = [7, 8, 9, 10] if scenario == "peak_urgency" else [3, 4, 5, 6, 7]
        colleges = ["COE"]*7 + COLLEGES if scenario == "workload_imbalance" else COLLEGES

        doc_types = list(DOCUMENT_COMPLEXITY.keys())
        requester_types = list(REQUESTER_PRIORITY.keys())

        for i in range(total_requests):
            time_offset = timedelta(minutes=i * (duration_min / total_requests))
            submission_time = self.start_time + time_offset
            college = random.choice(colleges)

            requests.append(DocumentRequest(
                request_id=f"REQ{i:04d}",
                college=college,
                document_type=random.choice(doc_types),
                urgency=random.choice(urgency_range),
                requester_type=random.choice(requester_types),
                submission_time=submission_time
            ))

        return requests

    # Run the simulation
    def run(self, scenario: str = "baseline", duration_min: int = 60) -> Dict:
        requests = self._generate_requests(scenario, duration_min)
        end_time = self.start_time + timedelta(minutes=duration_min)

        # Assign priorities if using Weighted scheduler
        simulation_start = self.start_time
        if self.scheduler_type == "WEIGHTED":
            for req in requests:
                req.calculate_priority(simulation_start)

        # Sort requests according to scheduler
        if self.scheduler_type == "FCFS":
            sorted_requests = sorted(requests, key=lambda r: r.submission_time)
        elif self.scheduler_type == "WEIGHTED":
            sorted_requests = sorted(requests, key=lambda r: r.priority_score, reverse=True)
        else:
            raise ValueError(f"Unknown scheduler type: {self.scheduler_type}")

        # Process each request
        for req in sorted_requests:
            if req.submission_time > end_time:
                continue  # Skip requests beyond simulation duration

            staff = self.allocator.assign(req, req.submission_time)
            if not staff:
                continue  # No available staff

            assignment_time = max(req.submission_time, staff.next_available_time)
            req.assignment_time = assignment_time
            req.assigned_staff = staff.staff_id

            base_mins = DOCUMENT_COMPLEXITY[req.document_type] * 3
            processing_time = timedelta(minutes=random.uniform(base_mins*0.8, base_mins*1.2))

            # Update staff availability
            staff.assign_request(assignment_time, processing_time)
            req.completion_time = assignment_time + processing_time
            self.completed.append(req)

        return self._calculate_metrics(duration_min)

    # Compute metrics
    def _calculate_metrics(self, duration_min: int) -> Dict:
        if not self.completed:
            return {
                "avg_waiting_time": 0,
                "avg_turnaround": 0,
                "throughput": 0,
                "total_processed": 0,
                "staff_load": {s.staff_id: s.total_assigned for s in self.staff_pool},
                "scenario": self.scenario
            }

        waiting_times = [req.get_waiting_time_minutes() for req in self.completed]
        turnaround_times = [req.get_turnaround_time_minutes() for req in self.completed]
        duration_hours = duration_min / 60.0
        throughput = len(self.completed) / duration_hours

        return {
            "avg_waiting_time": round(sum(waiting_times)/len(waiting_times), 2),
            "avg_turnaround": round(sum(turnaround_times)/len(turnaround_times), 2),
            "throughput": round(throughput, 2),
            "total_processed": len(self.completed),
            "staff_load": {s.staff_id: s.total_assigned for s in self.staff_pool},
            "scenario": self.scenario
        }
