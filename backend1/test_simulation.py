from backend1.scheduler_engine1 import SimulationEngine

# Run baseline scenario with 6 staff
engine = SimulationEngine(
    scheduler_type='FCFS',
    allocator_type='college_based',
    staff_config={
        'enable_custom_staff': True,
        'num_staff': 6,
        'quota_limit': 20
    }
)

results = engine.run(scenario='baseline')

print('\n' + '='*70)
print('SIMULATION RESULTS - 200 REQUEST BASELINE')
print('='*70)
print(f'Total Processed: {results["total_processed"]}/200')
print(f'Total Days Elapsed: {results["total_days_elapsed"]:.1f} days')
print(f'Avg Queue Wait: {results["avg_waiting_time_hours"]:.1f} hours ({results["avg_waiting_time_hours"]/24:.2f} days)')
print(f'Avg Turnaround: {results["avg_turnaround_days"]:.1f} days')
print(f'Throughput: {results["throughput_req_per_day"]:.1f} requests/day')
print(f'Absent Staff: {len(results["absent_staff"])} staff missing')
print(f'Waiting Queue: {len(results["waiting_queue"])} requests stuck')
print('\nStaff Load Distribution:')
for staff_id, load in results['staff_load'].items():
    print(f'  {staff_id}: {load} requests')
print('='*70)

