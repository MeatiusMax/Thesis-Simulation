"""
Flask Backend API for Thesis Simulation Engine
Wraps the scheduler_engine1.py with REST endpoints for running simulations
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
try:
    # Works when run from workspace root as a package
    from backend1.scheduler_engine1 import SimulationEngine, COLLEGES, DOCUMENT_COMPLEXITY, COLLEGE_POPULATION
except ImportError:
    # Works when run directly from backend1/ as a script
    from scheduler_engine1 import SimulationEngine, COLLEGES, DOCUMENT_COMPLEXITY, COLLEGE_POPULATION

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access


# ============================================================================
# HELPER: Convert responses to JSON-serializable format
# ============================================================================

def to_json_serializable(obj):
    """Convert datetime objects to ISO format strings for JSON"""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Thesis Simulation Backend Running"})


@app.route('/config', methods=['GET'])
def get_config():
    """Get simulation configuration and constants"""
    return jsonify({
        "colleges": COLLEGES,
        "document_types": list(DOCUMENT_COMPLEXITY.keys()),
        "document_complexity": DOCUMENT_COMPLEXITY,
        "college_population": COLLEGE_POPULATION,
        "allocator_types": ["college_based", "workload_based", "pooled", "quota_free"],
        "scheduler_types": ["FCFS", "WEIGHTED"],
        "scenarios": ["baseline", "staff_absence", "peak_urgency", "workload_imbalance"]
    })


@app.route('/simulate', methods=['POST'])
def run_simulation():
    """
    Run a simulation with custom parameters
    
    Request JSON:
    {
        "scheduler_type": "FCFS",
        "allocator_type": "college_based",
        "scenario": "baseline",
        "num_staff": 6,
        "quota_limit": 20,
        "num_requests": 80
    }
    
    Returns: Simulation metrics and results
    """
    try:
        data = request.get_json() or {}
        
        # Extract parameters with defaults
        scheduler_type = data.get('scheduler_type', 'FCFS')
        allocator_type = data.get('allocator_type', 'college_based')
        scenario = data.get('scenario', 'baseline')
        num_staff = data.get('num_staff', 6)
        quota_limit = data.get('quota_limit', 20)
        num_requests = data.get('num_requests', 80)  # Not directly used yet, needs override in engine
        random_seed = data.get('random_seed')
        
        # Validate inputs
        if scheduler_type not in ['FCFS', 'WEIGHTED']:
            return jsonify({"error": f"Invalid scheduler_type: {scheduler_type}"}), 400
        
        if allocator_type not in ['college_based', 'workload_based', 'pooled', 'quota_free']:
            return jsonify({"error": f"Invalid allocator_type: {allocator_type}"}), 400
        
        if scenario not in ['baseline', 'staff_absence', 'peak_urgency', 'workload_imbalance']:
            return jsonify({"error": f"Invalid scenario: {scenario}"}), 400
        
        # Create and run simulation
        engine = SimulationEngine(
            scheduler_type=scheduler_type,
            allocator_type=allocator_type,
            staff_config={
                "num_staff": num_staff,
                "quota_limit": quota_limit
            },
            random_seed=random_seed,
        )
        
        results = engine.run(custom_config={
            "scenario": scenario,
            "total_requests": num_requests,
            })
        # Return results with additional metadata
        return jsonify({
            "success": True,
            "parameters": {
                "scheduler_type": scheduler_type,
                "allocator_type": allocator_type,
                "scenario": scenario,
                "num_staff": num_staff,
                "quota_limit": quota_limit,
                "random_seed": results.get("seed_used"),
            },
            "results": results,
            "completed_requests": len(engine.completed),
            "staff_load": results['staff_load']
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/simulate/quick', methods=['POST'])
def run_quick_simulation():
    """
    Run a quick baseline simulation (default parameters)
    
    Request JSON (optional):
    {
        "num_requests": 80  (optional)
    }
    """
    try:
        data = request.get_json() or {}
        random_seed = data.get('random_seed')
        engine = SimulationEngine(
            scheduler_type='FCFS',
            allocator_type='college_based',
            staff_config={"num_staff": 6, "quota_limit": 20},
            random_seed=random_seed
        )
        
        results = engine.run(scenario='baseline')
        
        return jsonify({
            "success": True,
            "results": results,
            "staff_load": results['staff_load']
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/simulate/compare', methods=['POST'])
def compare_allocators():
    """
    Compare different allocator strategies on same scenario
    
    Request JSON:
    {
        "scenario": "baseline",
        "num_staff": 6,
        "quota_limit": 20
    }
    
    Returns: Results for all 4 allocator types
    """
    try:
        data = request.get_json() or {}
        random_seed = data.get('random_seed')
        scenario = data.get('scenario', 'baseline')
        num_staff = data.get('num_staff', 6)
        quota_limit = data.get('quota_limit', 20)
        
        allocators = ['college_based', 'workload_based', 'pooled', 'quota_free']
        results = {}
        
        for allocator in allocators:
            engine = SimulationEngine(
                scheduler_type='FCFS',
                allocator_type=allocator,
                staff_config={"num_staff": num_staff, "quota_limit": quota_limit},
                random_seed=random_seed
            )
            
            sim_results = engine.run(scenario=scenario)
            results[allocator] = {
                "metrics": sim_results,
                "staff_load": sim_results['staff_load']
            }
        
        return jsonify({
            "success": True,
            "scenario": scenario,
            "comparison": results
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/info', methods=['GET'])
def api_info():
    """Get API documentation and available endpoints"""
    return jsonify({
        "version": "1.0",
        "name": "Thesis Simulation Backend",
        "endpoints": {
            "GET /health": "Health check",
            "GET /config": "Get simulation configuration",
            "GET /api/info": "Get API documentation",
            "POST /simulate": "Run simulation with custom parameters",
            "POST /simulate/quick": "Run baseline simulation",
            "POST /simulate/compare": "Compare allocator strategies"
        }
    })


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("""
    ═══════════════════════════════════════════════════════════════════
    🎓 Thesis Simulation Backend API
    ═══════════════════════════════════════════════════════════════════
    
    Server running on: http://localhost:5000
    
    Available endpoints:
    • GET  http://localhost:5000/health          - Health check
    • GET  http://localhost:5000/config          - Configuration
    • GET  http://localhost:5000/api/info        - API documentation
    • POST http://localhost:5000/simulate        - Run simulation
    • POST http://localhost:5000/simulate/quick  - Quick baseline
    • POST http://localhost:5000/simulate/compare - Compare allocators
    
    ═══════════════════════════════════════════════════════════════════
    """)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False  # Disable reloader to avoid double-running simulations
    )
