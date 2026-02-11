"""
Flask API Backend for Registrar Simulation
Exposes real scheduling algorithms via REST endpoints
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from scheduler_engine import SimulationEngine  # Import engine only

app = Flask(__name__)
CORS(app)

@app.route('/api/simulate', methods=['POST'])
def simulate():
    data = request.get_json()
    
    scheduler_map = {
        "FCFS": "FCFS",
        "Weighted Priority-Based": "WEIGHTED"
    }
    
    allocator_map = {
        "College-Based Assignment": "college_based",
        "Workload-Based Assignment with College Affiliation": "workload_based",
        "Pooled Scheduling": "pooled",
        "Quota-Free Allocation": "quota_free"
    }
    
    scenario_map = {
        "Baseline": "baseline",
        "Staff Absence": "staff_absence",
        "Peak Urgency": "peak_urgency",
        "Workload Imbalance": "workload_imbalance"
    }
    
    try:
        engine = SimulationEngine(
            scheduler_type=scheduler_map.get(data['scheduler'], "FCFS"),
            allocator_type=allocator_map.get(data['allocator'], "college_based")
        )
        
        metrics = engine.run(
            scenario=scenario_map.get(data['scenario'], "baseline"),
            duration_min=data.get('duration_minutes', 60)
        )
        
        return jsonify(metrics), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Backend is running"}), 200

if __name__ == '__main__':
    print("🚀 Starting Registrar Simulation Backend on http://localhost:5000")
    print("   Endpoints:")
    print("   - POST /api/simulate  : Run simulation with your algorithms")
    print("   - GET  /api/health    : Check if backend is running")
    app.run(host='127.0.0.1', port=5000, debug=False)